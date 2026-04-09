"""
track_geometry.py
=================
Parametric mathematical representation of the Shell Eco-Marathon
club circuit configuration at the Silesia Ring.

Provides turn radii, inclinations, curve lengths, and kerb properties 
which directly feed into both the lateral 6-DOF physicals and the 
vertical 2-DOF bump simulations.

Authors: Antigravity AI
"""

from typing import List, Optional
from collections import namedtuple
import math
import numpy as np

class TrackSegment:
    def __init__(
        self,
        name: str,
        length_m: float,
        radius_m: Optional[float],    # None if straight
        inc_angle_deg: float,
        bank_angle_deg: float,
        kerb_height_m: float = 0.0,
        kerb_width_m: float = 0.0
    ):
        """
        Defines a unified section of the racing surface.

        Parameters
        ----------
        name : str
            Segment identifier (e.g., 'T1', 'Straight A')
        length_m : float
            Longitudinal length of the segment through the driving path
        radius_m : Optional[float]
            Radius. Positive denotes right-hand curves, Negative is left-hand. 
            None indicates a straight.
        inc_angle_deg : float
            Inclination (gradient/pitch). Positive is uphill.
        bank_angle_deg : float
            Banking/Camber of the road surface. Positive banking means the 
            inside of a curve is lower than the outside (favorable vector).
        kerb_height_m : float
            Height of the kerb at the apex if struck (0.0 if not a kerb strike corner)
        kerb_width_m : float
            Longitudinal width of the kerb profile for spatial wavelength calcs
        """
        self.name = name
        self.length_m = length_m
        self.radius_m = radius_m
        self.inc_angle_deg = inc_angle_deg
        self.bank_angle_deg = bank_angle_deg
        self.kerb_height_m = kerb_height_m
        self.kerb_width_m = kerb_width_m

        # Pre-calculate derived
        self.curvature = (1.0 / radius_m) if radius_m is not None else 0.0

def get_silesia_geometry() -> List[TrackSegment]:
    """
    Returns the master sequence of track segments defining the Silesia Ring
    club circuit layout used for the Shell Eco-Marathon.

    Based on the official visual schematic and standard FIA specifications 
    for the track.

    Track Flow (Starts at Start/Finish, heads anti-clockwise out, but the 
    SEM usually restricts to specific sub-loops). We model the specific 
    "Red T17 to T10 to T16" loop (~1.25 km).

    Returns
    -------
    List[TrackSegment]
        Chronological list of segments composing one full lap.
    """
    segments = []

    # 1. Start / Finish Straight (Pit Straight section)
    # 250m long, very slight positive inclination towards T14 complex
    segments.append(
        TrackSegment(
            name="S/F Straight",
            length_m=250.0,
            radius_m=None,
            inc_angle_deg=0.5,
            bank_angle_deg=0.0
        )
    )

    # 2. Turn 14 Complex Entry (Right hander)
    # Radii estimated from telemetry logs / visual map maps.
    segments.append(
        TrackSegment(
            name="T14 (Right)",
            length_m=85.0,
            radius_m=45.0,    # + indicates Right
            inc_angle_deg=0.2,
            bank_angle_deg=1.5, # 1.5 deg favourable banking
            kerb_height_m=0.04, # High probability of kerb strike on inside
            kerb_width_m=2.0
        )
    )

    # 3. Short linking straight
    segments.append(
        TrackSegment(
            name="Link 14-15",
            length_m=35.0,
            radius_m=None,
            inc_angle_deg=0.0,
            bank_angle_deg=0.0
        )
    )

    # 4. Turn 15 (Tight Left hander / hairpin)
    # The slowest point of the track. Harsh lateral G shift.
    segments.append(
        TrackSegment(
            name="T15 Hairpin (Left)",
            length_m=120.0,
            radius_m=-25.0,   # - indicates Left
            inc_angle_deg=-0.5, # Starts running downhill
            bank_angle_deg=0.5, # Very little banking
            kerb_height_m=0.06, # 6cm harsh exit kerb often struck for eco driving line
            kerb_width_m=3.5
        )
    )

    # 5. Long Back Straight (passing T16/T17)
    # Driver usually coasts/freewheels down this massive smooth straight
    segments.append(
        TrackSegment(
            name="Back Straight",
            length_m=380.0,
            radius_m=None,
            inc_angle_deg=-1.5, # Distinct downhill
            bank_angle_deg=0.0
        )
    )

    # 6. Turn 10 / Turn 11 (Long Sweeping Left)
    # Often taken flat out, high sustained lateral load on right side wheels
    segments.append(
        TrackSegment(
            name="T10/11 Sweeper (Left)",
            length_m=110.0,
            radius_m=-80.0,
            inc_angle_deg=-0.2,
            bank_angle_deg=2.5, # Well banked
            kerb_height_m=0.0,  # Driving line rarely touches inner kerb here
            kerb_width_m=0.0
        )
    )

    # 7. Short Link
    segments.append(
        TrackSegment(
            name="Link 11-12",
            length_m=40.0,
            radius_m=None,
            inc_angle_deg=0.0,
            bank_angle_deg=0.0
        )
    )

    # 8. Turn 12 (Right)
    # Tight right leading back to main straight loop
    segments.append(
        TrackSegment(
            name="T12 (Right)",
            length_m=75.0,
            radius_m=35.0,
            inc_angle_deg=1.0,  # Starts heading back uphill
            bank_angle_deg=1.0,
            kerb_height_m=0.03, # Flattened apex kerb
            kerb_width_m=2.0
        )
    )

    # 9. Return Straight to finish loop (T13 area)
    segments.append(
        TrackSegment(
            name="Final Sweeper Link",
            length_m=155.0,
            radius_m=350.0,     # Extremely shallow right kink
            inc_angle_deg=1.5,  # Uphill grind to S/F
            bank_angle_deg=0.0,
            kerb_height_m=0.0,
            kerb_width_m=0.0
        )
    )

    return segments

