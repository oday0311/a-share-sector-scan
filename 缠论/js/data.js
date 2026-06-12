// data.js — 缠论模块 API 客户端 + 格式化工具
(function () {
  'use strict';

  var API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';
  var STOCKS = [
    { code: '600519', symbol: 'sh600519', name: '贵州茅台', market: 'A股', unit: '¥' },
    { code: '300750', symbol: 'sz300750', name: '宁德时代', market: 'A股', unit: '¥' },
    { code: '601318', symbol: 'sh601318', name: '中国平安', market: 'A股', unit: '¥' },
    { code: '600036', symbol: 'sh600036', name: '招商银行', market: 'A股', unit: '¥' },
    { code: '002594', symbol: 'sz002594', name: '比亚迪', market: 'A股', unit: '¥' },
    { code: '688981', symbol: 'sh688981', name: '中芯国际', market: 'A股', unit: '¥' },
    { code: '00700', symbol: 'hk00700', name: '腾讯控股', market: '港股', unit: 'HK$' },
    { code: '09988', symbol: 'hk09988', name: '阿里巴巴', market: '港股', unit: 'HK$' },
    { code: '03690', symbol: 'hk03690', name: '美团', market: '港股', unit: 'HK$' },
    { code: '01810', symbol: 'hk01810', name: '小米集团', market: '港股', unit: 'HK$' },
    { code: '000001.SH', symbol: 'sh000001', name: '上证指数', market: '指数', unit: '点' },
    { code: '399001.SZ', symbol: 'sz399001', name: '深证成指', market: '指数', unit: '点' },
    { code: '399006.SZ', symbol: 'sz399006', name: '创业板指', market: '指数', unit: '点' },
    { code: '000300.SH', symbol: 'sh000300', name: '沪深300', market: '指数', unit: '点' },
    { code: '000688.SH', symbol: 'sh000688', name: '科创50', market: '指数', unit: '点' }
  ];

  function marketKey(market) {
    if (market === 'A股') return 'a';
    if (market === '港股') return 'hk';
    if (market === '指数') return 'index';
    return 'all';
  }

  function defaultStocks(market) {
    if (!market || market === '全部') return STOCKS.slice();
    return STOCKS.filter(function (s) { return s.market === market; });
  }

  function searchStocks(q, market) {
    var params = new URLSearchParams();
    params.set('q', q || '');
    params.set('market', marketKey(market));
    return fetch(API_BASE + '/api/chanlun/search?' + params.toString(), { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('search failed');
        return r.json();
      })
      .then(function (data) { return data.items || []; });
  }

  function fetchAnalysis(symbol, period, date, force) {
    var params = new URLSearchParams();
    params.set('symbol', symbol);
    params.set('period', period || 'day');
    if (date) params.set('date', date);
    if (force) params.set('refresh', '1');
    return fetch(API_BASE + '/api/chanlun/analyze?' + params.toString(), { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('analysis failed');
        return r.json();
      });
  }

  function fmtPrice(x) {
    if (x == null || isNaN(x)) return '—';
    return Number(x).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fmtVol(v) {
    v = Number(v || 0);
    if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
    if (v >= 1e4) return (v / 1e4).toFixed(1) + '万';
    return String(Math.round(v));
  }

  function fmtPct(x) {
    if (x == null || isNaN(x)) return '—';
    return (x >= 0 ? '+' : '') + (x * 100).toFixed(2) + '%';
  }

  function todayISO() {
    var d = new Date();
    var pad = function (n) { return n < 10 ? '0' + n : String(n); };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  window.CL_DATA = {
    STOCKS: STOCKS,
    defaultStocks: defaultStocks,
    searchStocks: searchStocks,
    fetchAnalysis: fetchAnalysis,
    fmtPrice: fmtPrice,
    fmtVol: fmtVol,
    fmtPct: fmtPct,
    todayISO: todayISO
  };
})();
