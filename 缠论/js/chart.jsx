// chart.jsx — 缠论结构图:K线 + 分型 + 笔 + 线段 + 中枢 + 背驰 + 买卖点 + 十字光标 + MACD + 成交量
const CHART_W = 1180;
const CH_PAD_L = 10, CH_PAD_R = 64, CH_PAD_T = 16;
const MAIN_H = 392, MACD_T = 424, MACD_H = 102, VOL_T = 540, VOL_H = 78, AXIS_Y = 636, CHART_H = 646;

function niceStep(raw) {
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const r = raw / mag;
  if (r < 1.5) return mag;
  if (r < 3.5) return 2.5 * mag;
  if (r < 7.5) return 5 * mag;
  return 10 * mag;
}

function ChanChart({ bars, an, showFractals, shadeDiv, onSelectSignal, selectedId }) {
  const { useMemo, useState, useRef } = React;
  const fmtP = window.CL_DATA.fmtPrice;
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);

  const n = bars.length;
  const geo = useMemo(() => {
    const slot = (CHART_W - CH_PAD_L - CH_PAD_R) / n;
    let minP = Infinity, maxP = -Infinity, maxV = 0;
    for (const b of bars) {
      if (b.low < minP) minP = b.low;
      if (b.high > maxP) maxP = b.high;
      if (b.volume > maxV) maxV = b.volume;
    }
    const pad = (maxP - minP) * 0.06;
    minP -= pad; maxP += pad;
    let maxM = 0;
    for (let i = 0; i < n; i++) {
      maxM = Math.max(maxM, Math.abs(an.macd.dif[i]), Math.abs(an.macd.dea[i]), Math.abs(an.macd.hist[i]));
    }
    return { slot, minP, maxP, maxV, maxM: maxM || 1 };
  }, [bars, an]);

  const x = (i) => CH_PAD_L + geo.slot * (i + 0.5);
  const py = (v) => CH_PAD_T + ((geo.maxP - v) / (geo.maxP - geo.minP)) * (MAIN_H - CH_PAD_T);
  const my = (v) => MACD_T + MACD_H / 2 - (v / geo.maxM) * (MACD_H / 2 - 4);
  const vy = (v) => VOL_T + VOL_H - (v / geo.maxV) * (VOL_H - 6);

  // 价格刻度
  const ticks = useMemo(() => {
    const step = niceStep((geo.maxP - geo.minP) / 4.5);
    const out = [];
    for (let v = Math.ceil(geo.minP / step) * step; v < geo.maxP; v += step) out.push(v);
    return out;
  }, [geo]);

  const dateTickEvery = Math.ceil(n / 8);

  // 鼠标 → viewBox 坐标
  const toVB = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    const sc = r.width / CHART_W;
    return { vx: (e.clientX - r.left) / sc, vyy: (e.clientY - r.top) / sc };
  };
  const onMove = (e) => {
    const { vx, vyy } = toVB(e);
    let i = Math.round((vx - CH_PAD_L) / geo.slot - 0.5);
    i = Math.max(0, Math.min(n - 1, i));
    setHover({ i, y: vyy });
  };

  // 买卖点同列堆叠偏移
  const sigOffsets = useMemo(() => {
    const cnt = {};
    return an.signals.map((s) => {
      cnt[s.kIdx] = (cnt[s.kIdx] || 0) + 1;
      return (cnt[s.kIdx] - 1) * 24;
    });
  }, [an]);

  const candleW = Math.max(2, geo.slot * 0.62);
  const upC = 'var(--up)', dnC = 'var(--down)';
  const div = an.divergence;

  return (
    <div style={{ position: 'relative' }}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        style={{ width: '100%', display: 'block', cursor: 'crosshair' }}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* 网格 + 价格刻度 */}
        {ticks.map((v, idx) => (
          <g key={'t' + idx}>
            <line x1={CH_PAD_L} x2={CHART_W - CH_PAD_R} y1={py(v)} y2={py(v)} stroke="#e7e2d6" strokeWidth="1" />
            <text x={CHART_W - CH_PAD_R + 8} y={py(v) + 4} fontSize="11" fill="#8a8676" fontFamily="var(--mono)">{fmtP(v)}</text>
          </g>
        ))}
        {/* 日期刻度 */}
        {bars.map((b, i) => (i % dateTickEvery === 0 && i > 2 && i < n - 3) ? (
          <g key={'d' + i}>
            <line x1={x(i)} x2={x(i)} y1={CH_PAD_T} y2={VOL_T + VOL_H} stroke="#efeadd" strokeWidth="1" />
            <text x={x(i)} y={AXIS_Y} fontSize="11" fill="#8a8676" textAnchor="middle" fontFamily="var(--mono)">
              {b.date.length > 9 ? b.date.slice(2) : b.date}
            </text>
          </g>
        ) : null)}

        {/* 中枢 */}
        {an.pivots.map((pv, idx) => (
          <g key={'pv' + idx}>
            <rect x={x(0) + (pv.startK - 0.45) * geo.slot} y={py(pv.zg)}
              width={(pv.endK - pv.startK + 0.9) * geo.slot} height={Math.max(2, py(pv.zd) - py(pv.zg))}
              fill="#9a7b2f" fillOpacity="0.08" stroke="#9a7b2f" strokeOpacity="0.55" strokeWidth="1.2" strokeDasharray="5 4" />
            <text x={x(0) + (pv.startK - 0.45) * geo.slot + 6} y={py(pv.zg) - 6} fontSize="11" fill="#9a7b2f" fontFamily="var(--sans)">
              中枢 {idx + 1} · ZG {fmtP(pv.zg)} / ZD {fmtP(pv.zd)}
            </text>
          </g>
        ))}

        {/* K线 */}
        {bars.map((b, i) => {
          const up = b.close >= b.open;
          const c = up ? upC : dnC;
          const bodyT = py(Math.max(b.open, b.close));
          const bodyH = Math.max(1.2, Math.abs(py(b.open) - py(b.close)));
          return (
            <g key={'k' + i}>
              <line x1={x(i)} x2={x(i)} y1={py(b.high)} y2={py(b.low)} stroke={c} strokeWidth="1" />
              <rect x={x(i) - candleW / 2} y={bodyT} width={candleW} height={bodyH}
                fill={up ? '#fffdf8' : c} stroke={c} strokeWidth="1" />
            </g>
          );
        })}

        {/* 分型标记 */}
        {showFractals && an.fractals.map((f, idx) => f.type === 'top' ? (
          <path key={'f' + idx} d={`M ${x(f.kIdx) - 3.6} ${py(f.price) - 11} l 3.6 -5.4 l 3.6 5.4 z`}
            fill="none" stroke="#b0a890" strokeWidth="1.1" />
        ) : (
          <path key={'f' + idx} d={`M ${x(f.kIdx) - 3.6} ${py(f.price) + 11} l 3.6 5.4 l 3.6 -5.4 z`}
            fill="none" stroke="#b0a890" strokeWidth="1.1" />
        ))}

        {/* 笔 */}
        {an.pts.length > 1 && (
          <polyline points={an.pts.map((p) => `${x(p.kIdx)},${py(p.price)}`).join(' ')}
            fill="none" stroke="#3d4350" strokeWidth="1.4" strokeOpacity="0.8" />
        )}

        {/* 线段 */}
        {an.segs.map((sg, idx) => (
          <line key={'sg' + idx}
            x1={x(an.pts[sg.from].kIdx)} y1={py(an.pts[sg.from].price)}
            x2={x(an.pts[sg.to].kIdx)} y2={py(an.pts[sg.to].price)}
            stroke="#2c4a73" strokeWidth="2.6" strokeOpacity="0.85"
            strokeDasharray={sg.confirmed ? 'none' : '7 5'} />
        ))}

        {/* 背驰标记 */}
        {div && div.detected && (
          <g>
            <line x1={x(div.bToK)} y1={py(div.bPrice)} x2={x(div.cToK)} y2={py(div.cPrice)}
              stroke="#a63a32" strokeWidth="1.6" strokeDasharray="6 4" />
            <g transform={`translate(${Math.min(x(div.cToK) + 10, CHART_W - 130)}, ${py(div.cPrice) + (div.dir === -1 ? 26 : -34)})`}>
              <rect x="0" y="0" width="86" height="22" rx="3" fill="#a63a32" />
              <text x="43" y="15" fontSize="12" fill="#fdf9f0" textAnchor="middle" fontFamily="var(--sans)">
                {div.type}{div.confirmed ? '' : '·形成中'}
              </text>
            </g>
          </g>
        )}

        {/* 买卖点 */}
        {an.signals.map((s, idx) => {
          const buy = s.kind[0] === 'B';
          const b = bars[s.kIdx];
          const yy = buy ? py(b.low) + 24 + sigOffsets[idx] : py(b.high) - 24 - sigOffsets[idx];
          const sel = selectedId === s.id;
          return (
            <g key={s.id} transform={`translate(${x(s.kIdx)}, ${yy})`}
              style={{ cursor: 'pointer' }}
              onClick={(e) => { e.stopPropagation(); onSelectSignal(s); }}>
              <line x1="0" y1={buy ? -12 : 12} x2="0" y2={buy ? -20 : 20} stroke={buy ? upC : dnC} strokeWidth="1.2" />
              {sel && <circle r="14.5" fill="none" stroke={buy ? upC : dnC} strokeWidth="1.4" strokeDasharray="3 2.5" />}
              <circle r="10.5" fill={buy ? upC : dnC} />
              <text y="3.8" fontSize="10.5" fill="#fdf9f0" textAnchor="middle" fontWeight="600" fontFamily="var(--mono)">{s.kind}</text>
            </g>
          );
        })}

        {/* ---- MACD 副图 ---- */}
        <line x1={CH_PAD_L} x2={CHART_W - CH_PAD_R} y1={MACD_T + MACD_H / 2} y2={MACD_T + MACD_H / 2} stroke="#e7e2d6" />
        <text x={CH_PAD_L + 2} y={MACD_T + 12} fontSize="11" fill="#8a8676" fontFamily="var(--sans)">MACD (12, 26, 9)</text>
        {shadeDiv && div && div.detected && (
          <g>
            <rect x={x(div.bFromK)} y={MACD_T} width={Math.max(4, x(div.bToK) - x(div.bFromK))} height={MACD_H}
              fill="#2c4a73" fillOpacity="0.07" />
            <text x={(x(div.bFromK) + x(div.bToK)) / 2} y={MACD_T + 12} fontSize="10" fill="#2c4a73" textAnchor="middle" fontFamily="var(--mono)">b段</text>
            <rect x={x(div.cFromK)} y={MACD_T} width={Math.max(4, x(div.cToK) - x(div.cFromK))} height={MACD_H}
              fill="#a63a32" fillOpacity="0.07" />
            <text x={(x(div.cFromK) + x(div.cToK)) / 2} y={MACD_T + 12} fontSize="10" fill="#a63a32" textAnchor="middle" fontFamily="var(--mono)">c段</text>
          </g>
        )}
        {bars.map((b, i) => {
          const h = an.macd.hist[i];
          return (
            <rect key={'m' + i} x={x(i) - candleW / 2} y={h >= 0 ? my(h) : my(0)}
              width={candleW} height={Math.max(0.8, Math.abs(my(h) - my(0)))}
              fill={h >= 0 ? upC : dnC} fillOpacity="0.75" />
          );
        })}
        <polyline points={bars.map((b, i) => `${x(i)},${my(an.macd.dif[i])}`).join(' ')} fill="none" stroke="#2c4a73" strokeWidth="1.3" />
        <polyline points={bars.map((b, i) => `${x(i)},${my(an.macd.dea[i])}`).join(' ')} fill="none" stroke="#b0a890" strokeWidth="1.3" />

        {/* ---- 成交量 ---- */}
        <text x={CH_PAD_L + 2} y={VOL_T + 12} fontSize="11" fill="#8a8676" fontFamily="var(--sans)">成交量</text>
        {bars.map((b, i) => (
          <rect key={'v' + i} x={x(i) - candleW / 2} y={vy(b.volume)} width={candleW}
            height={VOL_T + VOL_H - vy(b.volume)}
            fill={b.close >= b.open ? upC : dnC} fillOpacity="0.5" />
        ))}

        {/* ---- 十字光标 ---- */}
        {hover && (
          <g pointerEvents="none">
            <line x1={x(hover.i)} x2={x(hover.i)} y1={CH_PAD_T} y2={VOL_T + VOL_H} stroke="#3d4350" strokeWidth="0.8" strokeDasharray="4 3" />
            {hover.y > CH_PAD_T && hover.y < MAIN_H && (
              <g>
                <line x1={CH_PAD_L} x2={CHART_W - CH_PAD_R} y1={hover.y} y2={hover.y} stroke="#3d4350" strokeWidth="0.8" strokeDasharray="4 3" />
                <rect x={CHART_W - CH_PAD_R + 2} y={hover.y - 9} width={CH_PAD_R - 4} height="18" rx="2" fill="#3d4350" />
                <text x={CHART_W - CH_PAD_R / 2} y={hover.y + 4} fontSize="11" fill="#fdf9f0" textAnchor="middle" fontFamily="var(--mono)">
                  {fmtP(geo.maxP - ((hover.y - CH_PAD_T) / (MAIN_H - CH_PAD_T)) * (geo.maxP - geo.minP))}
                </text>
              </g>
            )}
          </g>
        )}
      </svg>

      {/* 悬停信息卡 */}
      {hover && (() => {
        const b = bars[hover.i];
        const prev = bars[hover.i - 1] || b;
        const chg = (b.close - prev.close) / prev.close;
        const left = hover.i < n * 0.62;
        const rows = [
          ['开', fmtP(b.open)], ['高', fmtP(b.high)], ['低', fmtP(b.low)], ['收', fmtP(b.close)],
          ['涨跌', window.CL_DATA.fmtPct(chg)], ['量', window.CL_DATA.fmtVol(b.volume)],
          ['DIF', an.macd.dif[hover.i].toFixed(3)], ['DEA', an.macd.dea[hover.i].toFixed(3)]
        ];
        return (
          <div className="cl-tooltip" style={{ [left ? 'right' : 'left']: '14px' }}>
            <div className="cl-tooltip-date">{b.date}</div>
            {rows.map((r, i) => (
              <div className="cl-tooltip-row" key={i}>
                <span>{r[0]}</span>
                <b style={r[0] === '涨跌' ? { color: chg >= 0 ? 'var(--up)' : 'var(--down)' } : null}>{r[1]}</b>
              </div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}

window.ChanChart = ChanChart;
