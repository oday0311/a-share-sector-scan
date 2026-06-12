# A股行业板块扫描与缠论分析终端

一个面向个人投资者的本地 A 股行业板块 AI 分析终端，用于复盘和动态感知标准行业板块的趋势变化，并提供 A 股、港股、指数的缠论结构复盘页签。系统优先使用 WeStock Data / 腾讯自选股获取行情，AKShare 作为备用数据源；后端负责全量行业板块扫描、排序、趋势、资金、技术指标和缠论结构识别，AI 负责过滤市场噪音、提炼复盘结论和辅助生成分析摘要。

> 本项目仅用于本地研究和复盘，不构成投资建议。

## 项目亮点

- 超轻量实现：前端使用原生 HTML / CSS / JavaScript，后端仅使用 Python 标准库 HTTP 服务，核心逻辑集中，便于编程智能体阅读、修改和部署。
- OpenAI 风格模型接入：支持灵活配置 `base_url`、`model`、`api_key`、`temperature` 和超时时间，可对接 DashScope、私有网关或其他兼容 Chat Completions 的模型服务。
- AI 边界清晰：AI 只做行情复盘、摘要生成、市场信号解释和方向归纳，不直接给出买卖建议，不替代投资决策。
- 类 Bloomberg 终端风格：高密度信息、深色终端、热力图、板块矩阵、资金流和信号面板，适合快速扫描市场结构变化。
- 双页签工作台：`板块扫描` 用于全市场行业强弱复盘，`缠论分析` 用于单标的 K 线结构拆解。
- 行业板块优先：只聚焦标准行业板块，过滤概念、主题、昨日涨停等噪音标签，让分析对象更稳定。
- 缠论结构识别：后端规则计算包含处理、分型、笔、线段、中枢、MACD、背驰和三类买卖点，AI 只解释结构事实。
- 日期可复盘：支持选择历史日期扫描，运行过的日期会保存本地结果，下次切换日期可直接读取。
- 数据源有兜底：WeStock Data 优先，AKShare 备选；数据源异常时可读取本地缓存或静态快照，避免页面空白。
- 适合二次开发：接口返回结构稳定，前后端耦合轻，适合用 Claude Code、Codex 等编程智能体快速扩展。

## 设计初衷

A 股每天的市场信息非常嘈杂，概念、题材、消息和短期异动容易掩盖真正的行业趋势。本项目希望提供一个轻量、可本地运行、可复盘的板块分析工具：先用规则和全量行情数据把标准行业板块排序、趋势和资金变化计算清楚，再让 AI 对结果进行压缩、归纳和解释，帮助个人投资者更快感知板块强弱切换、持续性变化和潜在风险，形成更清晰的复盘与分析决策依据。

项目的目标不是预测涨跌，也不是输出交易指令，而是把分散的行情数据整理成一个可读、可追溯、可重复扫描的板块趋势观察面板。

## 系统界面

![A股板块扫描系统界面](docs/screenshot.jpg)

## 核心功能

- 按日期扫描 A 股标准行业板块，支持交易日、周末、节假日和未来日期自动回退到最近可用交易日。
- 只展示标准行业板块，剔除概念、主题、昨日涨停、昨日连板等非行业维度。
- 基于全量行业板块复盘后呈现前 20 强板块，热力图按照当日涨幅动态排序。
- 领涨板块走势图与热力图保持同一组板块，切换日期后自动刷新排序和图表。
- 资金流展示 1 日、5 日、20 日维度。
- 指数区覆盖上证指数、沪深 300、创业板指、科创综指、科创 50、深证成指。
- AI 动态筛选板块与个股，并生成 `TOP PICKS`、`MARKET SIGNALS`、`STRATEGY SUMMARY`；AI 失败时自动使用规则分析兜底。
- 每个日期的扫描结果保存到本地缓存，重复查看直接读取缓存；点击“重新扫描”会覆盖该日期的最新结果。
- 缠论分析支持 A 股、港股、指数搜索，周期支持日线和周线。
- 缠论后端输出真实 K 线、分型、笔、线段、中枢、MACD、背驰、买卖点、趋势判断和复盘摘要。
- 缠论结果按 `symbol + period + date` 缓存到本地，点击“重新分析”会覆盖同一缓存。

## 技术架构

