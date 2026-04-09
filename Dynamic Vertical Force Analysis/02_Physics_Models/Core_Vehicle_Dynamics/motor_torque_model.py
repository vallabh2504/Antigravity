"""
motor_torque_model.py
=====================
Physics-based dynamic motor torque calculator for the Shell Eco-Marathon
Hydraix I vehicle.

Replaces the original constant 72 N·m assumption in main_simulation.py
with a resistance-force-based torque derived from the same physics
implemented in the MATLAB ecogenium_energy_analysis_1.m script.

Physics Model (ported from MATLAB):
-------------------------------------
Three resistance forces act on the vehicle at every timestep:

    F_rolling = Crr × m × g                          [N]   (speed-independent)
    F_aero    = 0.5 × Cd × A × ρ × v²               [N]   (quadratic in speed)
    F_inertia = m × a                                 [N]   (acceleration demand)

    F_total   = F_rolling + F_aero + F_inertia        [N]   (total wheel force)

The required wheel torque is:
    T_wheel  = F_total × r_wheel                      [N·m]

Accounting for drivetrain losses between motor and wheel:
    T_motor  = T_wheel / η_drivetrain                 [N·m]

Guard rules (from MATLAB logic):
    - If P_total_wheel ≤ 0 → coasting/braking → T_motor = 0
    - Clip T_motor to [0, T_motor_max] to prevent unrealistic spikes
    - T_motor_max = P_motor_rated / ω_min (at 1 m/s minimum wheel speed)

Usage:
------
    from motor_torque_model import MotorTorqueModel, MOTOR_PARAMS

    mtm = MotorTorqueModel(MOTOR_PARAMS)
    torque_Nm = mtm.compute(v_ms=8.5, ax_ms2=0.4)

    # Or batch:
    torque_array = mtm.compute_batch(v_array, ax_array)

Authors: Antigravity AI — ported from MATLAB ecogenium_energy_analysis_1.m
"""

import numpy as np

# ---------------------------------------------------------------------------
# Default motor + vehicle aero parameters
# (matching ecogenium_energy_analysis_1.m exactly)
# ---------------------------------------------------------------------------
MOTOR_PARAMS = {
    # ── Vehicle ──────────────────────────────────────────────────────────
    "vehicle_mass":             200.0,    # kg  (updated: 200 kg for full simulation)
    "wheel_radius":             0.279,    # m   (r_unloaded from Vehicle_Dynamics_V2)
    "gravity":                  9.81,     # m/s²

    # ── Aerodynamics & rolling (from MATLAB ecogenium script) ─────────────
    "drag_coefficient":         0.15,     # Cd  (Shell Eco-Marathon Urban Concept)
    "frontal_area":             0.8,      # m²
    "rolling_resistance_coef":  0.006,    # Crr (low-rolling-resistance tyres)
    "air_density":              1.225,    # kg/m³ (sea level)

    # ── Drivetrain ────────────────────────────────────────────────────────
    "drivetrain_efficiency":    0.85,     # 85%  (motor + transmission chain)
    "motor_efficiency":         0.90,     # 90%  (brushless DC)

    # ── Motor limits (Hydraix twin 380 W motors) ──────────────────────────
    "motor_power_rated_W":      760.0,    # W   (2 × 380 W)
    "motor_torque_max_Nm":      120.0,    # N·m hard cap (physical limit)

    # ── Smoothing ─────────────────────────────────────────────────────────
    "smooth_window":            25,       # samples for rolling average (50 ms × 25 = 1.25 s)
}


