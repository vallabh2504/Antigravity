"""
vertical_dynamics.py
====================
2-DOF (Quarter-car) solver for dynamic vertical tyre loads.

This module resolves the highly non-linear interaction between the road 
surface (Z_road), the tyre spring/damper, and the suspension (RockShox).
It is responsible for predicting the high-frequency Force spikes (Fz_dyn) 
that dictate structural fatigue on the wishbones. 

RockShox parameters are non-linear; particularly the 'bump stop' region.
The simulation uses `scipy.integrate.solve_ivp` to step the ODE system 
through time.

Authors: Antigravity AI
"""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
import time

class QuarterCarModel:
    """
    State-space 2-DOF formulation:
    
    State vector Y = [z_us, z_s, z_us_dot, z_s_dot]
        - z_us:      Unsprung mass vertical displacement (Wheel assembly)
        - z_s:       Sprung mass vertical displacement (Chassis)
        - z_us_dot:  Unsprung velocity
        - z_s_dot:   Sprung velocity
        
    Equations of motion:
    1) m_us * z_us_dot_dot = - F_tyre - F_susp
    2) m_s  * z_s_dot_dot  = F_susp
    
    where:
    F_tyre = k_t * (z_us - z_road) + c_t * (z_us_dot - z_road_dot)
    F_susp = k_s(del) * (z_s - z_us) + c_s(del_dot) * (z_s_dot - z_us_dot) + bump_stop(del)
    """

    def __init__(self, dt=0.05):
        """
        RockShox Super Deluxe Select+ (205x65) specific settings adapted 
        for carbon chassis mass ratios.
        """
        # Mass [kg]
        self.m_s  = 80.0       # Chassis corner (approx total 200kg + driver / 4 corners, offset to rear)
        self.m_us = 12.0       # Upright + rim + brake + tyre + halfaxle

        # Tyre characteristics (Michelin low rolling res)
        # Highly stiff vertically compared to passenger cars
        self.k_t = 220000.0    # N/m
        self.c_t = 150.0       # Ns/m (very low inherent damping)

        # Suspension default base rates (Linearised baseline)
        self.k_s_base = 28000.0  # N/m (Rockshox air spring dominant rate)
        self.c_s_base = 1500.0   # Ns/m (Heavily damped for eco-marathon smooth roads)

        # Bump stop parameters (polyurethane) - highly non-linear
        self.clearance_bump = 0.04  # m (suspension travel before bump stop is met)
        self.clearance_rebound = -0.02 # m
        self.k_bump_stop = 900000.0 # N/m (rapidly stiffens)

        self.g = 9.81
        self.dt = dt

        # Interpolation functions (set during solve)
        self._z_road_func = None
        self._v_road_func = None # derivative

    def _f_suspension(self, z_us, z_s, z_us_dot, z_s_dot):
        """
        Calculates suspension force with non-linear bump stops.
        Force is positive when pushing MASSES APART (Compression load).
        """
        delta_z = z_s - z_us
        delta_v = z_s_dot - z_us_dot

        # Base linear spring-damper
        force = -self.k_s_base * delta_z - self.c_s_base * delta_v

        # Add bump stop forces (Progressive non-linear engagement)
        if delta_z < -self.clearance_bump:
            # Heavily compressed (hitting bump stop)
            x_pen = (-self.clearance_bump) - delta_z
            # Use cubic ramp up for progressive foam bumpstop
            force += self.k_bump_stop * (x_pen ** 3) 
            
        elif delta_z > -self.clearance_rebound:
            # Full droop (hitting rebound stop)
            x_pen = delta_z - (-self.clearance_rebound)
            # Rebound stop usually stiffer steel ring
            force -= (self.k_bump_stop * 2.0) * (x_pen ** 3) 

        return force

    def _f_tyre(self, z_us, z_us_dot, t):
        """
        Calculates tyre contact patch force interacting with road surface.
        """
        z_r = self._z_road_func(t)
        v_r = self._v_road_func(t)

        delta_z = z_us - z_r
        delta_v = z_us_dot - v_r

        # Tyre cannot pull the ground (loss of contact check)
        force = -self.k_t * delta_z - self.c_t * delta_v
        
        # If force > 0, means tyre is in tension which is impossible, so it lifts off
        if force > 0:
            return 0.0
            
        return force

    def _state_derivative(self, t, Y):
        """
        ODE formulation for scipy solve_ivp
        Y = [z_us, z_s, v_us, v_s]
        """
        z_us, z_s, v_us, v_s = Y

        # Forces
        F_t = self._f_tyre(z_us, v_us, t)
        F_s = self._f_suspension(z_us, z_s, v_us, v_s)

        # Static load offset (gravity)
        W_s = self.m_s * self.g
        W_us = self.m_us * self.g

        # Equations of motion
        a_us = (F_t - F_s - W_us) / self.m_us
        a_s = (F_s - W_s) / self.m_s

        return [v_us, v_s, a_us, a_s]

    def solve(self, time_array: np.ndarray, road_profile_m: np.ndarray, base_static_load_N: np.ndarray):
        """
        Execute the 2-DOF ODE transient solver.

        Parameters
        ----------
        time_array : np.ndarray
            1D array of global time [s]
        road_profile_m : np.ndarray
            Corresponding z_road vertical displacements [m]
        base_static_load_N : np.ndarray
            The macroscopic normal force on this corner [N] calculated by the 6-DOF
            pitch/roll solver. Used to constantly modulate the m_s target load.

        Returns
        -------
        dict
            Contains Fz_dynamic[N], Z_suspension_travel[m]
        """
        print(f"[Quarter-Car] Integrating {len(time_array)} ODE points over {time_array[-1]:.1f}s...")
        start_time = time.time()

        if len(time_array) != len(road_profile_m):
            raise ValueError("Time and road profile arrays must be identical length")

        t_min, t_max = time_array[0], time_array[-1]

        # 1. Provide a Continuous Road Function for the step-solver
        self._z_road_func = interp1d(time_array, road_profile_m, kind='cubic', fill_value="extrapolate")

        # Create numerical derivative of road (z_road_dot)
        v_road_array = np.gradient(road_profile_m, time_array)
        self._v_road_func = interp1d(time_array, v_road_array, kind='cubic', fill_value="extrapolate")

        # 2. Add Warm-up Period (L1 FIX)
        # Prevents extreme t=0 transient spikes by giving the model a 2-sec flat road to settle.
        T_WARMUP = 2.0
        T_TOTAL = t_max + T_WARMUP

        # Shift road functions by T_WARMUP to start true road at t_shifted = 2.0s
        def shifted_z(t_shift):
            return self._z_road_func(np.clip(t_shift - T_WARMUP, t_min, t_max))
        def shifted_v(t_shift):
            return self._v_road_func(np.clip(t_shift - T_WARMUP, t_min, t_max))
        
        self._z_road_func = shifted_z
        self._v_road_func = shifted_v

        # 3. Simulate continuous static mass update (Slow macro dynamic load from braking/pitch)
        # We cheat the physics slightly by mapping the 6-DOF load to an equivalent shifting m_s.
        target_ms_array = base_static_load_N / self.g
        self._ms_func_original = interp1d(time_array, target_ms_array, kind='linear', fill_value="extrapolate")
        
        def shifted_ms(t_shift):
            return self._ms_func_original(np.clip(t_shift - T_WARMUP, t_min, t_max))
            
        def dynamic_derivative(t, Y):
            self.m_s = shifted_ms(t)  # Update m_s continuously
            return self._state_derivative(t, Y)

        # 4. Initial conditions (at rest, perfectly compressed for nominal m_s)
        nom_ms = target_ms_array[0]
        z_us_0 = (- (nom_ms + self.m_us) * self.g) / self.k_t
        z_s_0  = z_us_0 - (nom_ms * self.g) / self.k_s_base
        Y0 = [z_us_0, z_s_0, 0.0, 0.0]

        # 5. Solve via RK45 (Adaptive step)
        sol = solve_ivp(
            fun=dynamic_derivative,
            t_span=(0.0, T_TOTAL),
            y0=Y0,
            method='RK45', 
            t_eval=time_array + T_WARMUP, # Sample exactly exactly back onto the shifted original array
            rtol=1e-3, # Moderate tol for speed. Fz forces scale hugely so abs error isn't massive
            atol=1e-5
        )

        if not sol.success:
            print("[Quarter-Car] WARNING: ODE integration failed:", sol.message)

        # 6. Post-process to extract Forces
        print(f"[Quarter-Car] Finished integration in {time.time()-start_time:.2f}s")
        
        # Shift road functions BACK for array calculation
        self._z_road_func = interp1d(time_array, road_profile_m, kind='cubic', fill_value="extrapolate")
        self._v_road_func = interp1d(time_array, v_road_array, kind='cubic', fill_value="extrapolate")
        
        F_tyre_out = np.zeros(len(time_array))
        z_susp_travel = np.zeros(len(time_array))

        # Re-calculate boundary forces over result vector
        for i, t in enumerate(time_array):
            z_us = sol.y[0, i]
            z_s  = sol.y[1, i]
            v_us = sol.y[2, i]
            
            F_tyre_out[i] = abs(self._f_tyre(z_us, v_us, t))  # Magnitude in N
            z_susp_travel[i] = z_s - z_us
            
        return {
            'Fz_dynamic_N': F_tyre_out,
            'Z_suspension_travel_m': z_susp_travel
        }


