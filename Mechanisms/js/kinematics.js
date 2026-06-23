/* =============================================================================
 * kinematics.js  —  2D planar linkage solver library
 * -----------------------------------------------------------------------------
 * Pure functions for solving the positions of common suspension actuation
 * mechanisms. All geometry is in millimetres in a right-handed screen-neutral
 * frame (+x right, +y up). The renderer is responsible for flipping y for SVG.
 *
 * No external dependencies. Everything is deterministic and side-effect free so
 * it is trivial to unit-test and to drive from an animation loop.
 * ========================================================================== */

const K = (() => {
  'use strict';

  /* ---- vector helpers --------------------------------------------------- */
  const v = (x, y) => ({ x, y });
  const add = (a, b) => v(a.x + b.x, a.y + b.y);
  const sub = (a, b) => v(a.x - b.x, a.y - b.y);
  const scale = (a, s) => v(a.x * s, a.y * s);
  const dot = (a, b) => a.x * b.x + a.y * b.y;
  const len = (a) => Math.hypot(a.x, a.y);
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const norm = (a) => {
    const l = len(a) || 1;
    return v(a.x / l, a.y / l);
  };
  const perp = (a) => v(-a.y, a.x);
  const lerp = (a, b, t) => v(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t);
  const angle = (a) => Math.atan2(a.y, a.x);
  const fromAngle = (ang, r = 1) => v(Math.cos(ang) * r, Math.sin(ang) * r);
  const rot = (a, ang, about = v(0, 0)) => {
    const c = Math.cos(ang), s = Math.sin(ang);
    const d = sub(a, about);
    return v(about.x + d.x * c - d.y * s, about.y + d.x * s + d.y * c);
  };
  const mid = (a, b) => lerp(a, b, 0.5);
  const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

  /* ---- circle / circle intersection ------------------------------------
   * Returns the two intersection points of circles centred at p0,p1 with
   * radii r0,r1. `sign` (+1/-1) selects which of the two solutions to return
   * (the side relative to the line p0->p1). Returns null if no solution
   * (mechanism would break — caller should treat as invalid travel).        */
  function circleIntersect(p0, r0, p1, r1, sign = 1) {
    const d = dist(p0, p1);
    if (d > r0 + r1 + 1e-6 || d < Math.abs(r0 - r1) - 1e-6 || d < 1e-9) {
      return null;
    }
    const a = (r0 * r0 - r1 * r1 + d * d) / (2 * d);
    const h2 = r0 * r0 - a * a;
    const h = Math.sqrt(Math.max(0, h2));
    const dir = norm(sub(p1, p0));
    const base = add(p0, scale(dir, a));
    const off = scale(perp(dir), h * sign);
    return add(base, off);
  }

  /* ---- four-bar linkage solver -----------------------------------------
   * Grounded pivots O2 (input crank) and O4 (output rocker). The input crank
   * of length L2 is at angle theta2. Coupler length L3 connects crank tip B to
   * rocker tip C; rocker length L4 connects C to O4.
   * Returns {A,B,C} where A=O2, B=crank tip, C=coupler/rocker joint.
   * `branch` (+1/-1) chooses the assembly configuration.                     */
  function fourBar(O2, O4, L2, L3, L4, theta2, branch = 1) {
    const B = add(O2, fromAngle(theta2, L2));
    const C = circleIntersect(B, L3, O4, L4, branch);
    if (!C) return null;
    return { A: O2, B, C, O4 };
  }

  /* ---- slider-crank solver ---------------------------------------------
   * Crank pivot O at angle theta, crank length r, connecting rod length l,
   * slider constrained to a line through `axisPoint` with unit direction
   * `axisDir`. Returns {crankTip, slider, s} where s is slider displacement
   * along axisDir from axisPoint.                                            */
  function sliderCrank(O, r, l, theta, axisPoint, axisDir) {
    const tip = add(O, fromAngle(theta, r));
    const d = norm(axisDir);
    // Solve |axisPoint + s*d - tip| = l  ->  quadratic in s
    const f = sub(axisPoint, tip);
    const b = 2 * dot(f, d);
    const c = dot(f, f) - l * l;
    const disc = b * b - 4 * c;
    if (disc < 0) return null;
    const s = (-b + Math.sqrt(disc)) / 2; // far solution
    const slider = add(axisPoint, scale(d, s));
    return { crankTip: tip, slider, s };
  }

  /* ---- two-link IK (reach a target with a 2-bar chain) ------------------ */
  function twoLinkIK(base, target, l1, l2, branch = 1) {
    const joint = circleIntersect(base, l1, target, l2, branch);
    if (!joint) return null;
    return { base, joint, target };
  }

  /* ---- map a value from one range to another --------------------------- */
  const remap = (x, a0, a1, b0, b1) => b0 + ((x - a0) / (a1 - a0)) * (b1 - b0);

  /* ---- numeric derivative (for motion-ratio computation) ---------------- */
  function ddt(fn, t, h = 1e-4) {
    return (fn(t + h) - fn(t - h)) / (2 * h);
  }

  return {
    v, add, sub, scale, dot, len, dist, norm, perp, lerp, angle, fromAngle,
    rot, mid, clamp, circleIntersect, fourBar, sliderCrank, twoLinkIK,
    remap, ddt,
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = K;
