# A 股行业板块扫描与投资决策终端

把 A 股每天的市场噪音，压缩成一张可复盘的板块趋势雷达。

这是一个面向个人投资者的本地 AI 分析终端：先用全量行业板块数据找出当日强弱主线，再通过多因子模型量化排名，最后下钻到 A 股、港股和指数的缠论结构，帮助你快速回答三个问题：市场主线在哪里、资金是否延续、关键标的处在什么结构位置。

系统优先使用 WeStock Data / 腾讯自选股行情，AKShare 作为备用数据源；后端规则负责涨跌、资金、趋势、多因子评分和缠论结构识别，AI 只做复盘总结与信号解释，不提供投资建议。

## 项目亮点

- 轻量本地运行：原生前端 + Python 标准库 HTTP 服务，无 Flask、FastAPI、Node 后端。
- 四个模块贯穿完整复盘链路：大盘复盘 → 板块扫描 → 多因子决策看板 → 缠论结构下钻。
- 决策看板覆盖 33 个 A 股主要行业板块，全部通过硬编码 ETF 代码直接拉取行情，不依赖东方财富接口。
- 数据源有兜底：WeStock Data 优先，AKShare 备用，运行结果写入本地缓存，相同日期不重复请求。
- AI 边界清晰：兼容 OpenAI 风格模型接口，AI 只总结和解释，不覆盖原始行情指标。

## 核心功能

### 板块扫描

- 按日期扫描，非交易日或未来日期自动回退到最近可用交易日。
- 基于全量行业板块复盘，展示涨幅前 20 强板块。
- 热力图、领涨走势图和板块列表使用同一组排序结果。
- 资金流支持 1 日、5 日、20 日维度。
- 扫描结果按日期缓存；点击"重新扫描"会覆盖该日期缓存。

### 决策看板

基于四组因子对行业板块进行量化排名，提供从板块到个股的三级下钻视图。

**板块轮动排行**

- 覆盖 33 个主要行业板块，全部通过 ETF 行情代理计算，东方财富接口不可用时自动降级。
- 四组因子：趋势（MA 多空排列、MACD 柱、ADX 强度）、动量（20 日涨跌幅、相对强弱 RS）、资金（主力净流入 1 日 / 5 日）、广度（涨跌比）。
- 截面 Z-score 归一化，合成评分 [-1, +1]，映射到五档信号：强烈看多 / 看多 / 中性 / 看空 / 强烈看空。
- 结果按日期缓存；点击"重新扫描"会强制刷新。

**板块深度分析**

- 展示单一板块的各因子评分明细和置信度。
- ATR 基准价格区间：入场区间、止损位、目标价一 / 目标价二。
- 成分股列表（来自 WeStock ETF 持仓）和 AI 复盘叙事。

**个股分析**

- 对单只 A 股或港股进行趋势、动量和振荡因子评分。
- 同样提供 ATR 基准的价格区间参考。

### 缠论分析

- 点击搜索框即可展示常用候选，按 `宽基指数 / 行业指数 / 热门股票 / 港股热门` 分组。
- 指数候选覆盖上证、深证、创业板、科创、沪深 300、中证 500/1000、红利、中证行业、全指行业等。
- 当前前端只开放日线复盘。
- 后端计算 K 线包含处理、分型、笔、线段、中枢、MACD、背驰和买卖点。
- 分析结果按 `symbol + period + date` 缓存；点击"重新分析"会覆盖同一缓存。

### 大盘复盘

- 可自定义复盘日期；未生成的日期会自动拉取最近有效交易日数据并调用 LLM 生成报告。
- 运行时展示步骤、已用时间和预计完成时间；完成后展示实际完成时间、耗时、数据源与 LLM 状态。
- 市场宽度优先从指定日期的盘后新闻搜索中读取市场汇总数字，不从逐股明细累加；成交额使用沪深交易所日度股票数据。行业强弱优先使用同花顺全行业指数，再降级到 WeStock 真实行业板块，ETF 仅作末级降级。
- LLM 报告以全市场视角输出市场总结、指数点评、资金动向、热点解读和后市观察；无直接数据的资金流、政策催化和价位不允许编造。
- 结果按选择日期缓存；旧版本缓存会自动失效，避免沿用口径不一致的数据。

## 快速开始

### 1. 准备环境

需要：

- Python 3.10+
- Node.js / npx

安装 AKShare 备用依赖：

```bash
python3 -m pip install akshare pandas requests
```

### 2. 配置 AI

复制本地配置：

```bash
cp config.local.example.json config.local.json
```

在 `config.local.json` 中填写模型配置：

```json
{
  "llm": {
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "model": "glm5",
    "api_key": "",
    "temperature": 0.2,
    "timeout_seconds": 45
  }
}
```

也可以使用环境变量覆盖：

```bash
export LLM_BASE_URL="https://coding.dashscope.aliyuncs.com/v1"
export LLM_MODEL="glm5"
export LLM_API_KEY="your-api-key"
```

`config.local.json` 已加入 `.gitignore`，不要提交真实 key。

