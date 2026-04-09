# Dynamic Vertical Force Analysis
### Shell Eco-Marathon — Silesia Ring Club Circuit — Structural Fatigue Load Generation

---

## Purpose

This project produces a **time-series CSV of hub forces and moments** (Fx, Fy, Fz, Mx, My, Mz)
for the Shell Eco-Marathon vehicle over a 35-minute race session at the Silesia Ring.
The output is formatted for direct import into **Ansys Mechanical** for structural fatigue analysis.

---

## Folder Structure

```
Dynamic Vertical Force Analysis/
│
├── 01_Input_Data/                   ← Raw inputs (do not modify)
│   ├── Drive_Cycle/
│   │   └── canonical_drive_cycle_35min_1.csv   ← Logged speed vs time (35 min, real data)
│   └── Track_Reference/
│       └── Silesia_Ring.jpg                    ← Official Silesia Ring Plan Obiektu map
│
├── 02_Physics_Models/               ← Individual simulation modules
│   ├── Core_Vehicle_Dynamics/
│   │   ├── Vehicle_Dynamics_V2.py              ← Steady-state 6-DOF force solver (PAC89 tyre model)
│   │   └── road_profile.py                     ← ISO 8608 PSD utility (dependency of V2)
│   │
│   ├── Suspension_Quarter_Car/
│   │   └── vertical_dynamics.py                ← 2-DOF quarter-car ODE (RockShox 205x65 params)
│   │
│   └── Track_and_Road/
│       ├── track_geometry.py                   ← Digitised Silesia Ring club circuit (11 segments)
│       └── silesia_road_profile.py             ← ISO 8608 road surface + kerb bumps
│
├── 03_Simulation_Runner/            ← Entry point — run this to regenerate outputs
│   └── main_simulation.py                      ← Master orchestrator script
│
└── 04_Output/                       ← Generated outputs (auto-created on each run)
    ├── CSV_Results/
    │   └── fatigue_loads_output.csv            ← Ansys-ready force/moment time series (7.4 MB)
    └── Plots/
        └── fatigue_loads_summary.png           ← 9-panel summary plot of all channels
```

---

## How to Run

Open a terminal (Windows Command Prompt or PowerShell) and run:

```
python "d:\ANTIGRAVITY\Dynamic Vertical Force Analysis\03_Simulation_Runner\main_simulation.py"
```

**Runtime:** approximately 5 minutes on a standard PC.
**Output:** overwrites `04_Output/CSV_Results/fatigue_loads_output.csv` and regenerates the plot.

---

## Output CSV Columns

| Column | Unit | Description |
|---|---|---|
| `time_s` | s | Elapsed simulation time |
| `distance_m` | m | Cumulative vehicle distance |
| `speed_kmh` | km/h | Vehicle speed (from drive cycle) |
| `ax_ms2` | m/s² | Longitudinal acceleration (derived) |
| `turn_radius_m` | m | Signed turn radius (+right, -left) |
| `inc_angle_deg` | ° | Road inclination |
| `bank_angle_deg` | ° | Road banking |
| `segment` | — | Current track segment name |
| `Fz_outer_N` | N | Vertical force — RA outer wheel (static + pitch/roll) |
| `Fy_outer_N` | N | Lateral force — RA outer wheel |
| `Fx_outer_N` | N | Longitudinal force — RA outer wheel |
| `Mx_outer_Nm` | N·m | Overturning moment — RA outer wheel |
| `My_outer_Nm` | N·m | Rolling resistance moment — RA outer wheel |
| `Mz_outer_Nm` | N·m | Aligning torque — RA outer wheel |
| `Fz_inner_N` | N | Vertical force — RA inner wheel |
| `Fy_inner_N` | N | Lateral force — RA inner wheel |
| `Fx_inner_N` | N | Longitudinal force — RA inner wheel |
| `Mx_inner_Nm` | N·m | Overturning moment — RA inner wheel |
| `My_inner_Nm` | N·m | Rolling resistance moment — RA inner wheel |
| `Mz_inner_Nm` | N·m | Aligning torque — RA inner wheel |
| `Fz_dyn_outer_N` | N | Dynamic vertical force — quarter-car ODE result (outer) |
| `Fz_dyn_inner_N` | N | Dynamic vertical force — quarter-car ODE result (inner) |
| `z_road_m` | m | Road surface displacement at current position |
| `z_sprung_m` | m | Sprung mass vertical displacement (suspension deflection) |

---

## Key Simulation Parameters

| Parameter | Value | Source |
|---|---|---|
| Circuit | Silesia Ring Club Circuit | Digitised from official map |
| Lap route | Red → T17 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → Red | User specified |
| Lap length | 1,250 m | Estimated from map scale bars |
| Drive cycle | 35 min, 11.9 laps, 14.83 km | canonical_drive_cycle_35min_1.csv |
| Timestep | 50 ms | Uniform resampling of raw CSV |
| Total timesteps | 41,991 | — |
| Suspension spring (ks) | 28,000 N/m | RockShox Super Deluxe Select+ 205×65, linearised |
| Suspension damping (c) | 1,500 N·s/m | RockShox DebonAir+ (ζ ≈ 0.28) |
| Tyre stiffness (kt) | 220,000 N/m | Vehicle_Dynamics_V2.py (k_ver) |
| Sprung mass (corner) | 80 kg | Vehicle_Dynamics_V2.py (m_spr/2) |
| Motor torque | 72 N·m (constant) | Vehicle_Dynamics_V2.py default |

---

## Peak Loads (last run)

| Channel | Peak Value |
|---|---|
| Fz outer (static) | 2,206 N |
| Fz outer (dynamic, quarter-car) | 8,071 N |
| Fy outer | 481 N |
| Mx outer | 23.8 N·m |

---

## Dependencies

Install with: `pip install numpy scipy easydict matplotlib`

| Package | Role |
|---|---|
| numpy | Array maths, gradient, interpolation |
| scipy | ODE solver (RK45), cumtrapz |
| easydict | Vehicle config dict-as-object |
| matplotlib | Output plot generation |

---

*Generated by Antigravity AI — Shell Eco-Marathon Structural Fatigue Workflow*