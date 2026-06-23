/* =============================================================================
 * renderer.js — SVG scene renderer for suspension mechanisms
 * -----------------------------------------------------------------------------
 * A mechanism's solve(phase) returns a flat list of drawing PRIMITIVES in world
 * coordinates (mm, y-up). This module fits them to the viewport and renders them
 * with engineering-realistic styling (metallic gradients, soft shadows, coil
 * springs, dampers, gears, cams, dimension lines, motion arrows).
 *
 * Primitive types (each is a plain object with `type`):
 *   ground   {a,b}                      hatched fixed-support bar a->b
 *   pivot    {at, grounded?, r?, hot?}  revolute joint node
 *   link     {pts:[...], w?, kind?}     bar / arm / rod (kind: arm|rod|coupler|push|pull)
 *   plate    {pts:[...], pivot?}        filled rigid body (rocker/bellcrank)
 *   coilover {a,b, rest, kind?}         spring+damper between a(chassis) and b(rocker)
 *   spring   {a,b, rest, coils?}        bare coil spring
 *   damper   {a,b}                      bare damper (no spring)
 *   wheel    {at, r}                    tyre + rim
 *   upright  {pts:[...]}                hub carrier polygon
 *   gear     {center, r, teeth, angle, kind?}
 *   rack     {a,b, teeth, side?}        toothed bar a->b
 *   cam      {center, radii:[...], angle}  closed polar cam outline
 *   roller   {at, r}
 *   arrow    {from,to, color?, label?, w?}
 *   trace    {pts:[...], color?}        faint path / locus
 *   label    {at, text, sub?, anchor?, color?}
 *   dim      {a,b, text, off?}          dimension line with text
 *   note     {at, text}                 small annotation
 * ========================================================================== */

