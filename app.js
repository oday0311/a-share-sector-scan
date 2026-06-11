/* ============================================================
   APP  ·  渲染 + 交互
   ============================================================ */
(function () {
  'use strict';
  const D = window.TERMINAL_DATA;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';

  /* ---------- helpers ---------- */
  const fmtPct = (v) => (v == null || isNaN(v)) ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  const fmtPrice = (v) => (v == null || isNaN(v)) ? '—' : v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const cls = (v) => (v == null || isNaN(v)) ? 'flat' : (v > 0.05 ? 'up' : v < -0.05 ? 'down' : 'flat');
  const arrow = (v) => (v > 0.05 ? '▲' : v < -0.05 ? '▼' : '◆');
  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

  let RANGE = 't'; // 't' | 'd5' | 'd20'
  let SORT = { key: 'today', dir: -1 };
  let trendChart = null, ddChart = null;
  const hiddenSeries = new Set();

  /* ============================================================
     HEATMAP
     ============================================================ */
  function heatColor(v, maxAbs) {
    const t = clamp(Math.abs(v) / (maxAbs || 1), 0.12, 1);
    if (v > 0.05) { // 涨=红
      return `rgb(${Math.round(lerp(232,178,t))},${Math.round(lerp(150,33,t))},${Math.round(lerp(148,31,t))})`;
    } else if (v < -0.05) { // 跌=绿
      return `rgb(${Math.round(lerp(120,0,t))},${Math.round(lerp(190,110,t))},${Math.round(lerp(155,71,t))})`;
    }
    return 'rgb(150,162,184)';
  }
  function renderHeatmap() {
    const grid = $('#heatmap');
    grid.innerHTML = '';
    const key = RANGE;
    const maxAbs = Math.max(...D.heatmap.map(d => Math.abs(d[key])));
    D.heatmap.forEach(d => {
      const v = d[key];
      const c = el('div', 'heat-cell');
      c.style.background = heatColor(v, maxAbs);
      c.dataset.name = d.name;
      c.innerHTML = `
        <span class="heat-rank">#${d.rank}</span>
        <div class="heat-name">${d.name}</div>
        <div class="heat-chg" data-fkey="hm-${d.name}">${fmtPct(v)}</div>
        <div class="heat-vol">热度 ${d.heat}</div>`;
      c.addEventListener('mousemove', (e) => showTip(e, d));
      c.addEventListener('mouseleave', hideTip);
      c.addEventListener('click', () => openDrill(d.name));
      grid.appendChild(c);
    });
  }
  const tip = $('#hmTip');
  function showTip(e, d) {
    tip.innerHTML = `
      <div class="t-name"><span>${d.name}</span><span class="t-rank">热度#${d.rank}</span></div>
      <div class="t-row"><span class="k">今日</span><span class="${cls(d.t)}">${fmtPct(d.t)}</span></div>
      <div class="t-row"><span class="k">5日</span><span class="${cls(d.d5)}">${fmtPct(d.d5)}</span></div>
      <div class="t-row"><span class="k">20日</span><span class="${cls(d.d20)}">${fmtPct(d.d20)}</span></div>
      <div class="t-row"><span class="k">换手率</span><span>${d.turnover.toFixed(2)}%</span></div>
      <div class="t-row"><span class="k">热度指数</span><span style="color:var(--signal)">${d.heat}</span></div>
      <div class="t-hint">点击查看板块详情 →</div>`;
    tip.classList.add('show');
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = e.clientX + pad, y = e.clientY + pad;
    if (x + w > innerWidth) x = e.clientX - w - pad;
    if (y + h > innerHeight) y = e.clientY - h - pad;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hideTip() { tip.classList.remove('show'); }

  /* ============================================================
     SECTOR TABLE
     ============================================================ */
  function sparkSVG(data) {
    const w = 96, h = 30, n = data.length;
    const max = Math.max(...data), min = Math.min(...data), rng = (max - min) || 1;
    const pts = data.map((v, i) => [ (i / (n - 1)) * w, h - 2 - ((v - min) / rng) * (h - 4) ]);
    const up = data[n - 1] >= data[0];
    const col = up ? 'var(--up)' : 'var(--down)';
    const line = pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
    const area = `0,${h} ` + line + ` ${w},${h}`;
    const id = 'g' + Math.random().toString(36).slice(2, 7);
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${col}" stop-opacity="0.18"/>
        <stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
      <polygon points="${area}" fill="url(#${id})"/>
      <polyline points="${line}" fill="none" stroke="${col}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${pts[n-1][0].toFixed(1)}" cy="${pts[n-1][1].toFixed(1)}" r="1.8" fill="${col}"/>
    </svg>`;
  }
  const badgeHTML = (b) => {
    if (b === 'HOT') return `<span class="badge badge-hot">HOT</span>`;
    if (b === 'UP') return `<span class="badge badge-up">↑5D</span>`;
    if (b === 'STRONG') return `<span class="badge badge-strong">20D↑</span>`;
    if (b === 'AI') return `<span class="badge badge-strong">AI</span>`;
    return '';
  };
  function renderSectorTable() {
    const tb = $('#sectorTable');
    tb.innerHTML = '';
    const rows = [...D.sectors].sort((a, b) => {
      const k = SORT.key;
      if (k === 'name') return a.name.localeCompare(b.name) * SORT.dir;
      return (a[k] - b[k]) * SORT.dir;
    });
    rows.forEach(r => {
      const tr = el('tr');
      tr.dataset.name = r.name;
      tr.innerHTML = `
        <td><span class="sector-name">${r.name}</span>${r.badges.map(badgeHTML).join('')}</td>
        <td class="${cls(r.today)}" data-fkey="st-${r.name}">${fmtPct(r.today)}</td>
        <td class="${cls(r.d5)}">${fmtPct(r.d5)}</td>
        <td class="${cls(r.d20)}">${fmtPct(r.d20)}</td>
        <td class="cell-muted">${r.turnover.toFixed(2)}%</td>
        <td class="cell-amber">${r.heat}</td>
        <td>${sparkSVG(r.kline)}</td>`;
      tr.addEventListener('click', () => openDrill(r.name));
      tb.appendChild(tr);
    });
    // header sort indicators
    $$('#sectorHead th[data-key]').forEach(th => {
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (th.dataset.key === SORT.key) th.classList.add(SORT.dir === 1 ? 'sorted-asc' : 'sorted-desc');
    });
  }

  /* ============================================================
     CAPITAL FLOW
     ============================================================ */
  function renderFlows() {
    const fp = $('#flowPanel');
    fp.innerHTML = '';
    const maxAbs = Math.max(1, ...D.flows.map(f => Math.abs(f.val || 0)));
    const money = (v) => {
      const n = Number(v || 0);
      const abs = Math.abs(n / 10000).toFixed(1);
      return (n >= 0 ? '+' : '-') + abs + '亿';
    };
    D.flows.forEach(f => {
      const pos = f.val >= 0;
      const pct = Math.round(Math.abs(f.val) / maxAbs * 50);
      const val5 = f.val5 == null ? f.val : f.val5;
      const val20 = f.val20 == null ? val5 : f.val20;
      const row = el('div', 'flow-row');
      row.innerHTML = `
        <div class="flow-name">${f.name}</div>
        <div class="flow-track">
          <div class="flow-axis"></div>
          <div class="flow-bar ${pos ? 'pos' : 'neg'}" style="width:${pct}%"></div>
        </div>
        <div class="flow-metrics">
          <span class="flow-val ${cls(f.val)}" title="1日">${money(f.val)}</span>
          <span class="flow-val ${cls(val5)}" title="5日">${money(val5)}</span>
          <span class="flow-val ${cls(val20)}" title="20日">${money(val20)}</span>
        </div>`;
      fp.appendChild(row);
    });
  }

  /* ============================================================
     SIGNALS
     ============================================================ */
  function renderSignals() {
    const sp = $('#signals'); sp.innerHTML = '';
    D.signals.forEach(s => {
      const row = el('div', 'signal-row');
      const colorVar = s.cls === 'up' ? 'var(--up)' : s.cls === 'down' ? 'var(--down)' : 'var(--amber)';
      row.innerHTML = `
        <div class="signal-dot ${s.dot}"></div>
        <div class="signal-main">
          <div class="signal-top">
            <span class="signal-tag">${s.tag || 'SIGNAL'}</span>
            <span class="signal-val" style="color:${colorVar}">${s.val}</span>
          </div>
          <div class="signal-text">${s.text}</div>
        </div>`;
      sp.appendChild(row);
    });
  }

  /* ============================================================
     TOP PICKS
     ============================================================ */
  function renderPicks() {
    const g = $('#picks'); g.innerHTML = '';
    D.picks.forEach(p => {
      const card = el('div', 'rating-card ' + p.cls);
      card.dataset.sector = p.sector;
      card.innerHTML = `
        <div class="rating-head">
          <span class="rating-label">${p.label}</span>
          <span class="rating-score num">${p.score}</span>
        </div>
        <div class="rating-sector">${p.sector}</div>
        <div class="rating-reason">${p.reason}</div>
        <div class="rating-stocks">${p.stocks.map(s => `<span class="stock-tag">${s.t}${s.b ? ' <b>' + s.b + '</b>' : ''}</span>`).join('')}</div>`;
      card.addEventListener('click', () => openDrill(p.sector));
      g.appendChild(card);
    });
  }

  /* ============================================================
     CONCEPTS
     ============================================================ */
  function renderConcepts() {
    const tb = $('#conceptTable'); tb.innerHTML = '';
    D.concepts.forEach(c => {
      const tr = el('tr');
      const leaderCls = c.leader.includes('+') ? 'cell-amber' : 'cell-muted';
      tr.innerHTML = `
        <td><span class="sector-name">${c.name}</span>${c.badges.map(badgeHTML).join('')}</td>
        <td class="${cls(c.today)}">${fmtPct(c.today)}</td>
        <td class="cell-muted">${c.turnover.toFixed(2)}%</td>
        <td class="${cls(c.d5)}">${fmtPct(c.d5)}</td>
        <td class="${cls(c.d20)}">${fmtPct(c.d20)}</td>
        <td class="${leaderCls}" style="text-align:left;font-family:var(--cjk)">${c.leader}</td>`;
      tb.appendChild(tr);
    });
  }

  /* ============================================================
     TECH PANEL
     ============================================================ */
  function renderTech() {
    const p = $('#techPanel'); p.innerHTML = '';
    D.tech.forEach(t => {
      const rsiColor = t.rsi6 > 70 ? 'var(--up)' : t.rsi6 < 30 ? 'var(--down)' : 'var(--amber)';
      const macdColor = t.macd > 0 ? 'var(--up)' : 'var(--down)';
      const difColor = t.dif > 0 ? 'var(--up)' : 'var(--down)';
      const sigColor = t.signal === 'BEAR' ? 'var(--down)' : t.signal === 'BULL' ? 'var(--up)' : 'var(--amber)';
      const sigBg = t.signal === 'BEAR' ? 'var(--down-soft)' : t.signal === 'BULL' ? 'var(--up-soft)' : 'rgba(179,118,11,0.1)';
      const b = el('div', 'tech-block');
      b.innerHTML = `
        <div class="tech-head">
          <span class="tech-name">${t.name}</span>
          <span class="tech-sig" style="color:${sigColor};background:${sigBg}">${t.signal}</span>
        </div>
        <div class="rsi-row"><span>RSI(6)</span><span style="color:${rsiColor};font-weight:700">${t.rsi6.toFixed(1)}</span></div>
        <div class="rsi-track">
          <div class="rsi-fill" style="width:${clamp(t.rsi6,0,100)}%;background:${rsiColor}"></div>
          <div class="rsi-mark" style="left:30%"></div><div class="rsi-mark" style="left:70%"></div>
        </div>
        <div class="macd-row">
          <span>DIF <b style="color:${difColor}">${t.dif.toFixed(2)}</b></span>
          <span>DEA <b style="color:var(--text)">${t.dea.toFixed(2)}</b></span>
          <span>MACD <b style="color:${macdColor}">${t.macd.toFixed(2)}</b></span>
        </div>`;
      p.appendChild(b);
    });
    const hs = el('div');
    hs.innerHTML = `<div class="dd-section-h" style="margin-top:6px">HOT STOCKS · 热门标的</div>`;
    D.hotStocks.forEach(s => {
      const row = el('div', 'hot-stock');
      row.innerHTML = `
        <span class="nm">${s.name}</span>
        <span class="nt">${s.note}</span>
        <span class="vl ${cls(s.val)}">${fmtPct(s.val)}</span>`;
      hs.appendChild(row);
    });
    p.appendChild(hs);
  }

  /* ============================================================
     STRATEGY
     ============================================================ */
  function renderStrategy() {
    const s = D.strategy;
    $('#stratMacro').innerHTML = s.macro;
    const tw = $('#stratThemes'); tw.innerHTML = '';
    s.themes.forEach(t => {
      const line = el('div', 'theme-line');
      line.innerHTML = `<div class="theme-bar" style="background:${t.color}"></div>
        <div><div class="theme-name">${t.name}</div><div class="theme-desc">${t.desc}</div></div>`;
      tw.appendChild(line);
    });
    const rw = $('#stratRisks'); rw.innerHTML = '';
    s.risks.forEach(r => {
      const c = r.cls === 'up' ? 'var(--up)' : r.cls === 'down' ? 'var(--down)' : 'var(--amber)';
      const line = el('div', 'risk-line');
      line.innerHTML = `<span class="mk" style="color:${c}">${r.mk}</span><span>${r.text}</span>`;
      rw.appendChild(line);
    });
  }

  /* ============================================================
     INDEX BAR
     ============================================================ */
  function renderIndices() {
    const bar = $('#indexBar'); bar.innerHTML = '';
    D.indices.forEach(i => {
      const c = el('div', 'idx-item is-' + cls(i.pct));
      c.innerHTML = `
        <div class="idx-name">${i.name} <span class="en">${i.en}</span></div>
        <div class="idx-price" data-fkey="ix-${i.en}">${fmtPrice(i.price)}</div>
        <div class="idx-chg ${cls(i.pct)}"><span>${arrow(i.pct)}</span><span data-fkey="ixc-${i.en}">${i.chg >= 0 ? '+' : ''}${i.chg.toFixed(2)}</span><span>${fmtPct(i.pct)}</span></div>`;
      bar.appendChild(c);
    });
    D.stats.forEach(s => {
      const c = el('div', 'idx-item');
      const valColor = s.accent ? 'color:var(--amber)' : '';
      c.innerHTML = `
        <div class="idx-name">${s.name} <span class="en">${s.en}</span></div>
        <div class="idx-price" style="font-size:15px;${valColor}">${s.value}</div>
        <div class="idx-chg ${s.cls}">${s.sub || s.tag}</div>`;
      bar.appendChild(c);
    });
  }

  /* ============================================================
     TREND CHART
     ============================================================ */
  function normalize(arr) { const b = arr[0]; return arr.map(v => +(v / b * 100).toFixed(2)); }
  function renderTrend() {
    const ctx = $('#trendChart').getContext('2d');
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: D.trend.dates,
        datasets: D.trend.series.map((s, idx) => ({
          label: s.name, data: normalize(s.raw), borderColor: s.color,
          borderWidth: idx < 2 ? 2.4 : 1.6, pointRadius: 0, tension: 0.32, fill: false,
          hidden: hiddenSeries.has(s.name),
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0e1726', borderColor: '#24344d', borderWidth: 1, padding: 10,
            titleColor: '#fff', bodyColor: '#d4e2f7', titleFont: { family: 'IBM Plex Mono' },
            bodyFont: { family: 'IBM Plex Mono', size: 11 }, boxPadding: 4,
            callbacks: { label: c => ` ${c.dataset.label}  ${c.parsed.y.toFixed(1)}` },
          },
        },
        scales: {
          x: { grid: { color: '#eef2f8' }, ticks: { color: '#8694b0', font: { family: 'IBM Plex Mono', size: 9 }, maxRotation: 0, autoSkipPadding: 14 } },
          y: { grid: { color: '#eef2f8' }, ticks: { color: '#8694b0', font: { family: 'IBM Plex Mono', size: 9 }, callback: v => v.toFixed(0) } },
        },
      },
    });
    // legend
    const lg = $('#trendLegend'); lg.innerHTML = '';
    D.trend.series.forEach(s => {
      const item = el('div', 'tl-item' + (hiddenSeries.has(s.name) ? ' off' : ''));
      item.innerHTML = `<span class="tl-swatch" style="background:${s.color}"></span>
        <span class="tl-name">${s.name}</span><span class="tl-chg">${s.chg}</span>`;
      item.addEventListener('click', () => {
        if (hiddenSeries.has(s.name)) hiddenSeries.delete(s.name); else hiddenSeries.add(s.name);
        renderTrend();
      });
      lg.appendChild(item);
    });
  }

  /* ============================================================
     DRILL-DOWN DRAWER
     ============================================================ */
  const scrim = $('#scrim'), drawer = $('#drawer');
  function openDrill(name) {
    const sec = D.sectors.find(s => s.name === name)
      || D.sectors.find(s => name.includes(s.name) || s.name.includes(name));
    const hm = D.heatmap.find(h => h.name === name) || (sec && D.heatmap.find(h => sec.name.includes(h.name)));
    const today = sec ? sec.today : (hm ? hm.t : 0);
    const d5 = sec ? sec.d5 : (hm ? hm.d5 : 0);
    const d20 = sec ? sec.d20 : (hm ? hm.d20 : 0);
    const turnover = sec ? sec.turnover : (hm ? hm.turnover : 0);
    const heat = sec ? sec.heat : (hm ? hm.heat : 0);
    const kline = sec ? sec.kline : null;
    const stocks = D.constituents[sec ? sec.name : name] || D.constituents[name] || [];

    $('#ddName').textContent = name;
    $('#ddSub').textContent = `换手率 ${turnover.toFixed(2)}% · 热度 ${heat}`;
    const chgEl = $('#ddChg');
    chgEl.textContent = (today >= 0 ? '+' : '') + today.toFixed(2) + '%';
    chgEl.className = 'dh-chg ' + cls(today);

    $('#ddMetrics').innerHTML = [
      ['今日', today], ['5日', d5], ['20日', d20],
    ].map(([k, v]) => `<div class="dd-metric"><div class="k">${k}涨跌</div><div class="v ${cls(v)}">${fmtPct(v)}</div></div>`).join('')
      + `<div class="dd-metric"><div class="k">换手率</div><div class="v" style="color:var(--text)">${turnover.toFixed(2)}%</div></div>`;

    // stocks
    $('#ddStocks').innerHTML = stocks.length
      ? stocks.map(s => `<div class="dd-stock"><span class="nm">${s.nm}<span class="code">${s.code}</span></span><span class="vl ${cls(s.v)}">${fmtPct(s.v)}</span></div>`).join('')
      : `<div style="font-size:11px;color:var(--muted);font-family:var(--mono);padding:8px 0">暂无成分股明细数据</div>`;

    scrim.classList.add('show'); drawer.classList.add('show');
    // mini chart
    if (ddChart) { ddChart.destroy(); ddChart = null; }
    if (kline) {
      const up = kline[kline.length - 1] >= kline[0];
      const col = up ? '#e1322f' : '#008f5d';
      ddChart = new Chart($('#ddChart').getContext('2d'), {
        type: 'line',
        data: { labels: D.trend.dates, datasets: [{ data: normalize(kline), borderColor: col, borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true, backgroundColor: up ? 'rgba(225,50,47,0.08)' : 'rgba(0,143,93,0.08)' }] },
        options: {
          responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { grid: { color: '#eef2f8' }, ticks: { color: '#8694b0', font: { family: 'IBM Plex Mono', size: 9 }, maxTicksLimit: 4 } } },
        },
      });
    } else {
      $('#ddChart').parentElement.style.display = 'none';
    }
    if (kline) $('#ddChart').parentElement.style.display = '';
  }
  function closeDrill() { scrim.classList.remove('show'); drawer.classList.remove('show'); if (ddChart) { ddChart.destroy(); ddChart = null; } }
  scrim.addEventListener('click', closeDrill);
  $('#ddClose').addEventListener('click', closeDrill);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrill(); });

  /* ============================================================
     STATUS
     ============================================================ */
  function renderStatus() {
    $('#stSource').innerHTML = `数据源 <b>${D.meta.source}</b>`;
    const dateNote = D.meta.tradeDate ? ` · 分析日 <b>${D.meta.tradeDate}</b>` : '';
    const backNote = D.meta.requestedDate && D.meta.tradeDate && D.meta.requestedDate !== D.meta.tradeDate
      ? ` · 已回退自 <b>${D.meta.requestedDate}</b>` : '';
    $('#stAsOf').innerHTML = `截至 <b>${D.meta.asOf}</b>${dateNote}${backNote}`;
    const upN = D.heatmap.filter(h => h.t > 0).length;
    const dnN = D.heatmap.filter(h => h.t < 0).length;
    $('#stBreadth').innerHTML = `板块 <b style="color:#ff6b68">${upN}↑</b> / <b style="color:#4fd6a0">${dnN}↓</b>`;
    // 静态模式：更新底部行情状态标签
    const siEl = document.querySelector('.si b:last-child');
    if (siEl && siEl.parentElement.textContent.includes('行情')) {
      siEl.textContent = D.meta.session || '收盘';
    }
  }

  /* ============================================================
     REFRESH (本地 API 优先，静态 data.js 兜底)
     ============================================================ */

  function renderAll() {
    renderIndices(); renderHeatmap(); renderSectorTable(); renderFlows();
    renderSignals(); renderPicks(); renderConcepts(); renderTech();
    renderStrategy(); renderTrend(); renderStatus();
  }
  // 用新对象就地替换 D 的内容，使所有闭包都看到最新数据
  function replaceData(fresh) {
    Object.keys(D).forEach(k => delete D[k]);
    Object.assign(D, fresh);
  }

  function selectedDate() {
    const input = $('#scanDate');
    if (input && input.value) return input.value;
    const d = new Date();
    return d.toISOString().slice(0, 10);
  }

  function syncDateControl() {
    const input = $('#scanDate');
    if (!input) return;
    input.value = D.meta.requestedDate || D.meta.tradeDate || new Date().toISOString().slice(0, 10);
  }

  function toastForData() {
    const meta = D.meta || {};
    const parts = [];
    if (meta.tradeDate) parts.push('分析日 ' + meta.tradeDate);
    if (meta.requestedDate && meta.tradeDate && meta.requestedDate !== meta.tradeDate) parts.push('已回退自 ' + meta.requestedDate);
    if (meta.cacheHit) parts.push('本地缓存');
    if (meta.aiStatus) parts.push('AI ' + meta.aiStatus);
    if (meta.dataStatus && meta.dataStatus !== 'live') parts.push('数据 ' + meta.dataStatus);
    return parts.length ? parts.join(' · ') : (meta.asOf || meta.source || '已更新');
  }

  function loadStaticSnapshot() {
    return fetch('data.js?_=' + Date.now(), { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
      .then(text => {
        const fresh = new Function(text + '\nreturn window.TERMINAL_DATA;')();
        if (!fresh || !fresh.sectors) throw new Error('bad shape');
        fresh.meta = fresh.meta || {};
        fresh.meta.requestedDate = selectedDate();
        fresh.meta.dataStatus = 'snapshot';
        fresh.meta.aiStatus = fresh.meta.aiStatus || 'fallback';
        return fresh;
      })
      .catch(err => {
        if (window.TERMINAL_DATA && window.TERMINAL_DATA.sectors) {
          window.TERMINAL_DATA.meta = window.TERMINAL_DATA.meta || {};
          window.TERMINAL_DATA.meta.requestedDate = selectedDate();
          window.TERMINAL_DATA.meta.dataStatus = 'snapshot';
          window.TERMINAL_DATA.meta.aiStatus = window.TERMINAL_DATA.meta.aiStatus || 'fallback';
          return window.TERMINAL_DATA;
        }
        throw err;
      });
  }

  // 按日期扫描：优先请求本地后端；离线/后端未启动时仍可载入 data.js 快照
  function refresh(force = false) {
    const btn = force ? $('#btnRescan') : $('#btnRefresh');
    if ($('#btnRefresh').classList.contains('loading') || $('#btnRescan').classList.contains('loading')) return;
    btn.classList.add('loading');

    const date = selectedDate();
    const url = API_BASE + '/api/scan?date=' + encodeURIComponent(date) + (force ? '&refresh=1' : '');
    fetch(url, { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .catch(() => loadStaticSnapshot())
      .then(fresh => {
        if (!fresh || !fresh.sectors) throw new Error('bad shape');
        replaceData(fresh);
        renderAll();
        syncDateControl();
        btn.classList.remove('loading');
        showToast('扫描完成 · ' + toastForData());
      })
      .catch(() => {
        btn.classList.remove('loading');
        showToast('数据加载失败，请检查本地服务或 data.js');
      });
  }
  let toastTimer = null;
  function showToast(msg) {
    const t = $('#toast');
    t.querySelector('.msg').textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
  }

  /* ============================================================
     WIRE UP
     ============================================================ */
  function bindControls() {
    // heatmap range
    $$('#heatRange button').forEach(b => b.addEventListener('click', () => {
      $$('#heatRange button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      RANGE = b.dataset.range; renderHeatmap();
    }));
    // table sort
    $$('#sectorHead th[data-key]').forEach(th => th.addEventListener('click', () => {
      const k = th.dataset.key;
      if (SORT.key === k) SORT.dir *= -1; else { SORT.key = k; SORT.dir = (k === 'name') ? 1 : -1; }
      renderSectorTable();
    }));
    $('#btnRefresh').addEventListener('click', () => refresh(false));
    $('#btnRescan').addEventListener('click', () => refresh(true));
    $('#scanDate').addEventListener('change', () => refresh(false));
  }

  function init() {
    renderIndices(); renderHeatmap(); renderSectorTable(); renderFlows();
    renderSignals(); renderPicks(); renderConcepts(); renderTech(); renderStrategy();
    renderTrend(); renderStatus();
    syncDateControl();
    bindControls();
  }
  window.TERMINAL = { refresh, data: D };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
