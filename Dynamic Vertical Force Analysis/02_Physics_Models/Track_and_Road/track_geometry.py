"""
track_geometry.py
=================
Digitized geometry of the Silesia Ring CLUB CIRCUIT used for Shell Eco-Marathon.

Route: Red line (S/F) → Flag 17 → Flag 10 → Flag 11 → Flag 12 → Flag 13
                      → Flag 14 → Flag 15 → Flag 16 → Red line

Scale reference from official Silesia Ring map:
  - Main straight (east) : 520 m
  - Lower parallel straight : 730 m
  - Total club lap estimated : ~1,250 m

Corner radii are digitized from the official Plan Obiektu map using the
above scale references. Inclination and banking are estimated from circuit
elevation data and track design standards.

Convention (matches Vehicle_Dynamics_V2.py):
  turn_radius > 0  → Right turn
  turn_radius < 0  → Left turn
  turn_radius = inf → Straight (represented as 9999 m)
  inc_angle   > 0  → Uphill   [rad]
  bank_angle  > 0  → Road tilts in the same direction as the corner [rad]
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple


@dataclass
class TrackSegment:
    """One segment of the circuit."""
    name: str
    start_m: float          # cumulative distance at segment start [m]
    length_m: float         # segment length [m]
    turn_radius_m: float    # signed turn radius [m]; +ve=right, -ve=left, 9999=straight
    inc_angle_rad: float    # road inclination [rad]; +ve=uphill
    bank_angle_rad: float   # road banking [rad]; +ve=same direction as turn
    road_class: str         # ISO 8608 roughness class ('A','B','C','D')


# ---------------------------------------------------------------------------
# Club Circuit — 9 segments  (Red → 17 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → Red)
#
# Digitization methodology:
#   - The pit straight "520m" label anchors the east straight.
#   - The lower straight "730m" label anchors the south straight.
#   - Corner pixels were measured proportionally against these references.
#   - Turn radii set conservatively (inner radius, not centreline).
#   - Shell Eco-Marathon cars are slow (~35 km/h max) so even "fast" corners
#     are traversed at modest lateral acceleration.
# ---------------------------------------------------------------------------

_LAP_LENGTH_M = 1250.0   # total club circuit length [m]

_SEGMENTS: list[TrackSegment] = [

    # 0 ── S/F straight → Flag 17
    # Long pit straight, smooth asphalt, slight uphill gradient (airfield terrain)
    TrackSegment(
        name="SF_to_T17_straight",
        start_m=0.0,
        length_m=340.0,
        turn_radius_m=9999.0,           # straight
        inc_angle_rad=np.radians(0.5),  # gentle 0.5° incline (airfield approach)
        bank_angle_rad=0.0,
        road_class='B',                 # smooth pit-lane asphalt
    ),

    # 1 ── Flag 17: Fast sweeping RIGHT
    # Exit of pit lane / entry complex — wide, fast, banked right
    TrackSegment(
        name="T17_sweep_right",
        start_m=340.0,
        length_m=90.0,
        turn_radius_m=+75.0,            # fast right-hander
        inc_angle_rad=np.radians(0.0),
        bank_angle_rad=np.radians(1.5), # slight positive banking (helpful)
        road_class='B',
    ),

    # 2 ── Flag 17 exit → Flag 10: Short link straight
    TrackSegment(
        name="T17_to_T10_link",
        start_m=430.0,
        length_m=80.0,
        turn_radius_m=9999.0,
        inc_angle_rad=np.radians(0.0),
        bank_angle_rad=0.0,
        road_class='C',
    ),

    # 3 ── Flag 10: Medium-speed CHICANE (left-right combined)
    # The image shows flag 10 appears twice — this is a chicane / ess complex
    # Modelled as a combined LEFT entry
    TrackSegment(
        name="T10_chicane_left",
        start_m=510.0,
        length_m=65.0,
        turn_radius_m=-30.0,            # left entry of chicane
        inc_angle_rad=np.radians(-0.3), # slight downhill into chicane
        bank_angle_rad=np.radians(-0.5),
        road_class='C',
    ),

    # 4 ── Flag 11: Medium RIGHT (exit of chicane / entry to hairpin complex)
    TrackSegment(
        name="T11_medium_right",
        start_m=575.0,
        length_m=70.0,
        turn_radius_m=+28.0,            # medium right
        inc_angle_rad=np.radians(-0.5),
        bank_angle_rad=0.0,
        road_class='C',
    ),

    # 5 ── Flag 12: Tight HAIRPIN LEFT (the prominent left hairpin on the west end)
    # This is the tightest corner on the club circuit — kerb present
    TrackSegment(
        name="T12_hairpin_left",
        start_m=645.0,
        length_m=85.0,
        turn_radius_m=-13.5,            # tight hairpin — matches V2 default config
        inc_angle_rad=np.radians(0.0),
        bank_angle_rad=np.radians(-1.0),# adverse camber (off-camber hairpin)
        road_class='C',
    ),

    # 6 ── Flag 13: Second HAIRPIN LEFT (the upper left hairpin)
    # Slightly larger than T12, similar character
    TrackSegment(
        name="T13_hairpin_left",
        start_m=730.0,
        length_m=80.0,
        turn_radius_m=-17.0,
        inc_angle_rad=np.radians(0.3),  # slight uphill through apex
        bank_angle_rad=np.radians(-0.5),
        road_class='C',
    ),

    # 7 ── Flag 14: Medium RIGHT (return leg, infield)
    TrackSegment(
        name="T14_medium_right",
        start_m=810.0,
        length_m=70.0,
        turn_radius_m=+25.0,
        inc_angle_rad=np.radians(0.0),
        bank_angle_rad=np.radians(0.5),
        road_class='C',
    ),

    # 8 ── Flag 15: Fast RIGHT sweeper (return toward pit complex)
    TrackSegment(
        name="T15_fast_right",
        start_m=880.0,
        length_m=80.0,
        turn_radius_m=+45.0,
        inc_angle_rad=np.radians(0.5),  # slight uphill toward pits
        bank_angle_rad=np.radians(1.0),
        road_class='B',
    ),

    # 9 ── Flag 16: LEFT onto pit straight return
    TrackSegment(
        name="T16_left_onto_return",
        start_m=960.0,
        length_m=65.0,
        turn_radius_m=-35.0,
        inc_angle_rad=np.radians(0.5),
        bank_angle_rad=0.0,
        road_class='B',
    ),

    # 10 ── Flag 16 exit → S/F Red line: Final straight
    TrackSegment(
        name="T16_to_SF_straight",
        start_m=1025.0,
        length_m=225.0,
        turn_radius_m=9999.0,           # straight
        inc_angle_rad=np.radians(0.3),
        bank_angle_rad=0.0,
        road_class='B',
    ),
]

# Verify lap length consistency
_actual_end = _SEGMENTS[-1].start_m + _SEGMENTS[-1].length_m
assert abs(_actual_end - _LAP_LENGTH_M) < 5.0, (
    f"Segment layout mismatch: ends at {_actual_end:.1f} m, expected {_LAP_LENGTH_M:.1f} m"
)


def get_lap_length() -> float:
    """Return the club circuit lap length in metres."""
    return _LAP_LENGTH_M


def get_segment(distance_m: float) -> TrackSegment:
    """
    Return the TrackSegment at a given cumulative distance [m] within one lap.
    Distance is automatically wrapped modulo lap length.
    """
    d = distance_m % _LAP_LENGTH_M
    for seg in reversed(_SEGMENTS):
        if d >= seg.start_m:
            return seg
    return _SEGMENTS[0]


def get_track_state(distance_m: float) -> dict:
    """
    Main interface: given cumulative distance [m], returns the local track state.

    Returns
    -------
    dict with keys:
        turn_radius   [m]   signed (+ right, - left; 9999 = straight)
        inc_angle     [rad] road inclination
        bank_angle    [rad] road banking
        road_class    [str] ISO 8608 class e.g. 'B', 'C'
        segment_name  [str] name of current segment
        lap_frac      [float] 0–1, position within current lap
    """
    seg = get_segment(distance_m)
    d_lap = distance_m % _LAP_LENGTH_M

    # Linear blend at segment transitions (±5 m blend zone) to avoid step changes
    blend_zone = 5.0
    d_from_end = (seg.start_m + seg.length_m) - d_lap
    d_from_start = d_lap - seg.start_m

    if d_from_end < blend_zone and d_from_end > 0:
        # Approaching end of segment — blend toward next
        t = 1.0 - (d_from_end / blend_zone)
        next_seg = get_segment(d_lap + blend_zone + 1.0)
        turn_r = _blend_signed(seg.turn_radius_m, next_seg.turn_radius_m, t)
        inc    = seg.inc_angle_rad  * (1 - t) + next_seg.inc_angle_rad  * t
        bank   = seg.bank_angle_rad * (1 - t) + next_seg.bank_angle_rad * t
    elif d_from_start < blend_zone:
        # Just entered segment — blend from previous
        t = d_from_start / blend_zone
        prev_seg = get_segment(max(d_lap - blend_zone - 1.0, 0.0))
        turn_r = _blend_signed(prev_seg.turn_radius_m, seg.turn_radius_m, t)
        inc    = prev_seg.inc_angle_rad  * (1 - t) + seg.inc_angle_rad  * t
        bank   = prev_seg.bank_angle_rad * (1 - t) + seg.bank_angle_rad * t
    else:
        turn_r = seg.turn_radius_m
        inc    = seg.inc_angle_rad
        bank   = seg.bank_angle_rad

    return {
        'turn_radius':  turn_r,
        'inc_angle':    inc,
        'bank_angle':   bank,
        'road_class':   seg.road_class,
        'segment_name': seg.name,
        'lap_frac':     (d_lap / _LAP_LENGTH_M),
    }


def _blend_signed(r1: float, r2: float, t: float) -> float:
    """
    Smooth blend between two signed turn radii.
    Uses reciprocal blending (curvature space) to avoid infinite-radius artifacts.
    """
    STRAIGHT = 9999.0
    k1 = 0.0 if abs(r1) >= STRAIGHT else (1.0 / r1)
    k2 = 0.0 if abs(r2) >= STRAIGHT else (1.0 / r2)
    k_blend = k1 * (1 - t) + k2 * t
    if abs(k_blend) < 1e-6:
        return STRAIGHT
    return 1.0 / k_blend


def get_all_segments() -> list:
    """Return the full segment list for inspection / plotting."""
    return _SEGMENTS


def compute_roll_gradient(vehicle_params: dict) -> float:
    """
    Pre-compute the vehicle roll gradient [rad per m/s²] from suspension params.
    Used by main_simulation.py to dynamically estimate roll_angle from ay.

    Roll gradient = del_h × m_spr / (cf × sf²/2 + cr × sr²/2)
    where cf, cr are the effective roll stiffnesses.

    For a first-pass estimate before cf/cr are solved, we use:
      K_roll_total ≈ ks_corner × (track/2)²  × 2  [both axles]
    """
    p = vehicle_params
    # Use suspension spring rate as roll stiffness source
    ks      = p.get('ks_suspension', 28000.0)   # N/m
    s_f     = p.get('s_f', 1.08)               # front track [m]
    s_r     = p.get('s_r', 0.83)               # rear track [m]
    m_spr   = p.get('m_spr', 160.0)            # sprung mass [kg]
    del_h   = p.get('del_h', 0.386)            # CG to roll axis [m] — from V2

    K_f = ks * (s_f / 2.0) ** 2               # front roll stiffness [N·m/rad]
    K_r = ks * (s_r / 2.0) ** 2               # rear roll stiffness [N·m/rad]
    K_total = K_f + K_r

    roll_gradient = (m_spr * del_h) / K_total  # [rad / (m/s²)]
    return roll_gradient                        # typical range: 0.01–0.05 rad/g


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("Silesia Ring — Club Circuit Segment Map")
    print("=" * 60)
    print(f"{'Segment':<28} {'Start':>7} {'End':>7} {'R [m]':>8} {'Inc°':>6} {'Bank°':>6} {'Class'}")
    print("-" * 70)
    for seg in _SEGMENTS:
        end_m = seg.start_m + seg.length_m
        r_str = f"{seg.turn_radius_m:+.0f}" if abs(seg.turn_radius_m) < 9000 else "  str."
        print(f"  {seg.name:<26} {seg.start_m:7.0f} {end_m:7.0f} {r_str:>8} "
              f"{np.degrees(seg.inc_angle_rad):6.1f} {np.degrees(seg.bank_angle_rad):6.1f}   {seg.road_class}")
    print(f"\n  Total lap length: {_LAP_LENGTH_M:.0f} m  (actual end: {_actual_end:.0f} m)")

    print("\nSample track states:")
    for d in [0, 350, 510, 645, 730, 960, 1100, 1249]:
        s = get_track_state(d)
        r = s['turn_radius']
        r_str = f"{r:+.1f}" if abs(r) < 9000 else "straight"
        print(f"  d={d:5.0f}m  [{s['segment_name']:<28}]  R={r_str:>10}m  "
              f"inc={np.degrees(s['inc_angle']):+.1f}°  bank={np.degrees(s['bank_angle']):+.1f}°")
