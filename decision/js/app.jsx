// decision/js/app.jsx — 板块投资决策看板
const { useState, useEffect, useCallback, useRef } = React;

const API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

async function apiFetch(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = `${API_BASE}${path}${qs ? '?' + qs : ''}`;
  const r = await fetch(url, { cache: 'no-store' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ── Tier helpers ──
const TIER_CLASS = {
  '强烈看多': 'tier tier-strong-buy',
  '看多': 'tier tier-buy',
  '中性': 'tier tier-neutral',
  '看空': 'tier tier-sell',
  '强烈看空': 'tier tier-strong-sell',
  'NO_SIGNAL': 'tier tier-no-signal',
  'LOW_CONFIDENCE': 'tier tier-no-signal',
};

function TierBadge({ tier }) {
  return <span className={TIER_CLASS[tier] || 'tier tier-no-signal'}>{tier || '—'}</span>;
}

function compositeColor(v) {
  if (v > 0.2) return 'var(--up)';
  if (v < -0.2) return 'var(--down)';
  return 'var(--gold)';
}

function compositeClass(v) {
  if (v > 0.2) return 'up';
  if (v < -0.2) return 'down';
  return 'flat';
}

function computeGroupScores(factors) {
  const acc = {};
  for (const [, f] of Object.entries(factors || {})) {
    const g = f.group || 'other';
    if (f.norm == null) continue;
    if (!acc[g]) acc[g] = { sum: 0, n: 0 };
    acc[g].sum += f.norm;
    acc[g].n++;
  }
  const out = {};
  for (const [g, { sum, n }] of Object.entries(acc)) out[g] = n > 0 ? sum / n : 0;
  return out;
}

function scoreConstituents(constituents) {
  if (!constituents || !constituents.length) return [];
  const vals = constituents.map(c => c.change_pct ?? 0);
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const variance = vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length;
  const std = Math.sqrt(variance) || 1;
  return constituents
    .map(c => {
      const rs = ((c.change_pct ?? 0) - mean) / std;
      return {
        ...c,
        rs_sector: Math.round(rs * 1000) / 1000,
        is_leader: rs > 0.8 && (c.change_pct ?? 0) > 0,
        cons_tier: rs > 0.6 ? '强势' : rs < -0.6 ? '弱势' : '中性',
      };
    })
    .sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0));
}

// ── K-line Canvas renderer ──────────────────────────────────────────────
function renderKLine(canvas, bars) {
  const ctx  = canvas.getContext('2d');
  const dpr  = window.devicePixelRatio || 1;
  const W    = canvas.offsetWidth || 600;
  const H    = canvas.offsetHeight || 260;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  ctx.scale(dpr, dpr);

  const n = bars.length;
  if (!n) return;

  const VOL_H   = Math.floor(H * 0.18);
  const PRICE_H = H - VOL_H - 6;
  const PAD_L = 4, PAD_R = 52, PAD_T = 12, PAD_B = 18;
  const CW    = W - PAD_L - PAD_R;
  const barW  = CW / n;
  const cndW  = Math.max(1, Math.min(barW * 0.72, 12));

  const highs  = bars.map(b => b.high);
  const lows   = bars.map(b => b.low);
  const closes = bars.map(b => b.close);
  const maxP   = Math.max(...highs);
  const minP   = Math.min(...lows);
  const pRange = maxP - minP || 1;
  const maxVol = Math.max(...bars.map(b => b.volume || 0)) || 1;

  const px     = p => PAD_T + PRICE_H - (p - minP) / pRange * PRICE_H;
  const bx     = i => PAD_L + i * barW + barW / 2;
  const volTop = H - VOL_H - PAD_B + 2;

  // Background
  ctx.fillStyle = '#faf7f2';
  ctx.fillRect(0, 0, W, H);

  // Horizontal grid + price labels
  ctx.strokeStyle = '#e5ddd0';
  ctx.lineWidth   = 0.5;
  ctx.font = '9px -apple-system,PingFang SC,sans-serif';
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    const y = PAD_T + t * PRICE_H;
    ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R + 4, y); ctx.stroke();
    ctx.fillStyle = '#9b8e80';
    ctx.textAlign = 'left';
    ctx.fillText((maxP - pRange * t).toFixed(2), W - PAD_R + 7, y + 3);
  });

  // MA5 (gold) and MA20 (blue)
  [[5, '#c8900a'], [20, '#2a5fa5']].forEach(([period, color]) => {
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    let started = false;
    for (let i = period - 1; i < n; i++) {
      const ma = closes.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0) / period;
      if (!started) { ctx.moveTo(bx(i), px(ma)); started = true; }
      else ctx.lineTo(bx(i), px(ma));
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  });

  // Candles + volume bars
  for (let i = 0; i < n; i++) {
    const b     = bars[i];
    const x     = bx(i);
    const isUp  = b.close >= b.open;
    const color = isUp ? '#bf3a30' : '#1e8a5e';

    // Wick
    ctx.strokeStyle = color;
    ctx.lineWidth   = Math.max(0.5, cndW * 0.18);
    ctx.beginPath();
    ctx.moveTo(x, px(b.high));
    ctx.lineTo(x, px(b.low));
    ctx.stroke();

    // Body — hollow outline for up days, solid fill for down days
    const top = Math.min(px(b.open), px(b.close));
    const bh  = Math.max(1, Math.abs(px(b.open) - px(b.close)));
    if (isUp) {
      ctx.strokeStyle = color;
      ctx.lineWidth   = 1;
      ctx.strokeRect(x - cndW / 2, top, cndW, bh);
    } else {
      ctx.fillStyle = color;
      ctx.fillRect(x - cndW / 2, top, cndW, bh);
    }

    // Volume
    if (b.volume) {
      const vh = Math.max(1, (b.volume / maxVol) * (VOL_H - 4));
      ctx.fillStyle = isUp ? 'rgba(191,58,48,0.35)' : 'rgba(30,138,94,0.35)';
      ctx.fillRect(x - cndW / 2, volTop + (VOL_H - 4 - vh), cndW, vh);
    }
  }

  // Volume divider
  ctx.strokeStyle = '#e0d8cc';
  ctx.lineWidth   = 0.5;
  ctx.beginPath(); ctx.moveTo(PAD_L, volTop); ctx.lineTo(W - PAD_R + 4, volTop); ctx.stroke();

  // Date labels (6 evenly spaced)
  ctx.fillStyle = '#9b8e80';
  ctx.textAlign = 'center';
  ctx.font      = '9px -apple-system,PingFang SC,sans-serif';
  const step = Math.ceil(n / 6);
  for (let i = 0; i < n; i += step) {
    const d = bars[i]?.date;
    if (d) ctx.fillText(d.slice(5), bx(i), H - PAD_B + 14);
  }
}