const Renderer = (() => {
  'use strict';
  const SVGNS = 'http://www.w3.org/2000/svg';
  const el = (n, a = {}) => {
    const e = document.createElementNS(SVGNS, n);
    for (const k in a) e.setAttribute(k, a[k]);
    return e;
  };

  /* palette shared with CSS */
  const C = {
    arm:    '#9aa7bd', armEdge:'#5c6b82',
    rod:    '#2f3742', rodGlow:'#4ea1ff',
    plate:  '#2b4a73', plateEdge:'#4ea1ff',
    spring: '#ffb454', damperBody:'#cfd8e6', damperRod:'#8a94a6',
    pivot:  '#0b0e14', pivotRing:'#aeb9c9', pivotHot:'#ffb454',
    ground: '#3a4456',
    wheel:  '#15191f', rim:'#3a4456',
    gear:   '#7f8aa0', gearHub:'#2b3340',
    accent: '#4ea1ff', warm:'#ffb454', green:'#38e1b0', txt:'#cfd8e6', mute:'#6b7686',
  };

  class Stage {
    constructor(svg) {
      this.svg = svg;
      this._defsDone = false;
      this.bgGrid = true;
    }

    _ensureDefs() {
      if (this._defsDone) return;
      const defs = el('defs');
      defs.innerHTML = `
        <linearGradient id="gMetal" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#c3cdde"/>
          <stop offset="0.45" stop-color="#9aa7bd"/>
          <stop offset="0.55" stop-color="#7b889e"/>
          <stop offset="1" stop-color="#aab4c6"/>
        </linearGradient>
        <linearGradient id="gPlate" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#3a5f90"/>
          <stop offset="0.5" stop-color="#2b4a73"/>
          <stop offset="1" stop-color="#1f3858"/>
        </linearGradient>
        <linearGradient id="gCarbon" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#3a424e"/>
          <stop offset="0.5" stop-color="#20262e"/>
          <stop offset="1" stop-color="#2c333d"/>
        </linearGradient>
        <linearGradient id="gDamper" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#eef2f8"/>
          <stop offset="0.5" stop-color="#aeb9c9"/>
          <stop offset="1" stop-color="#cfd8e6"/>
        </linearGradient>
        <linearGradient id="gGear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#9aa6bb"/>
          <stop offset="1" stop-color="#5f6b80"/>
        </linearGradient>
        <radialGradient id="gPivot" cx="0.35" cy="0.35" r="0.75">
          <stop offset="0" stop-color="#eef2f8"/>
          <stop offset="0.4" stop-color="#9aa7bd"/>
          <stop offset="1" stop-color="#1d2533"/>
        </radialGradient>
        <radialGradient id="gWheel" cx="0.4" cy="0.35" r="0.8">
          <stop offset="0" stop-color="#2a3038"/>
          <stop offset="0.7" stop-color="#15191f"/>
          <stop offset="1" stop-color="#0a0d11"/>
        </radialGradient>
        <filter id="fSoft" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="2.2" stdDeviation="2.4" flood-color="#000" flood-opacity="0.45"/>
        </filter>
        <filter id="fGlow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="3" result="b"/>
          <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>`;
      this.svg.appendChild(defs);
      this._defsDone = true;
    }

    /* compute world->screen transform fitting `box` into the svg viewport */
    _fit(box, padFrac = 0.085) {
      const r = this.svg.getBoundingClientRect();
      const W = r.width || 800, H = r.height || 600;
      const bw = Math.max(1, box.maxX - box.minX);
      const bh = Math.max(1, box.maxY - box.minY);
      const pad = Math.max(W, H) * padFrac;
      const s = Math.min((W - pad * 2) / bw, (H - pad * 2) / bh);
      const cx = (box.minX + box.maxX) / 2;
      const cy = (box.minY + box.maxY) / 2;
      // y is flipped (world up -> screen down)
      const tx = W / 2 - s * cx;
      const ty = H / 2 + s * cy;
      this._s = s; this._tx = tx; this._ty = ty; this._W = W; this._H = H;
      return s;
    }
    X(p) { return this._tx + this._s * p.x; }
    Y(p) { return this._ty - this._s * p.y; }
    S(v) { return this._s * v; }

    /* ---- main render ---------------------------------------------------- */
    render(scene, box) {
      this._ensureDefs();
      // clear everything except defs
      [...this.svg.childNodes].forEach((n) => { if (n.tagName !== 'defs') this.svg.removeChild(n); });
      this._fit(box);
      // label size scales gently with zoom so text never dwarfs small diagrams
      this._fontPx = Math.max(9.5, Math.min(13.5, this._s * 5.5));
      const root = el('g');
      this.svg.appendChild(root);
      if (this.bgGrid) this._drawGrid(root);
      // draw order: traces/dims first (behind), then structure, then nodes/labels
      const order = { envelope: 0, trace: 0, dim: 1, ground: 2, wheel: 3, upright: 3, rack: 4, gear: 4,
        cam: 4, coilover: 5, spring: 5, damper: 5, plate: 6, link: 7, roller: 8,
        pivot: 9, arrow: 10, label: 11, note: 11 };
      const sorted = [...scene].map((p, i) => [p, i])
        .sort((a, b) => (order[a[0].type] ?? 6) - (order[b[0].type] ?? 6) || a[1] - b[1]);
      for (const [p] of sorted) {
        const fn = this['_' + p.type];
        if (fn) fn.call(this, root, p);
      }
    }

    _drawGrid(root) {
      const g = el('g', { opacity: 0.5 });
      const step = this.S(20); // 20 mm grid
      if (step < 6) return;
      const W = this._W, H = this._H;
      // align to world origin
      const ox = ((this._tx % step) + step) % step;
      const oy = ((this._ty % step) + step) % step;
      let d = '';
      for (let x = ox; x < W; x += step) d += `M${x} 0V${H}`;
      for (let y = oy; y < H; y += step) d += `M0 ${y}H${W}`;
      g.appendChild(el('path', { d, stroke: 'rgba(120,150,200,0.06)', 'stroke-width': 1, fill: 'none' }));
      // strong axes through origin
      const o = { x: 0, y: 0 };
      g.appendChild(el('path', {
        d: `M0 ${this.Y(o)}H${W}M${this.X(o)} 0V${H}`,
        stroke: 'rgba(120,150,200,0.10)', 'stroke-width': 1, fill: 'none',
      }));
      root.appendChild(g);
    }

    /* ---- primitives ----------------------------------------------------- */
    _ground(root, p) {
      // work entirely in SCREEN space so hatching is always a consistent angle/length
      const A = { x: this.X(p.a), y: this.Y(p.a) };
      const B = { x: this.X(p.b), y: this.Y(p.b) };
      const tx = B.x - A.x, ty = B.y - A.y;
      const tl = Math.hypot(tx, ty) || 1;
      const ux = tx / tl, uy = ty / tl;          // unit tangent (screen)
      const nx = uy, ny = -ux;                    // unit normal (points to the "support" side)
      const g = el('g');
      g.appendChild(el('line', { x1: A.x, y1: A.y, x2: B.x, y2: B.y,
        stroke: C.ground, 'stroke-width': 3.5, 'stroke-linecap': 'round' }));
      const hl = 9, n = Math.max(4, Math.round(tl / 12));
      let d = '';
      for (let i = 0; i <= n; i++) {
        const px = A.x + ux * (tl * i / n), py = A.y + uy * (tl * i / n);
        // 45° hatch: step back along tangent and out along normal, equal screen lengths
        d += `M${px} ${py} l${(nx - ux) * hl} ${(ny - uy) * hl}`;
      }
      g.appendChild(el('path', { d, stroke: C.ground, 'stroke-width': 1.4, opacity: 0.85 }));
      root.appendChild(g);
    }

    _link(root, p) {
      const pts = p.pts;
      const kind = p.kind || 'arm';
      let stroke = 'url(#gMetal)', w = p.w || 7, cap = 'round';
      if (kind === 'rod' || kind === 'push' || kind === 'pull') { stroke = 'url(#gCarbon)'; w = p.w || 6; }
      if (kind === 'coupler') { stroke = 'url(#gMetal)'; w = p.w || 6; }
      const d = pts.map((pt, i) => (i ? 'L' : 'M') + this.X(pt) + ' ' + this.Y(pt)).join(' ');
      const g = el('g', { filter: 'url(#fSoft)' });
      g.appendChild(el('path', { d, stroke, 'stroke-width': this.S(w), fill: 'none',
        'stroke-linecap': cap, 'stroke-linejoin': 'round' }));
      // accent centerline for rods to read as carbon/loaded
      if (kind === 'push' || kind === 'pull') {
        g.appendChild(el('path', { d, stroke: kind === 'pull' ? C.green : C.rodGlow,
          'stroke-width': Math.max(1, this.S(w) * 0.18), fill: 'none', opacity: 0.7,
          'stroke-linecap': 'round' }));
      }
      root.appendChild(g);
    }

    _plate(root, p) {
      const d = p.pts.map((pt, i) => (i ? 'L' : 'M') + this.X(pt) + ' ' + this.Y(pt)).join(' ') + ' Z';
      const g = el('g', { filter: 'url(#fSoft)' });
      g.appendChild(el('path', { d, fill: 'url(#gPlate)', stroke: C.plateEdge,
        'stroke-width': 1.5, 'stroke-linejoin': 'round', opacity: 0.96 }));
      root.appendChild(g);
    }

    /* smooth sinusoidal coil (side view of a helix) between two SCREEN points */
    _coilPath(A, B, coils, rad) {
      const tx = B.x - A.x, ty = B.y - A.y;
      const len = Math.hypot(tx, ty) || 1;
      const ux = tx / len, uy = ty / len, nx = -uy, ny = ux;
      const lead = len * 0.12, active = len - 2 * lead;
      const N = Math.max(24, coils * 16);
      let d = `M${A.x} ${A.y} L${A.x + ux * lead} ${A.y + uy * lead}`;
      for (let i = 0; i <= N; i++) {
        const t = i / N;
        const along = lead + active * t;
        const off = Math.sin(t * coils * Math.PI * 2) * rad;
        d += ` L${A.x + ux * along + nx * off} ${A.y + uy * along + ny * off}`;
      }
      d += ` L${A.x + ux * (len - lead) + 0} ${A.y + uy * (len - lead)} L${B.x} ${B.y}`;
      return d;
    }

    _coilover(root, p) {
      const a = p.a, b = p.b;                       // a = chassis mount, b = moving end
      const A = { x: this.X(a), y: this.Y(a) }, B = { x: this.X(b), y: this.Y(b) };
      const tx = B.x - A.x, ty = B.y - A.y, len = Math.hypot(tx, ty) || 1;
      const ux = tx / len, uy = ty / len, nx = -uy, ny = ux;
      const g = el('g', { filter: 'url(#fSoft)' });
      const bodyW = Math.max(7, this.S(13));
      const bodyLen = Math.min(len * 0.5, this.S((p.rest || 0) * 0.42) || len * 0.42);
      const bodyEnd = { x: A.x + ux * bodyLen, y: A.y + uy * bodyLen };
      const rad = bodyW * 0.62;
      // 1) coil spring over the full length (behind)
      g.appendChild(el('path', { d: this._coilPath(A, B, 7, rad),
        stroke: C.spring, 'stroke-width': Math.max(2, this.S(3)), fill: 'none',
        'stroke-linecap': 'round', 'stroke-linejoin': 'round', opacity: 0.95 }));
      // 2) shaft
      g.appendChild(el('line', { x1: bodyEnd.x, y1: bodyEnd.y, x2: B.x, y2: B.y,
        stroke: C.damperRod, 'stroke-width': Math.max(2, this.S(3.4)), 'stroke-linecap': 'round' }));
      // 3) damper body as a cylinder (rounded rect) over the coil near the mount
      const ang = Math.atan2(ty, tx) * 180 / Math.PI;
      const rectW = Math.hypot(bodyEnd.x - A.x, bodyEnd.y - A.y);
      const body = el('g', { transform: `translate(${A.x} ${A.y}) rotate(${ang})` });
      body.appendChild(el('rect', { x: 0, y: -bodyW / 2, width: rectW, height: bodyW, rx: bodyW * 0.32,
        fill: 'url(#gDamper)', stroke: '#7b889e', 'stroke-width': 1 }));
      body.appendChild(el('rect', { x: rectW * 0.12, y: -bodyW / 2 + 1.5, width: rectW * 0.76, height: bodyW * 0.16, rx: 2,
        fill: 'rgba(255,255,255,0.55)' }));
      g.appendChild(body);
      // 4) clevis eyelets at both ends
      [A, B].forEach((e) => {
        g.appendChild(el('circle', { cx: e.x, cy: e.y, r: Math.max(3, this.S(4)), fill: '#1d2533', stroke: C.damperBody, 'stroke-width': 1.8 }));
        g.appendChild(el('circle', { cx: e.x, cy: e.y, r: Math.max(1.2, this.S(1.6)), fill: '#0b0e14' }));
      });
      root.appendChild(g);
    }

    _spring(root, p) {
      const A = { x: this.X(p.a), y: this.Y(p.a) }, B = { x: this.X(p.b), y: this.Y(p.b) };
      root.appendChild(el('path', { d: this._coilPath(A, B, p.coils || 8, Math.max(5, this.S(8))),
        stroke: C.spring, 'stroke-width': Math.max(2, this.S(2.8)), fill: 'none',
        'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
    }

    _damper(root, p) {
      const a = p.a, b = p.b;
      const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len;
      const bodyEnd = { x: a.x + ux * len * 0.5, y: a.y + uy * len * 0.5 };
      const g = el('g', { filter: 'url(#fSoft)' });
      g.appendChild(el('line', { x1: this.X(bodyEnd), y1: this.Y(bodyEnd), x2: this.X(b), y2: this.Y(b),
        stroke: C.damperRod, 'stroke-width': this.S(3.2), 'stroke-linecap': 'round' }));
      g.appendChild(el('line', { x1: this.X(a), y1: this.Y(a), x2: this.X(bodyEnd), y2: this.Y(bodyEnd),
        stroke: 'url(#gDamper)', 'stroke-width': this.S(11), 'stroke-linecap': 'round' }));
      root.appendChild(g);
    }

    _wheel(root, p) {
      const c = { cx: this.X(p.at), cy: this.Y(p.at) };
      const R = this.S(p.r);
      const g = el('g', { filter: 'url(#fSoft)' });
      g.appendChild(el('circle', { ...c, r: R, fill: 'url(#gWheel)', stroke: '#000', 'stroke-width': 2 }));
      g.appendChild(el('circle', { ...c, r: R * 0.6, fill: 'none', stroke: C.rim, 'stroke-width': this.S(3) }));
      g.appendChild(el('circle', { ...c, r: R * 0.18, fill: C.rim }));
      for (let i = 0; i < 5; i++) {
        const a = (i / 5) * Math.PI * 2;
        g.appendChild(el('line', { x1: c.cx, y1: c.cy,
          x2: c.cx + Math.cos(a) * R * 0.58, y2: c.cy + Math.sin(a) * R * 0.58,
          stroke: C.rim, 'stroke-width': this.S(2.4), 'stroke-linecap': 'round' }));
      }
      root.appendChild(g);
    }

    _upright(root, p) {
      const d = p.pts.map((pt, i) => (i ? 'L' : 'M') + this.X(pt) + ' ' + this.Y(pt)).join(' ') + ' Z';
      root.appendChild(el('path', { d, fill: '#3a4250', stroke: '#5c6b82', 'stroke-width': 1.5,
        'stroke-linejoin': 'round', filter: 'url(#fSoft)' }));
    }

    _gear(root, p) {
      const c = p.center, R = this.S(p.r), teeth = p.teeth || 16;
      const g = el('g', { filter: 'url(#fSoft)' });
      // addendum/dedendum sized off a common module so meshing gears interlock;
      // `phase` lets the caller interleave one gear's teeth into the other's gaps
      const add = this.S(p.r) * (Math.PI / teeth) * 0.38; // ~ module-based tooth height (tip/root clearance kept)
      const rt = R + add, rr = R - add;
      const ph = (p.phase || 0);
      // faint pitch circle
      g.appendChild(el('circle', { cx: this.X(c), cy: this.Y(c), r: R, fill: 'none',
        stroke: 'rgba(120,150,200,0.25)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }));
      let d = '';
      const steps = teeth * 2;
      for (let i = 0; i <= steps; i++) {
        const ang = (i / steps) * Math.PI * 2 + (p.angle || 0) + ph;
        const rad = i % 2 === 0 ? rt : rr;
        const x = this.X(c) + Math.cos(ang) * rad;
        const y = this.Y(c) - Math.sin(ang) * rad;
        d += (i ? 'L' : 'M') + x + ' ' + y;
      }
      d += ' Z';
      g.appendChild(el('path', { d, fill: 'url(#gGear)', stroke: '#46505f', 'stroke-width': 1 }));
      g.appendChild(el('circle', { cx: this.X(c), cy: this.Y(c), r: R * 0.55, fill: C.gearHub, stroke: '#46505f' }));
      g.appendChild(el('circle', { cx: this.X(c), cy: this.Y(c), r: R * 0.16, fill: '#0b0e14' }));
      // pitch mark to read rotation
      const ma = p.angle || 0;
      g.appendChild(el('line', { x1: this.X(c), y1: this.Y(c),
        x2: this.X(c) + Math.cos(ma) * R * 0.5, y2: this.Y(c) - Math.sin(ma) * R * 0.5,
        stroke: C.warm, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      root.appendChild(g);
    }

    _rack(root, p) {
      const a = p.a, b = p.b, teeth = p.teeth || 12, side = p.side || 1;
      const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len;
      const px = -uy * side, py = ux * side;
      const g = el('g', { filter: 'url(#fSoft)' });
      const w = this.S(7);
      g.appendChild(el('line', { x1: this.X(a), y1: this.Y(a), x2: this.X(b), y2: this.Y(b),
        stroke: 'url(#gMetal)', 'stroke-width': w, 'stroke-linecap': 'round' }));
      const th = this.S(5), tw = len / teeth;
      let d = '';
      for (let i = 0; i < teeth; i++) {
        const t0 = (i + 0.25) * tw, t1 = (i + 0.75) * tw;
        const e0 = { x: a.x + ux * t0, y: a.y + uy * t0 };
        const e1 = { x: a.x + ux * t1, y: a.y + uy * t1 };
        d += `M${this.X(e0) + px * th * 0.0} ${this.Y(e0)} L${this.X(e0) + px * th} ${this.Y(e0) - py * th} L${this.X(e1) + px * th} ${this.Y(e1) - py * th} L${this.X(e1)} ${this.Y(e1)}`;
      }
      g.appendChild(el('path', { d, stroke: '#7b889e', 'stroke-width': 1.5, fill: 'none' }));
      root.appendChild(g);
    }

    _cam(root, p) {
      const c = p.center;
      let d = '';
      p.radii.forEach((rr, i) => {
        const ang = (i / p.radii.length) * Math.PI * 2 + (p.angle || 0);
        const x = this.X(c) + Math.cos(ang) * this.S(rr);
        const y = this.Y(c) - Math.sin(ang) * this.S(rr);
        d += (i ? 'L' : 'M') + x + ' ' + y;
      });
      d += ' Z';
      const g = el('g', { filter: 'url(#fSoft)' });
      g.appendChild(el('path', { d, fill: 'url(#gMetal)', stroke: '#5c6b82', 'stroke-width': 1.5 }));
      g.appendChild(el('circle', { cx: this.X(c), cy: this.Y(c), r: this.S(5), fill: C.gearHub, stroke: '#46505f' }));
      const ma = p.angle || 0;
      g.appendChild(el('line', { x1: this.X(c), y1: this.Y(c),
        x2: this.X(c) + Math.cos(ma) * this.S(p.radii[0] || 20) * 0.6,
        y2: this.Y(c) - Math.sin(ma) * this.S(p.radii[0] || 20) * 0.6,
        stroke: C.warm, 'stroke-width': 2 }));
      root.appendChild(g);
    }

    _roller(root, p) {
      root.appendChild(el('circle', { cx: this.X(p.at), cy: this.Y(p.at), r: this.S(p.r),
        fill: 'url(#gMetal)', stroke: '#46505f', 'stroke-width': 1.5, filter: 'url(#fSoft)' }));
      root.appendChild(el('circle', { cx: this.X(p.at), cy: this.Y(p.at), r: this.S(p.r) * 0.3,
        fill: C.gearHub }));
    }

    _pivot(root, p) {
      const r = this.S(p.r || 4.5);
      const g = el('g');
      if (p.grounded) {
        g.appendChild(el('circle', { cx: this.X(p.at), cy: this.Y(p.at), r: r * 1.5,
          fill: 'none', stroke: C.ground, 'stroke-width': 2, opacity: 0.6 }));
      }
      g.appendChild(el('circle', { cx: this.X(p.at), cy: this.Y(p.at), r,
        fill: 'url(#gPivot)', stroke: p.hot ? C.pivotHot : C.pivotRing, 'stroke-width': 1.8,
        filter: p.hot ? 'url(#fGlow)' : '' }));
      g.appendChild(el('circle', { cx: this.X(p.at), cy: this.Y(p.at), r: r * 0.3, fill: '#0b0e14' }));
      root.appendChild(g);
    }

    _arrow(root, p) {
      const a = p.from, b = p.to;
      const col = p.color || C.warm;
      const ang = Math.atan2(this.Y(b) - this.Y(a), this.X(b) - this.X(a));
      const hl = 10;
      const g = el('g');
      g.appendChild(el('line', { x1: this.X(a), y1: this.Y(a), x2: this.X(b), y2: this.Y(b),
        stroke: col, 'stroke-width': p.w || 2.4, 'stroke-linecap': 'round' }));
      g.appendChild(el('path', {
        d: `M${this.X(b)} ${this.Y(b)} L${this.X(b) - hl * Math.cos(ang - 0.4)} ${this.Y(b) - hl * Math.sin(ang - 0.4)} L${this.X(b) - hl * Math.cos(ang + 0.4)} ${this.Y(b) - hl * Math.sin(ang + 0.4)} Z`,
        fill: col }));
      if (p.label) {
        const mx = (this.X(a) + this.X(b)) / 2, my = (this.Y(a) + this.Y(b)) / 2;
        g.appendChild(this._text(mx, my - 7, p.label, { fill: col, size: 11, weight: 600, anchor: 'middle' }));
      }
      root.appendChild(g);
    }

    _envelope(root, p) {
      // a labelled footprint box (world coords). Used to contrast the long
      // single-rocker envelope against the compact mechanism's envelope.
      const x = this.X({ x: p.x, y: p.y + p.h });        // top-left in screen
      const y = this.Y({ x: p.x, y: p.y + p.h });
      const w = this.S(p.w), h = this.S(p.h);
      const g = el('g');
      g.appendChild(el('rect', { x, y, width: w, height: h, rx: 4,
        fill: p.fill || 'none', stroke: p.color || C.mute,
        'stroke-width': 1.4, 'stroke-dasharray': p.solid ? '' : '5 4', opacity: 0.9 }));
      if (p.label) g.appendChild(this._text(x + w / 2, y - 5, p.label,
        { fill: p.color || C.mute, size: this._fontPx * 0.86, anchor: 'middle', weight: 600 }));
      if (p.hLabel) g.appendChild(this._text(x + w / 2, y + h / 2, p.hLabel,
        { fill: p.color || C.mute, size: this._fontPx * 0.86, anchor: 'middle', mono: true }));
      root.appendChild(g);
    }

    _trace(root, p) {
      const d = p.pts.map((pt, i) => (i ? 'L' : 'M') + this.X(pt) + ' ' + this.Y(pt)).join(' ');
      root.appendChild(el('path', { d, stroke: p.color || 'rgba(78,161,255,0.35)',
        'stroke-width': 1.5, fill: 'none', 'stroke-dasharray': '4 4' }));
    }

    _dim(root, p) {
      const a = p.a, b = p.b, off = p.off || 0;
      const ux = b.x - a.x, uy = b.y - a.y;
      const l = Math.hypot(ux, uy) || 1;
      const nx = -uy / l, ny = ux / l;
      const a2 = { x: a.x + nx * off, y: a.y + ny * off };
      const b2 = { x: b.x + nx * off, y: b.y + ny * off };
      const g = el('g', { opacity: 0.85 });
      g.appendChild(el('line', { x1: this.X(a2), y1: this.Y(a2), x2: this.X(b2), y2: this.Y(b2),
        stroke: C.mute, 'stroke-width': 1 }));
      [[a, a2], [b, b2]].forEach(([s, e]) => g.appendChild(el('line', {
        x1: this.X(s), y1: this.Y(s), x2: this.X(e), y2: this.Y(e), stroke: C.mute, 'stroke-width': 0.8, 'stroke-dasharray': '2 2' })));
      const mx = (this.X(a2) + this.X(b2)) / 2, my = (this.Y(a2) + this.Y(b2)) / 2;
      g.appendChild(this._text(mx, my - 4, p.text, { fill: C.txt, size: this._fontPx * 0.92, anchor: 'middle', mono: true }));
      root.appendChild(g);
    }

    _label(root, p) {
      const g = el('g');
      g.appendChild(this._text(this.X(p.at) + (p.dx || 0), this.Y(p.at) + (p.dy || -10), p.text,
        { fill: p.color || C.txt, size: this._fontPx, weight: 600, anchor: p.anchor || 'middle' }));
      if (p.sub) g.appendChild(this._text(this.X(p.at) + (p.dx || 0), this.Y(p.at) + (p.dy || -10) + 12, p.sub,
        { fill: C.mute, size: this._fontPx * 0.85, anchor: p.anchor || 'middle' }));
      root.appendChild(g);
    }

    _note(root, p) {
      root.appendChild(this._text(this.X(p.at), this.Y(p.at), p.text,
        { fill: p.color || C.mute, size: this._fontPx * 0.9, anchor: p.anchor || 'start', mono: true }));
    }

    _text(x, y, str, o = {}) {
      const t = el('text', { x, y, fill: o.fill || C.txt, 'font-size': o.size || this._fontPx || 12,
        'font-weight': o.weight || 400, 'text-anchor': o.anchor || 'start',
        'font-family': o.mono ? 'var(--mono)' : 'var(--font)',
        'paint-order': 'stroke', stroke: 'rgba(8,11,16,0.82)', 'stroke-width': 2.5, 'stroke-linejoin': 'round' });
      t.textContent = str;
      return t;
    }
  }

  return { Stage, C };
})();
