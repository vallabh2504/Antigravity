"""
vertical_dynamics.py
====================
Quarter-car suspension model for the Shell Eco-Marathon vehicle.
Computes dynamic vertical tyre forces Fz(t) given a road displacement input z_road(t).

Model: 2-DOF linear quarter car
  ms * z̈s + c*(żs - żu) + ks*(zs - zu) = 0          [sprung mass EOM]
  mu * z̈u + c*(żu - żs) + ks*(zu - zs) + kt*(zu - zroad) = 0  [unsprung mass EOM]

  Dynamic tyre force:  Fz_dynamic = kt * (z_road - zu)  [N]
  (positive = compression = road pushing up on tyre)

Suspension Parameters — RockShox Super Deluxe Select+ 205×65mm
--------------------------------------------------------------
Stroke       : 65 mm  (eye-to-eye 205 mm)
Air spring   : DebonAir+ (progressive rate)
Linearised ks: 28,000 N/m  @ 35% sag, 120 PSI, 80 kg corner sprung mass
               Derivation: F_sag = 80×9.81 = 785 N
                           δ_sag = 0.35 × 0.065 = 0.0228 m
                           ks ≈ F_sag / δ_sag = 785/0.0228 ≈ 34,400 N/m
                           Derated by ~0.8 for progressivity in lower stroke:
                           ks ≈ 28,000 N/m  (conservative linear approx)
Damping c    : 1,500 N·s/m (High-Speed Compression fully open, Low-Speed ~mid)
               Damping ratio ζ = c / (2 × sqrt(ks × ms)) ≈ 0.28  (underdamped)
               Typical for off-road/performance suspension.

Tyre stiffness kt = 220,000 N/m  (from Vehicle_Dynamics_V2.py k_ver)

References:
  Dixon, J.C. (2009) — Tires, Suspension and Handling, SAE.
  RockShox product page — Super Deluxe Select+ (2023/24 model year).
  Milliken & Milliken — Race Car Vehicle Dynamics, SAE 1995.
"""

import numpy as np
from scipy.integrate import solve_ivp


# ---------------------------------------------------------------------------
# Default RockShox Super Deluxe Select+ Parameters
# ---------------------------------------------------------------------------
ROCKSHOX_PARAMS = {
    'ks': 28_000.0,     # suspension spring rate [N/m]  (linearised air-spring)
    'c' :  1_500.0,     # damping coefficient   [N·s/m]
    'kt': 220_000.0,    # tyre vertical stiffness [N/m]  (from V2)
    'ms':    80.0,      # sprung mass per rear corner [kg]  (160/2 from V2)
    'mu':    12.5,      # unsprung mass per rear corner [kg]  (25/2 from V2)
}


