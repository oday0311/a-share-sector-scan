// sections.jsx — 核心结论卡(3种样式) + 分项解读区块 + 买卖点推理
const fmtP = (x) => window.CL_DATA.fmtPrice(x);

const KIND_NAME = {
  B1: '第一类买点', B2: '第二类买点', B3: '第三类买点',
  S1: '第一类卖点', S2: '第二类卖点', S3: '第三类卖点'
};

// ---------- 推理步骤构造 ----------
function buildReason(sig, bars) {
  const d = (k) => (bars[k] ? bars[k].date : '—');
  const steps = [];
  const f = sig.facts;
  if (sig.kind === 'B1' || sig.kind === 'S1') {
    const buy = sig.kind === 'B1';
    const dv = f.div;
    steps.push({ tag: '前提', text: `此前为${buy ? '下跌' : '上涨'}走势:c段创出新${buy ? '低' : '高'} ${fmtP(dv.cPrice)}(${d(dv.cToK)}),越过前${buy ? '低' : '高'} ${fmtP(dv.bPrice)}(${d(dv.bToK)})。` });
    steps.push({ tag: '识别', text: `对比相邻两段同向走势的 MACD 柱面积:c段 ${dv.areaC.toFixed(2)},仅为 b段 ${dv.areaB.toFixed(2)} 的 ${(dv.ratio * 100).toFixed(0)}% —— 价格创新${buy ? '低' : '高'}而动能收缩,构成${dv.type}。` });
    steps.push({ tag: '结论', text: `背驰确认的转折点即${KIND_NAME[sig.kind]}(${fmtP(sig.price)})。其后若不再创新${buy ? '低' : '高'},可继续关注第二类${buy ? '买' : '卖'}点。` });
    steps.push({ tag: '风险', text: `背驰只说明原趋势力度衰竭,之后可能仅演化为盘整而非反转;${buy ? '跌破' : '升破'} ${fmtP(sig.price)} 则信号失效。` });
  } else if (sig.kind === 'B2' || sig.kind === 'S2') {
    const buy = sig.kind === 'B2';
    steps.push({ tag: '前提', text: `${buy ? '第一类买点' : '第一类卖点'}已出现于 ${d(f.ref.kIdx)},价格 ${fmtP(f.ref.price)}。` });
    steps.push({ tag: '识别', text: `其后第一次回抽${buy ? '低点' : '高点'} ${fmtP(f.pull)},${buy ? '高于前低' : '低于前高'} ${fmtP(f.ref.price)},未${buy ? '破前低' : '过前高'}。` });
    steps.push({ tag: '结论', text: `不${buy ? '回前低' : '过前高'}的首次回抽构成${KIND_NAME[sig.kind]},是对第一类${buy ? '买' : '卖'}点的确认。` });
    steps.push({ tag: '风险', text: `若后续回抽${buy ? '跌破' : '升破'} ${fmtP(f.ref.price)},该信号不成立,需按第一类${buy ? '买' : '卖'}点失效处理。` });
  } else {
    const buy = sig.kind === 'B3';
    const pv = f.pivot;
    steps.push({ tag: '前提', text: `中枢 [ZD ${fmtP(pv.zd)}, ZG ${fmtP(pv.zg)}] 已由 ${pv.strokes} 笔重叠构成(${d(pv.startK)} ~ ${d(pv.endK)})。` });
    steps.push({ tag: '识别', text: `价格向${buy ? '上' : '下'}离开中枢(${buy ? '高点' : '低点'} ${fmtP(f.breakPt.price)} ${buy ? '突破 ZG' : '跌破 ZD'}),随后首次回抽${buy ? '低点' : '高点'} ${fmtP(f.pull)} 未回到${buy ? ' ZG 之下' : ' ZD 之上'}。` });
    steps.push({ tag: '结论', text: `回抽不进入中枢区间,构成${KIND_NAME[sig.kind]};中枢${buy ? '上移或新生上涨中枢' : '下移或新生下跌中枢'}的概率较大。` });
    steps.push({ tag: '风险', text: `若回抽重新进入中枢区间(${buy ? '跌破' : '升破'} ${fmtP(buy ? pv.zg : pv.zd)}),信号失效,大概率转为中枢延伸。` });
  }
  return steps;
}

