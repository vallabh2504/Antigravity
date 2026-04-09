"""
silesia_road_profile.py
=======================
Generates a distance-domain road surface displacement profile z_road(x) [m]
for the Silesia Ring club circuit, suitable for feeding into the quarter-car
vertical dynamics model.

Profile construction:
  1. ISO 8608 PSD-based random profile  — captures general road roughness
     by surface class (B = smooth pit asphalt, C = older infield tarmac).
  2. Discrete deterministic bumps        — kerb/bump features at specific
     corners (T10 chicane kerb, T12 hairpin kerb, T13 hairpin kerb).
  3. Start/finish line raised strip      — small transverse strip at d=0.

References:
  ISO 8608:2016 — Mechanical vibration — Road surface profiles
  Guo & Lu (2001) — "Modelling of random road surface roughness"

Units: distance [m], displacement [m], positive = upward bump.
"""

import numpy as np
from functools import lru_cache

# ---------------------------------------------------------------------------
# ISO 8608 PSD Parameters
# Class:    Gd(n0) [m³/cycle]      where n0 = 0.1 cycle/m (spatial frequency ref)
# ---------------------------------------------------------------------------
_ISO_8608 = {
    'A': 1e-6,    # very smooth motorway
    'B': 4e-6,    # smooth asphalt (pit straight)
    'C': 16e-6,   # average road (older tarmac infield)
    'D': 64e-6,   # rough road
}
_WAVINESS = 2.0   # PSD slope exponent w (standard for roads)

