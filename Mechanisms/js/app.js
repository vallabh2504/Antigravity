/* =============================================================================
 * app.js — UI wiring, animation loop, live motion-ratio plot
 * ========================================================================== */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const SVGNS = 'http://www.w3.org/2000/svg';

  const state = {
    mech: Mechanisms[0],
    u: 0.5,
    playing: true,
    speed: 1,
    dir: 1,
    labels: true,
    last: performance.now(),
  };

  const stage = new Renderer.Stage($('#scene'));

  /* ---------------------------------------------------- sidebar build ---- */
  function buildSidebar() {
    const host = $('#mech-list');
    host.innerHTML = '';
    const cats = {};
    Mechanisms.forEach((m) => { (cats[m.category] ||= []).push(m); });
    Object.entries(cats).forEach(([cat, items]) => {
      const g = document.createElement('div');
      g.className = 'cat-group';
      g.innerHTML = `<div class="cat-label">${cat}</div>`;
      items.forEach((m) => {
        const it = document.createElement('div');
        it.className = 'mech-item' + (m === state.mech ? ' active' : '');
        it.dataset.id = m.id;
        it.innerHTML = `
          <div class="ico">${iconFor(m.id)}</div>
          <div class="meta">
            <div class="name">${m.name}</div>
            <div class="sub">${m.short}</div>
          </div>
          <span class="badge ${m.badge}">${m.badge === 'base' ? 'baseline' : m.badge === 'compact' ? 'compact' : 'advanced'}</span>`;
        it.addEventListener('click', () => select(m.id));
        g.appendChild(it);
      });
      host.appendChild(g);
    });
  }

  /* tiny inline glyphs per mechanism (schematic) */
  function iconFor(id) {
    const S = (inner) => `<svg viewBox="0 0 24 24" fill="none" stroke="#aeb9c9" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
    const m = {
      direct: '<path d="M5 20v-4M5 12V4M4 16h2M4 12h2M5 16l1.5-1M5 14l1.5-1M5 12l1.5-1"/><circle cx="5" cy="20" r="1.2"/>',
      pushrod: '<path d="M4 20l8-12M12 8l6 3M18 11v6"/><circle cx="12" cy="8" r="1.4"/><circle cx="18" cy="11" r="1.2"/>',
      pullrod: '<path d="M4 6l8 10M12 16l6-2M18 14v-6"/><circle cx="12" cy="16" r="1.4"/>',
      lcrank: '<path d="M8 20V10h8"/><circle cx="8" cy="10" r="1.6"/><path d="M8 20v-2M16 10h2"/>',
      compound: '<path d="M4 16l5-3 4 4 5-3"/><circle cx="9" cy="13" r="1.3"/><circle cx="13" cy="17" r="1.3"/>',
      fourbar: '<path d="M5 18l4-8 8 2-2 8z"/><circle cx="5" cy="18" r="1.2"/><circle cx="15" cy="20" r="1.2"/>',
      watt: '<path d="M5 7v10M19 7v10M5 12h6M13 12h6"/><circle cx="11" cy="12" r="1.2"/><circle cx="13" cy="12" r="1.2"/>',
      scott: '<path d="M4 18h14M6 18l8-12M10 12l4 6"/><circle cx="6" cy="18" r="1.3"/>',
      toggle: '<path d="M5 18l7-4 7 4"/><circle cx="12" cy="14" r="1.6"/><circle cx="5" cy="18" r="1.2"/><circle cx="19" cy="18" r="1.2"/>',
      gear: '<circle cx="9" cy="12" r="4"/><circle cx="17" cy="12" r="2.6"/><path d="M9 6v1M9 17v1M3 12h1M14 12h1"/>',
      rack: '<path d="M4 9h14M5 9v2M8 9v2M11 9v2M14 9v2"/><circle cx="18" cy="14" r="3"/>',
      cam: '<path d="M12 12m-6 0a6 5 0 1 0 12 0a6 5 0 1 0 -12 0"/><path d="M12 7V3"/><circle cx="12" cy="12" r="1.2"/>',
      slider: '<circle cx="7" cy="14" r="3"/><path d="M9 12l7 4M16 16h3"/><rect x="15" y="14" width="5" height="4" rx="1"/>',
    };
    return S(m[id] || m.lcrank);
  }

  /* ---------------------------------------------------- selection -------- */
  function select(id) {
    const m = Mechanisms.find((x) => x.id === id);
    if (!m) return;
    state.mech = m;
    $$('.mech-item').forEach((it) => it.classList.toggle('active', it.dataset.id === id));
    renderRail(m);
    renderHeader(m);
    draw();
  }

  function renderHeader(m) {
    $('#stage-title').textContent = m.name;
    $('#stage-tag').textContent = describe(m);
    const chips = $('#stage-chips');
    chips.innerHTML = `
      <span class="chip"><span class="k">Class</span><b>${m.category.replace(' architectures', '')}</b></span>
      <span class="chip"><span class="k">Motion ratio</span><b>${m.mrText}</b></span>
      <span class="chip"><span class="k">Compactness</span><b>${'●'.repeat(m.stats.compact)}${'○'.repeat(5 - m.stats.compact)}</b></span>
      <span class="chip"><span class="k">Rising-rate</span><b>${'●'.repeat(m.stats.rising)}${'○'.repeat(5 - m.stats.rising)}</b></span>`;
  }
  function describe(m) {
    return m.info.how.split('. ')[0] + '.';
  }

  function renderRail(m) {
    const r = $('#rail');
    r.innerHTML = `
      <div class="fade-swap">
        <div class="tabs" id="tabs">
          <button data-t="how" class="active">How it works</button>
          <button data-t="shorten">Shortens rocker</button>
        </div>
        <div class="card" id="desc-card"><p>${m.info.how}</p></div>

        <h3>${svgIcon('ruler')} Key metrics</h3>
        <div class="stat-grid">
          <div class="stat"><div class="k">Travel ratio (live)</div><div class="val" id="mr-live">–</div></div>
          <div class="stat"><div class="k">Input travel</div><div class="val" id="tr-live">–</div></div>
          <div class="stat full"><div class="k">Ratio measured as</div>
            <div class="val" style="font-size:12.5px;color:var(--txt-1)">${m.ratioNote || 'input : damper'}</div></div>
          <div class="stat"><div class="k">Joints</div><div class="val">${m.joints ?? '–'}</div></div>
          <div class="stat"><div class="k">Backlash</div><div class="val" style="font-size:14px">${m.backlash || '–'}</div></div>
          <div class="stat full"><div class="k">Compact · Complexity · Force · Rising-rate</div>
            <div class="val" style="font-size:14px">${rating(m.stats.compact)} · ${rating(m.stats.complex)} · ${rating(m.stats.force)} · ${rating(m.stats.rising)}</div></div>
        </div>
        ${m.footprint && m.footprint.reduction >= 10 ? `
        <h3>${svgIcon('ruler')} Rocker footprint vs single lever</h3>
        <div class="card">
          ${footBar('Equivalent single rocker', m.footprint.lever, m.footprint.lever, '#ff6b6b')}
          ${footBar('This mechanism', m.footprint.self, m.footprint.lever, '#38e1b0')}
          <p style="margin-top:10px;font-size:12px;color:var(--txt-2)">Envelope to deliver the same ratio &amp; travel — about a <b style="color:var(--accent-2)">${m.footprint.reduction}% reduction</b>. Primary benefit: <b style="color:var(--txt-1)">${m.benefit || 'compact packaging'}</b>. Indicative engineering estimates grounded in RESEARCH.md (the schematic is illustrative, not packaging-optimised).</p>
        </div>` : ''}

        <h3>${svgIcon('wave')} Motion-ratio map</h3>
        <div class="mr-card">
          <div class="mr-head"><span>droop → bump</span><span class="now"><span id="mr-now">–</span><small> :1</small></span></div>
          <svg id="mr-plot" viewBox="0 0 320 88" preserveAspectRatio="none"></svg>
          <div class="mr-foot">Motion ratio = input (wheel) travel ÷ damper travel, across the full stroke. Flat = linear rate; a downward slope into bump = rising wheel rate (k<sub>wheel</sub> = k<sub>spring</sub> ÷ MR²).</div>
        </div>

        <h3>${svgIcon('plus')} Advantages</h3>
        <ul class="list pros">${m.info.pros.map((x) => `<li>${x}</li>`).join('')}</ul>
        <h3>${svgIcon('minus')} Trade-offs</h3>
        <ul class="list cons">${m.info.cons.map((x) => `<li>${x}</li>`).join('')}</ul>
        <h3>${svgIcon('pin')} Where it's used</h3>
        <ul class="list use">${m.info.uses.map((x) => `<li>${x}</li>`).join('')}</ul>

        <h3>${svgIcon('layers')} Legend</h3>
        <div class="legend">
          <div class="li"><span class="sw" style="background:#9aa7bd"></span>control arm / link</div>
          <div class="li"><span class="sw" style="background:#2f3742"></span>pushrod / pullrod</div>
          <div class="li"><span class="sw" style="background:#2b4a73"></span>rocker / coupler body</div>
          <div class="li"><span class="sw" style="background:#ffb454"></span>spring</div>
          <div class="li"><span class="sw" style="background:#cfd8e6"></span>damper</div>
          <div class="li"><span class="sw" style="background:#4ea1ff;border-radius:50%;width:8px;height:8px"></span>moving pivot</div>
        </div>
      </div>`;
    // tab behaviour
    $$('#tabs button').forEach((b) => b.addEventListener('click', () => {
      $$('#tabs button').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      $('#desc-card').innerHTML = `<p>${b.dataset.t === 'how' ? m.info.how : m.info.shorten}</p>`;
    }));
    drawMRPlot(m);
  }

  const rating = (n) => `<span style="color:${n >= 4 ? '#38e1b0' : n >= 3 ? '#4ea1ff' : '#ffb454'}">${'▰'.repeat(n)}${'▱'.repeat(5 - n)}</span>`;
  const footBar = (label, val, max, color) => `
    <div style="margin:7px 0">
      <div style="display:flex;justify-content:space-between;font-size:11.5px;color:var(--txt-1);margin-bottom:3px">
        <span>${label}</span><span style="font-family:var(--mono);color:${color}">${val} mm</span></div>
      <div style="height:9px;background:var(--bg-3);border-radius:5px;overflow:hidden">
        <div style="height:100%;width:${(val / max) * 100}%;background:${color};border-radius:5px"></div></div>
    </div>`;

  function svgIcon(name) {
    const map = {
      ruler: '<path d="M3 7h18v6H3zM7 7v3M11 7v3M15 7v3M19 7v3"/>',
      wave: '<path d="M3 12c3-6 5 6 8 0s5-6 8 0"/>',
      plus: '<path d="M12 5v14M5 12h14"/>', minus: '<path d="M5 12h14"/>',
      pin: '<path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2"/>',
      layers: '<path d="M12 3l9 5-9 5-9-5z M3 14l9 5 9-5"/>',
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${map[name] || ''}</svg>`;
  }

  /* ------------------------------------------------ motion-ratio plot ---- */
  let mrSamples = [];
  function drawMRPlot(m) {
    const svg = $('#mr-plot');
    if (!svg) return;
    svg.innerHTML = '';
    mrSamples = [];
    const N = 60;
    let mn = Infinity, mx = -Infinity;
    for (let i = 0; i <= N; i++) {
      const u = i / N;
      const mr = m.solve(u).read.mr || 0;
      mrSamples.push(mr);
      if (isFinite(mr)) { mn = Math.min(mn, mr); mx = Math.max(mx, mr); }
    }
    if (!isFinite(mn)) { mn = 0; mx = 1; }
    const pad = (mx - mn) * 0.25 || 0.3;
    mn -= pad; mx += pad;
    state._mr = { mn, mx, N };
    const W = 320, H = 88;
    const X = (i) => (i / N) * W;
    const Y = (val) => H - 6 - ((val - mn) / (mx - mn || 1)) * (H - 16);
    // gridlines
    const gl = document.createElementNS(SVGNS, 'path');
    gl.setAttribute('d', `M0 ${H / 2}H${W}`);
    gl.setAttribute('stroke', 'rgba(120,150,200,0.12)');
    gl.setAttribute('stroke-dasharray', '3 3');
    svg.appendChild(gl);
    // area + line
    let d = '', area = `M0 ${H}`;
    mrSamples.forEach((val, i) => { const x = X(i), y = Y(val); d += (i ? 'L' : 'M') + x + ' ' + y; area += `L${x} ${y}`; });
    area += `L${W} ${H}Z`;
    const ar = document.createElementNS(SVGNS, 'path');
    ar.setAttribute('d', area); ar.setAttribute('fill', 'rgba(78,161,255,0.12)');
    svg.appendChild(ar);
    const ln = document.createElementNS(SVGNS, 'path');
    ln.setAttribute('d', d); ln.setAttribute('fill', 'none'); ln.setAttribute('stroke', '#4ea1ff'); ln.setAttribute('stroke-width', '2');
    svg.appendChild(ln);
    // ride-height marker
    const rh = document.createElementNS(SVGNS, 'line');
    rh.setAttribute('x1', W / 2); rh.setAttribute('x2', W / 2); rh.setAttribute('y1', 0); rh.setAttribute('y2', H);
    rh.setAttribute('stroke', 'rgba(255,255,255,0.12)');
    svg.appendChild(rh);
    // live cursor
    const cur = document.createElementNS(SVGNS, 'circle');
    cur.setAttribute('r', '4'); cur.setAttribute('fill', '#ffb454'); cur.id = 'mr-cursor';
    cur.setAttribute('filter', 'drop-shadow(0 0 4px #ffb454)');
    svg.appendChild(cur);
    state._mrPlot = { X, Y, W, H };
  }
  function updateMRCursor() {
    const p = state._mrPlot; if (!p) return;
    const cur = $('#mr-cursor'); if (!cur) return;
    const i = state.u * state._mr.N;
    const idx = Math.round(i);
    const val = mrSamples[Math.max(0, Math.min(mrSamples.length - 1, idx))] || 0;
    cur.setAttribute('cx', p.X(i));
    cur.setAttribute('cy', p.Y(val));
    const now = $('#mr-now'); if (now) now.textContent = val.toFixed(2);
  }

  /* ------------------------------------------------------- draw frame ---- */
  function draw() {
    const m = state.mech;
    const r = m.solve(state.u);
    stage.bgGrid = state.labels;
    let scene = r.scene;
    if (!state.labels) scene = scene.filter((p) => !['label', 'note', 'dim'].includes(p.type));
    stage.render(scene, m.box);
    // HUD
    $('#hud-travel').innerHTML = `${r.read.travel >= 0 ? '+' : ''}${r.read.travel.toFixed(1)}<small> mm</small>`;
    $('#hud-mr').innerHTML = `${(r.read.mr || 0).toFixed(2)}<small> :1</small>`;
    $('#phase-tag-text').textContent = r.read.phase;
    const ml = $('#mr-live'); if (ml) ml.innerHTML = `${(r.read.mr || 0).toFixed(2)}<small> :1</small>`;
    const tl = $('#tr-live'); if (tl) tl.innerHTML = `${r.read.travel >= 0 ? '+' : ''}${r.read.travel.toFixed(1)}<small> mm</small>`;
    updateMRCursor();
    $('#travel-slider').value = String(Math.round(state.u * 1000));
  }

  /* ------------------------------------------------------ anim loop ------ */
  function loop(now) {
    const dt = Math.min(0.05, (now - state.last) / 1000);
    state.last = now;
    if (state.playing) {
      state.u += state.dir * dt * 0.32 * state.speed;
      if (state.u >= 1) { state.u = 1; state.dir = -1; }
      if (state.u <= 0) { state.u = 0; state.dir = 1; }
      draw();
    }
    requestAnimationFrame(loop);
  }

  /* ------------------------------------------------------- controls ------ */
  function bindControls() {
    $('#btn-play').addEventListener('click', () => {
      state.playing = !state.playing;
      $('#btn-play').innerHTML = state.playing ? pauseIcon() + 'Pause' : playIcon() + 'Play';
    });
    $('#travel-slider').addEventListener('input', (e) => {
      state.playing = false;
      $('#btn-play').innerHTML = playIcon() + 'Play';
      state.u = +e.target.value / 1000;
      draw();
    });
    $$('.speed-seg button').forEach((b) => b.addEventListener('click', () => {
      $$('.speed-seg button').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      state.speed = +b.dataset.s;
    }));
    $('#toggle-labels').addEventListener('change', (e) => { state.labels = e.target.checked; draw(); });
    $('#btn-reset').addEventListener('click', () => { state.u = 0.5; state.dir = 1; draw(); });
    $('#btn-compare').addEventListener('click', () => { buildCompare(); $('#compare-modal').hidden = false; });
    $('#btn-compare-close').addEventListener('click', () => { $('#compare-modal').hidden = true; });
    $('#compare-modal').addEventListener('click', (e) => { if (e.target.id === 'compare-modal') $('#compare-modal').hidden = true; });
    $('#btn-bump').addEventListener('click', () => { state.playing = false; $('#btn-play').innerHTML = playIcon() + 'Play'; state.u = 1; draw(); });
    $('#btn-droop').addEventListener('click', () => { state.playing = false; $('#btn-play').innerHTML = playIcon() + 'Play'; state.u = 0; draw(); });
    // sidebar/rail toggles (responsive)
    $('#menu-toggle')?.addEventListener('click', () => $('.sidebar').classList.toggle('open'));
    window.addEventListener('resize', () => draw());
    // keyboard
    window.addEventListener('keydown', (e) => {
      if (e.key === ' ') { e.preventDefault(); $('#btn-play').click(); }
      const idx = Mechanisms.indexOf(state.mech);
      if (e.key === 'ArrowDown') { e.preventDefault(); select(Mechanisms[(idx + 1) % Mechanisms.length].id); }
      if (e.key === 'ArrowUp') { e.preventDefault(); select(Mechanisms[(idx - 1 + Mechanisms.length) % Mechanisms.length].id); }
    });
  }

  /* ----------------------------------------------- comparison table ----- */
  let cmpSort = { key: 'order', dir: 1 };
  function rowData(m, i) {
    const red = (s) => `<span class="${/high/i.test(s) ? 'red' : /med/i.test(s) ? 'wrn' : 'grn'}">${s}</span>`;
    return {
      order: i, m,
      name: m.name, cls: m.badge,
      ratio: m.mrText,
      rise: m.stats.rising, compact: m.stats.compact, force: m.stats.force,
      joints: typeof m.joints === 'number' ? m.joints : 99,
      jointsTxt: String(m.joints ?? '–'),
      backlash: m.backlash || '–', backlashHtml: red(m.backlash || '–'),
      reduce: m.footprint ? m.footprint.reduction : -1,
      footprint: m.footprint, note: m.tableNote || '',
    };
  }
  function buildCompare() {
    const table = $('#compare-table');
    const cols = [
      { k: 'name', t: 'Mechanism' }, { k: 'cls', t: 'Class' }, { k: 'ratio', t: 'Ratio behaviour' },
      { k: 'reduce', t: 'Rocker reduction' }, { k: 'joints', t: 'Joints' }, { k: 'backlash', t: 'Backlash' },
      { k: 'force', t: 'Force' }, { k: 'rise', t: 'Rising-rate' }, { k: 'compact', t: 'Compact' }, { k: 'note', t: 'Key idea' },
    ];
    let rows = Mechanisms.map(rowData);
    rows.sort((a, b) => {
      const k = cmpSort.key; let va = a[k], vb = b[k];
      if (typeof va === 'string') return cmpSort.dir * va.localeCompare(vb);
      return cmpSort.dir * ((va ?? 0) - (vb ?? 0));
    });
    const badgeTag = (c) => `<span class="tag ${c}" style="background:${c === 'compact' ? 'rgba(56,225,176,.14)' : c === 'adv' ? 'rgba(255,180,84,.14)' : 'var(--bg-3)'};color:${c === 'compact' ? '#38e1b0' : c === 'adv' ? '#ffb454' : '#aeb9c9'}">${c === 'base' ? 'baseline' : c === 'compact' ? 'compact' : 'advanced'}</span>`;
    const dots = (n) => `<span style="color:${n >= 4 ? '#38e1b0' : n >= 3 ? '#4ea1ff' : '#ffb454'}">${'●'.repeat(n)}${'○'.repeat(5 - n)}</span>`;
    const fpCell = (fp, red) => {
      if (!fp) return '<span style="color:var(--txt-2)">— (baseline)</span>';
      if (red < 10) return '<span style="color:var(--txt-2)" title="benefit is ratio / straight-line / amplification, not footprint">≈ same envelope</span>';
      return `<div class="fp-cell"><div class="bars">
        <div style="width:100%;background:rgba(255,107,107,.5)"></div>
        <div style="width:${Math.max(8, (fp.self / fp.lever) * 100)}%;background:#38e1b0"></div>
      </div><b class="grn">−${red}%</b></div>`;
    };
    table.innerHTML = `<thead><tr>${cols.map((c) =>
      `<th data-k="${c.k}" class="${cmpSort.key === c.k ? 'sorted' : ''}">${c.t}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr data-id="${r.m.id}">
        <td class="name">${r.name}</td>
        <td>${badgeTag(r.cls)}</td>
        <td style="font-family:var(--mono);color:var(--txt-1)">${r.ratio}</td>
        <td>${fpCell(r.footprint, r.reduce)}</td>
        <td style="font-family:var(--mono)">${r.jointsTxt}</td>
        <td>${r.backlashHtml}</td>
        <td>${dots(r.force)}</td>
        <td>${dots(r.rise)}</td>
        <td>${dots(r.compact)}</td>
        <td style="color:var(--txt-1);white-space:normal;min-width:200px">${r.note}</td>
      </tr>`).join('')}</tbody>`;
    $$('#compare-table th').forEach((th) => th.addEventListener('click', () => {
      const k = th.dataset.k;
      cmpSort = { key: k, dir: cmpSort.key === k ? -cmpSort.dir : 1 };
      buildCompare();
    }));
    $$('#compare-table tbody tr').forEach((tr) => tr.addEventListener('click', () => {
      $('#compare-modal').hidden = true; select(tr.dataset.id);
    }));
  }

  const playIcon = () => '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>';
  const pauseIcon = () => '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

  /* ----------------------------------------------------------- init ------ */
  function init() {
    buildSidebar();
    bindControls();
    $('#btn-play').innerHTML = pauseIcon() + 'Pause';
    select(state.mech.id);
    requestAnimationFrame((t) => { state.last = t; loop(t); });
  }
  document.addEventListener('DOMContentLoaded', init);
})();