class QuarterCarModel:
    """
    Quarter-car ODE integrator.

    Usage
    -----
    model = QuarterCarModel()

    # Option A — solve entire time history at once (recommended for batch mode):
    Fz_dyn, z_s, z_u = model.solve_batch(t_array, z_road_array)

    # Option B — step-by-step integration (for real-time loop):
    model.reset()
    for i, (t, zr) in enumerate(zip(t_array, z_road_array)):
        Fz = model.step(t, zr)
    """

    def __init__(self, params: dict = None):
        p = params or ROCKSHOX_PARAMS
        self.ks = float(p.get('ks', ROCKSHOX_PARAMS['ks']))
        self.c  = float(p.get('c',  ROCKSHOX_PARAMS['c']))
        self.kt = float(p.get('kt', ROCKSHOX_PARAMS['kt']))
        self.ms = float(p.get('ms', ROCKSHOX_PARAMS['ms']))
        self.mu = float(p.get('mu', ROCKSHOX_PARAMS['mu']))

        # Static equilibrium: both masses at rest, tyres at natural length
        # State vector: [zs, żs, zu, żu]  (positive = upward displacement)
        self._g    = 9.81
        zs0 = -(self.ms * self._g) / self.ks              # sprung mass sag
        zu0 = zs0 - (self.mu * self._g) / self.kt         # unsprung + tyre sag
        self._state0 = np.array([zs0, 0.0, zu0, 0.0])
        self._state  = self._state0.copy()
        self._t_prev = 0.0

        # Cache z_road interpolation for step-by-step mode
        self._z_road_interp = None

    # ------------------------------------------------------------------
    def _ode(self, t: float, y: np.ndarray, z_road_t: float) -> np.ndarray:
        """
        Equations of motion for the 2-DOF quarter car with progressive bump stop.

        State: y = [zs, vs, zu, vu]  (displacement + velocity for sprung/unsprung)

        Standard EOMs:
          ms*as = -c*(vs - vu) - ks*(zs - zu)
          mu*au =  c*(vs - vu) + ks*(zs - zu) - kt*(zu - z_road)

        M2 FIX: Progressive bump stop added.
        When suspension travel |zs-zu| > BUMP_THRESHOLD (85% of 65mm stroke),
        an additional progressive stiffness ramps in, preventing physically
        impossible deflections on large road inputs.
        """
        zs, dzs, zu, dzu = y

        # M2: Progressive bump stop constants
        STROKE_MAX     = 0.065   # 65 mm full stroke
        BUMP_THRESHOLD = 0.055   # 85% of stroke = 55 mm activate threshold
        K_BUMP_MAX     = 10.0 * self.ks   # stiffness at full bound

        travel = zs - zu
        if abs(travel) > BUMP_THRESHOLD:
            excess = abs(travel) - BUMP_THRESHOLD
            ramp   = min(excess / (STROKE_MAX - BUMP_THRESHOLD), 1.0)
            F_bump = K_BUMP_MAX * ramp * excess * np.sign(travel)
        else:
            F_bump = 0.0

        ddz_s = ((-self.c * (dzs - dzu) - self.ks * (zs - zu) - F_bump)
                 / self.ms)

        ddz_u = ((self.c  * (dzs - dzu) + self.ks * (zs - zu) + F_bump
                   - self.kt * (zu - z_road_t))
                  / self.mu)

        return np.array([dzs, ddz_s, dzu, ddz_u])
    # ------------------------------------------------------------------
    def solve_batch(self,
                    t_array: np.ndarray,
                    z_road_array: np.ndarray,
                    method: str = 'RK45') -> tuple:
        """
        Solve the quarter-car ODE for the entire simulation time history.

        This is the RECOMMENDED method — it allows scipy's adaptive stepper
        to use sub-step accuracy while still returning values at every
        requested output time.

        Parameters
        ----------
        t_array      : 1-D array of time stamps [s], monotonically increasing
        z_road_array : 1-D array of road surface displacement [m], same length
        method       : ODE solver ('RK45', 'RK23', 'DOP853')

        Returns
        -------
        Fz_dynamic   : dynamic tyre contact force [N], positive = compression
        z_sprung     : sprung mass displacement [m]
        z_unsprung   : unsprung mass displacement [m]
        """
        from scipy.interpolate import interp1d

        # Build a continuous road profile interpolant
        z_road_fn = interp1d(t_array, z_road_array,
                             kind='linear', fill_value='extrapolate')

        def ode_wrapper(t, y):
            return self._ode(t, y, float(z_road_fn(t)))

        # Solve
        sol = solve_ivp(
            ode_wrapper,
            t_span=(t_array[0], t_array[-1]),
            y0=self._state0,
            method=method,
            t_eval=t_array,
            rtol=1e-4,
            atol=1e-6,
            max_step=0.05,   # max 50 ms sub-step for accuracy
        )

        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")

        zs  = sol.y[0]    # sprung mass displacement
        zu  = sol.y[2]    # unsprung mass displacement
        zr  = z_road_fn(sol.t)

        # Dynamic tyre force = tyre stiffness × tyre compression
        # Fz_static = (ms + mu) × g  (weight on tyre at rest)
        Fz_static  = (self.ms + self.mu) * self._g
        Fz_dynamic = self.kt * (zr - zu) + Fz_static
        # Note: Fz_dynamic > Fz_static when hitting a bump,
        #              < Fz_static when airborne / in a valley.
        Fz_dynamic = np.maximum(Fz_dynamic, 0.0)   # tyre can't pull road up

        return Fz_dynamic, zs, zu

    # ------------------------------------------------------------------
    def step(self, t_now: float, z_road_now: float) -> float:
        """
        Single-step integration from previous time to t_now.
        Uses a fixed-step RK4 internally.

        Suitable for real-time / streaming use.
        Returns Fz_dynamic [N] at t_now.
        """
        dt = t_now - self._t_prev
        if dt <= 0.0:
            return self._compute_Fz(self._state, z_road_now)

        # RK4 sub-stepping for stability
        n_substeps = max(1, int(np.ceil(dt / 0.01)))  # ≤10 ms substeps
        dt_sub = dt / n_substeps

        y = self._state.copy()
        # Linearly interpolate z_road within the step
        z_prev = getattr(self, '_z_road_prev', z_road_now)
        for i in range(n_substeps):
            alpha = (i + 0.5) / n_substeps
            zr = z_prev * (1 - alpha) + z_road_now * alpha
            y = self._rk4_step(y, dt_sub, zr)

        self._state = y
        self._t_prev = t_now
        self._z_road_prev = z_road_now

        return self._compute_Fz(y, z_road_now)

    def _rk4_step(self, y: np.ndarray, dt: float, zr: float) -> np.ndarray:
        k1 = self._ode(0, y,              zr)
        k2 = self._ode(0, y + dt/2 * k1, zr)
        k3 = self._ode(0, y + dt/2 * k2, zr)
        k4 = self._ode(0, y + dt    * k3, zr)
        return y + dt / 6.0 * (k1 + 2*k2 + 2*k3 + k4)

    def _compute_Fz(self, y: np.ndarray, z_road: float) -> float:
        zu = y[2]
        Fz_static  = (self.ms + self.mu) * self._g
        Fz_dynamic = self.kt * (z_road - zu) + Fz_static
        return max(0.0, Fz_dynamic)

    def reset(self):
        """Reset state to static equilibrium."""
        self._state  = self._state0.copy()
        self._t_prev = 0.0
        if hasattr(self, '_z_road_prev'):
            del self._z_road_prev

    # ------------------------------------------------------------------
    @property
    def natural_freq_sprung(self) -> float:
        """Natural frequency of sprung mass [Hz]."""
        return float(np.sqrt(self.ks / self.ms) / (2 * np.pi))

    @property
    def natural_freq_unsprung(self) -> float:
        """Natural frequency of unsprung mass [Hz]."""
        return float(np.sqrt((self.ks + self.kt) / self.mu) / (2 * np.pi))

    @property
    def damping_ratio(self) -> float:
        """Damping ratio ζ of the sprung mass."""
        return float(self.c / (2 * np.sqrt(self.ks * self.ms)))

    def summary(self) -> str:
        return (
            f"QuarterCarModel — RockShox Super Deluxe Select+ (205×65mm)\n"
            f"  ks   = {self.ks:>9,.0f} N/m   (linearised air spring)\n"
            f"  c    = {self.c:>9,.0f} N·s/m (combined rebound+compression)\n"
            f"  kt   = {self.kt:>9,.0f} N/m   (tyre vertical stiffness)\n"
            f"  ms   = {self.ms:>9.1f} kg    (sprung corner mass)\n"
            f"  mu   = {self.mu:>9.1f} kg    (unsprung corner mass)\n"
            f"  fn_s = {self.natural_freq_sprung:>9.2f} Hz   (sprung natural freq)\n"
            f"  fn_u = {self.natural_freq_unsprung:>9.2f} Hz   (unsprung natural freq)\n"
            f"  ζ    = {self.damping_ratio:>9.3f}      (damping ratio)\n"
        )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    model = QuarterCarModel()
    print(model.summary())

    # Test: single-period bump at 0.5 s
    t = np.linspace(0, 2.0, 2000)
    dt = t[1] - t[0]

    # Step bump at t=0.5s, height=25mm, duration=0.1s
    z_road = np.zeros_like(t)
    bump_start = int(0.5 / dt)
    bump_end   = int(0.6 / dt)
    bump_x = np.linspace(0, np.pi, bump_end - bump_start)
    z_road[bump_start:bump_end] = 0.025 * np.sin(bump_x)

    Fz_dyn, zs, zu = model.solve_batch(t, z_road)

    static_Fz = (model.ms + model.mu) * 9.81
    peak_Fz   = Fz_dyn.max()
    print(f"\nBump test (25 mm versine bump):")
    print(f"  Static Fz              : {static_Fz:.1f} N")
    print(f"  Peak dynamic Fz        : {peak_Fz:.1f} N")
    print(f"  Dynamic amplification  : {peak_Fz/static_Fz:.2f}×")
    print(f"  Min Fz (after bump)    : {Fz_dyn.min():.1f} N")
    print(f"  Max sprung deflection  : {(zs - zu).max()*1000:.1f} mm")

    try:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

        axes[0].plot(t, z_road * 1000, color='saddlebrown', label='z_road [mm]')
        axes[0].set_ylabel('Road disp. [mm]')
        axes[0].legend(); axes[0].grid(True, alpha=0.4)

        axes[1].plot(t, zs * 1000, label='Sprung mass zs', color='steelblue')
        axes[1].plot(t, zu * 1000, label='Unsprung mass zu', color='orange', ls='--')
        axes[1].set_ylabel('Displacement [mm]')
        axes[1].legend(); axes[1].grid(True, alpha=0.4)

        axes[2].plot(t, Fz_dyn, label='Fz dynamic [N]', color='crimson')
        axes[2].axhline(static_Fz, color='k', ls='--', lw=0.8, label='Fz static')
        axes[2].set_ylabel('Tyre Force [N]')
        axes[2].set_xlabel('Time [s]')
        axes[2].legend(); axes[2].grid(True, alpha=0.4)

        plt.suptitle('Quarter-Car Response to 25 mm Bump')
        plt.tight_layout()
        plt.savefig(r'd:\ANTIGRAVITY\quarter_car_test.png', dpi=150)
        print("Plot saved to d:\\ANTIGRAVITY\\quarter_car_test.png")
        plt.show()
    except ImportError:
        print("(matplotlib not available)")
