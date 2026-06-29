/* === Stock Decision App === */
const { useState, useEffect, useRef, useCallback, useMemo } = React;

/* ── Strategy definitions ── */
const STRATEGIES = {
  turtle: { name: '海龟突破', desc: '突破20日最高价买入' },
  ma_volume: { name: '均线放量', desc: 'MA5上穿MA20且放量' },
  rps_breakout: { name: 'RPS突破', desc: '相对强度突破且收盘新高' },
  high_tight_flag: { name: '高而窄旗形', desc: '旗杆涨幅≥90%，旗形回撤<25%' },
};

const TIER_MAP = {
  3: { label: '强烈推荐', cls: 'tier-strong-buy' },
  2: { label: '推荐', cls: 'tier-buy' },
  1: { label: '中性', cls: 'tier-neutral' },
  0: { label: '无信号', cls: 'tier-no-signal' },
  '-1': { label: '回避', cls: 'tier-sell' },
};

/* ── Utility functions ── */
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' +
    String(d.getMonth() + 1).padStart(2, '0') + '-' +
    String(d.getDate()).padStart(2, '0');
}

function calcMa(closes, period) {
  const out = new Array(closes.length).fill(null);
  let sum = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    if (i >= period - 1) out[i] = +(sum / period).toFixed(2);
  }
  return out;
}

/* ── K-line drawing ── */
function drawKline(canvas, klines, signals) {
  if (!canvas || !klines || !klines.length) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth;
  const H = canvas.clientHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);

  const pad = { top: 20, bottom: 40, left: 0, right: 0 };
  const candleW = Math.max(3, (W - pad.left - pad.right) / klines.length * 0.7);
  const gap = (W - pad.left - pad.right) / klines.length;

  let minP = Infinity, maxP = -Infinity;
  klines.forEach(k => {
    minP = Math.min(minP, k.low);
    maxP = Math.max(maxP, k.high);
  });
  const pRange = maxP - minP || 1;
  const yScale = (H - pad.top - pad.bottom) / pRange;
  const yOf = p => H - pad.bottom - (p - minP) * yScale;

  ctx.strokeStyle = '#e4dfd2';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + (H - pad.top - pad.bottom) * i / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = '#9b9da2';
    ctx.font = '10px IBM Plex Mono';
    ctx.textAlign = 'right';
    ctx.fillText((maxP - pRange * i / 4).toFixed(2), W - 4, y - 4);
  }

  klines.forEach((k, i) => {
    const x = pad.left + gap * i + gap / 2;
    const isUp = k.close >= k.open;
    const color = isUp ? '#bf3a30' : '#1e8a5e';
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, yOf(k.high));
    ctx.lineTo(x, yOf(k.low));
    ctx.stroke();
    ctx.fillStyle = isUp ? '#bf3a30' : '#1e8a5e';
    const bodyTop = yOf(Math.max(k.open, k.close));
    const bodyBot = yOf(Math.min(k.open, k.close));
    ctx.fillRect(x - candleW / 2, bodyTop, candleW, Math.max(1, bodyBot - bodyTop));
  });

  const maxVol = Math.max(...klines.map(k => k.vol));
  const volH = 50;
  klines.forEach((k, i) => {
    const x = pad.left + gap * i + gap / 2;
    const isUp = k.close >= k.open;
    const h = (k.vol / maxVol) * volH;
    ctx.fillStyle = isUp ? 'rgba(191,58,48,0.3)' : 'rgba(30,138,94,0.3)';
    ctx.fillRect(x - candleW / 2, H - h, candleW, h);
  });

  if (signals) {
    signals.forEach(sig => {
      const idx = klines.findIndex(k => k.date === sig.date);
      if (idx < 0) return;
      const x = pad.left + gap * idx + gap / 2;
      const y = yOf(klines[idx].low) - 15;
      ctx.fillStyle = sig.type === 'buy' ? '#bf3a30' : '#1e8a5e';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(sig.type === 'buy' ? '▲' : '▼', x, y);
    });
  }

  ctx.fillStyle = '#9b9da2';
  ctx.font = '10px IBM Plex Mono';
  ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(klines.length / 8));
  for (let i = 0; i < klines.length; i += step) {
    const x = pad.left + gap * i + gap / 2;
    ctx.fillText(klines[i].date.slice(5), x, H - 5);
  }
}

