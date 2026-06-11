# A股行业板块扫描终端

本项目是一个本地运行的 A 股行业板块扫描系统。前端保留原型终端式页面，后端使用 Python 标准库 HTTP 服务提供接口，优先通过 WeStock Data 获取行情，AKShare 作为备选数据源。

## 功能

- 按日期扫描 A 股标准行业板块。
- 只展示行业板块，剔除概念、主题、昨日涨停、昨日连板等非行业板块。
- 板块热力图按当日涨幅排序，展示前 20 强。
- 领涨板块走势图与热力图保持同一组板块。
- 资金流展示 1 日、5 日、20 日维度。
- AI 生成核心方向、市场信号和策略总结，失败时自动使用规则兜底。
- 日期扫描结果本地缓存；普通扫描优先读缓存，重新扫描会覆盖该日期缓存。

## 本地运行

```bash
python3 server.py --host 127.0.0.1 --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

macOS 也可以双击 `start_server.command` 启动。

## AI 配置

复制示例配置：

```bash
cp config.local.example.json config.local.json
```

在 `config.local.json` 中填写：

- `llm.base_url`
- `llm.model`
- `llm.api_key`

也可以使用环境变量覆盖：

- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

`config.local.json` 已加入 `.gitignore`，不会提交到仓库。

## 数据说明

- 主数据源：WeStock Data / 腾讯自选股。
- 备选数据源：AKShare。
- 本系统仅用于研究扫描，不构成投资建议。
