// data.js — 缠论模块 API 客户端 + 格式化工具
(function () {
  'use strict';

  var API_BASE = location.protocol === 'file:' ? 'http://127.0.0.1:8765' : '';
  var STOCKS = [
    { code: '000001.SH', symbol: 'sh000001', name: '上证指数', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399001.SZ', symbol: 'sz399001', name: '深证成指', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399006.SZ', symbol: 'sz399006', name: '创业板指', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000300.SH', symbol: 'sh000300', name: '沪深300', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000905.SH', symbol: 'sh000905', name: '中证500', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000852.SH', symbol: 'sh000852', name: '中证1000', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000016.SH', symbol: 'sh000016', name: '上证50', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000010.SH', symbol: 'sh000010', name: '上证180', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000009.SH', symbol: 'sh000009', name: '上证380', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000903.SH', symbol: 'sh000903', name: '中证100', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000906.SH', symbol: 'sh000906', name: '中证800', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000985.SH', symbol: 'sh000985', name: '中证全指', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000680.SH', symbol: 'sh000680', name: '科创综指', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000688.SH', symbol: 'sh000688', name: '科创50', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399330.SZ', symbol: 'sz399330', name: '深证100', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399005.SZ', symbol: 'sz399005', name: '中小100', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399673.SZ', symbol: 'sz399673', name: '创业板50', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399303.SZ', symbol: 'sz399303', name: '国证2000', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000015.SH', symbol: 'sh000015', name: '上证红利', market: '指数', unit: '点', group: '宽基指数' },
    { code: '399324.SZ', symbol: 'sz399324', name: '深证红利', market: '指数', unit: '点', group: '宽基指数' },
    { code: '000928.SH', symbol: 'sh000928', name: '中证能源', market: '指数', unit: '点', group: '行业指数' },
    { code: '000929.SH', symbol: 'sh000929', name: '中证材料', market: '指数', unit: '点', group: '行业指数' },
    { code: '000930.SH', symbol: 'sh000930', name: '中证工业', market: '指数', unit: '点', group: '行业指数' },
    { code: '000931.SH', symbol: 'sh000931', name: '中证可选', market: '指数', unit: '点', group: '行业指数' },
    { code: '000932.SH', symbol: 'sh000932', name: '中证消费', market: '指数', unit: '点', group: '行业指数' },
    { code: '000933.SH', symbol: 'sh000933', name: '中证医药', market: '指数', unit: '点', group: '行业指数' },
    { code: '000934.SH', symbol: 'sh000934', name: '中证金融', market: '指数', unit: '点', group: '行业指数' },
    { code: '000935.SH', symbol: 'sh000935', name: '中证信息', market: '指数', unit: '点', group: '行业指数' },
    { code: '000936.SH', symbol: 'sh000936', name: '中证电信', market: '指数', unit: '点', group: '行业指数' },
    { code: '000937.SH', symbol: 'sh000937', name: '中证公用', market: '指数', unit: '点', group: '行业指数' },
    { code: '000986.SH', symbol: 'sh000986', name: '全指能源', market: '指数', unit: '点', group: '行业指数' },
    { code: '000987.SH', symbol: 'sh000987', name: '全指材料', market: '指数', unit: '点', group: '行业指数' },
    { code: '000988.SH', symbol: 'sh000988', name: '全指工业', market: '指数', unit: '点', group: '行业指数' },
    { code: '000989.SH', symbol: 'sh000989', name: '全指可选', market: '指数', unit: '点', group: '行业指数' },
    { code: '000990.SH', symbol: 'sh000990', name: '全指消费', market: '指数', unit: '点', group: '行业指数' },
    { code: '000991.SH', symbol: 'sh000991', name: '全指医药', market: '指数', unit: '点', group: '行业指数' },
    { code: '000992.SH', symbol: 'sh000992', name: '全指金融', market: '指数', unit: '点', group: '行业指数' },
    { code: '000993.SH', symbol: 'sh000993', name: '全指信息', market: '指数', unit: '点', group: '行业指数' },
    { code: '000994.SH', symbol: 'sh000994', name: '全指电信', market: '指数', unit: '点', group: '行业指数' },
    { code: '000995.SH', symbol: 'sh000995', name: '全指公用', market: '指数', unit: '点', group: '行业指数' },
    { code: '399986.SZ', symbol: 'sz399986', name: '中证银行', market: '指数', unit: '点', group: '行业指数' },
    { code: '399975.SZ', symbol: 'sz399975', name: '证券公司', market: '指数', unit: '点', group: '行业指数' },
    { code: '399967.SZ', symbol: 'sz399967', name: '中证军工', market: '指数', unit: '点', group: '行业指数' },
    { code: '399808.SZ', symbol: 'sz399808', name: '中证新能', market: '指数', unit: '点', group: '行业指数' },
    { code: '399976.SZ', symbol: 'sz399976', name: 'CS新能车', market: '指数', unit: '点', group: '行业指数' },
    { code: '399989.SZ', symbol: 'sz399989', name: '中证医疗', market: '指数', unit: '点', group: '行业指数' },
    { code: '399971.SZ', symbol: 'sz399971', name: '中证传媒', market: '指数', unit: '点', group: '行业指数' },
    { code: '399998.SZ', symbol: 'sz399998', name: '中证煤炭', market: '指数', unit: '点', group: '行业指数' },
    { code: '000819.SH', symbol: 'sh000819', name: '有色金属', market: '指数', unit: '点', group: '行业指数' },
    { code: '000827.SH', symbol: 'sh000827', name: '中证环保', market: '指数', unit: '点', group: '行业指数' },
    { code: '600519', symbol: 'sh600519', name: '贵州茅台', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '300750', symbol: 'sz300750', name: '宁德时代', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '601318', symbol: 'sh601318', name: '中国平安', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '600036', symbol: 'sh600036', name: '招商银行', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '002594', symbol: 'sz002594', name: '比亚迪', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '688981', symbol: 'sh688981', name: '中芯国际', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '601138', symbol: 'sh601138', name: '工业富联', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '002475', symbol: 'sz002475', name: '立讯精密', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '300059', symbol: 'sz300059', name: '东方财富', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '600900', symbol: 'sh600900', name: '长江电力', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '601899', symbol: 'sh601899', name: '紫金矿业', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '000858', symbol: 'sz000858', name: '五粮液', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '601127', symbol: 'sh601127', name: '赛力斯', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '000725', symbol: 'sz000725', name: '京东方A', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '300308', symbol: 'sz300308', name: '中际旭创', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '300502', symbol: 'sz300502', name: '新易盛', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '688256', symbol: 'sh688256', name: '寒武纪', market: 'A股', unit: '¥', group: '热门股票' },
    { code: '00700', symbol: 'hk00700', name: '腾讯控股', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '09988', symbol: 'hk09988', name: '阿里巴巴', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '03690', symbol: 'hk03690', name: '美团', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '01810', symbol: 'hk01810', name: '小米集团', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '01024', symbol: 'hk01024', name: '快手', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '09618', symbol: 'hk09618', name: '京东集团', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '00981', symbol: 'hk00981', name: '中芯国际', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '01211', symbol: 'hk01211', name: '比亚迪股份', market: '港股', unit: 'HK$', group: '港股热门' },
    { code: '00388', symbol: 'hk00388', name: '香港交易所', market: '港股', unit: 'HK$', group: '港股热门' }
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
