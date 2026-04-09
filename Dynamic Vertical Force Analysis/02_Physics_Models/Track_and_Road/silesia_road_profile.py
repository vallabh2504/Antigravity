"""
silesia_road_profile.py
=======================
Composite road profile generator for the Shell Eco-Marathon Silesia Ring.
Combines an ISO 8608 semi-smooth baseline (Class A/B) with deterministic
discrete kerb bumps located exactly at the apexes of key turns.

Provides the spatial road elevation series `z_road_m` sampled at identical
10 Hz equivalent resolution (dx) as the distance vector.

Authors: Antigravity AI
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt

# Dependencies
try:
    from track_geometry import get_silesia_geometry, build_track_vector
except ImportError:
    # Allows fallback if run individually
    pass

class SilesiaRoadProfile:
    """
    Constructs a 1D spatial road profile sequence.

    Steps:
      1) Generate a stochastic ISO 8608 PSD track model
      2) Insert deterministic deterministic kerbs (Apex bumps)
      3) Optionally apply a smoothing pass to remove non-physical high-frequency noise
    """

    def __init__(self, length_m=1250.0, dx=0.5):
        """
        Parameters
        ----------
        length_m : float
            Total track length to generate (Silesia club circuit is ~1250m)
        dx : float
            Spatial step size in meters. Defaults to 0.5m.
        """
        self.length_m = length_m
        self.dx = dx
        
        # Spatial arrays
        self.x = np.arange(0, self.length_m, self.dx)
        self.N = len(self.x)

        # Output profile
        self.z_road = np.zeros(self.N)

        self.kerb_events = []

    def load_track_geometry(self):
        """
        Extracts kerb locations directly from track_geometry.py's segment definitions.
        We place a kerb exactly halfway through any segment marked with kerb_height > 0.
        """
        try:
            segments = get_silesia_geometry()
            dist = 0.0
            
            for seg in segments:
                # apex is middle of the turn
                apex_dist = dist + (seg.length_m / 2.0)
                
                # Check if it's a kerb turn
                if getattr(seg, 'kerb_height_m', 0.0) > 0.0:
                    self.kerb_events.append({
                        'loc_m': apex_dist,
                        'height_m': seg.kerb_height_m,
                        'width_m': getattr(seg, 'kerb_width_m', 2.0),
                        'name': seg.name
                    })
                
                dist += seg.length_m
            
        except NameError:
            print("[Warning] track_geometry module not available. Using fallback kerbs.")
            # Fallback for Silesia kerbs (T12, T14, T15)
            self.kerb_events = [
                {'loc_m': 300, 'height_m': 0.04, 'width_m': 3.0, 'name': 'T12 Apex'},
                {'loc_m': 600, 'height_m': 0.05, 'width_m': 2.5, 'name': 'T14 Apex'},
                {'loc_m': 750, 'height_m': 0.04, 'width_m': 3.0, 'name': 'T15 Apex'},
            ]

    def _generate_iso8608_baseline(self, roughness_class='A', seed=42):
        """
        Generate background track roughness based on ISO 8608 PSD.

        Class A/B represents very good/good quality paved asphalt.
        L1 FIX (2026-04-09): The ISO 8608 reference PSD scale has been fixed.
        The previous logic applied a 16x multiplier error resulting in an
        RMS amplitude of ~12mm. It is now correctly ~3mm RMS.
        """
        np.random.seed(seed)

        # Reference PSDs Gd(n0) in [m^3/cycle] @ n0 = 0.1 cycle/m
        Gd_class = {
            'A': 1e-6,   # Very smooth / Motorway new
            'B': 4e-6,   # Smooth / Good surface
            'C': 16e-6,  # Average road
        }
        Gd = Gd_class.get(roughness_class, 1e-6)

        n0 = 0.1 # reference spatial freq
        w = 2.0  # standard waviness constant

        dn = 1 / self.length_m
        n = np.arange(1, self.N//2 + 1) * dn

        # Power spectrum array
        Gd_n = Gd * (n / n0) ** (-w)

        # IFFT random phase implementation
        amplitude = np.sqrt(2 * Gd_n * dn)
        phase = np.random.uniform(0, 2*np.pi, len(n))
        spectrum = amplitude * np.exp(1j * phase)

        full_spectrum = np.zeros(self.N, dtype=complex)
        full_spectrum[1:self.N//2+1] = spectrum
        full_spectrum[self.N//2+1:] = np.conj(spectrum[:-1][::-1])

        # Multiply by N correctly maps the IFFT scale
        baseline = np.real(np.fft.ifft(full_spectrum)) * self.N

        # Remove macroscopic drifting slope
        baseline -= np.polyval(np.polyfit(self.x, baseline, 1), self.x)

        return baseline

    def _add_kerb(self, baseline, center_m, width_m, height_m):
        """
        Overlays an isolated track bump onto the baseline profile.
        Uses a half-cosine wave profile to mimic a typical racing kerb.
        """
        start = center_m - width_m/2
        end = center_m + width_m/2
        
        # logical index vector
        mask = (self.x >= start) & (self.x <= end)
        
        # x-values within the kerb bounding zone
        x_kerb = self.x[mask]
        
        # cosine bell amplitude mapping [0 ... height ... 0]
        bump = height_m * 0.5 * (1 - np.cos(2 * np.pi * (x_kerb - start) / width_m))
        
        baseline[mask] += bump
        return baseline

    def generate(self, roughness_class='A', seed=42):
        """
        Master method to construct the full profile sequence.
        Returns x, z
        """
        self.load_track_geometry()

        # Step 1: Base surface
        self.z_road = self._generate_iso8608_baseline(roughness_class, seed)
        
        # Step 2: Overlay kerbs
        for kerb in self.kerb_events:
            self._add_kerb(
                self.z_road, 
                center_m=kerb['loc_m'], 
                width_m=kerb['width_m'], 
                height_m=kerb['height_m']
            )

        # Step 3: Lowpass spatial filter (tyre envelopment logic)
        # Tyres act as a spatial low-pass filter (they bridge gaps smaller than contact patch ~10cm)
        # Using a Butterworth filter at a spatial frequency representing a 15cm wavelength cut-off
        wavelength_cutoff = 0.15 # m
        spatial_cutoff = 1.0 / wavelength_cutoff  # cycles/m
        spatial_nyquist = (1.0 / self.dx) / 2.0   
        
        if spatial_cutoff < spatial_nyquist:
            b, a = butter(2, spatial_cutoff / spatial_nyquist, btype='low')
            self.z_road = filtfilt(b, a, self.z_road)
        
        return self.x, self.z_road

    def export_csv(self, filename="01_Input_Data/Track_Reference/Silesia_Profile.csv"):
        """Utility to dump the synthesized road to CSV."""
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        data = np.column_stack((self.x, self.z_road))
        np.savetxt(filename, data, delimiter=',', header='distance_m,z_road_m', comments='')
        print(f"Road profile successfully written to {filename}")


# -----------------------------------------------------------------
# Diagnostic Run
# -----------------------------------------------------------------
if __name__ == "__main__":
    dx = 0.1 # 10 cm resolution
    profile = SilesiaRoadProfile(length_m=1250, dx=dx)
    
    # 1. Generate Class B (smooth) track
    x, z = profile.generate(roughness_class='B')
    
    # Check max values
    print(f"Max Track Bump Height: {np.max(z)*1000:.1f} mm")
    print(f"Min Track Dip Depth: {np.min(z)*1000:.1f} mm")
    print(f"Kernel Kerbs Included: {len(profile.kerb_events)}")
    for k in profile.kerb_events:
        print(f"  - {k['name']} at {k['loc_m']:.1f}m -> Height: {k['height_m']*1000}mm")

    # 2. Visual Checks
    plt.figure(figsize=(14, 6))
    
    # Full Track
    ax1 = plt.subplot(1, 2, 1)
    ax1.plot(x, z * 1000, 'b', lw=0.8) # to mm
    ax1.set_title("Full Silesia Ring Spatial Profile (Class B)")
    ax1.set_xlabel("Distance [m]")
    ax1.set_ylabel("Elevation [mm]")
    ax1.grid(True, alpha=0.3)
    
    # Highlight kerbs on main plot
    for k in profile.kerb_events:
        ax1.axvline(k['loc_m'], color='r', linestyle='--', alpha=0.5)
        ax1.text(k['loc_m'], 45, k['name'], rotation=90, color='r', alpha=0.8)

    # Zoom in on an apex section (e.g., Turn 14 & 15 complex)
    ax2 = plt.subplot(1, 2, 2)
    # search for kerb roughly in T14
    zoom_center = 800
    if len(profile.kerb_events) >= 2:
        zoom_center = profile.kerb_events[1]['loc_m']
        
    mask = (x > zoom_center - 50) & (x < zoom_center + 100)
    ax2.plot(x[mask], z[mask] * 1000, 'g', lw=2)
    ax2.set_title("Zoomed: Turn Complex (Kerb Overlay)")
    ax2.set_xlabel("Distance [m]")
    ax2.set_ylabel("Elevation [mm]")
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()