### 3. 启动服务

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765/          ← 板块扫描
http://127.0.0.1:8765/decision  ← 决策看板
http://127.0.0.1:8765/chanlun   ← 缠论分析
http://127.0.0.1:8765/review    ← 大盘复盘
```

macOS 可双击 `start_server.command` 启动。

## 数据源

默认主数据源是 WeStock Data，不需要行情 key，但需要本机可运行 `npx` 并访问腾讯自选股接口。

验证命令：

```bash
npx -y westock-data-clawhub@1.0.4 board
npx -y westock-data-clawhub@1.0.4 kline sh000001 --period day --limit 5
```

决策看板通过 ETF 代码拉取板块行情（例如半导体 → sz159558、通信设备 → sz159994），覆盖 33 个主要行业板块，不依赖东方财富的行业板块接口。

AKShare 是备用数据源。若要直接使用 AKShare，可在 `config.local.json` 中设置：

```json
{
  "market": {
    "primary_source": "akshare"
  }
}
```

## 使用方式

- **板块扫描**：选择日期，点击"按日期扫描"；需要刷新数据时点击"重新扫描"。
- **决策看板**：进入"决策看板"页签，查看多因子排名；点击板块行下钻到因子明细和价格区间；点击成分股进入个股分析；需要刷新数据时点击"重新分析"。
- **缠论分析**：进入"缠论分析"页签，搜索或直接选择候选标的，选择日期后自动分析；需要刷新数据时点击"重新分析"。
- **大盘复盘**：选择复盘日期，系统会汇总指数、市场宽度、行业强弱和资讯，并生成结构化复盘报告。
- 页面会展示实际分析日期、数据源、缓存状态和 AI 状态。

## 接口

**板块扫描**

```text
GET /api/scan?date=YYYY-MM-DD
GET /api/scan?date=YYYY-MM-DD&refresh=1
```

返回板块扫描完整数据，包含 `meta / indices / heatmap / sectors / flows / signals / picks / trend / tech / strategy` 等字段。

**决策看板**

```text
GET /api/decision/rotation?date=YYYY-MM-DD
GET /api/decision/rotation?date=YYYY-MM-DD&refresh=1
GET /api/decision/sector?name=半导体&date=YYYY-MM-DD
GET /api/decision/stock?symbol=600519&date=YYYY-MM-DD
```

`rotation` 返回所有板块的排名列表，包含 `tier / composite / group_scores / gates`；`sector` 额外返回 `factors / target_price / constituents / evidence`；`stock` 返回个股因子和价格区间。

**缠论分析**

```text
GET /api/chanlun/search?q=腾讯&market=all
GET /api/chanlun/analyze?symbol=600519&period=day&date=2026-06-12
GET /api/chanlun/analyze?symbol=sh000932&period=day&refresh=1
```

**大盘复盘**

```text
GET /api/review?date=YYYY-MM-DD
GET /api/review?date=YYYY-MM-DD&refresh=1
GET /api/review/history?limit=14
```

返回值 `meta.data_sources` 记录各数据项的实际提供方、状态和是否发生降级；`meta.llm_status`、`completed_at` 与 `duration_seconds` 用于核验模型调用及完成状态。

## 缓存与安全

- 板块扫描缓存：`.cache/scan_request_YYYY-MM-DD.json`
- 缠论分析缓存：`.cache/chanlun_{symbol}_{period}_{date}.json`
- 决策看板缓存：`.cache/decision_rotation_all_{date}.json` / `.cache/decision_sector_{name}_{date}.json`
- 大盘复盘缓存：`.cache/review/review_YYYYMMDD.json`
- 本地配置：`config.local.json`

`config.local.json`、`.cache/`、`__pycache__/`、`uploads/`、`bridge/`、本机 `plist` 和 macOS 资源文件不会提交到 Git。提交前请确认 README、前端源码、缓存样例和提交历史里没有真实 API key。

## 部署建议

- 推荐部署在个人电脑、本地开发机、NAS 或内网服务器。
- 局域网访问可用 `--host 0.0.0.0`，但需要自行加访问控制。
- 不建议裸露到公网；GitHub Pages 也不适合本项目，因为无法运行后端接口或安全保存 AI key。

## 开发原则

- 保持轻量，优先复用标准库和现有结构。
- AI key 只允许放在本地配置或环境变量中。
- 行情指标、排序、资金和缠论结构由后端规则计算，AI 只生成复盘文案。
- 数据源调用必须保留缓存或静态快照兜底。

本项目源码可见，仅允许个人学习、研究、复盘和非商业本地使用；不支持二次商用、转售、白标、付费托管或作为商业服务交付。详细条款见 [LICENSE](LICENSE)。

## 项目结构

```text
.
├── A股板块分析终端.html   ← 板块扫描前端
├── app.js
├── terminal.css
├── data.js
├── server.py              ← 统一后端（扫描 + 缠论 + 决策 + 复盘）
├── config.local.example.json
├── start_server.command
├── LICENSE
├── docs/
│   └── screenshot.jpg
├── 缠论/                  ← 缠论分析前端
│   ├── index.html
│   ├── styles.css
│   └── js/
│       ├── data.js
│       ├── app.jsx
│       ├── chart.jsx
│       └── sections.jsx
├── decision/              ← 决策看板前端
    ├── index.html
    ├── styles.css
    └── js/
        └── app.jsx
├── review/                ← 大盘复盘前端
│   ├── index.html
│   ├── styles.css
│   └── js/
│       └── app.jsx
└── help/                  ← 系统帮助文档
    └── index.html
```

## 免责声明

本项目仅用于行情复盘、研究和技术演示，不构成投资建议。市场数据可能延迟、缺失或因源站接口变更而异常，AI 生成内容也可能存在误判。