- 前端：原生 HTML / CSS / JavaScript，保留终端式原型界面。
- 后端：Python 标准库 HTTP 服务，无 Flask、FastAPI、Node 服务依赖。
- 数据源优先级：WeStock Data / 腾讯自选股优先，AKShare 备选。
- AI 接口：OpenAI-compatible Chat Completions 风格调用，配置只在后端读取，不暴露到浏览器。
- 本地缓存：`.cache/scan_request_YYYY-MM-DD.json`，默认不提交到 Git。
- 缠论缓存：`.cache/chanlun_{symbol}_{period}_{date}.json`，默认不提交到 Git。

## 代码标准与许可

本项目采用“源码可见、非商业使用”的开放方式，许可声明结构参考了 [Dify License](https://github.com/langgenius/dify/blob/main/LICENSE) 中“基于 Apache 2.0 并增加额外条件”的做法，但本项目限制更明确：不支持二次商用。详细条款见 [LICENSE](LICENSE)。

允许：

- 个人学习、研究、复盘和本地非商业使用。
- 在非商业场景下 fork、修改、部署和二次开发。
- 用于编程智能体、量化学习、行情复盘工具链的本地实验。

不允许，除非获得书面授权：

- 将本项目或其衍生版本打包销售、转售、出租或授权给第三方。
- 将本项目作为付费 SaaS、托管服务、API 服务、订阅产品或商业终端提供。
- 将本项目改名、换标、白标后作为商业软件交付。
- 基于本项目提供付费部署、付费集成、付费定制或付费咨询交付。
- 移除项目中的许可说明、风险提示、来源说明或非商业限制。

代码贡献和二次开发需遵循：

- 保持轻量化：优先使用标准库和现有结构，避免引入不必要的框架。
- 保持安全边界：AI key 只允许存在于 `config.local.json` 或环境变量中，不得进入前端、日志、缓存样例或 Git 历史。
- 保持 AI 边界：AI 只做复盘总结、信号解释和噪音过滤，不输出买卖指令或投资承诺。
- 保持可验证：行情排序、涨跌幅、资金、趋势、技术指标等计算逻辑应由后端规则生成，AI 文案不能覆盖原始指标。
- 保持可回退：数据源调用必须有缓存或静态快照兜底，避免页面空白。
- 提交前运行基础检查：`python3 -m py_compile server.py`、`node --check app.js`，并执行敏感信息扫描。

## 快速开始

### 1. 准备环境

需要本机已安装：

- Python 3.10+
- Node.js / npx，用于调用 WeStock Data

建议同时准备 AKShare 备用依赖，便于 WeStock Data 网络异常时自动兜底：

```bash
python3 -m pip install akshare pandas requests
```

### 2. 配置 AI

复制本地配置模板：

```bash
cp config.local.example.json config.local.json
```

在 `config.local.json` 中填写本机私有配置：

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

也可以通过环境变量覆盖：

```bash
export LLM_BASE_URL="https://coding.dashscope.aliyuncs.com/v1"
export LLM_MODEL="glm5"
export LLM_API_KEY="your-api-key"
```

`config.local.json` 已加入 `.gitignore`，不要把真实 key 写入 README、前端文件或提交记录。

### 3. 配置数据源

默认配置已经写在 `config.local.example.json` 中，本地可按需覆盖到 `config.local.json`：

```json
{
  "market": {
    "primary_source": "westock",
    "top": 20,
    "trend": 5,
    "history_days": 90,
    "http_timeout_seconds": 10,
    "westock_hot_limit": 300,
    "westock_candidate_limit": 300,
    "westock_kline_limit": 45,
    "westock_batch_size": 30,
    "westock_kline_workers": 4,
    "westock_timeout_seconds": 90,
    "industry_only": true
  },
  "chanlun": {
    "bars": 220,
    "westock_kline_limit": 260,
    "min_stroke_gap": 4
  }
}
```

#### WeStock Data 主数据源

WeStock Data 是默认主数据源，不需要单独配置行情 key。服务会通过下面的固定命令形式调用腾讯自选股行情数据：

```bash
npx -y westock-data-clawhub@1.0.4 board
npx -y westock-data-clawhub@1.0.4 hot board --limit 10
npx -y westock-data-clawhub@1.0.4 kline sh000001 --period day --limit 5
```

对接要求：

- 本机已安装 Node.js 和 `npx`。
- 首次运行会从 npm 下载 `westock-data-clawhub@1.0.4`，需要能访问 npm registry。
- 运行时需要能访问腾讯自选股行情接口。
- 敏感或生产环境建议固定包版本、使用可信 npm 镜像或提前完成安全审查。

可用性验证：

```bash
node -v
npx --version
npx -y westock-data-clawhub@1.0.4 board
```

如果 `npx` 下载慢或失败，可以先检查本机网络、npm registry、代理设置，再重新启动服务。

#### AKShare 备用数据源

AKShare 作为备用源使用，主要在 WeStock Data 失败时自动回退。它不需要行情 key，但需要安装 Python 依赖并能访问东方财富相关接口：

```bash
python3 -m pip install akshare pandas requests
```

可用性验证：

```bash
python3 - <<'PY'
import akshare as ak
df = ak.stock_board_industry_name_em()
print(len(df))
print(df.head(1).to_dict("records"))
PY
```

如果希望直接以 AKShare 作为主数据源，可以在 `config.local.json` 中调整：

```json
{
  "market": {
    "primary_source": "akshare"
  }
}
```

实际扫描结果会在页面底部和接口 `meta.dataProvider` 中标明当前使用的数据源，例如 `westock` 或 `akshare`。

### 4. 启动本地服务

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

打开浏览器访问：

```text
http://127.0.0.1:8765/
```

缠论分析页签也可以直接访问：

```text
http://127.0.0.1:8765/chanlun
```

macOS 也可以直接双击：

```text
start_server.command
```

## 使用说明

1. 在顶部日期选择器中选择要复盘的日期。
2. 点击“按日期扫描”，系统会优先读取该日期的本地缓存；如果没有缓存，则拉取行情并生成分析。
3. 点击“重新扫描”，系统会重新拉取行情、重新分析，并覆盖保存该日期的缓存结果。
4. 页面会展示实际分析日。如果选择的是周末、节假日或未来日期，系统会回退到不晚于所选日期的最近可用交易日。
5. 当 AI 不可用、超时或返回格式异常时，页面仍会使用规则分析结果正常展示。
6. 切换到“缠论分析”页签后，可搜索 A 股、港股或指数，选择日线/周线并按日期复盘结构。
7. 缠论页点击“重新分析”会重新拉取 K 线、重新计算结构、重新生成摘要，并覆盖同一标的、周期、日期的缓存。

## 接口说明

### `GET /api/scan`

请求示例：

```text
GET /api/scan?date=2026-06-11
GET /api/scan?date=2026-06-11&refresh=1
```

参数：

- `date`：可选，格式为 `YYYY-MM-DD`；缺省时使用当前日期。
- `refresh`：可选，传 `1` 时强制重新扫描并覆盖该日期缓存。

返回数据结构与前端 `TERMINAL_DATA` 保持一致，核心字段包括：

- `meta`：请求日期、实际分析日期、数据源、AI 状态、缓存状态。
- `indices`：主要指数表现。
- `stats`：市场统计卡片。
- `heatmap`：前 20 行业板块热力图。
- `sectors`：前 20 行业板块明细。
- `constituents`：板块关联个股。
- `flows`：1 日、5 日、20 日资金维度。
- `signals`：市场信号。
- `picks`：AI 或规则筛选方向。
- `trend`：领涨板块走势。
- `tech`：技术指标。
- `hotStocks`、`concepts`、`strategy`：个股热度、强势方向和策略摘要。

`meta.aiStatus` 可能为：

- `ok`：AI 分析成功。
- `fallback`：AI 不可用，已使用规则兜底。
- `disabled`：未配置 AI key。
- `error`：AI 调用失败。

### `GET /api/chanlun/search`

请求示例：

```text
GET /api/chanlun/search?q=腾讯&market=all
GET /api/chanlun/search?q=600519&market=a
```

参数：

- `q`：搜索关键字，支持名称、A 股代码、港股代码和指数代码。
- `market`：可选，`all`、`a`、`hk`、`index`，缺省为 `all`。

返回字段：

- `items`：候选标的列表，包含 `code`、`symbol`、`name`、`market`、`unit`。
- `meta`：查询关键字、市场过滤条件和结果数量。

### `GET /api/chanlun/analyze`

请求示例：

```text
GET /api/chanlun/analyze?symbol=600519&period=day
GET /api/chanlun/analyze?symbol=hk00700&period=week&date=2026-06-12&refresh=1
```

参数：

- `symbol`：必填，支持 `600519`、`sh600519`、`hk00700`、`sh000001` 等形式。
- `period`：可选，`day` 或 `week`，缺省为 `day`；第一版不实现分钟级周期。
- `date`：可选，格式为 `YYYY-MM-DD`；非交易日或未来日期会回退到最近可用 K 线。
- `refresh`：可选，传 `1` 时强制重新分析并覆盖同一缓存。

返回字段：

- `meta`：请求日期、实际 K 线日期、周期、数据源、缓存状态、AI 状态。
- `stock`：标的代码、名称、市场、价格单位。
- `bars`：真实 K 线数据。
- `analysis`：`fractals / pts / segs / pivots / macd / divergence / signals / trend / stats`。
- `verdict`：规则版核心结论、分项卡片、风险提示和解释依据。
- `ai`：AI 复盘文案，AI 不可用时为空对象或规则兜底内容。

## 面向编程智能体的部署指引

本项目刻意保持文件少、依赖少、启动路径短，适合交给 Claude Code、Codex 这类编程智能体按指引快速部署和排障。

### Agent 执行清单

1. 确认当前目录包含 `server.py`、`A股板块分析终端.html`、`app.js`、`terminal.css` 和 `config.local.example.json`。
2. 检查本机是否有 Python 3.10+、Node.js 和 `npx`。
3. 复制 `config.local.example.json` 为 `config.local.json`，或用环境变量注入 `LLM_API_KEY`。
4. 验证 WeStock Data：`npx -y westock-data-clawhub@1.0.4 board`。
5. 安装 AKShare 备用源：`python3 -m pip install akshare pandas requests`。
6. 验证 AKShare：`python3 -c "import akshare as ak; print(len(ak.stock_board_industry_name_em()))"`。
7. 启动服务：`python3 server.py --host 127.0.0.1 --port 8765`。
8. 打开 `http://127.0.0.1:8765/`，选择日期并执行扫描。
9. 打开 `http://127.0.0.1:8765/chanlun`，搜索 `腾讯` 或 `600519`，确认日线/周线能返回真实 K 线和结构分析。
10. 验证 `http://127.0.0.1:8765/api/scan` 能返回 JSON，且 `sectors` 数量为 20 左右、`meta.dataProvider` 和 `meta.aiStatus` 有明确状态。
11. 验证 `http://127.0.0.1:8765/api/chanlun/analyze?symbol=600519&period=day` 能返回 JSON，且 `bars`、`analysis.fractals`、`analysis.pts` 不为空。
12. 提交或分发前执行敏感信息检查，确认 `config.local.json`、`.cache/`、本地 plist 和真实 key 没有进入 Git。

### 适合部署的环境

- 个人 Mac / Windows / Linux 电脑：最推荐，适合本地复盘和日常使用。
- 本地开发机或 NAS：适合在内网长期运行，通过浏览器访问。
- 内网服务器或小型 VPS：适合多设备访问，但建议加访问控制，并使用环境变量管理 key。
- GitHub Codespaces / Dev Container：适合演示、改造和临时开发，但行情接口和 `npx` 网络访问可能受环境限制。
- 不推荐纯 GitHub Pages：只能托管静态页面，无法运行 `/api/scan` 后端接口，也无法安全保存 AI key。

### 本机部署（推荐）

本项目默认按本机单用户方式运行。启动后仅监听 `127.0.0.1`，AI key 和缓存文件都保留在本机，不会暴露到公网。

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

### 局域网访问

如果需要在同一局域网内访问，可以改为监听 `0.0.0.0`：

```bash
python3 server.py --host 0.0.0.0 --port 8765
```

此方式会把本地服务暴露给局域网设备。请确认防火墙、网络环境和 AI key 保护方式后再使用。

### macOS 后台运行

可以使用 `start_server.command` 手动启动，也可以自行创建本机 `launchd` 配置。建议把个人 `plist` 文件放在本机用户目录，不要提交到仓库，因为其中通常包含绝对路径和个人环境信息。

### 远程服务器部署

可以部署到 VPS 或内网服务器，但需要注意：

- 使用环境变量注入 `LLM_API_KEY`，不要把 key 写入仓库。
- 建议放在内网或加访问控制，不建议裸露到公网。
- `.cache/` 属于运行时数据，可以按需持久化，但不应提交。
- 若仅使用 GitHub Pages，只能托管静态页面，无法运行 `/api/scan` 后端接口，也无法安全保存 AI key。

## 数据与缓存

- 优先数据源：WeStock Data / 腾讯自选股。
- 备用数据源：AKShare / 东方财富。
- 数据源选择：`market.primary_source` 默认为 `westock`；设置为 `akshare` 可直接使用 AKShare。
- 普通扫描会优先读取 `.cache/scan_request_YYYY-MM-DD.json`。
- 重新扫描会覆盖同一日期缓存，只保留最新版本。
- 缠论分析会优先读取 `.cache/chanlun_{symbol}_{period}_{date}.json`。
- 缠论页面点击“重新分析”会覆盖同一标的、周期和日期的缓存，只保留最新版本。
- 当实时数据源异常时，系统会尝试读取最近缓存；若缓存也不可用，则回退到 `data.js` 中的静态快照，避免页面空白。

## 敏感信息与脱敏

仓库默认不会提交以下本地文件：

- `config.local.json`
- `.cache/`
- `__pycache__/`
- `uploads/`
- `bridge/`
- `com.local.sector-scan.plist`
- macOS 资源文件 `._*`

提交前建议执行一次敏感信息检查：

```bash
git status --short --ignored
rg -n "\bsk-[A-Za-z0-9_-]{16,}|api_key\s*[:=]\s*['\"]?sk-[A-Za-z0-9_-]{16,}|LLM_API_KEY\s*=\s*sk-[A-Za-z0-9_-]{16,}" --hidden --glob '!config.local.json' --glob '!.cache/**' --glob '!.git/**' --glob '!**/._*' .
```

真实 API key 只应存在于本机 `config.local.json` 或环境变量中，不应出现在前端源码、README、截图、接口响应或 Git 提交历史里。

## 常见问题

### 页面提示数据加载失败

先确认本地服务仍在运行，并访问：

```text
http://127.0.0.1:8765/api/scan
```

如果接口不可访问，重新启动服务即可。

### 浏览器提示 127.0.0.1 拒绝连接

说明本地服务没有启动，或端口不是 `8765`。重新运行：

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

### AI 分析失败

检查 `config.local.json` 或环境变量中的 `LLM_API_KEY` 是否有效。即使 AI 调用失败，系统也会自动使用规则分析兜底，页面不会空白。

### 数据源失败

WeStock Data 需要本机可以运行 `npx` 并访问对应行情接口。若 WeStock 不可用，系统会尝试 AKShare；若两个数据源都不可用，会读取本地缓存或静态快照。

建议按顺序排查：

```bash
npx -y westock-data-clawhub@1.0.4 board
python3 -c "import akshare as ak; print(len(ak.stock_board_industry_name_em()))"
curl -sS "http://127.0.0.1:8765/api/scan?date=2026-06-11" | python3 -m json.tool
curl -sS "http://127.0.0.1:8765/api/chanlun/analyze?symbol=600519&period=day" | python3 -m json.tool
```

如果只想临时绕过 WeStock Data，可把 `config.local.json` 中的 `market.primary_source` 改为 `akshare` 后重启服务。

## 项目结构

```text
.
├── A股板块分析终端.html     # 页面入口
├── app.js                  # 前端渲染与交互
├── terminal.css            # 终端风格样式
├── server.py               # 本地 HTTP 服务、行情扫描、AI 分析
├── data.js                 # 静态兜底快照
├── config.local.example.json
├── start_server.command    # macOS 一键启动脚本
├── LICENSE                 # 源码可见、非商业使用许可
├── docs/
│   └── screenshot.jpg      # GitHub README 截图
├── 缠论/
│   ├── index.html          # 缠论分析页入口
│   ├── styles.css          # 缠论页样式
│   └── js/
│       ├── data.js         # 缠论 API 客户端
│       ├── app.jsx         # 缠论页面状态与交互
│       ├── chart.jsx       # K 线与结构图表
│       └── sections.jsx    # 结构解读与买卖点面板
└── .gitignore
```

## 免责声明

本项目输出仅用于行情复盘、研究和技术演示。市场数据可能存在延迟、缺失或源站接口变更，AI 生成内容可能存在误判。任何投资决策请自行核验并承担风险。
