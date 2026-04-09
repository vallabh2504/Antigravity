import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch

def generate_road_profile(length_m=1000, dx=0.04, roughness_class='C'):
    """
    Generates a random road profile using ISO 8608 PSD classification.
    """

    # Defining reference PSD and Spatial Frequency
    # L1 FIX: Corrected ISO 8608 Gd(n0) reference PSD values [m^3/cycle].
    # Previous values were 16x too high (Class C was 256e-6 instead of 16e-6).
    # Source: ISO 8608:2016, Table 1. Now consistent with silesia_road_profile.py.
    Gd_table = {
        'A':    1e-6,   # very smooth (new motorway)
        'B':    4e-6,   # smooth (good asphalt)
        'C':   16e-6,   # average (normal road) — WAS 256e-6 (BUG FIXED)
        'D':   64e-6,   # rough (poor road)
        'E':  256e-6,   # very rough (off-road)
    }

    Gd   = Gd_table[roughness_class] # Reference PSD of Unevenness
    n0   = 0.1          # reference spatial frequency (cycles/m)
    w    = 2.0          # waviness exponent (ISO standard = 2)
    
    # Generating the frequency buckets to capture 1000m hill to 20cm hump
    x    = np.arange(0, length_m, dx)
    N    = len(x)
    dn   = 1 / length_m                                            
    n    = np.arange(1, N//2 + 1) * dn             
    
    # PSD amplitude at each spatial frequency (The Blueprint)
    Gd_n = Gd * (n / n0) ** (-w)
    
    # Random phase road profile (IFFT method)
    amplitude = np.sqrt(2 * Gd_n * dn)
    phase     = np.random.uniform(0, 2 * np.pi, len(n))
    spectrum  = amplitude * np.exp(1j * phase)
    
    # Reconstruct full spectrum (symmetric for real signal)
    full_spectrum           = np.zeros(N, dtype=complex)
    full_spectrum[1:N//2+1] = spectrum
    
    # [:-1] strips off the Nyquist frequency, [::-1] flips the remaining elements
    full_spectrum[N//2+1:]  = np.conj(spectrum[:-1][::-1])
    
    road_profile = np.real(np.fft.ifft(full_spectrum)) * N
    
    return x, road_profile, n, Gd_n

# ---------------------------------------------------------
# Execution and Real-World Simulation
# ---------------------------------------------------------
if __name__ == "__main__":
    dx_resolution = 0.04

    # 1. Generate the physical data
    x, road, n_target, psd_target = generate_road_profile(length_m=1000, dx=dx_resolution, roughness_class='C')

    # 2. Simulate the Real World Measurement (Welch's Method)
    fs = 1 / dx_resolution # Sampling frequency (10 samples per meter)
    n_measured, psd_measured = welch(road, fs=fs, nperseg=1024)

    # ---------------------------------------------------------
    # Matplotlib Dashboard
    # ---------------------------------------------------------
    fig = plt.figure(figsize=(14, 10))
    plt.suptitle("ISO 8608 Road Profile: Target Blueprint vs. Simulated Reality", fontsize=16, fontweight='bold')

    # --- Subplot 1: The Full Road (Spatial Domain) ---
    ax1 = plt.subplot(2, 2, 1)
    ax1.plot(x, road, color='royalblue', linewidth=1)
    ax1.set_title("Full 1000m Road")
    ax1.set_xlabel("Distance (m)")
    ax1.set_ylabel("Elevation (m)")
    ax1.grid(True, linestyle='--', alpha=0.6)

    # --- Subplot 2: Zoomed In (Spatial Domain) ---
    ax2 = plt.subplot(2, 2, 2)
    ax2.plot(x, road, color='crimson', linewidth=1.5)
    ax2.set_xlim(0, 50)  # Zoom in on just the first 50 meters
    ax2.set_title("50m Zoom")
    ax2.set_xlabel("Distance (m)")
    ax2.set_ylabel("Elevation (m)")
    ax2.grid(True, linestyle='--', alpha=0.6)

    # --- Subplot 3: The Log-Log PSD (Frequency Domain) ---
    ax3 = plt.subplot(2, 1, 2)

    # Plot the real-world measured data FIRST (so it sits behind the dashed line)
    ax3.loglog(n_measured, psd_measured, color='black', linewidth=1.5, label="Simulated Real-World Measurement (Welch)")

    # Plot the theoretical target math SECOND (The straight dashed line)
    ax3.loglog(n_target, psd_target, color='limegreen', linewidth=3, linestyle='--', label="Theoretical Target (w = 2.0)")

    # Plotting the Anchor Point
    ax3.scatter([0.1], [256e-6], color='darkorange', s=100, zorder=5, label="Anchor Point n0 (0.1 cycles/m)")

    ax3.set_title("Power Spectral Density: Target vs. Measured")
    ax3.set_xlabel("Spatial Frequency n (cycles/m)")
    ax3.set_ylabel("PSD Gd(n) (m³/cycle)")
    ax3.grid(True, which="both", linestyle='--', alpha=0.6)

    # Lock the axes so the comparison is perfectly framed
    ax3.set_xlim(1e-2, 5)
    ax3.set_ylim(1e-8, 1e0)
    ax3.legend(fontsize=12)

    plt.tight_layout()
    plt.show()