function SignalReason({ sig, bars, onClose }) {
  const steps = buildReason(sig, bars);
  const buy = sig.kind[0] === 'B';
  return (
    <div className="reason-panel" data-comment-anchor="signal-reason">
      <div className="reason-head">
        <span className="sig-dot" style={{ background: buy ? 'var(--up)' : 'var(--down)' }}>{sig.kind}</span>
        <div>
          <div className="reason-title">{sig.label} · {bars[sig.kIdx].date} · {fmtP(sig.price)}{sig.forming ? ' · 形成中' : ''}</div>
          <div className="reason-sub">缠论推理过程</div>
        </div>
        {onClose && <button className="reason-close" onClick={onClose} type="button">收起 ✕</button>}
      </div>
      <ol className="reason-steps">
        {steps.map((s, i) => (
          <li key={i}>
            <span className={'step-tag' + (s.tag === '风险' ? ' risk' : '')}>{s.tag}</span>
            <span className="step-text">{s.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------- 核心结论:样式一 横幅 ----------
function VerdictBanner({ v }) {
  return (
    <div className="verdict-banner" data-comment-anchor="verdict">
      <div className="vb-main">
        <p className="vb-headline">{v.headline}</p>
        <p className="vb-body">{v.body}</p>
      </div>
      <div className="vb-metas">
        {v.metas.map((m, i) => (
          <div className="vb-meta" key={i}>
            <span className="meta-k">{m.k}</span>
            <span className="meta-v" style={m.tone ? { color: m.tone } : null}>{m.v}</span>
            <span className="meta-note">{m.note}</span>
          </div>
        ))}
      </div>
      <div className="vb-risk"><span className="risk-flag">风险提示</span>{v.risk}</div>
    </div>
  );
}

// ---------- 核心结论:样式二 指标卡组 ----------
function VerdictCards({ v }) {
  return (
    <div className="verdict-cards" data-comment-anchor="verdict">
      <div className="vc-lead">
        <p className="vb-headline">{v.headline}</p>
        <p className="vb-body">{v.body}</p>
        <div className="vb-risk"><span className="risk-flag">风险提示</span>{v.risk}</div>
      </div>
      {v.metas.map((m, i) => (
        <div className="vc-card" key={i}>
          <span className="meta-k">{m.k}</span>
          <span className="vc-value" style={m.tone ? { color: m.tone } : null}>{m.v}</span>
          <span className="meta-note">{m.note}</span>
        </div>
      ))}
    </div>
  );
}

// ---------- 核心结论:样式三 研报批注 ----------
function VerdictNotes({ v }) {
  return (
    <div className="verdict-notes" data-comment-anchor="verdict">
      <div className="vn-left">
        <p className="vb-headline">{v.headline}</p>
        <p className="vb-body">{v.body}</p>
        <div className="vb-risk"><span className="risk-flag">风险提示</span>{v.risk}</div>
      </div>
      <div className="vn-right">
        {v.metas.map((m, i) => (
          <div className="vn-row" key={i}>
            <span className="meta-k">{m.k}</span>
            <div className="vn-cell">
              <span className="meta-v" style={m.tone ? { color: m.tone } : null}>{m.v}</span>
              <span className="meta-note">{m.note}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- 分项:结构统计 ----------
function StructurePanel({ an }) {
  const lastSeg = an.segs[an.segs.length - 1];
  const items = [
    { k: '顶分型 / 底分型', v: `${an.stats.tops} / ${an.stats.bottoms}`, note: '相邻三K线(包含处理后)的极值结构' },
    { k: '笔', v: String(an.stats.strokes), note: '相邻顶底分型连接,中间至少间隔1根独立K线' },
    { k: '线段', v: String(an.stats.segments), note: lastSeg ? `当前线段方向:${lastSeg.dir === 1 ? '向上' : '向下'}${lastSeg.confirmed ? '' : '(未完成)'}` : '—' },
    { k: '中枢', v: String(an.stats.pivots), note: '至少三笔重叠区间,虚线框标于主图' }
  ];
  return (
    <div className="panel" data-comment-anchor="structure">
      <h3 className="panel-title">结构识别</h3>
      <div className="struct-grid">
        {items.map((it, i) => (
          <div className="struct-item" key={i}>
            <span className="meta-k">{it.k}</span>
            <span className="struct-num">{it.v}</span>
            <span className="meta-note">{it.note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- 分项:中枢列表 ----------
function PivotPanel({ an, bars, lastClose }) {
  return (
    <div className="panel" data-comment-anchor="pivots">
      <h3 className="panel-title">中枢一览</h3>
      {an.pivots.length === 0 && <p className="empty-note">当前样本内未识别出有效中枢(三笔无重叠)。</p>}
      {an.pivots.map((pv, i) => {
        const isLast = i === an.pivots.length - 1;
        const rel = lastClose > pv.zg ? '现价位于其上方' : lastClose < pv.zd ? '现价位于其下方' : '现价仍在其区间内';
        return (
          <div className="pivot-row" key={i}>
            <span className="pivot-idx">{i + 1}</span>
            <div className="pivot-info">
              <span className="pivot-range">[{fmtP(pv.zd)} — {fmtP(pv.zg)}]</span>
              <span className="meta-note">{bars[pv.startK].date} ~ {bars[pv.endK].date} · {pv.strokes} 笔{isLast ? ' · ' + rel : ''}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- 分项:背驰分析 ----------
function DivergencePanel({ an }) {
  const d = an.divergence;
  return (
    <div className="panel" data-comment-anchor="divergence">
      <h3 className="panel-title">背驰分析</h3>
      {!d ? (
        <p className="empty-note">线段数量不足三段,暂无可比较的同向走势段。</p>
      ) : (
        <div>
          <p className="div-desc">
            最近一段{d.dir === -1 ? '下跌' : '上涨'}(c段)与前一同向段(b段)比较:
            价格{d.newExt ? `创出新${d.dir === -1 ? '低' : '高'}` : `未创新${d.dir === -1 ? '低' : '高'}`},
            MACD 柱面积{d.ratio < 1 ? `收缩至 ${(d.ratio * 100).toFixed(0)}%` : '未见收缩'}。
          </p>
          <div className="area-bars">
            <div className="area-row">
              <span className="meta-k">b段面积</span>
              <div className="area-track"><div className="area-fill b" style={{ width: '100%' }}></div></div>
              <span className="area-num">{d.areaB.toFixed(2)}</span>
            </div>
            <div className="area-row">
              <span className="meta-k">c段面积</span>
              <div className="area-track"><div className="area-fill c" style={{ width: Math.min(100, d.ratio * 100).toFixed(1) + '%' }}></div></div>
              <span className="area-num">{d.areaC.toFixed(2)}</span>
            </div>
          </div>
          <p className={'div-verdict' + (d.detected ? ' hit' : '')}>
            {d.detected
              ? `判定:构成${d.type}${d.confirmed ? '' : '(走势未完成,结论随新K线动态变化)'}`
              : '判定:未构成背驰,原方向走势动能尚未衰竭'}
          </p>
        </div>
      )}
    </div>
  );
}

// ---------- 分项:买卖点记录 ----------
function SignalListPanel({ an, bars, selectedId, onSelect }) {
  return (
    <div className="panel" data-comment-anchor="signals">
      <h3 className="panel-title">买卖点记录 <span className="panel-hint">点击行或图中标记展开推理</span></h3>
      {an.signals.length === 0 && <p className="empty-note">样本期内未识别出符合定义的三类买卖点。</p>}
      <div className="sig-list">
        {an.signals.map((s) => {
          const buy = s.kind[0] === 'B';
          const sel = selectedId === s.id;
          return (
            <React.Fragment key={s.id}>
              <button type="button" className={'sig-row' + (sel ? ' sel' : '')} onClick={() => onSelect(sel ? null : s)}>
                <span className="sig-dot" style={{ background: buy ? 'var(--up)' : 'var(--down)' }}>{s.kind}</span>
                <span className="sig-label">{s.label}{s.forming ? <em className="forming-tag">形成中</em> : null}</span>
                <span className="sig-date">{bars[s.kIdx].date}</span>
                <span className="sig-price">{fmtP(s.price)}</span>
                <span className={'sig-caret' + (sel ? ' open' : '')}>▾</span>
              </button>
              {sel && <SignalReason sig={s} bars={bars} onClose={null} />}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, {
  VerdictBanner, VerdictCards, VerdictNotes,
  StructurePanel, PivotPanel, DivergencePanel, SignalListPanel,
  SignalReason, buildReason, KIND_NAME
});