function KLineChart({ type, name }) {
  const canvasRef         = useRef(null);
  const [bars, setBars]   = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!name) return;
    setBars(null);
    setError(null);
    const param = type === 'stock'
      ? `symbol=${encodeURIComponent(name)}`
      : `name=${encodeURIComponent(name)}`;
    apiFetch(`/api/decision/kline?type=${type}&${param}`)
      .then(d => setBars(d.bars || []))
      .catch(e => setError(e.message));
  }, [type, name]);

  useEffect(() => {
    if (!canvasRef.current || !bars || !bars.length) return;
    renderKLine(canvasRef.current, bars);
  }, [bars]);

  // Re-render on container resize
  useEffect(() => {
    if (!canvasRef.current || !bars || !bars.length) return;
    const obs = new ResizeObserver(() => {
      if (canvasRef.current) renderKLine(canvasRef.current, bars);
    });
    obs.observe(canvasRef.current);
    return () => obs.disconnect();
  }, [bars]);

  if (error) return (
    <div style={{ fontSize: 12, color: 'var(--ink3)', padding: '8px 0' }}>
      K线加载失败：{error}
    </div>
  );
  if (!bars) return (
    <div style={{ fontSize: 12, color: 'var(--ink3)', padding: '8px 0' }}>K线数据加载中…</div>
  );
  if (!bars.length) return null;

  return (
    <div style={{ margin: '14px 0' }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 5 }}>
        <span style={{ fontSize: 11, color: 'var(--ink3)' }}>近一年日线 · {bars.length} 根</span>
        <span style={{ fontSize: 10, color: '#c8900a' }}>━ MA5</span>
        <span style={{ fontSize: 10, color: '#2a5fa5' }}>━ MA20</span>
        <span style={{ fontSize: 10, color: 'var(--up)', marginLeft: 'auto' }}>☐ 阳线</span>
        <span style={{ fontSize: 10, color: 'var(--down)' }}>■ 阴线</span>
      </div>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%', height: 260, display: 'block',
          borderRadius: 6, border: '1px solid var(--border)',
        }}
      />
    </div>
  );
}

