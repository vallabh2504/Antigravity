# Research — Compact Alternatives to a Long Suspension Rocker Arm

> Source: deep web research (FSAE.com, SAE/IJIRSET/ScienceDirect papers, Wikipedia,
> Firgelli mechanism library, Google Patents, F1technical, Norton *Design of Machinery*,
> Erdman & Sandor *Advanced Mechanism Design*). Coordinates are animation-ready
> (math convention, y-up; flip y for SVG). Baseline target: ~30 mm pushrod travel →
> ~30–45 mm damper travel, wheel motion ratio ≈ 1.0–1.3, package box ≈ 120×120 mm.

## The core problem
A simple rocker/bellcrank is one rigid body on a pivot with two effective arms:
`r_in` (pivot→pushrod) and `r_out` (pivot→spring). Instantaneous motion ratio
`MR_rocker = r_in / r_out`; wheel rate `k_wheel = k_spring / MR²`. To get a large ratio
*and* keep both rods sweeping small near-perpendicular (linear) angles you need **long
arms** — a bellcrank stays linear only to ~±15–30° before the transmission angle
collapses. Every mechanism below either (a) gets the ratio with shorter arms,
(b) decouples "ratio" from "travel/linearity", or (c) replaces the swinging arm with
rolling/sliding/gear contact needing no radius.

## Mechanism families (with shortening rationale)
1. **Compound / two-stage rocker** — ratios multiply, so each stage needs only √(total),
   shrinking both pivot radii; coupler folds geometry around chassis. Used in MTB/moto
   linkages, FSAE.
2. **Four-bar (coupler-curve) actuation** — a coupler point traces a designed near-straight
   path; short cranks replace a big radius; ratio curve is synthesizable.
3. **Watt's linkage** — symmetric four-bar, coupler midpoint ≈ straight line; folded package
   ≈ travel height; substitutes for both long lever and slider.
4. **Scott-Russell linkage** — exact straight line + built-in 2:1 amplification from a short
   swing link; needs a slider.
5. **Toggle (over-center)** — huge rising-rate/force from two short links near dead-center;
   packs progressivity into a tiny cell; highly nonlinear by design.
6. **Geared rocker / sector** — ratio from gear-radii ratio in a small center distance;
   backlash is the headline penalty.
7. **Rack-and-pinion** — constant-radius rolling lever (pinion pitch radius); constant ratio,
   compact, but backlash and no built-in rising rate.
8. **Cam-and-follower** — cam profile programs the motion ratio vs travel in a small disc;
   ultimate rising/falling-rate freedom; contact stress limits force.
9. **Slider-crank** — short crank drives inline guided damper travel ≈ 2r; natural end-stroke
   softening; needs a guide.
10. **L-crank / offset pivot** — fold the arms to shrink the bounding box for the same ratio;
    zero extra joints; the FSAE/racecar default.
11. **System-level** — torsion-bar springing (spring becomes the pivot shaft), monoshock,
    third-spring/heave damper — relocate where stiffness comes from so main rockers stay small.

## Baselines for comparison
- **Direct-acting coilover** (no rocker, MR≈1, outboard).
- **Pushrod + bellcrank** (rod in compression, rocker high/inboard).
- **Pullrod + bellcrank** (rod in tension, rocker low, lower CG).

See `js/mechanisms.js` for the concrete per-mechanism coordinate sets and solvers derived
from this research, and `index.html` for the interactive visualizer.

## Key sources
FSAE.com bellcrank/rising-rate threads; JUSST FSAE pullrod bellcrank structural analysis;
IJIRSET "Design & Analysis of Rocker Arm Suspension"; ScienceDirect S2214785320351671;
Wikipedia (Scott Russell, Watt's linkage, Bellcrank, Slider-crank); Firgelli mechanism
library (toggle, cam, rack, Watt's link); Google Patents US4053171, US6926298B2, US7328910B2,
US6076423A; F1technical (monoshock, third spring, interconnected/torsion suspension);
Norton *Design of Machinery*; Sandor & Erdman *Advanced Mechanism Design* (Prentice-Hall 1984).
