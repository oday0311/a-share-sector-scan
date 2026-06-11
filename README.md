# A股行业板块扫描终端

一个面向个人投资者的本地 A 股行业板块 AI 分析终端，用于复盘和动态感知标准行业板块的趋势变化。系统优先使用 WeStock Data / 腾讯自选股获取行情，AKShare 作为备用数据源；后端负责全量行业板块扫描、排序、趋势、资金和技术指标计算，AI 负责过滤市场噪音、提炼复盘结论和辅助生成分析摘要。

> 本项目仅用于本地研究和复盘，不构成投资建议。

## 项目亮点

- 超轻量实现：前端使用原生 HTML / CSS / JavaScript，后端仅使用 Python 标准库 HTTP 服务，核心逻辑集中，便于编程智能体阅读、修改和部署。
- OpenAI 风格模型接入：支持灵活配置 `base_url`、`model`、`api_key`、`temperature` 和超时时间，可对接 DashScope、私有网关或其他兼容 Chat Completions 的模型服务。
- AI 边界清晰：AI 只做行情复盘、摘要生成、市场信号解释和方向归纳，不直接给出买卖建议，不替代投资决策。
- 类 Bloomberg 终端风格：高密度信息、深色终端、热力图、板块矩阵、资金流和信号面板，适合快速扫描市场结构变化。
- 行业板块优先：只聚焦标准行业板块，过滤概念、主题、昨日涨停等噪音标签，让分析对象更稳定。
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

## 技术架构

- 前端：原生 HTML / CSS / JavaScript，保留终端式原型界面。
- 后端：Python 标准库 HTTP 服务，无 Flask、FastAPI、Node 服务依赖。
- 数据源优先级：WeStock Data / 腾讯自选股优先，AKShare 备选。
- AI 接口：OpenAI-compatible Chat Completions 风格调用，配置只在后端读取，不暴露到浏览器。
- 本地缓存：`.cache/scan_request_YYYY-MM-DD.json`，默认不提交到 Git。

## 快速开始

### 1. 准备环境

需要本机已安装：

- Python 3.10+
- Node.js / npx，用于调用 WeStock Data

如果需要启用 AKShare 备用数据源，可安装：

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

### 3. 启动本地服务

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

打开浏览器访问：

```text
http://127.0.0.1:8765/
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

## 面向编程智能体的部署指引

本项目刻意保持文件少、依赖少、启动路径短，适合交给 Claude Code、Codex 这类编程智能体按指引快速部署和排障。

### Agent 执行清单

1. 确认当前目录包含 `server.py`、`A股板块分析终端.html`、`app.js`、`terminal.css` 和 `config.local.example.json`。
2. 检查本机是否有 Python 3.10+ 和 Node.js / npx。
3. 复制 `config.local.example.json` 为 `config.local.json`，或用环境变量注入 `LLM_API_KEY`。
4. 启动服务：`python3 server.py --host 127.0.0.1 --port 8765`。
5. 打开 `http://127.0.0.1:8765/`，选择日期并执行扫描。
6. 验证 `http://127.0.0.1:8765/api/scan` 能返回 JSON，且 `sectors` 数量为 20 左右、`meta.aiStatus` 有明确状态。
7. 提交或分发前执行敏感信息检查，确认 `config.local.json`、`.cache/`、本地 plist 和真实 key 没有进入 Git。

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
- 普通扫描会优先读取 `.cache/scan_request_YYYY-MM-DD.json`。
- 重新扫描会覆盖同一日期缓存，只保留最新版本。
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
rg -n "sk-[A-Za-z0-9_-]+|api_key.*sk-|LLM_API_KEY=.*[A-Za-z0-9]" --hidden --glob '!config.local.json' --glob '!.cache/**' --glob '!.git/**' .
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
├── docs/
│   └── screenshot.jpg      # GitHub README 截图
└── .gitignore
```

## 免责声明

本项目输出仅用于行情复盘、研究和技术演示。市场数据可能存在延迟、缺失或源站接口变更，AI 生成内容可能存在误判。任何投资决策请自行核验并承担风险。