/* ── Stock List Component ── */
function StockList({ stocks, selectedCode, onSelect, loading }) {
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('score');
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = useMemo(() => {
    let list = stocks;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(s =>
        s.code.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q)
      );
    }
    list = [...list].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey];
      if (typeof va === 'string') {
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      va = va ?? 0; vb = vb ?? 0;
      return sortAsc ? va - vb : vb - va;
    });
    return list;
  }, [stocks, search, sortKey, sortAsc]);

  function handleSort(key) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <span>正在分析股票列表...</span>
      </div>
    );
  }

  return (
    <div>
      <div className="stock-list-header">
        <h2>个股决策看板</h2>
        <span className="stock-count">{stocks.length} 只股票</span>
      </div>
      <div className="search-box">
        <input
          className="search-input"
          placeholder="搜索股票代码或名称..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>
      <div className="stock-table-wrap">
        <table className="stock-table">
          <thead>
            <tr>
              <th className="sortable" onClick={() => handleSort('code')}>
                代码 {sortKey === 'code' && <span className="arr">{sortAsc ? '↑' : '↓'}</span>}
              </th>
              <th className="sortable" onClick={() => handleSort('name')}>
                名称 {sortKey === 'name' && <span className="arr">{sortAsc ? '↑' : '↓'}</span>}
              </th>
              <th className="sortable" onClick={() => handleSort('score')}>
                综合评分 {sortKey === 'score' && <span className="arr">{sortAsc ? '↑' : '↓'}</span>}
              </th>
              <th>策略信号</th>
              <th className="sortable" onClick={() => handleSort('price')}>
                最新价 {sortKey === 'price' && <span className="arr">{sortAsc ? '↑' : '↓'}</span>}
              </th>
              <th className="sortable" onClick={() => handleSort('change')}>
                涨跌幅 {sortKey === 'change' && <span className="arr">{sortAsc ? '↑' : '↓'}</span>}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => {
              const tier = s.score >= 3 ? 3 : s.score >= 2 ? 2 : s.score >= 1 ? 1 : s.score === 0 ? 0 : -1;
              const tierInfo = TIER_MAP[String(tier)];
              return (
                <tr
                  key={s.code}
                  className={selectedCode === s.code ? 'selected' : ''}
                  onClick={() => onSelect(s.code)}
                  style={{ cursor: 'pointer' }}
                >
                  <td><span className="stock-code">{s.code}</span></td>
                  <td><span className="stock-name">{s.name}</span></td>
                  <td>
                    <span className={`composite-score ${s.score > 0 ? 'up' : s.score < 0 ? 'down' : 'flat'}`}>
                      {s.score ?? '-'}
                    </span>
                    <span className={`tier ${tierInfo.cls}`} style={{ marginLeft: 8 }}>
                      {tierInfo.label}
                    </span>
                  </td>
                  <td>
                    {Object.entries(s.strategies || {}).map(([k, v]) => (
                      <span key={k} className={`strategy-tag ${v ? 'pass' : 'fail'}`}>
                        {STRATEGIES[k]?.name || k}
                      </span>
                    ))}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>
                    {s.price?.toFixed(2) ?? '-'}
                  </td>
                  <td style={{
                    fontFamily: 'var(--mono)', fontWeight: 700,
                    color: (s.change ?? 0) > 0 ? 'var(--up)' : (s.change ?? 0) < 0 ? 'var(--down)' : 'var(--ink2)'
                  }}>
                    {s.change != null ? (s.change > 0 ? '+' : '') + s.change.toFixed(2) + '%' : '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Stock Detail Component ── */
function StockDetail({ code, data, loading }) {
  const klineRef = useRef(null);

  useEffect(() => {
    if (!data || !data.klines) return;
    const timer = setTimeout(() => {
      drawKline(klineRef.current, data.klines, data.signals);
    }, 50);
    return () => clearTimeout(timer);
  }, [data]);

  if (loading) {
    return (
      <div className="loading-state">
        <div className="spinner" />
        <span>正在加载 {code} 详细数据...</span>
      </div>
    );
  }

  if (!data) return null;

  const tier = data.score >= 3 ? 3 : data.score >= 2 ? 2 : data.score >= 1 ? 1 : data.score === 0 ? 0 : -1;
  const tierInfo = TIER_MAP[String(tier)];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <h2 style={{ font: '700 22px/1.3 var(--serif)' }}>{data.name}</h2>
        <span style={{ font: '500 14px/1 var(--mono)', color: 'var(--ink2)' }}>{data.code}</span>
        <span className={`tier ${tierInfo.cls}`} style={{ fontSize: 13, padding: '4px 12px' }}>
          {tierInfo.label}
        </span>
        <span className={`composite-score ${data.score > 0 ? 'up' : data.score < 0 ? 'down' : 'flat'}`}
          style={{ fontSize: 22, marginLeft: 'auto' }}>
          综合评分: {data.score}
        </span>
      </div>

      <div className="kline-container">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <span style={{ font: '700 11px/1 var(--mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink2)' }}>
            K线走势
          </span>
          {data.ma && (
            <div style={{ display: 'flex', gap: 12 }}>
              {data.ma.map(m => (
                <span key={m.label} style={{
                  font: '500 11px/1 var(--mono)',
                  color: m.label === 'MA5' ? '#bf3a30' : m.label === 'MA10' ? '#2c4a73' : '#9a7b2f'
                }}>
                  {m.label}: {m.value?.toFixed(2)}
                </span>
              ))}
            </div>
          )}
        </div>
        <canvas ref={klineRef} style={{ width: '100%', height: 300 }} />
      </div>

      <div className="detail-panel">
        <div className="detail-card">
          <h3>策略信号</h3>
          {Object.entries(data.strategies || {}).map(([key, passed]) => (
            <div key={key} className="factor-row">
              <span className="factor-label">{STRATEGIES[key]?.name || key}</span>
              <span className={`strategy-tag ${passed ? 'pass' : 'fail'}`}>
                {passed ? '通过' : '未通过'}
              </span>
            </div>
          ))}
        </div>

        <div className="detail-card">
          <h3>技术指标</h3>
          {data.ma && data.ma.map(m => (
            <div key={m.label} className="factor-row">
              <span className="factor-label">{m.label}</span>
              <span className="factor-value">{m.value?.toFixed(2) ?? '-'}</span>
            </div>
          ))}
          {data.details && Object.entries(data.details).map(([k, v]) => (
            <div key={k} className="factor-row">
              <span className="factor-label">{k}</span>
              <span className="factor-value">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
            </div>
          ))}
        </div>
      </div>

      {data.recommendation && (
        <div className="recommendation-box">
          <h3>投资建议</h3>
          <div className="recommendation-text">{data.recommendation.text}</div>
          <div className="recommendation-metas">
            {data.recommendation.metas && Object.entries(data.recommendation.metas).map(([k, v]) => (
              <span key={k} className="recommendation-meta">{k}: {v}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main App ── */
function App() {
  const [stocks, setStocks] = useState([]);
  const [selectedCode, setSelectedCode] = useState(null);
  const [stockDetail, setStockDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [date, setDate] = useState(todayStr());
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [taskId, setTaskId] = useState('');
  const [progress, setProgress] = useState({ done: 0, total: 0, percent: 0, current: null, status: 'idle' });
  const pollingRef = useRef(null);

  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  useEffect(() => {
    setLoadingList(true);
    fetch('/api/stock-decision/list')
      .then(r => r.json())
      .then(data => {
        if (data.stocks) setStocks(data.stocks);
        setLoadingList(false);
      })
      .catch(() => setLoadingList(false));
  }, []);

  const pollTask = useCallback((currentTaskId) => {
    fetch('/api/stock-decision/analyze/status?task_id=' + encodeURIComponent(currentTaskId))
      .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('进度获取失败(' + r.status + ')'));
        return data;
      })
      .then(data => {
        setProgress({
          done: data.done || 0,
          total: data.total || 0,
          percent: data.percent || 0,
          current: data.current || null,
          status: data.status || 'running',
        });
        if (Array.isArray(data.results) && data.results.length) {
          setStocks(data.results);
        }
        if (data.status === 'completed') {
          clearPolling();
          setAnalyzing(false);
          setTaskId('');
        } else if (data.status === 'failed') {
          clearPolling();
          setAnalyzing(false);
          setTaskId('');
          setError(data.error || '批量分析失败');
        }
      })
      .catch(err => {
        clearPolling();
        setAnalyzing(false);
        setTaskId('');
        setError(err?.message || '进度获取失败，请稍后重试');
      });
  }, [clearPolling]);

  useEffect(() => {
    if (!taskId) return undefined;
    clearPolling();
    pollTask(taskId);
    pollingRef.current = window.setInterval(() => pollTask(taskId), 1000);
    return () => clearPolling();
  }, [taskId, pollTask, clearPolling]);

  useEffect(() => () => clearPolling(), [clearPolling]);

  const handleAnalyze = useCallback(() => {
    clearPolling();
    setAnalyzing(true);
    setError('');
    setProgress({ done: 0, total: 0, percent: 0, current: null, status: 'pending' });
    fetch('/api/stock-decision/analyze?date=' + encodeURIComponent(date))
      .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('分析启动失败(' + r.status + ')'));
        return data;
      })
      .then(data => {
        setTaskId(data.task_id || '');
        setProgress({
          done: data.done || 0,
          total: data.total || 0,
          percent: data.percent || 0,
          current: data.current || null,
          status: data.status || 'pending',
        });
      })
      .catch(err => {
        setAnalyzing(false);
        setError(err?.message || '分析启动失败，请稍后重试');
      });
  }, [date, clearPolling]);

  const handleSelectStock = useCallback((code) => {
    setSelectedCode(code);
    setLoadingDetail(true);
    setError('');
    fetch('/api/stock-decision/detail?code=' + encodeURIComponent(code) + '&date=' + encodeURIComponent(date))
      .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || ('明细加载失败(' + r.status + ')'));
        return data;
      })
      .then(data => {
        setStockDetail(data);
        setLoadingDetail(false);
      })
      .catch(err => {
        setError(err?.message || '明细加载失败');
        setLoadingDetail(false);
      });
  }, [date]);

  const showProgress = analyzing || progress.status === 'running' || progress.status === 'pending';

  return (
    <div>
      <header className="top">
        <a href="/" className="brand">
          <div className="brand-mark">势</div>
          <div className="brand-text">
            <strong>板块决策系统</strong>
            <small>A-SHARE DECISION</small>
          </div>
        </a>
        <nav className="module-tabs" aria-label="功能模块">
          <a href="/sector">板块扫描</a>
          <a href="/chanlun">缠论分析</a>
          <a href="/decision">决策看板</a>
          <a className="active" href="/stock-decision">个股决策</a>
          <a href="/review">大盘复盘</a>
          <a href="/help">帮助</a>
        </nav>
        <div className="top-actions">
          <div className="date-field">
            <span>日期</span>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} />
          </div>
          <button className="mini-btn primary" onClick={handleAnalyze} disabled={analyzing}>
            {analyzing ? '分析中，请稍候...' : '分析全部'}
          </button>
        </div>
      </header>

      <div className="page" style={{ paddingTop: 24 }}>
        {showProgress ? (
          <div className="progress-card">
            <div className="progress-header">
              <div>
                <div className="progress-title">批量分析进度</div>
                <div className="progress-subtitle">
                  {progress.current ? `当前分析: ${progress.current.code} ${progress.current.name || ''}` : '正在初始化分析任务...'}
                </div>
              </div>
              <div className="progress-stats">
                <span>{progress.done}/{progress.total || '-'}</span>
                <strong>{(progress.percent || 0).toFixed(1)}%</strong>
              </div>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${Math.max(0, Math.min(100, progress.percent || 0))}%` }} />
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="card" style={{ marginBottom: 16, borderColor: 'rgba(191,58,48,.35)', color: 'var(--up)' }}>
            {error}
          </div>
        ) : null}
        {selectedCode ? (
          <div>
            <button
              className="mini-btn"
              onClick={() => { setSelectedCode(null); setStockDetail(null); }}
              style={{ marginBottom: 16 }}
            >
              ← 返回列表
            </button>
            <StockDetail code={selectedCode} data={stockDetail} loading={loadingDetail} />
          </div>
        ) : (
          <StockList
            stocks={stocks}
            selectedCode={selectedCode}
            onSelect={handleSelectStock}
            loading={loadingList}
          />
        )}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