// ── CompositeBar ──
function CompositeBar({ value }) {
  const pct   = Math.abs(value || 0) * 100;
  const left  = value >= 0 ? '50%' : `${50 - pct / 2}%`;
  const color = compositeColor(value);
  return (
    <div className="composite-bar-wrap">
      <div className="composite-bar">
        <div className="composite-bar-fill" style={{ left, width: `${pct / 2}%`, background: color }} />
        <div style={{ position: 'absolute', left: '50%', top: -1, width: 1, height: 7, background: 'var(--hair)' }} />
      </div>
      <span className={`composite-val ${compositeClass(value)}`}>
        {value != null ? (value > 0 ? '+' : '') + value.toFixed(3) : '—'}
      </span>
    </div>
  );
}

// ── FactorBar ──
function FactorBar({ norm }) {
  if (norm == null) return <div className="factor-bar"><span style={{ fontSize: 10, color: 'var(--hair)', paddingLeft: 3 }}>N/A</span></div>;
  const pct   = Math.abs(norm) * 100;
  const left  = norm >= 0 ? '50%' : `${50 - pct / 2}%`;
  const color = norm > 0.1 ? 'var(--up)' : norm < -0.1 ? 'var(--down)' : 'var(--gold)';
  return (
    <div className="factor-bar">
      <div className="factor-bar-fill" style={{ left, width: `${pct / 2}%`, background: color }} />
      <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: '#d8d3c8' }} />
    </div>
  );
}

// ── GatePills ──
function GatePills({ gates }) {
  if (!gates || !gates.length) return null;
  return (
    <span>
      {gates.map((g, i) => {
        const isWarn = g.startsWith('SG4') || g.startsWith('SG5') || g.startsWith('SG2') || g.startsWith('TG');
        return <span key={i} className={`gate-pill${isWarn ? ' warn' : ''}`}>{g.split(':')[0]}</span>;
      })}
    </span>
  );
}

// ── Rotation Board ────────────────────────────────────────────────────────
function RotationView({ date, onSelectSector, refreshTrigger, forceRefresh, onRefreshDone, setLoading }) {
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);
  const [sortKey, setSortKey] = useState('composite');
  const [sortDir, setSortDir] = useState('desc');

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    apiFetch('/api/decision/rotation', { date, refresh: forceRefresh ? '1' : '0' })
      .then(d => { if (alive) { setData(d); onRefreshDone(); } })
      .catch(e => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [date, refreshTrigger]);

  const doSort = key => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };
  const arr = key => sortKey === key ? (sortDir === 'asc' ? '↑' : '↓') : '';

  const sectors = data ? [...(data.sectors || [])].sort((a, b) => {
    const av = a[sortKey] ?? 0, bv = b[sortKey] ?? 0;
    return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  }) : [];

  return (
    <div className="page">
      <div className="rotation-header">
        <div>
          <h2>板块轮动排行 <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--ink2)', fontFamily: 'var(--mono)' }}>ROTATION BOARD</span></h2>
          {data?.meta && (
            <div className="sub">
              交易日 {data.meta.tradeDate} · 共 {data.meta.sectorCount} 个板块参与排名
              {data.meta.cacheHit && <span style={{ marginLeft: 8, color: 'var(--gold)' }}>● 缓存</span>}
            </div>
          )}
        </div>
      </div>

      {error && <div className="error-state"><div className="error-title">加载失败</div>{error}</div>}

      {data && (
        <>
          <div className="rotation-table-wrap">
            <table className="rotation-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>排名</th>
                  <th onClick={() => doSort('name')} className="sortable">板块 <span className="arr">{arr('name')}</span></th>
                  <th>决策信号</th>
                  <th onClick={() => doSort('composite')} className="sortable" style={{ minWidth: 160 }}>综合评分 <span className="arr">{arr('composite')}</span></th>
                  <th onClick={() => doSort('confidence')} className="sortable">置信度 <span className="arr">{arr('confidence')}</span></th>
                  <th onClick={() => doSort('rs20')} className="sortable">RS20% <span className="arr">{arr('rs20')}</span></th>
                  <th onClick={() => doSort('flow_score')} className="sortable">资金 <span className="arr">{arr('flow_score')}</span></th>
                  <th onClick={() => doSort('breadth_score')} className="sortable">广度 <span className="arr">{arr('breadth_score')}</span></th>
                  <th>门控</th>
                </tr>
              </thead>
              <tbody>
                {sectors.map(s => (
                  <tr key={s.name} onClick={() => onSelectSector(s.name)}>
                    <td><span className="rank-num">{s.rank || '—'}</span></td>
                    <td><span className="sector-name">{s.name}</span></td>
                    <td><TierBadge tier={s.tier} /></td>
                    <td><CompositeBar value={s.composite} /></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <div className="confidence-bar"><div className="confidence-bar-fill" style={{ width: `${(s.confidence || 0) * 100}%` }} /></div>
                        <span className="score-num">{s.confidence != null ? (s.confidence * 100).toFixed(0) + '%' : '—'}</span>
                      </div>
                    </td>
                    <td><span className={`score-num ${s.rs20 > 0 ? 'up' : s.rs20 < 0 ? 'down' : 'flat'}`}>{s.rs20 != null ? (s.rs20 > 0 ? '+' : '') + s.rs20.toFixed(1) + '%' : '—'}</span></td>
                    <td><span className={`score-num ${s.flow_score > 0.1 ? 'up' : s.flow_score < -0.1 ? 'down' : 'flat'}`}>{s.flow_score != null ? s.flow_score.toFixed(3) : '—'}</span></td>
                    <td>
                      <span className={`score-num ${s.breadth_low_confidence ? 'flat' : s.breadth_score > 0.1 ? 'up' : s.breadth_score < -0.1 ? 'down' : 'flat'}`}>
                        {s.breadth_low_confidence ? <span style={{ color: 'var(--hair)', fontSize: 11 }}>~</span> : (s.breadth_score != null ? s.breadth_score.toFixed(3) : '—')}
                      </span>
                    </td>
                    <td><GatePills gates={s.gates} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.abstained && data.abstained.length > 0 && (
            <div className="abstained-section">
              <div className="abstained-title">弃权板块 ({data.abstained.length})</div>
              <div className="abstained-list">
                {data.abstained.map(s => (
                  <span key={s.name} className="abstained-item" title={s.gates?.join('; ')}>{s.name}</span>
                ))}
              </div>
            </div>
          )}

          <div style={{ marginTop: 16, fontSize: 11, color: 'var(--ink2)' }}>
            提示：点击板块行查看详细决策分析。综合评分范围 [-1, +1]，0 为中性基准。广度列 ~ 表示数据不足（低置信）。
          </div>
        </>
      )}
    </div>
  );
}

