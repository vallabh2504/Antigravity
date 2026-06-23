/* =============================================================================
 * mechanisms.js — catalogue of suspension actuation mechanisms
 * -----------------------------------------------------------------------------
 * Each mechanism is defined by:
 *   meta/info/stats   descriptive content for the UI
 *   box               fixed world bounding box (view never jumps mid-animation)
 *   drive(u)          u in [0,1]; 0=full droop, 0.5=ride, 1=full bump.
 *                     Returns a dict of named world points (mm, y-up). Two are
 *                     special: `out` = the moving spring/damper end, and
 *                     `track` = the input reference whose travel defines MR.
 *   scene(P, ctx)     builds the drawing primitives from points P and the
 *                     auto-computed damper context ctx = {mount, rest}.
 *
 * The wrapper auto-places the (grounded) damper mount ALONG the path that `out`
 * sweeps, so the spring genuinely compresses through travel, and computes an
 * honest motion ratio  MR = |Δtrack| / |Δdamper|  by central difference.
 * ========================================================================== */

const Mechanisms = (() => {
  'use strict';
  const { v, add, sub, scale, dist, norm, perp, fromAngle, angle, rot, lerp } = K;
  const TAU = Math.PI * 2, D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const BB = (minX, minY, maxX, maxY) => ({ minX, minY, maxX, maxY });
  const bf = (u) => (u - 0.5) * 2;
  const phaseName = (u) => {
    const b = bf(u);
    if (b > 0.66) return 'FULL BUMP'; if (b > 0.12) return 'BUMP';
    if (b < -0.66) return 'FULL DROOP'; if (b < -0.12) return 'DROOP';
    return 'RIDE HEIGHT';
  };

  /* ---- factory: wraps a drive()/scene() pair into a full mechanism ------ */
  function make(def) {
    const gap = def.damperGap ?? 30;
    // place grounded damper mount beyond the bump-end of the out-path, so the
    // damper axis is aligned with the output motion (real compression).
    function mountRest() {
      const o0 = def.drive(0).out, o1 = def.drive(1).out, oc = def.drive(0.5).out;
      let dir = sub(o1, o0);
      if (Math.hypot(dir.x, dir.y) < 1) dir = v(0, 1);
      dir = norm(dir);
      const mount = def.mount || add(o1, scale(dir, gap));
      const rest = dist(mount, oc);
      return { mount, rest };
    }
    const ctx = mountRest();
    const damperLen = (u) => dist(ctx.mount, def.drive(u).out);
    function mr(u) {
      const h = 0.02;
      const a = Math.max(0, u - h), b = Math.min(1, u + h);
      const Pa = def.drive(a), Pb = def.drive(b);
      const dD = Math.abs(dist(ctx.mount, Pb.out) - dist(ctx.mount, Pa.out));
      const dT = dist(Pb.track, Pa.track);
      return dD < 1e-4 ? 99 : dT / dD;
    }
    /* footprint MEASURED from the drawn geometry:
     *  self  = vertical extent of the mechanism's core nodes (rod/mount outliers
     *          rejected) across the full stroke;
     *  lever = derived envelope of an equivalent SINGLE rocker that delivers this
     *          mechanism's own (measured) damper travel & ratio at a ±25° swing.   */
    function measureFootprint() {
      const pts = [];
      for (let i = 0; i <= 10; i++) { const P = def.drive(i / 10); for (const k in P) { const p = P[k]; if (p && typeof p.x === 'number' && isFinite(p.x) && isFinite(p.y)) pts.push(p); } }
      if (pts.length < 3) return null;
      const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length, cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
      const ds = pts.map((p) => Math.hypot(p.x - cx, p.y - cy)).sort((a, b) => a - b);
      const med = ds[Math.floor(ds.length / 2)] || 1;
      const core = pts.filter((p) => Math.hypot(p.x - cx, p.y - cy) <= med * 1.9);
      let mn = Infinity, mx = -Infinity; core.forEach((p) => { mn = Math.min(mn, p.y); mx = Math.max(mx, p.y); });
      const self = Math.max(18, Math.round(mx - mn));
      let dmn = Infinity, dmx = -Infinity;
      for (let i = 0; i <= 20; i++) { const d = damperLen(i / 20); dmn = Math.min(dmn, d); dmx = Math.max(dmx, d); }
      const damperFull = Math.max(8, dmx - dmn);
      const mrRide = Math.max(0.4, Math.min(3, mr(0.5)));
      const rOut = damperFull / (2 * Math.sin(25 * D2R));   // arm to give that travel at ±25°
      const lever = Math.round(rOut * (1 + mrRide));         // straight lever envelope = r_in + r_out
      const reduction = Math.round((1 - self / lever) * 100);
      return { self, lever, reduction };
    }
    // measured envelope of THIS schematic (informational only — schematics are
    // not packaging-optimised, so the headline comparison uses curated,
    // research-grounded estimates assigned via META below).
    const measured = /Compact/.test(def.category) ? measureFootprint() : null;
    return Object.assign({}, def, {
      ctx, phase: phaseName, measured, footprint: null,
      solve(u) {
        const P = def.drive(u);
        const scene = def.scene(P, ctx, u);
        scene.push({ type: 'coilover', a: ctx.mount, b: P.out, rest: ctx.rest });
        scene.push({ type: 'pivot', at: ctx.mount, grounded: true });
        scene.push({ type: 'pivot', at: P.out });
        // thesis overlay: contrast the equivalent long single-rocker envelope
        // against this mechanism's envelope, drawn in the box corner.
        if (this.footprint && this.footprint.reduction >= 10) {
          const b = def.box, fp = this.footprint;
          const span = b.maxY - b.minY;
          const x0 = b.maxX - (b.maxX - b.minX) * 0.30;
          const y0 = b.minY + span * 0.04;
          const sc = (span * 0.78) / Math.max(fp.lever, fp.self);
          const wL = fp.lever * sc * 0.42, wS = fp.self * sc * 0.42;
          scene.push({ type: 'envelope', x: x0, y: y0, w: wL, h: fp.lever * sc,
            color: 'rgba(255,107,107,0.55)', label: 'single rocker', hLabel: fp.lever + 'mm' });
          scene.push({ type: 'envelope', x: x0 + wL + (b.maxX - b.minX) * 0.04, y: y0, w: wS, h: fp.self * sc,
            color: 'rgba(56,225,176,0.7)', solid: true, label: 'this', hLabel: fp.self + 'mm' });
        }
        const travel = (def.travelOf ? def.travelOf(P, u) : bf(u) * 30);
        return { scene, read: { travel, damper: damperLen(u), mr: mr(u), phase: phaseName(u) } };
      },
    });
  }

  /* ---- shared double-wishbone geometry (pushrod & pullrod & direct) ----- */
  function wishbone(z) {
    const LAi = v(0, 0), UAi = v(20, 150), Llow = 280, Lup = 250, upright = 150;
    const LAo0 = v(279, 0), wheelOut = 78;
    const yT = LAo0.y + z, dy = yT - LAi.y;
    const dx = Math.sqrt(Math.max(1, Llow * Llow - dy * dy));
    const LAo = v(LAi.x + dx, yT);
    const UAo = K.circleIntersect(UAi, Lup, LAo, upright, +1) || v(248, 150);
    const upDir = norm(sub(UAo, LAo)), outN = perp(upDir);
    const wheel = add(lerp(LAo, UAo, 0.5), scale(outN, wheelOut));
    return { LAi, UAi, LAo, UAo, wheel, upDir, outN };
  }
  function uprightPoly(s) {
    return [add(s.LAo, scale(s.upDir, -8)), add(s.UAo, scale(s.upDir, 8)),
      add(add(s.UAo, scale(s.upDir, 8)), scale(s.outN, 18)),
      add(add(s.LAo, scale(s.upDir, -8)), scale(s.outN, 18))];
  }
  function wishboneScene(s) {
    return [
      { type: 'ground', a: v(-40, -5), b: v(-40, 200) }, { type: 'ground', a: v(-14, 0), b: v(36, 0) },
      { type: 'link', kind: 'arm', pts: [s.LAi, s.LAo], w: 10 },
      { type: 'link', kind: 'arm', pts: [s.UAi, s.UAo], w: 9 },
      { type: 'upright', pts: uprightPoly(s) },
      { type: 'wheel', at: s.wheel, r: 95 },
      { type: 'pivot', at: s.LAi, grounded: true }, { type: 'pivot', at: s.UAi, grounded: true },
      { type: 'pivot', at: s.LAo }, { type: 'pivot', at: s.UAo },
    ];
  }

  const list = [];

  /* ===================== 1. Direct-acting coilover ====================== */
  list.push(make({
    id: 'direct', name: 'Direct-Acting Coilover', short: 'No rocker — baseline',
    category: 'Baseline architectures', badge: 'base', mrText: '≈ 1.1 (fixed)',
    stats: { compact: 2, complex: 1, force: 5, rising: 1 },
    info: {
      how: 'The spring-damper bolts straight between the lower wishbone and the chassis — no rocker at all. Wheel travel and damper travel are almost equal, so the motion ratio sits near 1.0 and barely changes through the stroke.',
      shorten: 'This is the reference case: there is no rocker to shorten. Everything that follows exists to beat its packaging, its near-fixed rate, or its outboard mass — while re-introducing a rocker that must then be made as short as possible.',
      pros: ['Simplest, lightest, cheapest', 'No rocker compliance or bearings', 'Very high force capacity', 'Easy to analyse'],
      cons: ['Motion ratio stuck near 1.0', 'No rising-rate tuning', 'Damper hangs outboard (mass, aero)', 'Bulky in the wheel area'],
      uses: ['Road cars, GT, MacPherson / wishbone production cars', 'Club racers'],
    },
    box: BB(-70, -40, 360, 360), damperGap: 44,
    drive(u) { const s = wishbone(bf(u) * 30); return Object.assign(s, { out: lerp(s.LAi, s.LAo, 0.9), track: s.wheel }); },
    travelOf: (P, u) => bf(u) * 30,
    scene(P, ctx) {
      return [...wishboneScene(P),
        { type: 'label', at: ctx.mount, text: 'chassis mount', dy: -14 },
        { type: 'label', at: P.wheel, text: 'wheel', dy: 4 },
        { type: 'arrow', from: add(P.wheel, v(118, -36)), to: add(P.wheel, v(118, 36)), color: '#38e1b0', label: 'travel' },
        { type: 'pivot', at: P.out, hot: true }];
    },
  }));

  /* ===================== 2. Pushrod + bellcrank ======================== */
  list.push(make({
    id: 'pushrod', name: 'Pushrod + Bellcrank', short: 'Rod in compression',
    category: 'Baseline architectures', badge: 'base', mrText: '≈ 1.3 → 1.6',
    stats: { compact: 3, complex: 3, force: 5, rising: 2 },
    info: {
      how: 'A rod runs from low on the upright up-and-inboard to a rocker (bellcrank) mounted high on the chassis. As the wheel rises, the rod pushes (compression) and rotates the rocker, which compresses an inboard spring-damper. The rocker arm lengths r_in and r_out set the motion ratio.',
      shorten: 'The rocker here is a long single lever — exactly the part later mechanisms attack. Its length is dictated by needing both the rod and the damper to sweep small, near-perpendicular angles. Watch how much vertical space the rocker + damper consume up high.',
      pros: ['Inboard spring/damper — clean aero, lower unsprung influence', 'Tunable motion ratio & mild rising rate', 'High force path (rod in compression)'],
      cons: ['Rocker is long → mass, compliance, packaging up high', 'Raises CG vs pullrod', 'More joints than direct-acting'],
      uses: ['F1 (front, historically), most formula cars', 'FSAE, sports prototypes'],
    },
    box: BB(-70, -40, 380, 430),
    drive(u) {
      const s = wishbone(bf(u) * 30);
      const rodBot = lerp(s.LAo, s.UAo, 0.16);
      const RP = v(70, 372), rodLen = 352, armIn = 108;
      const rIn = K.circleIntersect(rodBot, rodLen, RP, armIn, -1) || v(40, 312);
      const baseAng = angle(sub(K.circleIntersect(lerp(wishbone(0).LAo, wishbone(0).UAo, 0.16), rodLen, RP, armIn, -1) || v(40, 312), RP));
      const dAng = angle(sub(rIn, RP)) - baseAng;
      const rOut = add(RP, rot(v(-72, 8), dAng));
      return { s, rodBot, RP, rIn, rOut, out: rOut, track: s.wheel };
    },
    scene(P, ctx, u) {
      const plate = [P.rIn, P.RP, P.out, add(P.RP, scale(norm(add(sub(P.rIn, P.RP), sub(P.out, P.RP))), 24))];
      return [...wishboneScene(P.s),
        { type: 'ground', a: v(46, 372), b: v(96, 408) },
        { type: 'link', kind: 'push', pts: [P.rodBot, P.rIn], w: 6 },
        { type: 'plate', pts: plate },
        { type: 'pivot', at: P.rodBot }, { type: 'pivot', at: P.rIn, hot: true },
        { type: 'pivot', at: P.RP, grounded: true },
        { type: 'dim', a: P.RP, b: P.rIn, text: 'r_in', off: 18 },
        { type: 'dim', a: P.RP, b: P.out, text: 'r_out', off: -18 },
        { type: 'label', at: lerp(P.rodBot, P.rIn, 0.5), text: 'pushrod', dx: 14, anchor: 'start', color: '#4ea1ff' },
        { type: 'label', at: P.RP, text: 'rocker', dx: 26, anchor: 'start' },
        { type: 'arrow', from: P.rodBot, to: add(P.rodBot, scale(norm(sub(P.rIn, P.rodBot)), bf(u) >= 0 ? 42 : -42)), color: '#4ea1ff', label: bf(u) >= 0 ? 'COMPRESSION' : 'unloading' }];
    },
  }));

  /* ===================== 3. Pullrod + bellcrank ======================== */
  list.push(make({
    id: 'pullrod', name: 'Pullrod + Bellcrank', short: 'Rod in tension, low CG',
    category: 'Baseline architectures', badge: 'base', mrText: '≈ 1.2 → 1.5',
    stats: { compact: 3, complex: 3, force: 5, rising: 2 },
    info: {
      how: 'Mirror of the pushrod: the rod runs from high on the upright down-and-inboard to a low-mounted rocker, so on bump the rod pulls (tension). The low rocker drives a spring-damper near the floor.',
      shorten: 'Same long-lever rocker problem, but mounted low. Pullrod lowers the centre of gravity and frees the top of the chassis, yet the rocker itself is no shorter — the motivation for the compact alternatives is identical.',
      pros: ['Lowers CG, mass low in chassis', 'Frees the top deck / airbox area', 'Rod in tension can be slimmer'],
      cons: ['Rocker still long', 'Harder to access low down', 'Tight packaging near floor/gearbox'],
      uses: ['F1 (rear widely; front on some cars)', 'LMP, IndyCar'],
    },
    box: BB(-70, -130, 380, 320),
    drive(u) {
      const s = wishbone(bf(u) * 30);
      const rodTop = lerp(s.UAo, s.LAo, 0.14);
      const RP = v(70, -78), rodLen = 300, armIn = 70;
      const rest0 = lerp(wishbone(0).UAo, wishbone(0).LAo, 0.14);
      const rIn = K.circleIntersect(rodTop, rodLen, RP, armIn, +1) || v(42, -12);
      const baseAng = angle(sub(K.circleIntersect(rest0, rodLen, RP, armIn, +1) || v(42, -12), RP));
      const dAng = angle(sub(rIn, RP)) - baseAng;
      const rOut = add(RP, rot(v(60, 4), dAng));
      return { s, rodTop, RP, rIn, rOut, out: rOut, track: s.wheel };
    },
    scene(P, ctx, u) {
      const plate = [P.rIn, P.RP, P.out, add(P.RP, scale(norm(add(sub(P.rIn, P.RP), sub(P.out, P.RP))), 22))];
      return [...wishboneScene(P.s),
        { type: 'ground', a: v(46, -78), b: v(96, -114) },
        { type: 'link', kind: 'pull', pts: [P.rodTop, P.rIn], w: 5 },
        { type: 'plate', pts: plate },
        { type: 'pivot', at: P.rodTop }, { type: 'pivot', at: P.rIn, hot: true },
        { type: 'pivot', at: P.RP, grounded: true },
        { type: 'dim', a: P.RP, b: P.rIn, text: 'r_in', off: 16 },
        { type: 'dim', a: P.RP, b: P.out, text: 'r_out', off: -16 },
        { type: 'label', at: lerp(P.rodTop, P.rIn, 0.5), text: 'pullrod (tension)', dx: 14, anchor: 'start', color: '#38e1b0' },
        { type: 'arrow', from: P.rodTop, to: add(P.rodTop, scale(norm(sub(P.rIn, P.rodTop)), bf(u) >= 0 ? -42 : 42)), color: '#38e1b0', label: bf(u) >= 0 ? 'TENSION' : 'unloading' }];
    },
  }));

  /* ===================== 4. L-shaped bellcrank ========================= */
  list.push(make({
    id: 'lcrank', name: 'L-Shaped Bellcrank', short: 'Fold the arms — shrink the box',
    category: 'Compact rocker alternatives', badge: 'compact', mrText: '≈ 1.18 (fixed-ish)',
    stats: { compact: 3, complex: 1, force: 5, rising: 2 },
    info: {
      how: 'The same single-lever rocker, but the two arms are folded to ~90° (an "L") and the pivot is offset toward the more heavily loaded rod. The motion ratio is still r_in / r_out, but the package is far tighter.',
      shorten: 'The "free lunch" of the rocker family: folding a 180° straight lever into a 90° L keeps both arm lengths (so the ratio is unchanged) while the bounding-box height collapses — here from ~83 mm to ~45 mm for the same ratio. No extra joints, no friction, no backlash. The trade is that an L-crank stays linear only to ~±30°.',
      pros: ['Zero extra parts — cheapest, stiffest, no backlash', 'Big packaging win for free', 'Highest force capacity'],
      cons: ["Can't beat the fundamental ratio-vs-length coupling", 'Linear only to ~±30° swing', 'Limited rising rate'],
      uses: ['The default FSAE / racecar inboard rocker', 'Wherever a simple rocker just needs to fit'],
    },
    box: BB(-40, -120, 120, 80),
    drive(u) {
      const P = v(0, 0), a0 = bf(u) * 24 * D2R;
      const rIn = add(P, fromAngle(-90 * D2R + a0, 45));
      const rOut = add(P, fromAngle(-12 * D2R + a0, 38));
      return { P, rIn, rOut, out: rOut, track: rIn };
    },
    scene(P, ctx, u) {
      const gOut = add(P.P, fromAngle(90 * D2R + bf(u) * 24 * D2R, 38));
      return [
        { type: 'ground', a: v(-25, -10), b: v(25, 10) },
        { type: 'trace', pts: [P.P, gOut], color: 'rgba(255,107,107,0.4)' },
        { type: 'note', at: v(-30, 56), text: 'straight 180° crank → box H≈83mm', anchor: 'start' },
        { type: 'link', kind: 'push', pts: [v(-2, -100), P.rIn], w: 6 },
        { type: 'plate', pts: [P.rIn, P.P, P.out, lerp(P.rIn, P.out, 0.5)] },
        { type: 'pivot', at: P.P, grounded: true }, { type: 'pivot', at: P.rIn, hot: true },
        { type: 'pivot', at: v(-2, -100) },
        { type: 'dim', a: P.P, b: P.rIn, text: 'r_in 45', off: 16 },
        { type: 'dim', a: P.P, b: P.out, text: 'r_out 38', off: -16 },
        { type: 'arrow', from: v(-2, -100), to: v(-2, -100 + (bf(u) >= 0 ? 30 : -30)), color: '#4ea1ff', label: 'pushrod' }];
    },
  }));

  /* ===================== 5. Compound two-stage rocker ================== */
  list.push(make({
    id: 'compound', name: 'Compound Two-Stage Rocker', short: 'Ratios multiply → short arms',
    category: 'Compact rocker alternatives', badge: 'compact', mrText: 'progressive',
    stats: { compact: 3, complex: 4, force: 4, rising: 5 },
    info: {
      how: 'Two pivoted rockers in series, linked by a short coupler (a Watt-type six-bar). The pushrod drives rocker A; the coupler drives rocker B; rocker B drives the spring. The overall ratio is the product of the two stage ratios.',
      shorten: 'Because the stage ratios MULTIPLY, each stage only needs the square root of the total. For a 3:1 ratio a single lever needs 3:1 arms (large radius); two stages need only ~1.73:1 each, so both pivots sit on small ~30–40 mm radii. The coupler also folds the linkage around chassis tubes. Strong rising rate falls out naturally.',
      pros: ['Compact yet high ratio (arms ~√ of single lever)', 'Excellent designed-in rising rate', 'Folds around structure', 'Loads split across two pivots'],
      cons: ['Six joints — more bearings, mass, compliance', 'Two wear paths, harder to analyse', 'Backlash adds up'],
      uses: ['MTB & motorcycle linkage rear ends (DW-link, Horst, Pro-Link)', 'FSAE "three-hinged" staged rockers'],
    },
    box: BB(-60, -90, 180, 90),
    drive(u) {
      const PA = v(0, 0), PB = v(95, 26), aA = bf(u) * 15 * D2R;
      const Ain = add(PA, fromAngle(-128 * D2R + aA, 42));
      const Aout = add(PA, fromAngle(34 * D2R + aA, 34));
      const couplerLen = 42, armBin = 36;
      const Bin = K.circleIntersect(Aout, couplerLen, PB, armBin, -1) || v(62, 36);
      const base = angle(sub(K.circleIntersect(add(PA, fromAngle(34 * D2R, 34)), couplerLen, PB, armBin, -1) || v(62, 36), PB));
      const dB = angle(sub(Bin, PB)) - base;
      const Bout = add(PB, rot(v(-4, -36), dB));
      return { PA, PB, Ain, Aout, Bin, Bout, out: Bout, track: Ain };
    },
    scene(P, ctx, u) {
      return [
        { type: 'ground', a: v(-20, -10), b: v(20, 8) }, { type: 'ground', a: v(78, 18), b: v(118, 36) },
        { type: 'link', kind: 'push', pts: [v(-30, -76), P.Ain], w: 6 },
        { type: 'plate', pts: [P.Ain, P.PA, P.Aout, lerp(P.Ain, P.Aout, 0.5)] },
        { type: 'plate', pts: [P.Bin, P.PB, P.Bout, lerp(P.Bin, P.Bout, 0.5)] },
        { type: 'link', kind: 'coupler', pts: [P.Aout, P.Bin], w: 6 },
        { type: 'pivot', at: P.PA, grounded: true }, { type: 'pivot', at: P.PB, grounded: true },
        { type: 'pivot', at: P.Ain, hot: true }, { type: 'pivot', at: P.Aout }, { type: 'pivot', at: P.Bin },
        { type: 'pivot', at: v(-30, -76) },
        { type: 'label', at: P.PA, text: 'stage A', dy: 22 }, { type: 'label', at: P.PB, text: 'stage B', dy: 22 },
        { type: 'label', at: lerp(P.Aout, P.Bin, 0.5), text: 'coupler', dy: -12, color: '#9aa7bd' },
        { type: 'arrow', from: v(-30, -76), to: add(v(-30, -76), scale(norm(sub(P.Ain, v(-30, -76))), bf(u) >= 0 ? 34 : -34)), color: '#4ea1ff' }];
    },
  }));

  /* ===================== 6. Four-bar coupler actuation ================= */
  list.push(make({
    id: 'fourbar', name: 'Four-Bar Coupler Actuation', short: 'Coupler-curve does the work',
    category: 'Compact rocker alternatives', badge: 'compact', mrText: 'synthesizable',
    stats: { compact: 3, complex: 3, force: 4, rising: 4 },
    info: {
      how: 'A classic four-bar: ground + input crank (driven by the pushrod) + coupler + output rocker. The spring attaches to a tracer point on the coupler that follows a designed coupler curve.',
      shorten: 'The coupler-point trick: a point on the coupler can trace an arbitrary near-straight or curved path, so a short, compact four-bar produces the end-point travel a long single lever would need a big radius for. You exploit the changing transmission angle deliberately, keeping the cranks short (30–45 mm), and the ratio curve is directly synthesizable.',
      pros: ['Short stiff members for a given travel', 'Motion-ratio curve can be synthesized', 'Only pin joints — low friction, low backlash'],
      cons: ['Coupler bending loads need stiffness', 'Nonlinear ratio must be designed carefully', 'Synthesis is non-trivial'],
      uses: ['MTB / motorcycle linkages', 'Machine-tool toggles; the wishbone set is itself a four-bar'],
    },
    box: BB(-50, -70, 170, 120),
    drive(u) {
      const O2 = v(0, 0), O4 = v(90, 0), L2 = 35, L3 = 78, L4 = 42;
      const th2 = (62 + bf(u) * 20) * D2R;
      const fb = K.fourBar(O2, O4, L2, L3, L4, th2, +1) || { B: v(20, 30), C: v(90, 42) };
      const A = fb.B, Bp = fb.C, cdir = norm(sub(Bp, A));
      const Pt = add(add(A, scale(cdir, 30)), scale(perp(cdir), 18));
      return { O2, O4, A, Bp, Pt, out: Pt, track: A };
    },
    scene(P, ctx, u) {
      const trace = [];
      for (let i = 0; i <= 24; i++) {
        const t = (62 + ((i / 24) - 0.5) * 40) * D2R;
        const f = K.fourBar(P.O2, P.O4, 35, 78, 42, t, +1); if (!f) continue;
        const cd = norm(sub(f.C, f.B));
        trace.push(add(add(f.B, scale(cd, 30)), scale(perp(cd), 18)));
      }
      return [
        { type: 'ground', a: v(-20, -12), b: v(20, 8) }, { type: 'ground', a: v(72, -12), b: v(110, 8) },
        { type: 'trace', pts: trace, color: 'rgba(56,225,176,0.5)' },
        { type: 'note', at: v(30, -44), text: 'coupler curve', anchor: 'middle' },
        { type: 'link', kind: 'push', pts: [v(-26, -52), P.A], w: 6 },
        { type: 'link', kind: 'arm', pts: [P.O2, P.A], w: 8 },
        { type: 'plate', pts: [P.A, P.Bp, P.Pt] },
        { type: 'link', kind: 'arm', pts: [P.O4, P.Bp], w: 8 },
        { type: 'pivot', at: P.O2, grounded: true }, { type: 'pivot', at: P.O4, grounded: true },
        { type: 'pivot', at: P.A, hot: true }, { type: 'pivot', at: P.Bp }, { type: 'pivot', at: v(-26, -52) },
        { type: 'label', at: P.O2, text: 'crank', dy: 22 }, { type: 'label', at: P.O4, text: 'rocker', dy: 22 },
        { type: 'label', at: P.Pt, text: 'tracer P', dx: 12, anchor: 'start' },
        { type: 'arrow', from: v(-26, -52), to: add(v(-26, -52), scale(norm(sub(P.A, v(-26, -52))), bf(u) >= 0 ? 32 : -32)), color: '#4ea1ff' }];
    },
  }));

  /* ===================== 7. Watt's linkage ============================= */
  list.push(make({
    id: 'watt', name: "Watt's Linkage", short: 'Near-straight from a folded cell',
    category: 'Compact rocker alternatives', badge: 'compact', mrText: '≈ 1.0 (straight zone)',
    stats: { compact: 3, complex: 3, force: 4, rising: 2 },
    info: {
      how: 'A symmetric four-bar: two equal outer bars and a shorter middle coupler. The coupler MIDPOINT traces a figure-eight whose central crossing is straight to a few thousandths of link length. The damper hangs off that midpoint.',
      shorten: 'Instead of swinging a long arm to keep the spring eye moving straight, the Watt cell delivers near-straight travel from a folded, symmetric package whose height ≈ the travel itself. It substitutes for BOTH a long lever and a sliding guide, giving an essentially constant motion ratio (≈1) with no big radius — provided the outer bars match to ~0.1%.',
      pros: ['Near-straight damper motion, only pin joints', 'Very low friction, no backlash', 'Compact symmetric package'],
      cons: ['Only approximate straight line', 'Usable straight range ~20–25% of bar length', 'Symmetry tolerance critical'],
      uses: ['Live-axle lateral location (many road cars)', 'Inline shock actuation without a slider'],
    },
    box: BB(-90, -70, 90, 150), damperGap: 36,
    drive(u) {
      const G1 = v(-50, 60), G2 = v(50, 60), L = 60, half = 25;
      const a1 = (-72 + bf(u) * 14) * D2R;
      const C1 = add(G1, fromAngle(a1, L));
      const C2 = K.circleIntersect(C1, 2 * half, G2, L, +1) || v(25, 5);
      const M = lerp(C1, C2, 0.5);
      // input reference = the vertical travel the damper actually sees (the
      // sideways figure-eight error is the straightness defect, not the input).
      return { G1, G2, C1, C2, M, out: M, track: v(0, M.y) };
    },
    travelOf: (P, u) => bf(u) * 30,
    scene(P, ctx, u) {
      const trace = [];
      for (let i = 0; i <= 20; i++) {
        const a = (-72 + ((i / 20) - 0.5) * 28) * D2R;
        const c1 = add(P.G1, fromAngle(a, 60));
        const c2 = K.circleIntersect(c1, 50, P.G2, 60, +1); if (!c2) continue;
        trace.push(lerp(c1, c2, 0.5));
      }
      return [
        { type: 'ground', a: v(-70, 60), b: v(-50, 78) }, { type: 'ground', a: v(50, 78), b: v(70, 60) },
        { type: 'trace', pts: trace, color: 'rgba(78,161,255,0.45)' },
        { type: 'link', kind: 'arm', pts: [P.G1, P.C1], w: 7 }, { type: 'link', kind: 'arm', pts: [P.G2, P.C2], w: 7 },
        { type: 'link', kind: 'coupler', pts: [P.C1, P.C2], w: 6 },
        { type: 'pivot', at: P.G1, grounded: true }, { type: 'pivot', at: P.G2, grounded: true },
        { type: 'pivot', at: P.C1 }, { type: 'pivot', at: P.C2 }, { type: 'pivot', at: P.M, hot: true },
        { type: 'label', at: P.M, text: 'midpoint ≈ straight', dy: 18, color: '#4ea1ff' }];
    },
  }));

  /* ===================== 8. Scott-Russell ============================== */
  list.push(make({
    id: 'scott', name: 'Scott-Russell Linkage', short: 'Exact line + 2:1 amplification',
    category: 'Compact rocker alternatives', badge: 'compact', mrText: '2:1 amplifier',
    stats: { compact: 4, complex: 3, force: 2, rising: 2 },
    info: {
      how: 'A coupler with a slider at one end (on a guide line) and a fixed pivot at its midpoint carried by an equal-length swing link. The far coupler end traces an EXACT straight line perpendicular to the slider path, with a built-in 2:1 displacement ratio.',
      shorten: 'A short swing link of length a produces ~2a of PURE straight output travel — a built-in motion amplifier. So the spring gets large, perfectly linear travel from a tiny rotating link, with no long lever radius at all. The amplification is done by geometry rather than arm length.',
      pros: ['Exact straight-line output', 'Built-in 2:1 amplification from a tiny link', 'Very compact'],
      cons: ['Needs a slider — friction, wear, contamination', 'Limited stroke before geometry degrades', 'Lower force capacity'],
      uses: ['Lab stages, antenna/mirror deployers, presses', 'Modified slider-less forms for compact actuation'],
    },
    box: BB(-30, -25, 130, 150), damperGap: 30,
    drive(u) {
      const G = v(0, 0), a = 50, ang = (52 + bf(u) * 13) * D2R;
      const Mc = add(G, fromAngle(ang, a));
      const S = v(2 * Mc.x, 0), T = v(0, 2 * Mc.y);
      return { G, Mc, S, T, out: T, track: S };
    },
    travelOf: (P, u) => bf(u) * 30,
    scene(P, ctx, u) {
      return [
        { type: 'ground', a: v(-12, -8), b: v(12, 8) }, { type: 'ground', a: v(-25, 0), b: v(125, 0) },
        { type: 'trace', pts: [v(0, 0), v(0, 130)], color: 'rgba(56,225,176,0.4)' },
        { type: 'link', kind: 'arm', pts: [P.G, P.Mc], w: 7 },
        { type: 'link', kind: 'coupler', pts: [P.S, P.T], w: 6 },
        { type: 'roller', at: P.S, r: 8 },
        { type: 'pivot', at: P.G, grounded: true }, { type: 'pivot', at: P.Mc }, { type: 'pivot', at: P.T, hot: true },
        { type: 'label', at: P.S, text: 'slider', dy: 20 }, { type: 'label', at: P.Mc, text: 'mid', dx: 12, anchor: 'start' },
        { type: 'label', at: P.T, text: 'output (exact line)', dx: 12, anchor: 'start', color: '#38e1b0' }];
    },
  }));

  /* ===================== 9. Toggle / over-center ======================= */
  list.push(make({
    id: 'toggle', name: 'Toggle / Over-Center', short: 'Strong rising rate, tiny cell',
    category: 'Compact rocker alternatives', badge: 'adv', mrText: 'MA = 1/(2·tanθ) ↑',
    stats: { compact: 5, complex: 1, force: 5, rising: 5 },
    info: {
      how: 'Two links hinged at a knee. As they straighten toward 180°, a small input at the knee produces a huge output along the line of the links: mechanical advantage MA = 1/(2·tanθ), where θ is the half-angle from straight. MA → ∞ as θ → 0.',
      shorten: 'The toggle packs enormous, rapidly-rising motion ratio / force multiplication into two SHORT links — no long lever. Near dead-centre the output displacement per unit input collapses, which is exactly the rising-rate characteristic designers otherwise chase with a big curved bellcrank, now in a tiny over-centre cell.',
      pros: ['Extreme compactness', 'Built-in strong rising rate', 'Very high force near straight', 'Only two pins'],
      cons: ['Highly nonlinear by design', 'Must stay off exact dead-centre (locks/reverses)', 'Position-sensitive — poor for large linear travel'],
      uses: ['Clamps, presses, knee-action mechanisms', 'MX/off-road end-stroke rising-rate linkages'],
    },
    box: BB(-80, -25, 70, 160), damperGap: 26,
    drive(u) {
      // A grounded at origin; knee K driven horizontally inward as bump rises;
      // output B rides up the y-axis (displacement amplifier → rising wheel rate).
      const A = v(0, 0), L1 = 52, L2 = 52;
      const kx = 42 - u * 35;                       // 42 (droop) -> 7 (bump, near straight)
      const ky = Math.sqrt(Math.max(1, L1 * L1 - kx * kx));
      const Kpt = v(kx, ky);
      const B = v(0, ky + Math.sqrt(Math.max(1, L2 * L2 - kx * kx)));
      return { A, B, Kpt, out: B, track: Kpt };
    },
    travelOf: (P, u) => bf(u) * 30,
    scene(P, ctx, u) {
      const theta = Math.atan2(Math.abs(P.Kpt.x), P.Kpt.y); // half-angle from straight
      const MA = 1 / (2 * Math.tan(Math.max(0.05, theta)));
      return [
        { type: 'ground', a: v(-12, -8), b: v(12, 8) },
        { type: 'trace', pts: [v(0, 60), v(0, 110)], color: 'rgba(255,180,84,0.35)' },
        { type: 'link', kind: 'arm', pts: [P.A, P.Kpt], w: 8 }, { type: 'link', kind: 'arm', pts: [P.Kpt, P.B], w: 8 },
        { type: 'pivot', at: P.A, grounded: true }, { type: 'pivot', at: P.B, hot: true },
        { type: 'pivot', at: P.Kpt },
        { type: 'label', at: P.Kpt, text: 'knee θ=' + (theta * R2D).toFixed(0) + '°', dx: 14, anchor: 'start', color: '#ffb454' },
        { type: 'label', at: P.B, text: 'output (amplified)', dx: 12, anchor: 'start', color: '#ffb454' },
        { type: 'note', at: v(-74, 140), text: 'MA = 1/(2·tanθ) = ' + MA.toFixed(2), anchor: 'start' },
        { type: 'arrow', from: add(P.Kpt, v(26, 0)), to: add(P.Kpt, v(26 - (bf(u) >= 0 ? 20 : -20), 0)), color: '#ffb454', label: 'input' }];
    },
  }));

  /* ===================== 10. Geared sector rocker ===================== */
  list.push(make({
    id: 'gear', name: 'Geared Sector Rocker', short: 'Ratio from gear radii',
    category: 'Compact rocker alternatives', badge: 'adv', mrText: 'R1/R2 ≈ 1.67',
    stats: { compact: 4, complex: 3, force: 3, rising: 3 },
    info: {
      how: 'The two-arm lever is replaced by a pair of meshing gear sectors. The pushrod drives sector 1 (radius R1); it meshes sector 2 (radius R2) that drives the spring crank. The angular ratio is R1/R2.',
      shorten: 'A gear pair multiplies rotation in a tiny centre distance — the ratio comes from the gear-radii ratio, not from a long moment arm. You can get 2:1 or 3:1 in a ~50 mm centre distance, then take the spring off a short crank on the second gear. Ratio (gears) is decoupled from the force arm (short crank).',
      pros: ['Big ratio in a small centre distance', 'Can counter-rotate / fold compactly', 'Decouples ratio from force arm'],
      cons: ['Backlash is the headline problem (precision, noise, fatigue)', 'Tooth friction & contact stress limit force', 'Cost, mass, lubrication'],
      uses: ['Cambering trikes (opposed sector gears)', 'Anti-roll-bar / heave interconnects; active actuators'],
    },
    box: BB(-60, -80, 130, 90),
    drive(u) {
      const O1 = v(0, 0), R1 = 40, O2 = v(64, 0), R2 = 24;
      const th1 = bf(u) * 25 * D2R, th2 = -(R1 / R2) * th1;
      const Pin = add(O1, fromAngle(-90 * D2R + th1, 38));
      const Sout = add(O2, fromAngle(90 * D2R + th2, 30));
      return { O1, R1, O2, R2, th1, th2, Pin, Sout, out: Sout, track: Pin };
    },
    scene(P, ctx, u) {
      return [
        { type: 'ground', a: v(-12, -8), b: v(12, 8) }, { type: 'ground', a: v(52, -8), b: v(76, 8) },
        { type: 'gear', center: P.O1, r: P.R1, teeth: 20, angle: P.th1 },
        { type: 'gear', center: P.O2, r: P.R2, teeth: 12, angle: P.th2, phase: -Math.PI / 12 },
        { type: 'pivot', at: v(40, 0), r: 2.4, hot: true }, // pitch point (tangent of pitch circles)
        { type: 'note', at: v(34, 8), text: 'pitch point', anchor: 'start' },
        { type: 'link', kind: 'push', pts: [v(-6, -78), P.Pin], w: 6 },
        { type: 'link', kind: 'arm', pts: [P.O1, P.Pin], w: 6 }, { type: 'link', kind: 'arm', pts: [P.O2, P.Sout], w: 6 },
        { type: 'pivot', at: P.O1, grounded: true }, { type: 'pivot', at: P.O2, grounded: true },
        { type: 'pivot', at: P.Pin, hot: true }, { type: 'pivot', at: v(-6, -78) },
        { type: 'label', at: P.O1, text: 'R1=40', dy: 22 }, { type: 'label', at: P.O2, text: 'R2=24', dy: 22 },
        { type: 'arrow', from: v(-6, -78), to: add(v(-6, -78), v(0, bf(u) >= 0 ? 30 : -30)), color: '#4ea1ff' }];
    },
  }));

  /* ===================== 11. Rack-and-pinion ========================== */
  list.push(make({
    id: 'rack', name: 'Rack-and-Pinion', short: 'Constant-radius rolling lever',
    category: 'Compact rocker alternatives', badge: 'adv', mrText: '≈ 1.0 (constant)',
    stats: { compact: 4, complex: 3, force: 3, rising: 1 },
    info: {
      how: 'The pushrod drives a rack that rotates a pinion; a crank off the pinion drives the spring. Linear travel per pinion turn = π·D.',
      shorten: 'The pinion is a continuously rolling lever of CONSTANT radius — no long arm and no transmission-angle loss. The effective "lever arm" is the pinion pitch radius (e.g. 14 mm) and never changes through travel, giving a perfectly constant motion ratio in a tiny envelope. Retune the ratio by changing pinion diameter, not packaging length.',
      pros: ['Constant ratio, perfectly linear', 'Very compact', 'Retune by changing pinion diameter'],
      cons: ['Backlash & tooth friction/wear', 'No built-in rising rate (needs progressive spring)', 'Load limited by tooth strength'],
      uses: ['Universal in steering', 'Linear actuators, active-roll / test-rig actuators'],
    },
    box: BB(-50, -75, 110, 75),
    drive(u) {
      const O = v(0, 0), r = 14, dy = bf(u) * 24, th = dy / r;
      // input rack on the left drives the pinion; output rack on top translates
      // horizontally by the same pitch travel → exactly 1:1, constant ratio.
      const outPt = v(34 - dy, r + 2);
      return { O, r, th, dy, outPt, out: outPt, track: v(-r, dy) };
    },
    scene(P, ctx, u) {
      const r = 14;
      return [
        { type: 'rack', a: v(-r, -42 + P.dy), b: v(-r, 42 + P.dy), teeth: 9, side: 1 },
        { type: 'link', kind: 'push', pts: [v(-r, 58 + P.dy), v(-r, 42 + P.dy)], w: 5 },
        { type: 'gear', center: P.O, r: r, teeth: 12, angle: -P.th },
        { type: 'rack', a: v(P.outPt.x - 34, r + 2), b: v(P.outPt.x + 30, r + 2), teeth: 8, side: -1 },
        { type: 'pivot', at: P.O, grounded: true },
        { type: 'label', at: P.O, text: 'pinion r=14', dy: -26 },
        { type: 'note', at: v(-46, -60), text: 'input rack ↕ → pinion → output rack ↔ (1:1)', anchor: 'start' },
        { type: 'arrow', from: v(-r - 22, P.dy), to: v(-r - 22, P.dy + (bf(u) >= 0 ? 24 : -24)), color: '#4ea1ff', label: 'in' }];
    },
  }));

  /* ===================== 12. Cam-and-follower ========================= */
  list.push(make({
    id: 'cam', name: 'Cam-and-Follower', short: 'Profile programs the ratio',
    category: 'Compact rocker alternatives', badge: 'adv', mrText: 'ds/dφ (profiled)',
    stats: { compact: 5, complex: 2, force: 2, rising: 5 },
    info: {
      how: 'A profiled cam (rotated by the pushrod crank) pushes a translating follower that compresses the spring-damper. The cam profile — its rise vs cam angle — directly programs the motion ratio as a function of travel.',
      shorten: 'The cam IS the ratio function baked into a disc of radius ~30–50 mm. You get any progressive / digressive curve you want without a long, carefully shaped lever, because the effective arm is the local cam radius / pressure-angle, redefined at every point. Total rising-rate freedom in a compact rotating package.',
      pros: ['Ultimate ratio-curve freedom in tiny space', 'Smooth programmable rising/falling rate', 'Few moving parts'],
      cons: ['Sliding/rolling contact — friction, wear, high contact stress', 'Spring must keep follower in contact (no tension)', 'Precision manufacture, pressure-angle limits'],
      uses: ['Engine valvetrain (the canonical compact ratio-setter)', 'Progressive bicycle/motorcycle & seat suspensions'],
    },
    box: BB(-60, -60, 60, 130), damperGap: 30,
    drive(u) {
      const O = v(0, 0), base = 25, h = 34, beta = 130 * D2R;
      const sOf = (phi) => { const t = ((phi % TAU) + TAU) % TAU; if (t > beta) return 0; return h * (t / beta - Math.sin(2 * Math.PI * t / beta) / (2 * Math.PI)); };
      const camAng = 25 * D2R + u * beta * 0.7;
      const lift = sOf(camAng);
      const follower = v(0, base + lift + 6);
      // track = a virtual input-crank tip rotating with the cam, so MR reflects
      // the cam's programmed ds/dφ (input rotation vs output lift).
      return { O, base, follower, camAng, _sOf: sOf, out: follower, track: add(O, fromAngle(camAng, 22)) };
    },
    travelOf: (P, u) => bf(u) * 30,
    scene(P, ctx, u) {
      const radii = [];
      for (let i = 0; i < 90; i++) { const a = (i / 90) * TAU; radii.push(P.base + P._sOf(a)); }
      return [
        { type: 'ground', a: v(-12, -8), b: v(12, 8) },
        { type: 'cam', center: P.O, radii, angle: P.camAng },
        { type: 'roller', at: P.follower, r: 6 },
        { type: 'link', kind: 'arm', pts: [P.follower, v(0, 92)], w: 5 },
        { type: 'pivot', at: P.O, grounded: true },
        { type: 'label', at: P.O, text: 'cam φ=' + (P.camAng * R2D).toFixed(0) + '°', dy: -34 },
        { type: 'arrow', from: v(34, P.base), to: v(34, P.base + (bf(u) >= 0 ? 22 : -22)), color: '#ffb454', label: 'lift' }];
    },
  }));

  /* ===================== 13. Slider-crank ============================= */
  list.push(make({
    id: 'slider', name: 'Slider-Crank Actuation', short: 'Short crank, inline damper',
    category: 'Compact rocker alternatives', badge: 'adv', mrText: 'dx/dθ (varies)',
    stats: { compact: 4, complex: 3, force: 4, rising: 3 },
    info: {
      how: 'A pushrod-driven crank (radius r) plus a connecting rod (length l) drives a slider that compresses an inline spring-damper. Slider position x(θ)=r·cosθ+√(l²−r²sin²θ); the ratio dx/dθ varies through the stroke.',
      shorten: 'A short crank (r≈30 mm) directly drives a long inline damper stroke (≈2r) with a natural soft rising/falling character at the ends — no separate long rocker, and the damper lies straight along the chassis. Offsetting the slider tunes the ratio asymmetry.',
      pros: ['Inline, guided damper motion', 'Long stroke from a short crank', 'Natural end-stroke softening'],
      cons: ['Needs a slider/guide — friction, side-load, wear', 'Dead-centre singularities to avoid', 'Ratio is θ-dependent'],
      uses: ['Every piston engine; presses', 'Inline "puller" actuators & active dampers'],
    },
    box: BB(-50, -55, 205, 50), damperGap: 0, mount: v(186, 0),
    drive(u) {
      const O = v(0, 0), r = 30, l = 90, th = (90 - bf(u) * 55) * D2R;
      const A = add(O, fromAngle(th, r));
      const x = A.x + Math.sqrt(Math.max(1, l * l - A.y * A.y));
      const B = v(x, 0);
      return { O, r, l, th, A, B, out: B, track: A };
    },
    scene(P, ctx, u) {
      return [
        { type: 'ground', a: v(-12, -8), b: v(12, 8) }, { type: 'ground', a: v(176, -10), b: v(198, 10) },
        { type: 'ground', a: v(-30, -16), b: v(168, -16) },
        { type: 'link', kind: 'push', pts: [add(P.O, fromAngle(P.th - Math.PI, 36)), P.A], w: 6 },
        { type: 'link', kind: 'arm', pts: [P.O, P.A], w: 7 },
        { type: 'link', kind: 'coupler', pts: [P.A, P.B], w: 6 },
        { type: 'roller', at: P.B, r: 9 },
        { type: 'pivot', at: P.O, grounded: true }, { type: 'pivot', at: P.A, hot: true },
        { type: 'label', at: P.O, text: 'crank r=30', dy: 24 },
        { type: 'label', at: lerp(P.A, P.B, 0.5), text: 'con-rod l=90', dy: -10, color: '#9aa7bd' },
        { type: 'arrow', from: add(P.O, fromAngle(P.th - Math.PI, 36)), to: add(add(P.O, fromAngle(P.th - Math.PI, 36)), scale(norm(sub(P.A, add(P.O, fromAngle(P.th - Math.PI, 36)))), bf(u) >= 0 ? 30 : -30)), color: '#4ea1ff' }];
    },
  }));

  /* ---- metadata: footprint (illustrative mm), ratio meaning & table data --
   * footprint.lever = approx envelope height of an equivalent SINGLE rocker that
   * achieves the same ratio/travel; footprint.self = this mechanism's envelope.
   * These are illustrative engineering estimates, consistent with RESEARCH.md.   */
  // fp:[single-rocker envelope mm, this-mechanism envelope mm] — indicative
  // engineering estimates grounded in RESEARCH.md (the schematics themselves are
  // not packaging-optimised). benefit = the mechanism's PRIMARY win.
  const META = {
    direct:   { ratioNote: 'wheel travel : damper travel', joints: 2, backlash: 'none', table: 'No rocker (reference).' },
    pushrod:  { ratioNote: 'wheel travel : damper travel', joints: 5, backlash: 'none', table: 'Long lever, rod in compression.' },
    pullrod:  { ratioNote: 'wheel travel : damper travel', joints: 5, backlash: 'none', table: 'Long lever, rod in tension, low CG.' },
    lcrank:   { fp: [83, 48], benefit: 'packaging (fold)', ratioNote: 'rod travel : damper travel', joints: 3, backlash: 'none', table: 'Fold arms 90° → shorter box, same ratio.' },
    compound: { fp: [96, 58], benefit: 'short stiff arms', ratioNote: 'rod travel : damper travel (per-stage product)', joints: 6, backlash: 'low-med', table: 'Stage ratios multiply → each arm ≈ √(total).' },
    fourbar:  { fp: [90, 56], benefit: 'synthesised curve', ratioNote: 'crank travel : damper travel', joints: 4, backlash: 'low', table: 'Coupler curve replaces a big radius.' },
    watt:     { fp: [88, 60], benefit: 'straight-line, folded', ratioNote: 'vertical travel : damper travel', joints: 4, backlash: 'very low', table: 'Near-straight motion from a folded cell.' },
    scott:    { fp: [100, 56], benefit: '2:1 amplification', ratioNote: 'slider travel : damper travel', joints: 4, backlash: 'med (slider)', table: 'Exact line + built-in 2:1 amplification.' },
    toggle:   { fp: [110, 44], benefit: 'rising rate', ratioNote: 'knee travel : damper travel', joints: 2, backlash: 'low', table: 'Two short links → strong rising rate.' },
    gear:     { fp: [100, 52], benefit: 'ratio in small space', ratioNote: 'gear-radii ratio R1/R2', joints: 2, backlash: 'HIGH', table: 'Ratio from gear radii in tiny centre distance.' },
    rack:     { fp: [95, 46], benefit: 'constant linear ratio', ratioNote: 'constant 1:1 (set by pinion radius)', joints: 2, backlash: 'high', table: 'Constant-radius rolling lever, linear.' },
    cam:      { fp: [95, 45], benefit: 'programmable ratio', ratioNote: 'cam ds/dφ (profiled)', joints: 2, backlash: 'med (contact)', table: 'Profile programs any ratio curve.' },
    slider:   { fp: [92, 52], benefit: 'inline long stroke', ratioNote: 'crank travel : damper travel (dx/dθ)', joints: 4, backlash: 'med (slider)', table: 'Short crank → long inline damper stroke.' },
  };
  list.forEach((m) => {
    const x = META[m.id]; if (!x) return;
    m.ratioNote = x.ratioNote; m.joints = x.joints; m.backlash = x.backlash; m.tableNote = x.table; m.benefit = x.benefit;
    if (x.fp) m.footprint = { lever: x.fp[0], self: x.fp[1], reduction: Math.round((1 - x.fp[1] / x.fp[0]) * 100) };
  });

  return list;
})();

if (typeof module !== 'undefined' && module.exports) module.exports = Mechanisms;