# -----------------------------------------------------------------
# Diagnostic Run
# -----------------------------------------------------------------
if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # 10 second run
    t = np.linspace(0, 10, 1000) 
    
    # Generate an explicit kerb bump at t=4s (height 5cm, width 0.5s)
    road = np.zeros_like(t)
    bump_idx = (t > 3.8) & (t < 4.2)
    road[bump_idx] = 0.05 * 0.5 * (1 - np.cos(2*np.pi*(t[bump_idx]-3.8)/0.4))
    
    # Macro load hovering around 800N (e.g. constant speed)
    base_load = np.full_like(t, 800.0)

    # Spike brake load at t=8s
    brake_idx = (t > 7.5) & (t < 9.5)
    base_load[brake_idx] += 400 * np.sin(np.pi*(t[brake_idx]-7.5)/2.0)

    model = QuarterCarModel()
    res = model.solve(t, road, base_load)

    # Plot
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    ax1.plot(t, road*1000, 'k', label='Road Z [mm]')
    ax1.set_ylabel("Disp. [mm]")
    ax1.legend()
    ax1.grid()

    ax2.plot(t, base_load, 'b--', label='Target Mean Fz [N]')
    ax2.plot(t, res['Fz_dynamic_N'], 'r-', label='Dynamic Actual Fz [N]', alpha=0.8)
    ax2.set_ylabel("Force [N]")
    ax2.legend()
    ax2.grid()

    ax3.plot(t, res['Z_suspension_travel_m']*1000, 'g', label='Suspension Stroke [mm]')
    ax3.axhline(model.clearance_bump * -1000, color='r', linestyle='--', label='Bumpstop Limits')
    ax3.axhline(model.clearance_rebound * -1000, color='r', linestyle='--')
    ax3.set_ylabel("Stroke [mm]")
    ax3.set_xlabel("Time [s]")
    ax3.legend()
    ax3.grid()

    plt.suptitle("Quarter Car 2-DOF Drop & Bump Test")
    plt.tight_layout()
    plt.show()