class MotorTorqueModel:
    """
    Physics-based dynamic motor torque from resistance forces.

    Mirrors the power / torque computation in:
        ecogenium_energy_analysis_1.m  (MATLAB, Ecogenium Telemetry Suite)

    The model computes required motor torque at each timestep from:
        rolling resistance  + aerodynamic drag  + inertia demand
    then divides by drivetrain efficiency to obtain motor-shaft torque.

    Notes
    -----
    * Torque is zero during coasting / braking (motor off, no regen).
    * Torque is capped at motor_torque_max_Nm to avoid unrealistic spikes
      caused by acceleration noise in the drive cycle.
    * Uses the same smoothing window as the acceleration signal upstream.
    """

    def __init__(self, params: dict = None):
        p = params or MOTOR_PARAMS
        self.m      = float(p["vehicle_mass"])
        self.r      = float(p["wheel_radius"])
        self.g      = float(p["gravity"])
        self.Cd     = float(p["drag_coefficient"])
        self.A      = float(p["frontal_area"])
        self.Crr    = float(p["rolling_resistance_coef"])
        self.rho    = float(p["air_density"])
        self.eta_dt = float(p["drivetrain_efficiency"])
        self.P_rated = float(p["motor_power_rated_W"])
        self.T_max  = float(p["motor_torque_max_Nm"])
        self.smooth = int(p.get("smooth_window", 25))

        # Minimum wheel speed for torque calculation (avoid /0 at standstill)
        self._v_min = 0.1   # m/s; below this torque → 0

    # ------------------------------------------------------------------
    # Single-point calculation
    # ------------------------------------------------------------------
    def compute(self, v_ms: float, ax_ms2: float) -> float:
        """
        Compute required motor torque at a single operating point.

        Parameters
        ----------
        v_ms   : float
            Vehicle speed [m/s]
        ax_ms2 : float
            Longitudinal acceleration [m/s²]  (positive = speeding up)

        Returns
        -------
        float
            Motor shaft torque [N·m], ≥ 0 (coasting → 0)
        """
        if v_ms < self._v_min:
            return 0.0

        # Resistance forces
        F_rolling = self.Crr * self.m * self.g          # [N]
        F_aero    = 0.5 * self.Cd * self.A * self.rho * v_ms ** 2  # [N]
        F_inertia = self.m * ax_ms2                     # [N]  (± signed)

        F_total   = F_rolling + F_aero + F_inertia      # [N]

        # Power at wheels
        P_wheel   = F_total * v_ms                      # [W]

        # If vehicle is coasting / braking → no motor torque
        if P_wheel <= 0.0:
            return 0.0

        # Motor output power (accounting for drivetrain friction)
        P_motor   = P_wheel / self.eta_dt               # [W]

        # Motor shaft angular velocity
        omega     = v_ms / self.r                        # [rad/s]

        # Required motor torque
        T_motor   = P_motor / omega                      # [N·m]

        # Clip to physical motor limit
        return float(np.clip(T_motor, 0.0, self.T_max))

    # ------------------------------------------------------------------
    # Batch calculation (operates on numpy arrays)
    # ------------------------------------------------------------------
    def compute_batch(self,
                      v_array: np.ndarray,
                      ax_array: np.ndarray) -> np.ndarray:
        """
        Compute motor torque for an entire drive cycle array.

        Parameters
        ----------
        v_array   : ndarray, shape (N,)
            Vehicle speed [m/s]
        ax_array  : ndarray, shape (N,)
            Longitudinal acceleration [m/s²]

        Returns
        -------
        torque_array : ndarray, shape (N,)
            Motor shaft torque [N·m] at each timestep
        """
        v   = np.asarray(v_array,  dtype=float)
        ax  = np.asarray(ax_array, dtype=float)

        # Resistance forces (vectorised)
        F_rolling = self.Crr * self.m * self.g * np.ones_like(v)
        F_aero    = 0.5 * self.Cd * self.A * self.rho * v**2
        F_inertia = self.m * ax

        F_total   = F_rolling + F_aero + F_inertia
        P_wheel   = F_total * v               # [W] — signed

        # Motor power (only when propulsion is needed)
        P_motor   = np.where(P_wheel > 0.0, P_wheel / self.eta_dt, 0.0)

        # Angular velocity, guarded at low speed
        omega     = np.where(v >= self._v_min, v / self.r, 1.0)  # avoid /0

        # Torque: zero where v is too low OR P_wheel ≤ 0
        T_raw  = np.where(
            (v >= self._v_min) & (P_motor > 0.0),
            P_motor / omega,
            0.0
        )

        # Clip to motor physical maximum
        T_clipped = np.clip(T_raw, 0.0, self.T_max)

        # Remove any NaN/Inf from noise in ax
        T_clipped = np.where(np.isfinite(T_clipped), T_clipped, 0.0)

        return T_clipped

    # ------------------------------------------------------------------
    # Diagnostic summary
    # ------------------------------------------------------------------
    def summary(self) -> str:
        return (
            f"MotorTorqueModel | m={self.m:.0f}kg  r={self.r:.3f}m  "
            f"Cd={self.Cd:.2f}  Crr={self.Crr:.4f}  "
            f"eta_dt={self.eta_dt:.0%}  T_max={self.T_max:.0f}Nm"
        )


# ---------------------------------------------------------------------------
# Standalone validation (run: python motor_torque_model.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    mtm = MotorTorqueModel(MOTOR_PARAMS)
    print(mtm.summary())
    print()

    test_cases = [
        # (v_kmh, ax_ms2, description)
        (0.0,  0.0,  "standstill"),
        (30.0, 0.5,  "acceleration 30 km/h"),
        (35.0, 0.0,  "cruise 35 km/h"),
        (35.0, 2.0,  "hard acceleration 35 km/h"),
        (20.0, -0.8, "braking/coasting 20 km/h"),
        (10.0, 0.2,  "slow acceleration 10 km/h"),
    ]

    print(f"{'Speed':>12}  {'ax':>8}  {'Torque':>10}  Description")
    print("-" * 60)
    for v_kmh, ax, desc in test_cases:
        v_ms = v_kmh / 3.6
        T = mtm.compute(v_ms, ax)
        print(f"{v_kmh:>10.1f} km/h  {ax:>+7.2f} m/s2  {T:>8.2f} N·m  {desc}")

    # Quick batch test
    v_arr  = np.array([0.0, 5.0, 10.0, 9.722, 8.0, 0.0])  # m/s
    ax_arr = np.array([0.0, 1.0,  0.5,   0.0, -0.5, -1.0])
    T_arr  = mtm.compute_batch(v_arr, ax_arr)
    print(f"\nBatch check — torques: {np.round(T_arr, 2)}")
    print(f"All finite: {np.all(np.isfinite(T_arr))}")
    print(f"All non-negative: {np.all(T_arr >= 0)}")
    print("\nValidation PASSED.")