// ── Factor Groups ─────────────────────────────────────────────────────────
const GROUP_LABELS = { trend: '趋势', momentum: '动量', flow: '资金', breadth: '广度', crowd: '拥挤度', oscillator: '振荡器' };

function FactorGroups({ factors, groupScores }) {
  const [open, setOpen] = useState({ trend: true, momentum: true, flow: true, breadth: false, crowd: false, oscillator: false });
  const toggle = g => setOpen(o => ({ ...o, [g]: !o[g] }));

  const groups = {};
  for (const [fid, fdata] of Object.entries(factors || {})) {
    const g = fdata.group || 'other';
    (groups[g] = groups[g] || []).push({ fid, ...fdata });
  }

  return (
    <div className="factor-groups">
      {Object.entries(groups).map(([g, items]) => {
        const gs    = groupScores?.[g];
        const color = gs != null ? compositeColor(gs) : 'var(--hair)';
        const pct   = gs != null ? Math.abs(gs) * 100 : 0;
        const left  = gs != null && gs >= 0 ? '50%' : `${50 - pct / 2}%`;
        return (
          <div key={g} className="factor-group">
            <div className={`factor-group-header${open[g] ? ' open' : ''}`} onClick={() => toggle(g)}>
              <span className="group-name">{GROUP_LABELS[g] || g}</span>
              <div className="group-score-bar">
                <div className="group-score-fill" style={{ left, width: `${pct / 2}%`, background: color }} />
                <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: '#cfc7b6' }} />
              </div>
              <span className={`group-score-val ${compositeClass(gs)}`}>{gs != null ? (gs > 0 ? '+' : '') + gs.toFixed(3) : '—'}</span>
              <span className={`chevron${open[g] ? ' open' : ''}`}>▾</span>
            </div>
            {open[g] && (
              <div className="factor-rows">
                <div className="factor-row" style={{ fontWeight: 700, fontSize: 10, color: 'var(--ink2)', padding: '4px 0 2px' }}>
                  <span>因子</span><span>方向强度</span>
                  <span style={{ textAlign: 'right' }}>原始值</span>
                  <span style={{ textAlign: 'right' }}>标准化</span>
                </div>
                {items.map(({ fid, label, raw, norm, real }) => (
                  <div key={fid} className="factor-row">
                    <span className="factor-label">
                      {label || fid}
                      {real === false && <span style={{ color: 'var(--hair)', marginLeft: 4, fontSize: 10 }}>(估)</span>}
                    </span>
                    <FactorBar norm={norm} />
                    <span className="factor-raw">
                      {raw == null ? 'N/A' : typeof raw === 'number'
                        ? (Math.abs(raw) > 100 ? (raw / 10000).toFixed(1) + '万' : raw.toFixed(raw % 1 === 0 ? 0 : 3))
                        : raw}
                    </span>
                    <span className={`factor-norm ${compositeClass(norm)}`}>
                      {norm != null ? (norm > 0 ? '+' : '') + norm.toFixed(3) : '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Breadth Panel ─────────────────────────────────────────────────────────
function BreadthPanel({ factors }) {
  const ma20 = factors?.breadth_pct_above_ma20;
  const ma60 = factors?.breadth_pct_above_ma60;
  const adv  = factors?.breadth_adv_decline;
  if (!ma20 && !ma60 && !adv) return null;
  const bar = (v, good) => {
    if (v == null) return null;
    const p     = Math.min(Math.abs(v) * 100, 100);
    const color = v >= good ? 'var(--up)' : v < 0.3 ? 'var(--down)' : 'var(--gold)';
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ flex: 1, height: 4, background: 'var(--hair)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${p}%`, height: '100%', background: color, borderRadius: 2 }} />
        </div>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color, minWidth: 32 }}>{(v * 100).toFixed(0)}%</span>
      </div>
    );
  };
  return (
    <div className="card" style={{ marginTop: 14 }}>
      <div className="card-title">板块广度</div>
      <div style={{ display: 'grid', gap: 8 }}>
        {ma20 != null && <div><div style={{ fontSize: 11, color: 'var(--ink2)', marginBottom: 3 }}>站上MA20（趋势参与度）</div>{bar(ma20.raw ?? ma20.norm, 0.5)}</div>}
        {ma60 != null && <div><div style={{ fontSize: 11, color: 'var(--ink2)', marginBottom: 3 }}>站上MA60（中期健康度）</div>{bar(ma60.raw ?? ma60.norm, 0.5)}</div>}
        {adv  != null && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--ink2)', marginBottom: 3 }}>涨跌比（今日）</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ flex: 1, height: 4, background: 'var(--hair)', borderRadius: 2, overflow: 'hidden', position: 'relative' }}>
                <div style={{ position: 'absolute', left: '50%', width: 1, height: '100%', background: 'var(--ink2)' }} />
                {adv.norm != null && (() => {
                  const p = Math.abs(adv.norm) * 50;
                  return <div style={{ position: 'absolute', left: adv.norm >= 0 ? '50%' : `${50 - p}%`, width: `${p}%`, height: '100%', background: adv.norm >= 0 ? 'var(--up)' : 'var(--down)' }} />;
                })()}
              </div>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: adv.norm > 0.1 ? 'var(--up)' : adv.norm < -0.1 ? 'var(--down)' : 'var(--gold)', minWidth: 36 }}>
                {adv.raw != null ? (adv.raw > 0 ? '+' : '') + adv.raw.toFixed(2) : '—'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Target Price Card ─────────────────────────────────────────────────────
function TargetPriceCard({ tp }) {
  if (!tp) return (
    <div className="target-card">
      <div className="card-title">目标价位</div>
      <div style={{ color: 'var(--ink2)', fontSize: 12 }}>数据不足，无法计算</div>
    </div>
  );
  const stopLabel = tp.stop_method ? `止损位 (${tp.stop_method})` : '止损位 (ATR×1.5)';
  return (
    <div className="target-card">
      <div className="card-title">目标价位 · ATR模型</div>
      <div className="target-zone">
        <span className="zone-label">进场参考区</span>
        <span className="zone-range">{tp.entry_low} — {tp.entry_high}</span>
      </div>
      <div className="target-rows">
        <div className="target-row">
          <span className="target-label">最新收盘</span>
          <span className="target-val" style={{ fontFamily: 'var(--mono)' }}>{tp.last_close}</span>
        </div>
        <div className="target-row">
          <span className="target-label">{stopLabel}</span>
          <span className="target-val down">{tp.stop_loss}</span>
        </div>
        <div className="target-row">
          <span className="target-label">目标1 (ATR×2)</span>
          <span className="target-val up">{tp.target_1}</span>
        </div>
        <div className="target-row">
          <span className="target-label">目标2 (ATR×3.5)</span>
          <span className="target-val up">{tp.target_2}</span>
        </div>
        <div className="target-row">
          <span className="target-label">ATR(14)</span>
          <span className="target-val" style={{ color: 'var(--ink2)' }}>{tp.atr14}</span>
        </div>
        <div className="target-row" style={{ borderBottom: 'none' }}>
          <span className="target-label">盈亏比 (目标1)</span>
          <span className="rr-badge">R:{tp.risk_reward}</span>
        </div>
      </div>
      <div className="disclaimer">{tp.note}</div>
    </div>
  );
}

// ── Sector Detail ─────────────────────────────────────────────────────────
function SectorView({ sectorName, date, onBack, onSelectStock, refreshTrigger, forceRefresh, onRefreshDone, setLoading }) {
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setData(null);
    apiFetch('/api/decision/sector', { name: sectorName, date, refresh: forceRefresh ? '1' : '0' })
      .then(d => { if (alive) { setData(d); onRefreshDone(); } })
      .catch(e => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [sectorName, date, refreshTrigger]);

  const scoredCons = data ? scoreConstituents(data.constituents || []) : [];

  return (
    <div className="page">
      <button className="back-btn" onClick={onBack}>← 返回轮动排行</button>

      {error && <div className="error-state"><div className="error-title">加载失败</div>{error}</div>}

      {data && !data.meta?.error && (
        <div className="sector-detail">
          <div className="sector-hero">
            <h2>{data.name}</h2>
            <TierBadge tier={data.tier} />
            <div className="confidence-meter">
              <div className="confidence-bar"><div className="confidence-bar-fill" style={{ width: `${(data.confidence || 0) * 100}%` }} /></div>
              <span>{data.confidence != null ? (data.confidence * 100).toFixed(0) + '% 置信' : ''}</span>
            </div>
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--ink2)', letterSpacing: 1, marginBottom: 2 }}>综合评分</div>
              <span className={`composite-big ${compositeClass(data.composite)}`}>
                {data.composite != null ? (data.composite > 0 ? '+' : '') + data.composite.toFixed(3) : '—'}
              </span>
            </div>
          </div>

          {data.meta && (
            <div className="meta-bar">
              <span>交易日 {data.meta.tradeDate}</span>
              <span>更新 {data.meta.asOf}</span>
              {data.meta.cacheHit && <span style={{ color: 'var(--gold)' }}>● 缓存</span>}
            </div>
          )}

          {/* ── K-line chart ── */}
          <KLineChart type="sector" name={sectorName} />

          {data.gates && data.gates.length > 0 && (
            <div className="card gates-section" style={{ marginBottom: 14 }}>
              <div className="card-title">⚠ 触发门控</div>
              {data.gates.map((g, i) => (
                <div key={i} className="gate-item">
                  <span className="gate-icon">{g.startsWith('SG1') ? '🕒' : g.startsWith('SG2') ? '📉' : g.startsWith('SG4') ? '↕' : '⚡'}</span>
                  <span>{g}</span>
                </div>
              ))}
            </div>
          )}

          <div className="detail-grid">
            <div>
              <FactorGroups factors={data.factors} groupScores={data.group_scores} />
              <BreadthPanel factors={data.factors} />

              {data.evidence && (
                <div className="evidence-card">
                  <div className="evidence-label">AI 辅助解读</div>
                  <div className="evidence-text">{data.evidence}</div>
                  <div className="ai-note">AI文本仅供参考，所有数字以引擎因子为准，不构成投资建议。</div>
                </div>
              )}

              {data.etf_candidates && data.etf_candidates.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <div className="card-title">可操作ETF参考</div>
                  <div className="etf-row">
                    {data.etf_candidates.map(e => (
                      <span key={e.etf_code} className="etf-tag">
                        <span className="etf-code">{e.etf_code}</span>
                        <span>{e.name}</span>
                        <span style={{ color: 'var(--ink2)' }}>{e.liquidity}</span>
                      </span>
                    ))}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink2)', marginTop: 4 }}>价位仍以板块指数为基准，ETF仅供操作参考。</div>
                </div>
              )}

              {scoredCons.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div className="card-title">
                    成份股排序
                    <span style={{ fontWeight: 400, fontSize: 11, color: 'var(--ink2)', marginLeft: 8 }}>
                      按今日涨跌排列 · 龙头 = 板块内前25%强势股
                    </span>
                  </div>
                  <table className="cons-table">
                    <thead>
                      <tr>
                        <th>股票</th>
                        <th>代码</th>
                        <th>今日%</th>
                        <th>板块信号</th>
                        <th style={{ textAlign: 'right' }}>板块内RS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scoredCons.slice(0, 20).map(c => (
                        <tr key={c.code || c.name} onClick={() => c.code && onSelectStock(c.code, c.name)} style={{ cursor: c.code ? 'pointer' : 'default' }}>
                          <td>
                            <span>{c.name}</span>
                            {c.is_leader && <span className="leader-tag">龙头</span>}
                          </td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{c.code}</td>
                          <td>
                            <span className={c.change_pct > 0 ? 'up' : c.change_pct < 0 ? 'down' : 'flat'} style={{ fontFamily: 'var(--mono)' }}>
                              {c.change_pct > 0 ? '+' : ''}{(c.change_pct ?? 0).toFixed(2)}%
                            </span>
                          </td>
                          <td>
                            <span className={`cons-tier-badge ${c.cons_tier === '强势' ? 'cons-strong' : c.cons_tier === '弱势' ? 'cons-weak' : 'cons-neutral'}`}>
                              {c.cons_tier}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 11, color: c.rs_sector > 0 ? 'var(--up)' : c.rs_sector < 0 ? 'var(--down)' : 'var(--ink2)' }}>
                            {c.rs_sector > 0 ? '+' : ''}{c.rs_sector?.toFixed(2) ?? '—'}σ
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <TargetPriceCard tp={data.target_price} />
              {data.disclaimer && <div style={{ fontSize: 11, color: 'var(--ink2)', marginTop: 10 }}>{data.disclaimer}</div>}
            </div>
          </div>
        </div>
      )}

      {data?.meta?.error && (
        <div className="error-state">
          <div className="error-title">{data.meta.error}</div>
          <div>{data.meta.message}</div>
        </div>
      )}
    </div>
  );
}

// ── Stock Detail ──────────────────────────────────────────────────────────
function StockView({ symbol, stockName, date, onBack, refreshTrigger, forceRefresh, onRefreshDone, setLoading }) {
  const [data, setData]   = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    setData(null);
    apiFetch('/api/decision/stock', { symbol, date, refresh: forceRefresh ? '1' : '0' })
      .then(d => { if (alive) { setData(d); onRefreshDone(); } })
      .catch(e => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [symbol, date, refreshTrigger]);

  return (
    <div className="page">
      <button className="back-btn" onClick={onBack}>← 返回板块详情</button>

      {error && <div className="error-state"><div className="error-title">加载失败</div>{error}</div>}

      {data && !data.meta?.error && (
        <div className="stock-detail">
          <div className="stock-hero">
            <h2>{data.name || stockName}</h2>
            <span className="stock-code">{symbol}</span>
            <TierBadge tier={data.tier} />
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--ink2)', letterSpacing: 1, marginBottom: 2 }}>综合评分</div>
              <span className={`composite-big ${compositeClass(data.composite)}`} style={{ fontSize: 22 }}>
                {data.composite != null ? (data.composite > 0 ? '+' : '') + data.composite.toFixed(3) : '—'}
              </span>
            </div>
          </div>

          {data.meta && (
            <div className="meta-bar">
              <span>交易日 {data.meta.tradeDate}</span>
              {data.meta.cacheHit && <span style={{ color: 'var(--gold)' }}>● 缓存</span>}
            </div>
          )}

          {/* ── K-line chart ── */}
          <KLineChart type="stock" name={symbol} />

          {data.gates && data.gates.length > 0 && (
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="card-title">门控</div>
              {data.gates.map((g, i) => <div key={i} className="gate-item"><span className="gate-icon">⚠</span><span>{g}</span></div>)}
            </div>
          )}

          <div className="detail-grid">
            <div>
              <FactorGroups
                factors={data.factors}
                groupScores={data.group_scores || computeGroupScores(data.factors)}
              />
              {data.disclaimer && <div style={{ fontSize: 11, color: 'var(--ink2)', marginTop: 10 }}>{data.disclaimer}</div>}
            </div>
            <div>
              <TargetPriceCard tp={data.target_price} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Header ────────────────────────────────────────────────────────────────
function Header({ view, sectorName, stockName, date, onDateChange, onBackToRotation, onBackToSector, onRefresh, loading }) {
  const btnLabel = loading ? '分析中…' : view === 'rotation' ? '重新扫描' : '重新分析';
  return (
    <div className="top">
      <a className="brand" href="/sector">
        <div className="brand-mark">决</div>
        <div className="brand-text">
          <strong>决策看板</strong>
          <small>DECISION BOARD</small>
        </div>
      </a>
      <nav className="module-tabs" aria-label="功能模块">
        <a href="/sector">板块扫描</a>
        <a href="/chanlun">缠论分析</a>
        <a className="active" href="/decision">决策看板</a>
        <a href="/review">大盘复盘</a>
        <a href="/help">帮助</a>
      </nav>
      {view !== 'rotation' && (
        <div className="breadcrumb">
          <span className="sep">›</span>
          <button onClick={onBackToRotation}>轮动排行</button>
          {view === 'sector' && sectorName && <><span className="sep">›</span><span>{sectorName}</span></>}
          {view === 'stock' && (
            <>
              <span className="sep">›</span>
              <button onClick={onBackToSector}>{sectorName}</button>
              <span className="sep">›</span>
              <span>{stockName}</span>
            </>
          )}
        </div>
      )}
      <div className="top-actions">
        <label className="date-field">
          <span>日期</span>
          <input type="date" value={date} onChange={e => onDateChange(e.target.value)} max={todayStr()} />
        </label>
        <button className="mini-btn primary" onClick={onRefresh} disabled={loading}>{btnLabel}</button>
      </div>
    </div>
  );
}

function LoadingBar({ loading }) {
  if (!loading) return null;
  return (
    <div className="loading-state" style={{ margin: '24px 32px' }}>
      <div className="spinner" />
      <span>正在加载数据…</span>
    </div>
  );
}

// ── App Root ──────────────────────────────────────────────────────────────
function App() {
  const [view, setView]                       = useState('rotation');
  const [date, setDate]                       = useState(todayStr());
  const [selectedSector, setSelectedSector]   = useState(null);
  const [selectedStock, setSelectedStock]     = useState(null);
  const [selectedStockName, setSelectedStockName] = useState('');
  const [loading, setLoading]                 = useState(false);
  const [refreshTrigger, setRefreshTrigger]   = useState(0);
  const [forceRefresh, setForceRefresh]       = useState(false);

  const triggerRefresh = useCallback(() => {
    setForceRefresh(true);
    setRefreshTrigger(t => t + 1);
  }, []);
  const onRefreshDone = useCallback(() => setForceRefresh(false), []);

  const goToSector = useCallback(name => {
    setSelectedSector(name);
    setView('sector');
    setForceRefresh(false);
    setRefreshTrigger(0);
    window.scrollTo(0, 0);
  }, []);

  const goToStock = useCallback((symbol, name) => {
    setSelectedStock(symbol);
    setSelectedStockName(name || symbol);
    setView('stock');
    setForceRefresh(false);
    setRefreshTrigger(0);
    window.scrollTo(0, 0);
  }, []);

  const goToRotation = useCallback(() => {
    setView('rotation');
    setForceRefresh(false);
    setRefreshTrigger(0);
    window.scrollTo(0, 0);
  }, []);

  const goToSectorBack = useCallback(() => {
    setView('sector');
    setForceRefresh(false);
    setRefreshTrigger(0);
    window.scrollTo(0, 0);
  }, []);

  const sharedProps = { refreshTrigger, forceRefresh, onRefreshDone, setLoading };

  return (
    <>
      <Header
        view={view}
        sectorName={selectedSector}
        stockName={selectedStockName}
        date={date}
        onDateChange={setDate}
        onBackToRotation={goToRotation}
        onBackToSector={goToSectorBack}
        onRefresh={triggerRefresh}
        loading={loading}
      />
      <LoadingBar loading={loading} />
      {view === 'rotation' && (
        <RotationView date={date} onSelectSector={goToSector} {...sharedProps} />
      )}
      {view === 'sector' && selectedSector && (
        <SectorView
          sectorName={selectedSector}
          date={date}
          onBack={goToRotation}
          onSelectStock={goToStock}
          {...sharedProps}
        />
      )}
      {view === 'stock' && selectedStock && (
        <StockView
          symbol={selectedStock}
          stockName={selectedStockName}
          date={date}
          onBack={goToSectorBack}
          {...sharedProps}
        />
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