# ---------------------------------------------------------------------------
# Track feature: discrete bump descriptor
# ---------------------------------------------------------------------------
_KERB_BUMPS = [
    # (distance_m, height_m, half_length_m, description)
    # T10 chicane entry — chicane kerb crossing
    (510.0,  0.025, 0.30, "T10_chicane_kerb_entry"),
    (535.0,  0.020, 0.25, "T10_chicane_kerb_exit"),
    # T12 tight hairpin — typical apex kerb
    (655.0,  0.030, 0.35, "T12_hairpin_kerb"),
    # T13 second hairpin — apex kerb
    (740.0,  0.025, 0.30, "T13_hairpin_kerb"),
    # Start/finish line — raised strip (timing trigger)
    (0.0,    0.008, 0.10, "SF_line_strip"),
    (1248.0, 0.008, 0.10, "SF_line_strip_lap_end"),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SilesiaRoadProfile:
    """
    Pre-generates the full road displacement profile for one lap and caches it.
    Use get_displacement(distance_m) for point queries during simulation.
    """

    def __init__(self,
                 lap_length_m: float = 1250.0,
                 dx: float = 0.02,
                 random_seed: int = 42):
        """
        Parameters
        ----------
        lap_length_m : total circuit length [m]
        dx           : spatial resolution of profile [m]  (0.02 m = 2 cm)
        random_seed  : for reproducible random profile
        """
        self.lap_length_m = lap_length_m
        self.dx = dx
        self.random_seed = random_seed

        # Distance axis for one lap
        self.x = np.arange(0.0, lap_length_m, dx)
        self.N = len(self.x)

        # Generate one full lap profile
        self.z_road = self._generate_profile()

    # ------------------------------------------------------------------
    def _generate_profile(self) -> np.ndarray:
        """Build the composite road profile for one lap."""
        from track_geometry import _SEGMENTS

        rng = np.random.default_rng(self.random_seed)
        z = np.zeros(self.N)

        # 1. ISO 8608 PSD profile — segment-by-segment, matched at boundaries
        for seg in _SEGMENTS:
            idx_start = int(seg.start_m / self.dx)
            idx_end   = min(int((seg.start_m + seg.length_m) / self.dx), self.N)
            n_pts = idx_end - idx_start
            if n_pts <= 1:
                continue

            seg_len = seg.length_m
            z_seg = self._iso8608_segment(seg_len, n_pts, seg.road_class, rng)

            # Smooth boundary: offset so z_seg starts at z value of previous endpoint
            if idx_start > 0:
                z_seg = z_seg - z_seg[0] + z[idx_start - 1]

            z[idx_start:idx_end] = z_seg[:n_pts]

        # 2. Add deterministic kerb / bump features
        z = self._add_bumps(z)

        # 3. Remove mean (zero-mean displacement)
        z -= np.mean(z)

        return z

    # ------------------------------------------------------------------
    @staticmethod
    def _iso8608_segment(length_m: float,
                         n_pts: int,
                         road_class: str,
                         rng: np.random.Generator) -> np.ndarray:
        """
        Generate a single road segment profile via filtered white noise.

        Uses the ISO 8608 PSD:  Gd(n) = Gd(n0) × (n/n0)^(-w)

        where n = spatial frequency [cycles/m], n0 = 0.1 cycles/m reference.

        Implementation: frequency-domain synthesis (IFFT of PSD amplitudes
        with random phases), then IFFT to spatial domain.
        """
        Gd_n0 = _ISO_8608.get(road_class, _ISO_8608['C'])
        n0    = 0.1           # reference spatial frequency [cycles/m]
        w     = _WAVINESS

        dx = length_m / n_pts
        # Spatial frequencies (one-sided)
        freqs = np.fft.rfftfreq(n_pts, d=dx)   # [cycles/m]

        # PSD amplitude at each frequency (avoid DC singularity)
        freqs_safe = np.where(freqs > 0, freqs, 1e-6)
        Gd = Gd_n0 * (freqs_safe / n0) ** (-w)
        Gd[0] = 0.0   # zero DC component

        # Complex amplitudes with random phase
        # Power spectral amplitude: A = sqrt(Gd * df)
        df = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
        A  = np.sqrt(Gd * df)
        phase = rng.uniform(0, 2 * np.pi, size=len(freqs))
        spectrum = A * np.exp(1j * phase)
        spectrum[0] = 0.0   # force zero mean

        # IFFT to spatial domain
        z = np.fft.irfft(spectrum, n=n_pts)
        return z

    # ------------------------------------------------------------------
    def _add_bumps(self, z: np.ndarray) -> np.ndarray:
        """Superimpose discrete deterministic bump profiles."""
        for (d_centre, height, half_len, _label) in _KERB_BUMPS:
            # Versine bump: z_bump = height/2 × (1 - cos(π × Δx / half_len))
            bump_start = d_centre - half_len
            bump_end   = d_centre + half_len

            idx_s = max(0,        int(bump_start / self.dx))
            idx_e = min(self.N,   int(bump_end   / self.dx))

            for i in range(idx_s, idx_e):
                x_local = self.x[i] - bump_start
                z_bump = (height / 2.0) * (1.0 - np.cos(np.pi * x_local / (half_len * 2)))
                z[i] += z_bump

        return z

    # ------------------------------------------------------------------
    def get_displacement(self, distance_m: float) -> float:
        """
        Return road surface displacement z [m] at a given distance.
        Distance is wrapped modulo lap_length for continuous lapping.

        Parameters
        ----------
        distance_m : cumulative distance along the lap [m]

        Returns
        -------
        z_road : surface displacement [m] (positive = upward)
        """
        d = distance_m % self.lap_length_m
        # Linear interpolation between profile grid points
        idx_f = d / self.dx
        idx_lo = int(idx_f)
        idx_hi = min(idx_lo + 1, self.N - 1)
        frac = idx_f - idx_lo
        return float(self.z_road[idx_lo] * (1 - frac) + self.z_road[idx_hi] * frac)

    def get_profile_array(self) -> tuple:
        """Return (x, z_road) arrays for the full lap profile."""
        return self.x.copy(), self.z_road.copy()

    def get_rms(self, road_class: str = None) -> float:
        """Return RMS road displacement [m] — useful for validation."""
        return float(np.sqrt(np.mean(self.z_road ** 2)))


# ---------------------------------------------------------------------------
# Convenience function for external import
# ---------------------------------------------------------------------------
_default_profile: SilesiaRoadProfile | None = None


def get_road_displacement(distance_m: float,
                          lap_length_m: float = 1250.0) -> float:
    """
    Module-level function — creates a singleton profile on first call.
    Suitable for direct use in main_simulation.py loop.
    """
    global _default_profile
    if _default_profile is None:
        _default_profile = SilesiaRoadProfile(lap_length_m=lap_length_m)
    return _default_profile.get_displacement(distance_m)


# ---------------------------------------------------------------------------
# Quick self-test / visualisation
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    profile = SilesiaRoadProfile(lap_length_m=1250.0, dx=0.02, random_seed=42)
    x, z = profile.get_profile_array()

    print("=" * 60)
    print("Silesia Ring Road Profile Summary")
    print("=" * 60)
    print(f"  Profile length : {x[-1]:.1f} m")
    print(f"  Resolution     : {profile.dx*1000:.0f} mm")
    print(f"  Total points   : {profile.N}")
    print(f"  RMS amplitude  : {profile.get_rms()*1000:.2f} mm")
    print(f"  Peak positive  : {z.max()*1000:.2f} mm")
    print(f"  Peak negative  : {z.min()*1000:.2f} mm")

    print("\nSample displacements at key distances:")
    for d in [0, 340, 510, 655, 740, 960, 1100, 1249]:
        z_val = profile.get_displacement(d)
        print(f"  d={d:6.1f} m  →  z_road = {z_val*1000:+7.3f} mm")

    # Optional: plot if matplotlib available
    try:
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)

        ax1.plot(x, z * 1000, lw=0.5, color='steelblue', label='Road surface')
        ax1.set_ylabel('Displacement [mm]')
        ax1.set_title('Silesia Ring Club Circuit — Road Displacement Profile')
        ax1.axhline(0, color='k', lw=0.5, ls='--')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Mark bump features
        for (d_c, h, _, lbl) in _KERB_BUMPS:
            ax1.axvline(d_c, color='red', lw=0.8, ls=':', alpha=0.6)
            ax1.text(d_c, z.max() * 1000 * 0.8, lbl.split('_')[0],
                     fontsize=6, color='red', rotation=90, va='top')

        # PSD plot
        from scipy import signal
        f_psd, psd = signal.welch(z, fs=1.0/profile.dx, nperseg=1024)
        f_psd_safe = np.where(f_psd > 0, f_psd, np.nan)
        ax2.loglog(f_psd_safe, psd, color='steelblue', label='Measured PSD')
        # ISO reference lines
        for cls, gd in _ISO_8608.items():
            psd_ref = gd * (f_psd_safe / 0.1) ** (-_WAVINESS)
            ax2.loglog(f_psd_safe, psd_ref, '--', lw=0.8, label=f'ISO {cls}', alpha=0.7)
        ax2.set_xlabel('Spatial frequency [cycles/m]')
        ax2.set_ylabel('PSD [m²/(cycle/m)]')
        ax2.set_title('Road Profile PSD vs ISO 8608')
        ax2.legend(fontsize=7)
        ax2.grid(True, which='both', alpha=0.3)

        plt.tight_layout()
        plt.savefig(r'd:\ANTIGRAVITY\road_profile_plot.png', dpi=150)
        print("\nProfile plot saved to: d:\\ANTIGRAVITY\\road_profile_plot.png")
        plt.show()
    except ImportError:
        print("\n(matplotlib not available for plotting)")