def build_track_vector(distance_array: np.ndarray, laps: float = 1.0) -> dict:
    """
    Interpolates the discrete segment geometry onto a high-resolution 
    distance array representation.

    Parameters
    ----------
    distance_array : np.ndarray
        Array of cumulative vehicle distance (e.g. from speed integration).
    laps : float
        Not strictly required if distance_array handles looping, but used to 
        safely modulus the distance back to 1 lap length.

    Returns
    -------
    dict
        Vectorised parameters mapped 1:1 with the distance_array
        - 'radii': array of turn radiuses (inf if straight)
        - 'inc_angles': array of pitch angles [deg]
        - 'bank_angles': array of roll bank angles [deg]
        - 'names': array of string segment names
    """
    segments = get_silesia_geometry()
    
    # Calculate one full lap length parameter
    lap_length = sum(s.length_m for s in segments)
    
    N = len(distance_array)
    out_radii = np.full(N, np.inf)
    out_inc = np.zeros(N)
    out_bank = np.zeros(N)
    out_names = np.full(N, "Unknown", dtype=object)

    # Map distance modulo lap_length stringing continuous laps
    dist_mod = distance_array % lap_length

    # Create mapping bins
    bin_edges = [0.0]
    for s in segments:
        bin_edges.append(bin_edges[-1] + s.length_m)

    # Using standard indexing map
    for i, d in enumerate(dist_mod):
        # find segment idx. next(iter) or fallback
        seg_idx = -1
        for j in range(len(segments)):
            if bin_edges[j] <= d <= bin_edges[j+1]:
                seg_idx = j
                break
        if seg_idx == -1:
            # edge case at exactly lap_length boundary
            seg_idx = len(segments) - 1
            
        seg = segments[seg_idx]
        out_radii[i] = seg.radius_m if seg.radius_m is not None else np.inf
        out_inc[i] = seg.inc_angle_deg
        out_bank[i] = seg.bank_angle_deg
        out_names[i] = seg.name

    return {
        'lap_length_m': lap_length,
        'radii_m': out_radii,
        'inc_deg': out_inc,
        'bank_deg': out_bank,
        'segment_names': out_names
    }


# -----------------------------------------------------------------
# Diagnostic Run
# -----------------------------------------------------------------
if __name__ == "__main__":
    segs = get_silesia_geometry()
    total_len = sum(s.length_m for s in segs)
    
    print("Silesia Ring - Club Circuit Layout")
    print("=" * 65)
    print(f"{'Segment':<20} | {'Len [m]':<8} | {'Rad [m]':<8} | {'Inc [°]':<8} | {'Bank [°]':<8}")
    print("-" * 65)
    
    for s in segs:
        rad_str = f"{s.radius_m:+.1f}" if s.radius_m else "Straight"
        print(f"{s.name:<20} | {s.length_m:<8.1f} | {rad_str:<8} | {s.inc_angle_deg:<+8.1f} | {s.bank_angle_deg:<+8.1f}")
        
    print("=" * 65)
    print(f"Total Circuit Length: {total_len:.1f} m")
    
    # Test vector mapping
    distances = np.arange(0, 1500, 100)
    mapping = build_track_vector(distances)
    
    print("\nVector check via modulus:")
    for d, r, n in zip(distances, mapping['radii_m'], mapping['segment_names']):
        print(f"  @ {d:04d}m -> {n:<20} (Rad: {r})")