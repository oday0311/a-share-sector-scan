// app.jsx — 缠论决策台主应用:真实行情搜索、后端分析、图表与推理展示
const { useState, useEffect, useRef } = React;
const CLD = window.CL_DATA;

const PERIODS = [
  { id: 'day', label: '日线' },
  { id: 'week', label: '周线' }
];

function SearchBox({ onPick }) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [mk, setMk] = useState('全部');
  const [list, setList] = useState(CLD.defaultStocks('全部'));
  const [loading, setLoading] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    const h = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  useEffect(() => {
    let alive = true;
    const query = q.trim();
    if (!query) {
      setList(CLD.defaultStocks(mk));
      return;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      CLD.searchStocks(query, mk)
        .then((items) => { if (alive) setList(items); })
        .catch(() => { if (alive) setList([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, 180);
    return () => { alive = false; clearTimeout(timer); };
  }, [q, mk]);

  const pick = (s) => {
    onPick(s);
    setOpen(false);
    setQ('');
  };

  return (
    <div className="searchbox" ref={boxRef}>
      <span className="search-icon">⌕</span>
      <input
        type="text"
        value={q}
        placeholder="输入 A股 / 港股 / 指数代码或名称,如 600519、腾讯控股"
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && list.length > 0) pick(list[0]);
          if (e.key === 'Escape') setOpen(false);
        }}
      />
      {open && (
        <div className="search-drop">
          <div className="search-chips">
            {['全部', 'A股', '港股', '指数'].map((m) => (
              <button key={m} type="button"
                className={'chip' + (mk === m ? ' on' : '')}
                onClick={() => setMk(m)}>{m}</button>
            ))}
          </div>
          {loading && <div className="search-empty">搜索中...</div>}
          {!loading && list.length === 0 && <div className="search-empty">未找到匹配标的(第一版暂不支持北交所)</div>}
          {!loading && list.map((s) => (
            <button key={s.symbol || s.code} type="button" className="sr-row" onClick={() => pick(s)}>
              <span className="sr-code">{s.code}</span>
              <span className="sr-name">{s.name}</span>
              <span className={'mtag m-' + (s.market === 'A股' ? 'a' : s.market === '港股' ? 'h' : 'i')}>{s.market}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SecHead({ no, title, hint }) {
  return (
    <div className="sec-head">
      <span className="sec-no">{no}</span>
      <h2 className="sec-title">{title}</h2>
      {hint && <span className="sec-hint">{hint}</span>}
      <span className="sec-rule"></span>
    </div>
  );
}

function Legend({ showFractals }) {
  return (
    <div className="legend">
      <span className="lg"><i className="lg-stroke"></i>笔</span>
      <span className="lg"><i className="lg-seg"></i>线段</span>
      <span className="lg"><i className="lg-pivot"></i>中枢</span>
      <span className="lg"><i className="lg-div"></i>背驰</span>
      {showFractals && <span className="lg"><i className="lg-frac">▵</i>分型</span>}
      <span className="lg"><i className="lg-sig" style={{ background: 'var(--up)' }}>B</i>买点</span>
      <span className="lg"><i className="lg-sig" style={{ background: 'var(--down)' }}>S</i>卖点</span>
    </div>
  );
}

function EmptyState({ error, loading }) {
  return (
    <div className="empty-state">
      <div className="empty-mark">缠</div>
      <div>
        <h2>{loading ? '正在拉取行情并识别缠论结构' : '暂时无法完成缠论分析'}</h2>
        <p>{loading ? '正在读取真实K线、计算分型/笔/线段/中枢/背驰。' : (error || '请稍后重试或切换标的。')}</p>
      </div>
    </div>
  );
}

function App() {
  const [stock, setStock] = useState(CLD.STOCKS.find((s) => s.symbol === 'sh600519') || CLD.STOCKS[0]);
  const [period, setPeriod] = useState('day');
  const [date, setDate] = useState(CLD.todayISO());
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sel, setSel] = useState(null);
  const [showFractals, setShowFractals] = useState(true);
  const [shadeDiv, setShadeDiv] = useState(true);

  const load = (force = false) => {
    setLoading(true);
    setError('');
    CLD.fetchAnalysis(stock.symbol || stock.code, period, date, force)
      .then((data) => {
        setPayload(data);
        if (data.meta && data.meta.dataStatus === 'error') setError(data.meta.message || '数据源暂不可用');
      })
      .catch((err) => {
        setError(err.message || '数据加载失败');
        setPayload(null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setSel(null);
    load(false);
  }, [stock.symbol, period, date]);

  const data = payload || {};
  const bars = data.bars || [];
  const an = data.analysis || null;
  const verdict = data.verdict || null;
  const serverStock = data.stock || stock;
  const last = bars[bars.length - 1];
  const prev = bars[bars.length - 2];
  const chg = last && prev && prev.close ? (last.close - prev.close) / prev.close : 0;
  const redUp = true;
  const up = redUp ? '#bf3a30' : '#1e8a5e';
  const dn = redUp ? '#1e8a5e' : '#bf3a30';
  const periodLabel = PERIODS.find((p) => p.id === period).label;
  const statusText = data.meta
    ? `${data.meta.dataProvider || '数据源'}${data.meta.cacheHit ? ' · 本地缓存' : ''} · AI ${data.meta.aiStatus || 'fallback'}`
    : '等待数据';

  return (
    <div className="page" style={{ '--up': up, '--down': dn }} data-screen-label="缠论分析决策台">
      <header className="top">
        <a className="brand" href="/sector" title="返回板块扫描">
          <span className="brand-mark">缠</span>
          <span className="brand-text">
            <strong>缠论决策台</strong>
            <small>ChanLun Decision Desk</small>
          </span>
        </a>
        <nav className="module-tabs" aria-label="功能模块">
          <a href="/sector">板块扫描</a>
          <a className="active" href="/chanlun">缠论分析</a>
        </nav>
        <SearchBox onPick={setStock} />
        <div className="top-actions">
          <label className="date-field">
            <span>日期</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <button type="button" className="mini-btn" onClick={() => load(true)} disabled={loading}>重新分析</button>
        </div>
        <div className="top-meta">数据截至 {data.meta ? data.meta.tradeDate : '—'}<em>{statusText}</em></div>
      </header>

      {(!bars.length || !an || !verdict) ? (
        <EmptyState loading={loading} error={error} />
      ) : (
        <>
          {error && <div className="error-banner">{error}</div>}
          <section className="masthead">
            <div className="mh-left">
              <h1 className="stock-name">{serverStock.name}</h1>
              <div className="stock-chips">
                <span className="code-chip">{serverStock.code}</span>
                <span className={'mtag m-' + (serverStock.market === 'A股' ? 'a' : serverStock.market === '港股' ? 'h' : 'i')}>{serverStock.market}</span>
                <span className="period-chip">{periodLabel} · {bars.length} 根真实K线</span>
              </div>
            </div>
            <div className="mh-right">
              <div className="price-line">
                <span className="price-unit">{serverStock.unit !== '点' ? serverStock.unit : ''}</span>
                <span className="price-big" style={{ color: chg >= 0 ? 'var(--up)' : 'var(--down)' }}>{CLD.fmtPrice(last.close)}</span>
                <span className="chg-pill" style={{ color: chg >= 0 ? 'var(--up)' : 'var(--down)' }}>
                  {CLD.fmtPct(chg)}
                </span>
              </div>
              <div className="price-sub">
                今开 {CLD.fmtPrice(last.open)} · 最高 {CLD.fmtPrice(last.high)} · 最低 {CLD.fmtPrice(last.low)} · 量 {CLD.fmtVol(last.volume)}
              </div>
            </div>
          </section>

          <SecHead no="壹" title="核心结论" hint="技术结构 + AI复盘摘要" />
          <VerdictBanner v={verdict} />
          {verdict.notes && verdict.notes.length > 0 && (
            <div className="ai-notes">
              {verdict.notes.map((note, idx) => <span key={idx}>{note}</span>)}
            </div>
          )}

          <SecHead no="贰" title="走势结构" hint="K线 · 分型 · 笔 · 线段 · 中枢 · 背驰 · 买卖点" />
          <div className="card chart-card">
            <div className="chart-bar">
              <div className="ptabs">
                {PERIODS.map((p) => (
                  <button key={p.id} type="button"
                    className={'ptab' + (period === p.id ? ' on' : '')}
                    onClick={() => setPeriod(p.id)}>{p.label}</button>
                ))}
              </div>
              <div className="chart-tools">
                <button type="button" className={'tool-toggle' + (showFractals ? ' on' : '')} onClick={() => setShowFractals(!showFractals)}>分型</button>
                <button type="button" className={'tool-toggle' + (shadeDiv ? ' on' : '')} onClick={() => setShadeDiv(!shadeDiv)}>背驰区间</button>
              </div>
              <Legend showFractals={showFractals} />
            </div>
            <ChanChart
              bars={bars} an={an}
              showFractals={showFractals} shadeDiv={shadeDiv}
              selectedId={sel ? sel.sig.id : null}
              onSelectSignal={(s) => setSel({ sig: s, src: 'chart' })}
            />
            {sel && sel.src === 'chart' && (
              <SignalReason sig={sel.sig} bars={bars} onClose={() => setSel(null)} />
            )}
          </div>

          <SecHead no="叁" title="分项解读" hint="结构 · 中枢 · 背驰" />
          <div className="breakdown">
            <StructurePanel an={an} />
            <PivotPanel an={an} bars={bars} lastClose={last.close} />
            <DivergencePanel an={an} />
          </div>

          <SecHead no="肆" title="买卖点推理" hint="点击展开每个信号的缠论推理过程" />
          <SignalListPanel
            an={an} bars={bars}
            selectedId={sel ? sel.sig.id : null}
            onSelect={(s) => setSel(s ? { sig: s, src: 'list' } : null)}
          />
        </>
      )}

      <footer className="foot">
        <p><strong>免责声明</strong>本页为缠论(缠中说禅)技术结构的自动识别与复盘展示;分型、笔、线段、中枢与买卖点判定存在级别与主观性差异,仅供学习研究,不构成任何投资建议。股市有风险,投资需谨慎。</p>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
