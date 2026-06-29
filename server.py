#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import copy
import datetime as dt
import html as html_lib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / ".cache"
DATA_JS = BASE_DIR / "data.js"
CONFIG_LOCAL = BASE_DIR / "config.local.json"
CACHE_VERSION = "2026-06-11-industry-top20-v2"

DEFAULT_CONFIG = {
    "llm": {
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "model": "glm5",
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 2200,
        "enable_thinking": False,
        "timeout_seconds": 45,
    },
    "market": {
        "primary_source": "westock",
        "top": 20,
        "trend": 5,
        "industry_candidates": 28,
        "concept_candidates": 18,
        "history_days": 90,
        "http_timeout_seconds": 10,
        "westock_hot_limit": 300,
        "westock_candidate_limit": 300,
        "westock_kline_limit": 45,
        "westock_batch_size": 30,
        "westock_kline_workers": 4,
        "westock_timeout_seconds": 90,
        "industry_only": True,
        "review_universe_ttl_days": 7,
        "review_breadth_batch_size": 500,
        "review_breadth_workers": 4,
        "review_sector_workers": 6,
    },
    "chanlun": {
        "bars": 220,
        "westock_kline_limit": 260,
        "min_stroke_gap": 4,
    },
}

INDEX_SYMBOLS = [
    ("上证指数", "SSE", "sh000001"),
    ("沪深300", "CSI300", "sh000300"),
    ("创业板指", "GEM", "sz399006"),
    ("科创综指", "STAR", "sh000680"),
    ("科创50", "STAR50", "sh000688"),
    ("深证成指", "SZSE", "sz399001"),
]

CHANLUN_DEFAULT_STOCKS = [
    {"code": "000001.SH", "symbol": "sh000001", "name": "上证指数", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399001.SZ", "symbol": "sz399001", "name": "深证成指", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399006.SZ", "symbol": "sz399006", "name": "创业板指", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000300.SH", "symbol": "sh000300", "name": "沪深300", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000905.SH", "symbol": "sh000905", "name": "中证500", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000852.SH", "symbol": "sh000852", "name": "中证1000", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000016.SH", "symbol": "sh000016", "name": "上证50", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000010.SH", "symbol": "sh000010", "name": "上证180", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000009.SH", "symbol": "sh000009", "name": "上证380", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000903.SH", "symbol": "sh000903", "name": "中证100", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000906.SH", "symbol": "sh000906", "name": "中证800", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000985.SH", "symbol": "sh000985", "name": "中证全指", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000680.SH", "symbol": "sh000680", "name": "科创综指", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000688.SH", "symbol": "sh000688", "name": "科创50", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399330.SZ", "symbol": "sz399330", "name": "深证100", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399005.SZ", "symbol": "sz399005", "name": "中小100", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399673.SZ", "symbol": "sz399673", "name": "创业板50", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399303.SZ", "symbol": "sz399303", "name": "国证2000", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000015.SH", "symbol": "sh000015", "name": "上证红利", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "399324.SZ", "symbol": "sz399324", "name": "深证红利", "market": "指数", "unit": "点", "group": "宽基指数"},
    {"code": "000928.SH", "symbol": "sh000928", "name": "中证能源", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000929.SH", "symbol": "sh000929", "name": "中证材料", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000930.SH", "symbol": "sh000930", "name": "中证工业", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000931.SH", "symbol": "sh000931", "name": "中证可选", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000932.SH", "symbol": "sh000932", "name": "中证消费", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000933.SH", "symbol": "sh000933", "name": "中证医药", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000934.SH", "symbol": "sh000934", "name": "中证金融", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000935.SH", "symbol": "sh000935", "name": "中证信息", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000936.SH", "symbol": "sh000936", "name": "中证电信", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000937.SH", "symbol": "sh000937", "name": "中证公用", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000986.SH", "symbol": "sh000986", "name": "全指能源", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000987.SH", "symbol": "sh000987", "name": "全指材料", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000988.SH", "symbol": "sh000988", "name": "全指工业", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000989.SH", "symbol": "sh000989", "name": "全指可选", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000990.SH", "symbol": "sh000990", "name": "全指消费", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000991.SH", "symbol": "sh000991", "name": "全指医药", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000992.SH", "symbol": "sh000992", "name": "全指金融", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000993.SH", "symbol": "sh000993", "name": "全指信息", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000994.SH", "symbol": "sh000994", "name": "全指电信", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000995.SH", "symbol": "sh000995", "name": "全指公用", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399986.SZ", "symbol": "sz399986", "name": "中证银行", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399975.SZ", "symbol": "sz399975", "name": "证券公司", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399967.SZ", "symbol": "sz399967", "name": "中证军工", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399808.SZ", "symbol": "sz399808", "name": "中证新能", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399976.SZ", "symbol": "sz399976", "name": "CS新能车", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399989.SZ", "symbol": "sz399989", "name": "中证医疗", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399971.SZ", "symbol": "sz399971", "name": "中证传媒", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "399998.SZ", "symbol": "sz399998", "name": "中证煤炭", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000819.SH", "symbol": "sh000819", "name": "有色金属", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "000827.SH", "symbol": "sh000827", "name": "中证环保", "market": "指数", "unit": "点", "group": "行业指数"},
    {"code": "600519", "symbol": "sh600519", "name": "贵州茅台", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "300750", "symbol": "sz300750", "name": "宁德时代", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "601318", "symbol": "sh601318", "name": "中国平安", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "600036", "symbol": "sh600036", "name": "招商银行", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "002594", "symbol": "sz002594", "name": "比亚迪", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "688981", "symbol": "sh688981", "name": "中芯国际", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "601138", "symbol": "sh601138", "name": "工业富联", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "002475", "symbol": "sz002475", "name": "立讯精密", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "300059", "symbol": "sz300059", "name": "东方财富", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "600900", "symbol": "sh600900", "name": "长江电力", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "601899", "symbol": "sh601899", "name": "紫金矿业", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "000858", "symbol": "sz000858", "name": "五粮液", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "601127", "symbol": "sh601127", "name": "赛力斯", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "000725", "symbol": "sz000725", "name": "京东方A", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "300308", "symbol": "sz300308", "name": "中际旭创", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "300502", "symbol": "sz300502", "name": "新易盛", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "688256", "symbol": "sh688256", "name": "寒武纪", "market": "A股", "unit": "¥", "group": "热门股票"},
    {"code": "00700", "symbol": "hk00700", "name": "腾讯控股", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "09988", "symbol": "hk09988", "name": "阿里巴巴", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "03690", "symbol": "hk03690", "name": "美团", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "01810", "symbol": "hk01810", "name": "小米集团", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "01024", "symbol": "hk01024", "name": "快手", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "09618", "symbol": "hk09618", "name": "京东集团", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "00981", "symbol": "hk00981", "name": "中芯国际", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "01211", "symbol": "hk01211", "name": "比亚迪股份", "market": "港股", "unit": "HK$", "group": "港股热门"},
    {"code": "00388", "symbol": "hk00388", "name": "香港交易所", "market": "港股", "unit": "HK$", "group": "港股热门"},
]

HOT_KW = ("机器人", "AI", "算力", "芯片", "光模块", "半导体", "6G", "低空", "航天", "军工")
PRIVATE_NAMES = {
    "config.local.json",
    "config.local.example.json",
    "server.py",
    ".gitignore",
}

_scan_lock = threading.Lock()
_ak = None
_requests_patched = False


def log(msg: str) -> None:
    print(f"[sector-scan] {msg}", file=sys.stderr)


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if CONFIG_LOCAL.exists():
        with CONFIG_LOCAL.open("r", encoding="utf-8") as f:
            cfg = deep_merge(cfg, json.load(f))

    llm = cfg.setdefault("llm", {})
    if os.environ.get("LLM_BASE_URL"):
        llm["base_url"] = os.environ["LLM_BASE_URL"]
    if os.environ.get("LLM_MODEL"):
        llm["model"] = os.environ["LLM_MODEL"]
    if os.environ.get("LLM_API_KEY"):
        llm["api_key"] = os.environ["LLM_API_KEY"]
    return cfg


def normalize_model_name(model: Any) -> str:
    text = str(model or "").strip()
    aliases = {
        "glm5": "glm-5",
        "glm51": "glm-5.1",
        "glm47": "glm-4.7",
        "glm46": "glm-4.6",
    }
    return aliases.get(text.lower(), text)


def patch_requests_timeout(timeout: int) -> None:
    global _requests_patched
    if _requests_patched:
        return
    try:
        import requests
    except Exception:
        return

    original = requests.sessions.Session.request

    def request_with_timeout(self, method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return original(self, method, url, **kwargs)

    requests.sessions.Session.request = request_with_timeout
    _requests_patched = True


def get_ak():
    global _ak
    if _ak is None:
        import akshare as akshare
        _ak = akshare
    return _ak


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
            if value in ("", "-", "--", "nan", "None"):
                return default
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return default
        return num
    except Exception:
        return default


def clean_value(value: Any) -> Any:
    try:
        if value is None or value != value:
            return None
    except Exception:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()[:10]
        except Exception:
            pass
    return value


def records(df: Any) -> list[dict]:
    if df is None:
        return []
    try:
        return [{str(k): clean_value(v) for k, v in row.items()} for row in df.to_dict("records")]
    except Exception:
        return []


def get_field(row: dict, *names: str) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    for name in names:
        for key, value in row.items():
            if name in key:
                return value
    return None


def parse_iso_date(raw: Any) -> dt.date | None:
    if raw is None:
        return None
    if isinstance(raw, dt.datetime):
        return raw.date()
    if isinstance(raw, dt.date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    text = text[:10].replace("/", "-")
    try:
        return dt.date.fromisoformat(text)
    except Exception:
        return None


def parse_request_date(value: str | None) -> dt.date:
    if value:
        parsed = parse_iso_date(value)
        if parsed:
            return parsed
    return dt.date.today()


def ymd(value: dt.date) -> str:
    return value.strftime("%Y%m%d")


def pct_change(values: list[float], days: int) -> float:
    if len(values) <= days:
        return 0.0
    base = values[-1 - days]
    if not base:
        return 0.0
    return round((values[-1] / base - 1) * 100, 2)


def rsi(closes: list[float], period: int = 6) -> float:
    if len(closes) <= period:
        return 50.0
    gains = losses = 0.0
    for idx in range(len(closes) - period, len(closes)):
        diff = closes[idx] - closes[idx - 1]
        gains += max(diff, 0)
        losses += max(-diff, 0)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return round(100 - 100 / (1 + rs), 2)


def ema(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    k = 2 / (span + 1)
    out = [values[0]]
    for val in values[1:]:
        out.append(val * k + out[-1] * (1 - k))
    return out


def macd(closes: list[float]) -> tuple[float, float, float]:
    if len(closes) < 2:
        return 0.0, 0.0, 0.0
    dif = [a - b for a, b in zip(ema(closes, 12), ema(closes, 26))]
    dea = ema(dif, 9)
    return round(dif[-1], 2), round(dea[-1], 2), round(2 * (dif[-1] - dea[-1]), 2)


def date_rows(rows: list[dict]) -> list[tuple[dt.date, dict]]:
    out = []
    for row in rows:
        d = parse_iso_date(get_field(row, "日期", "date", "时间"))
        if d:
            out.append((d, row))
    out.sort(key=lambda item: item[0])
    return out


def rows_until(rows: list[tuple[dt.date, dict]], target: dt.date) -> list[tuple[dt.date, dict]]:
    return [item for item in rows if item[0] <= target]


def last_at_or_before(rows: list[tuple[dt.date, dict]], target: dt.date) -> tuple[dt.date, dict] | None:
    filtered = rows_until(rows, target)
    return filtered[-1] if filtered else None


def split_md_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown_table(lines: list[str]) -> list[dict]:
    rows = [split_md_row(line) for line in lines if line.strip().startswith("|")]
    if len(rows) < 2:
        return []
    headers = rows[0]
    start = 1
    if all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in rows[1]):
        start = 2
    out = []
    for cells in rows[start:]:
        if not cells or all(not cell for cell in cells):
            continue
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        out.append({headers[idx]: cells[idx] for idx in range(min(len(headers), len(cells)))})
    return out


def parse_markdown_tables(text: str) -> list[tuple[str, list[dict]]]:
    heading = ""
    tables: list[tuple[str, list[dict]]] = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("**") and line.endswith("**"):
            heading = line.strip("*").strip()
            idx += 1
            continue
        if line.startswith("|"):
            block = []
            while idx < len(lines) and lines[idx].strip().startswith("|"):
                block.append(lines[idx])
                idx += 1
            rows = parse_markdown_table(block)
            if rows:
                tables.append((heading, rows))
            continue
        idx += 1
    return tables


def westock_run(args: list[str], cfg: dict) -> str:
    market_cfg = cfg.get("market", {})
    timeout = int(market_cfg.get("westock_timeout_seconds", 35))
    cmd = ["npx", "-y", "westock-data-clawhub@1.0.4", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"WeStock {' '.join(args)} failed: {err[:240]}")
    text = proc.stdout.strip()
    if not text:
        raise RuntimeError(f"WeStock {' '.join(args)} returned empty output")
    return text


def first_table_rows(text: str) -> list[dict]:
    tables = parse_markdown_tables(text)
    return tables[0][1] if tables else []


def parse_lead_stock(raw: Any) -> dict | None:
    text = str(raw or "").strip()
    if not text or text in {"-", "--"}:
        return None
    match = re.match(r"(.+?)\((-?\d+(?:\.\d+)?)%?\)", text)
    if match:
        return {"nm": match.group(1).strip(), "v": round(safe_float(match.group(2)), 2)}
    return {"nm": text, "v": 0.0}


def westock_type_from_row(row: dict) -> str:
    stock_type = str(row.get("stock_type") or "").upper()
    return "行业" if "HY" in stock_type else "概念"


def is_standard_industry_candidate(item: dict) -> bool:
    if item.get("cn") != "行业":
        return False
    stock_type = str(item.get("_stockType") or "").upper()
    if stock_type and "HY" not in stock_type:
        return False
    name = str(item.get("name") or "")
    blocked = ("概念", "昨日", "涨停", "连板", "首板")
    return not any(word in name for word in blocked)


def westock_kline(symbol: str, cfg: dict, limit: int | None = None) -> list[tuple[dt.date, dict]]:
    if not symbol:
        return []
    market_cfg = cfg.get("market", {})
    kline_limit = int(limit or market_cfg.get("westock_kline_limit", 45))
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            text = westock_run(["kline", symbol, "--period", "day", "--limit", str(kline_limit)], cfg)
            rows = date_rows(first_table_rows(text))
            if rows:
                return rows
            last_error = RuntimeError(f"WeStock kline {symbol} returned no rows")
        except Exception as exc:
            last_error = exc
        if attempt == 0:
            time.sleep(0.4)
    if last_error:
        raise last_error
    return []


def westock_kline_batch(symbols: list[str], cfg: dict, limit: int | None = None) -> dict[str, list[tuple[dt.date, dict]]]:
    symbols = [symbol for symbol in symbols if symbol]
    if not symbols:
        return {}
    market_cfg = cfg.get("market", {})
    kline_limit = int(limit or market_cfg.get("westock_kline_limit", 45))
    text = westock_run(["kline", ",".join(symbols), "--period", "day", "--limit", str(kline_limit)], cfg)
    rows = first_table_rows(text)
    grouped: dict[str, list[dict]] = {symbol: [] for symbol in symbols}
    single_symbol = symbols[0] if len(symbols) == 1 else ""
    for row in rows:
        symbol = str(row.get("symbol") or single_symbol or "").strip()
        if symbol in grouped:
            grouped[symbol].append(row)
    return {symbol: date_rows(items) for symbol, items in grouped.items() if items}


def chunked(items: list[str], size: int) -> list[list[str]]:
    size = max(1, size)
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def westock_search_stock(name: str, cfg: dict) -> str:
    if not name:
        return ""
    try:
        rows = first_table_rows(westock_run(["search", name, "--stock"], cfg))
    except Exception:
        try:
            rows = first_table_rows(westock_run(["search", name], cfg))
        except Exception:
            return ""
    for row in rows:
        code = str(row.get("code") or row.get("symbol") or "").strip()
        if code:
            return code
    return ""


def clean_sector_private_fields(data: dict) -> None:
    for bucket in ("sectors", "heatmap", "concepts"):
        for item in data.get(bucket, []) or []:
            if isinstance(item, dict):
                for key in list(item.keys()):
                    if key.startswith("_"):
                        item.pop(key, None)
    data.pop("_universe", None)


def quote_js_keys(text: str) -> str:
    return re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)\s*:", r'\1"\2":', text)


def parse_data_js(path: Path = DATA_JS) -> dict:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    match = re.search(r"window\.TERMINAL_DATA\s*=\s*(\{.*\})\s*;?\s*$", text, flags=re.S)
    if not match:
        raise ValueError("data.js shape not recognized")
    body = quote_js_keys(match.group(1))
    body = re.sub(r",\s*([}\]])", r"\1", body)
    return json.loads(body)


def latest_cache(target: dt.date | None = None) -> dict | None:
    if not CACHE_DIR.exists():
        return None
    files = sorted(CACHE_DIR.glob("scan_*.json"), reverse=True)
    for path in files:
        if target:
            parsed = parse_iso_date(path.stem.replace("scan_", ""))
            if parsed and parsed > target:
                continue
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            continue
    return None


def request_cache_path(requested: dt.date) -> Path:
    return CACHE_DIR / f"scan_request_{requested.isoformat()}.json"


def load_request_cache(requested: dt.date) -> dict | None:
    path = request_cache_path(requested)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("meta", {}).get("cacheVersion") != CACHE_VERSION:
            return None
        data.setdefault("meta", {})["cacheHit"] = True
        return data
    except Exception as exc:
        log(f"request cache read failed: {path.name}: {exc}")
        return None


def write_request_cache(requested: dt.date, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    meta = data.setdefault("meta", {})
    meta["cacheVersion"] = CACHE_VERSION
    meta["cacheHit"] = False
    path = request_cache_path(requested)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_md_label(label: Any, ref_year: int) -> dt.date | None:
    text = str(label or "").strip()
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if not match:
        return parse_iso_date(text)
    month, day = int(match.group(1)), int(match.group(2))
    try:
        return dt.date(ref_year, month, day)
    except ValueError:
        return None


def project_snapshot_to_date(data: dict, requested: dt.date) -> dict:
    data = copy.deepcopy(data)
    meta = data.setdefault("meta", {})
    ref_date = parse_iso_date(meta.get("tradeDate")) or requested
    ref_year = ref_date.year

    available: set[dt.date] = set()
    for sector in data.get("sectors", []):
        for label in sector.get("dates", []):
            parsed = parse_md_label(label, ref_year)
            if parsed:
                available.add(parsed)
    if not available:
        meta["tradeDate"] = ref_date.isoformat()
        return data

    candidates = [item for item in available if item <= requested]
    trade_date = max(candidates) if candidates else min(available)

    updated_by_name = {}
    for sector in data.get("sectors", []):
        labels = sector.get("dates", [])
        dated = [(parse_md_label(label, ref_year), idx) for idx, label in enumerate(labels)]
        dated = [(date, idx) for date, idx in dated if date and date <= trade_date]
        if not dated:
            continue
        _, idx = max(dated, key=lambda item: item[0])
        raw = [safe_float(value) for value in sector.get("kline", [])[: idx + 1]]
        raw = [value for value in raw if value > 0]
        if not raw:
            continue
        today = pct_change(raw, 1) if len(raw) > 1 else safe_float(sector.get("today"))
        sector["today"] = today
        sector["d5"] = pct_change(raw, 5)
        sector["d20"] = pct_change(raw, min(19, max(len(raw) - 1, 0)))
        sector["kline"] = raw[-20:]
        sector["dates"] = labels[max(0, idx - 19): idx + 1]
        sector["badges"] = []
        if sector["today"] >= 4 or safe_float(sector.get("turnover")) >= 8:
            sector["badges"].append("HOT")
        elif sector["d5"] >= 3:
            sector["badges"].append("UP")
        elif sector["d20"] >= 10:
            sector["badges"].append("STRONG")
        updated_by_name[sector["name"]] = sector

    for item in data.get("heatmap", []):
        sector = updated_by_name.get(item.get("name"))
        if not sector:
            continue
        item["t"] = sector["today"]
        item["d5"] = sector["d5"]
        item["d20"] = sector["d20"]
        item["turnover"] = sector.get("turnover", item.get("turnover", 0))
    data["heatmap"] = sorted(
        data.get("heatmap", []),
        key=lambda item: abs(safe_float(item.get("t"))) * 2 + safe_float(item.get("turnover")),
        reverse=True,
    )
    for idx, item in enumerate(data.get("heatmap", []), 1):
        item["rank"] = idx

    sectors = sorted(
        data.get("sectors", []),
        key=lambda item: abs(safe_float(item.get("today"))) * 2 + safe_float(item.get("turnover")),
        reverse=True,
    )
    for idx, item in enumerate(sectors, 1):
        item["rank"] = idx
    data["sectors"] = sectors

    trend_sectors = sectors[: max(len(data.get("trend", {}).get("series", [])), 5)]
    palette = ["#e1322f", "#1657d4", "#b3760b", "#7c3aed", "#008f5d", "#0aa6b8"]
    longest = max(trend_sectors, key=lambda item: len(item.get("dates", [])), default=None)
    data["trend"] = {
        "dates": (longest or {}).get("dates", []),
        "series": [
            {
                "name": item["name"],
                "color": palette[idx % len(palette)],
                "chg": f'{safe_float(item.get("d20")):+.1f}% (20D)',
                "raw": item.get("kline", []),
            }
            for idx, item in enumerate(trend_sectors[:5])
        ],
    }

    tech = []
    for item in sectors[:3]:
        closes = item.get("_techKline") or item.get("kline", [])
        r6 = rsi(closes)
        dif, dea, m = macd(closes)
        signal = "BULL" if m > 0 and r6 >= 50 else "BEAR" if m < 0 and r6 <= 45 else "NEUTRAL"
        tech.append({"name": item["name"], "rsi6": r6, "dif": dif, "dea": dea, "macd": m, "signal": signal})
    if tech:
        data["tech"] = tech

    top = sectors[0] if sectors else None
    up_count = sum(1 for item in data.get("heatmap", []) if safe_float(item.get("t")) > 0)
    data["stats"] = [
        {"name": "板块数", "en": "BREADTH", "value": str(len(data.get("heatmap", []))), "tag": "快照板块", "cls": "flat"},
        {
            "name": "今日热度 #1",
            "en": "TOP HEAT",
            "value": top["name"] if top else "—",
            "sub": f'{safe_float(top.get("today")):+.2f}% · 快照回放' if top else "—",
            "cls": "up" if top and safe_float(top.get("today")) >= 0 else "down",
            "accent": True,
        },
        {"name": "上涨板块", "en": "ADV", "value": str(up_count), "sub": "快照样本", "cls": "up" if up_count else "flat"},
    ]
    meta["tradeDate"] = trade_date.isoformat()
    return data


def fallback_data(requested: dt.date, reason: str, status: str = "fallback", cfg: dict | None = None) -> dict:
    cached = latest_cache(requested)
    if cached and cached.get("meta", {}).get("aiStatus") == "ok":
        data = copy.deepcopy(cached)
        meta = data.setdefault("meta", {})
        meta["requestedDate"] = requested.isoformat()
        meta["fallbackReason"] = reason[:180]
        return data

    data = cached or parse_data_js()
    data = project_snapshot_to_date(data, requested)
    meta = data.setdefault("meta", {})
    meta["requestedDate"] = requested.isoformat()
    meta["asOf"] = meta.get("asOf") or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    meta["dataStatus"] = status
    meta["aiStatus"] = meta.get("aiStatus") or "fallback"
    meta["fallbackReason"] = reason[:180]
    try:
        build_rule_analysis(data)
        if cfg:
            apply_ai_analysis(data, cfg)
    except Exception as exc:
        log(f"fallback analysis failed: {exc}")
    try:
        trade_date = parse_iso_date(meta.get("tradeDate"))
        if trade_date:
            CACHE_DIR.mkdir(exist_ok=True)
            with (CACHE_DIR / f"scan_{trade_date.isoformat()}.json").open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        log(f"fallback cache write failed: {exc}")
    return data


def merge_westock_candidate(candidates: dict[str, dict], name: str, values: dict) -> None:
    name = str(name or "").strip()
    if not name:
        return
    item = candidates.setdefault(name, {"name": name})
    for key, value in values.items():
        if value is None or value == "":
            continue
        if key == "cn" and item.get("cn") == "行业":
            continue
        item[key] = value


def fetch_westock_candidate_rows(target: dt.date, cfg: dict) -> tuple[list[dict], str]:
    market_cfg = cfg.get("market", {})
    hot_limit = int(market_cfg.get("westock_hot_limit", 60))
    board_text = westock_run(["board"], cfg)
    hot_text = westock_run(["hot", "board", "--limit", str(hot_limit)], cfg)

    board_tables = parse_markdown_tables(board_text)
    hot_rows = []
    for _, rows in parse_markdown_tables(hot_text):
        if rows and "symbol" in rows[0] and "name" in rows[0]:
            hot_rows = rows
            break

    symbol_by_name = {str(row.get("name") or "").strip(): str(row.get("symbol") or "").strip() for row in hot_rows}
    hot_by_name = {str(row.get("name") or "").strip(): row for row in hot_rows if str(row.get("name") or "").strip()}
    observed_at = ""
    for row in hot_rows:
        observed_at = str(row.get("date") or "").strip()
        if observed_at:
            break

    candidates: dict[str, dict] = {}
    flow_rows = []
    for heading, rows in board_tables:
        if "行业板块" in heading and "涨幅" in heading:
            cn = "行业"
        elif "概念板块" in heading and "涨幅" in heading:
            cn = "概念"
        elif "资金流入" in heading:
            flow_rows = rows
            continue
        else:
            continue
        for row in rows:
            name = str(row.get("name") or "").strip()
            merge_westock_candidate(
                candidates,
                name,
                {
                    "cn": cn,
                    "today": safe_float(row.get("changePct")),
                    "turnover": safe_float(row.get("turnoverRate")),
                    "d5": safe_float(row.get("changePct5d")),
                    "d20": safe_float(row.get("changePct20d")),
                    "leadStock": str(row.get("leadStock") or "").strip(),
                    "_sourceSymbol": symbol_by_name.get(name, ""),
                    "_boardSource": "board",
                },
            )

    for row in flow_rows:
        name = str(row.get("name") or "").strip()
        merge_westock_candidate(
            candidates,
            name,
            {
                "cn": "行业",
                "today": safe_float(row.get("changePct")),
                "_mainNetInflow": safe_float(row.get("mainNetInflow")),
                "_mainNetInflow5d": safe_float(row.get("mainNetInflow5d")),
                "_upDownRatio": str(row.get("upDownRatio") or "").strip(),
                "_sourceSymbol": symbol_by_name.get(name, ""),
                "_boardSource": "flow",
            },
        )

    for row in hot_rows:
        name = str(row.get("name") or "").strip()
        merge_westock_candidate(
            candidates,
            name,
            {
                "cn": westock_type_from_row(row),
                "today": safe_float(row.get("zdf")),
                "_hotRank": safe_float(row.get("rank"), 9999),
                "_hotIndex": safe_float(row.get("index")),
                "_sourceSymbol": str(row.get("symbol") or "").strip(),
                "_latestPrice": safe_float(row.get("zxj")),
                "_hotDate": str(row.get("date") or "").strip(),
                "_stockType": str(row.get("stock_type") or "").strip(),
            },
        )

    for name, row in hot_by_name.items():
        if name in candidates:
            candidates[name]["_hotRank"] = safe_float(row.get("rank"), candidates[name].get("_hotRank", 9999))
            candidates[name]["_sourceSymbol"] = str(row.get("symbol") or candidates[name].get("_sourceSymbol") or "").strip()

    if not candidates:
        raise RuntimeError("WeStock board candidate list is empty")
    return list(candidates.values()), observed_at


def westock_seed_score(item: dict) -> float:
    hot_rank = safe_float(item.get("_hotRank"), 9999)
    hot_boost = max(0.0, 70.0 - hot_rank) / 8.0 if hot_rank < 9999 else 0.0
    flow_boost = max(safe_float(item.get("_mainNetInflow")), 0.0) / 30000.0
    return (
        abs(safe_float(item.get("today"))) * 2.8
        + safe_float(item.get("turnover")) * 1.35
        + max(safe_float(item.get("d5")), 0.0) * 0.65
        + max(safe_float(item.get("d20")), 0.0) * 0.25
        + hot_boost
        + flow_boost
    )


def build_westock_sector_item(candidate: dict, hist: list[tuple[dt.date, dict]], trade_date: dt.date) -> dict | None:
    filtered = rows_until(hist, trade_date)
    if not filtered:
        return None
    last_date, last = filtered[-1]
    closes = [safe_float(get_field(row, "last", "close", "收盘", "收盘价")) for _, row in filtered]
    closes = [value for value in closes if value > 0]
    if not closes:
        return None

    today = pct_change(closes, 1) if len(closes) > 1 else safe_float(candidate.get("today"))
    turnover = safe_float(get_field(last, "exchange", "换手率"), safe_float(candidate.get("turnover")))
    item = {
        "name": candidate["name"],
        "cn": candidate.get("cn") or "概念",
        "today": round(today, 2),
        "d5": pct_change(closes, 5),
        "d20": pct_change(closes, min(19, max(len(closes) - 1, 0))),
        "turnover": round(turnover, 2),
        "heat": 0,
        "rank": 0,
        "badges": [],
        "kline": [round(value, 2) for value in closes[-20:]],
        "_techKline": [round(value, 2) for value in closes[-60:]],
        "dates": [f"{d.month}/{d.day}" for d, _ in filtered[-20:]],
        "leadStock": candidate.get("leadStock", ""),
        "_tradeDate": last_date.isoformat(),
        "_sourceSymbol": candidate.get("_sourceSymbol", ""),
        "_hotRank": candidate.get("_hotRank", 9999),
        "_mainNetInflow": candidate.get("_mainNetInflow"),
        "_mainNetInflow5d": candidate.get("_mainNetInflow5d"),
        "_upDownRatio": candidate.get("_upDownRatio", ""),
    }
    if item["today"] >= 4 or item["turnover"] >= 8:
        item["badges"].append("HOT")
    elif item["d5"] >= 3:
        item["badges"].append("UP")
    elif item["d20"] >= 10:
        item["badges"].append("STRONG")
    if any(kw in item["name"] for kw in HOT_KW):
        item["badges"].append("AI")
    item["_marketScore"] = westock_market_score(item)
    return item


def westock_market_score(item: dict) -> float:
    hot_rank = safe_float(item.get("_hotRank"), 9999)
    hot_boost = max(0.0, 75.0 - hot_rank) / 12.0 if hot_rank < 9999 else 0.0
    flow_boost = max(safe_float(item.get("_mainNetInflow")), 0.0) / 35000.0
    return (
        abs(safe_float(item.get("today"))) * 2.4
        + safe_float(item.get("turnover")) * 1.25
        + max(safe_float(item.get("d5")), 0.0) * 0.55
        + max(safe_float(item.get("d20")), 0.0) * 0.22
        + hot_boost
        + flow_boost
    )


def estimate_sector_flow(sector: dict, pct_key: str, scale: float) -> float:
    return round(
        safe_float(sector.get(pct_key))
        * max(safe_float(sector.get("turnover")), 0.2)
        * scale,
        0,
    )


def build_westock_flows(sectors: list[dict]) -> list[dict]:
    flows = []
    for sector in sectors:
        if sector.get("_mainNetInflow") is not None:
            val = round(safe_float(sector.get("_mainNetInflow")), 0)
        else:
            val = estimate_sector_flow(sector, "today", 1800)
        if sector.get("_mainNetInflow5d") is not None:
            val5 = round(safe_float(sector.get("_mainNetInflow5d")), 0)
        else:
            val5 = estimate_sector_flow(sector, "d5", 1400)
        val20 = estimate_sector_flow(sector, "d20", 900)
        flows.append(
            {
                "name": sector["name"],
                "type": sector.get("cn", "板块"),
                "val": val,
                "val5": val5,
                "val20": val20,
            }
        )
    flows.sort(key=lambda item: item["val"], reverse=True)
    positives = flows[:6]
    negatives = sorted(flows, key=lambda item: item["val"])[:4]
    picked = []
    seen = set()
    for item in positives + negatives:
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        picked.append(item)
    return picked


def build_market_signals(data: dict) -> None:
    sectors = data.get("sectors", [])
    flows = data.get("flows", [])
    if not sectors:
        data["signals"] = []
        return
    top = sectors[0]
    up_count = sum(1 for item in sectors if safe_float(item.get("today")) > 0)
    down_count = sum(1 for item in sectors if safe_float(item.get("today")) < 0)
    trend_ok = [item for item in sectors if safe_float(item.get("d5")) > 0 and safe_float(item.get("d20")) > 0]
    strongest_20 = max(sectors, key=lambda item: safe_float(item.get("d20")))
    weakest = min(sectors, key=lambda item: safe_float(item.get("today")))
    best_flow = max(flows, key=lambda item: safe_float(item.get("val")), default=None)
    best_flow5 = max(flows, key=lambda item: safe_float(item.get("val5")), default=None)
    top_turnover = max(sectors, key=lambda item: safe_float(item.get("turnover")))
    breadth_cls = "up" if up_count >= len(sectors) * 0.55 else "down" if up_count <= len(sectors) * 0.35 else "flat"
    breadth_dot = "bullish" if breadth_cls == "up" else "bearish" if breadth_cls == "down" else "neutral"

    data["signals"] = [
        {
            "dot": "bullish" if safe_float(top.get("today")) >= 0 else "bearish",
            "cls": "up" if safe_float(top.get("today")) >= 0 else "down",
            "tag": "RANK",
            "text": f'前20强中 {top["name"]} 综合强度第一，今日{safe_float(top.get("today")):+.2f}%，5日{safe_float(top.get("d5")):+.2f}%，换手{safe_float(top.get("turnover")):.1f}%。',
            "val": "#1",
        },
        {
            "dot": breadth_dot,
            "cls": breadth_cls,
            "tag": "BREADTH",
            "text": f"前20强上涨 {up_count} 个、下跌 {down_count} 个，{len(trend_ok)} 个板块同时保持5日和20日正收益。",
            "val": f"{up_count}/{len(sectors)}",
        },
        {
            "dot": "bullish" if best_flow and safe_float(best_flow.get("val")) >= 0 else "neutral",
            "cls": "up" if best_flow and safe_float(best_flow.get("val")) >= 0 else "flat",
            "tag": "FLOW",
            "text": (
                f'{best_flow["name"]} 1日资金强度居前，'
                f'{best_flow5["name"]} 5日资金延续性最好。'
                if best_flow and best_flow5
                else "资金维度以板块涨跌、换手和可用主力净流入共同估算。"
            ),
            "val": f'{safe_float(best_flow.get("val"))/10000:+.1f}亿' if best_flow else "FLOW",
        },
        {
            "dot": "bullish" if safe_float(strongest_20.get("d20")) > 0 else "neutral",
            "cls": "up" if safe_float(strongest_20.get("d20")) > 0 else "flat",
            "tag": "TREND",
            "text": f'{strongest_20["name"]} 20日涨幅{safe_float(strongest_20.get("d20")):+.2f}%，是当前前20强中中期趋势最强方向。',
            "val": "20D",
        },
        {
            "dot": "neutral" if safe_float(top_turnover.get("turnover")) < 10 else "bearish",
            "cls": "flat" if safe_float(top_turnover.get("turnover")) < 10 else "down",
            "tag": "RISK",
            "text": f'{top_turnover["name"]} 换手{safe_float(top_turnover.get("turnover")):.1f}%，{weakest["name"]} 今日{safe_float(weakest.get("today")):+.2f}%，注意强势板块内部分化和高位承接。',
            "val": "CHECK",
        },
    ]


def build_westock_leader_table(universe: list[dict]) -> list[dict]:
    concepts = [item for item in universe if item.get("cn") == "行业"]
    concepts.sort(key=lambda item: safe_float(item.get("today")), reverse=True)
    out = []
    for item in concepts[:10]:
        lead = parse_lead_stock(item.get("leadStock"))
        leader = f'{lead["nm"]} {lead["v"]:+.2f}%' if lead else "—"
        out.append(
            {
                "name": item["name"],
                "badges": item.get("badges", [])[:2],
                "today": round(safe_float(item.get("today")), 2),
                "turnover": round(safe_float(item.get("turnover")), 2),
                "d5": round(safe_float(item.get("d5")), 2),
                "d20": round(safe_float(item.get("d20")), 2),
                "leader": leader,
            }
        )
    return out


def fetch_westock_indices(target: dt.date, cfg: dict, fallback: dict | None) -> list[dict]:
    out = []
    symbols = [symbol for _, _, symbol in INDEX_SYMBOLS]
    histories: dict[str, list[tuple[dt.date, dict]]] = {}
    try:
        histories = westock_kline_batch(symbols, cfg, limit=18)
    except Exception as exc:
        log(f"westock index batch failed: {exc}")
    for name, en, symbol in INDEX_SYMBOLS:
        try:
            filtered = rows_until(histories.get(symbol) or westock_kline(symbol, cfg, limit=18), target)
            if len(filtered) < 2:
                continue
            _, last = filtered[-1]
            _, prev = filtered[-2]
            close = safe_float(get_field(last, "last", "close", "收盘"))
            prev_close = safe_float(get_field(prev, "last", "close", "收盘"), close)
            chg = round(close - prev_close, 2)
            pct = round((close / prev_close - 1) * 100, 2) if prev_close else 0.0
            out.append({"name": name, "en": en, "price": round(close, 2), "chg": chg, "pct": pct})
        except Exception as exc:
            log(f"westock index failed: {name}: {exc}")
    if out:
        return out
    return copy.deepcopy((fallback or {}).get("indices", []))


def finalize_westock_market_view(data: dict, cfg: dict) -> None:
    sectors = data.get("sectors", [])
    if not sectors:
        return
    for item in sectors:
        item["_marketScore"] = westock_market_score(item)
    max_score = max((safe_float(item.get("_marketScore")) for item in sectors), default=1) or 1
    for idx, item in enumerate(sectors, 1):
        item["rank"] = idx
        item["heat"] = int(900 + safe_float(item.get("_marketScore")) / max_score * 1600)

    data["heatmap"] = [
        {
            "name": item["name"],
            "t": round(safe_float(item.get("today")), 2),
            "d5": round(safe_float(item.get("d5")), 2),
            "d20": round(safe_float(item.get("d20")), 2),
            "heat": item["heat"],
            "rank": item["rank"],
            "turnover": round(safe_float(item.get("turnover")), 2),
        }
        for item in sectors[:20]
    ]
    data["flows"] = build_westock_flows(sectors)
    data["concepts"] = build_westock_leader_table(data.get("_universe") or sectors)

    trend_sectors = sectors[: len(data.get("heatmap", []))]
    longest = max(trend_sectors, key=lambda item: len(item.get("dates", [])), default=None)
    palette = ["#e1322f", "#1657d4", "#b3760b", "#7c3aed", "#008f5d", "#0aa6b8"]
    data["trend"] = {
        "dates": (longest or {}).get("dates", []),
        "series": [
            {
                "name": item["name"],
                "color": palette[idx % len(palette)],
                "chg": f'{safe_float(item.get("d20")):+.1f}% (20D)',
                "raw": item.get("kline", []),
            }
            for idx, item in enumerate(trend_sectors)
        ],
    }

    tech = []
    for item in sectors[:3]:
        closes = item.get("_techKline") or item.get("kline", [])
        r6 = rsi(closes)
        dif, dea, m = macd(closes)
        signal = "BULL" if m > 0 and r6 >= 50 else "BEAR" if m < 0 and r6 <= 45 else "NEUTRAL"
        tech.append({"name": item["name"], "rsi6": r6, "dif": dif, "dea": dea, "macd": m, "signal": signal})
    data["tech"] = tech

    top_sector = sectors[0]
    up_count = sum(1 for item in data.get("heatmap", []) if safe_float(item.get("t")) > 0)
    positive_flow_total = sum(max(safe_float(item.get("val")), 0) for item in data.get("flows", [])) / 10000
    data["stats"] = [
        {
            "name": "复盘候选",
            "en": "UNIVERSE",
            "value": str(len(data.get("_universe") or sectors)),
            "tag": "取前20强",
            "cls": "flat",
        },
        {
            "name": "AI热度 #1",
            "en": "TOP HEAT",
            "value": top_sector["name"],
            "sub": f'{safe_float(top_sector.get("today")):+.2f}% · 热度{top_sector["heat"]}',
            "cls": "up" if safe_float(top_sector.get("today")) >= 0 else "down",
            "accent": True,
        },
        {
            "name": "主力净流入",
            "en": "NET FLOW",
            "value": f"{positive_flow_total:+.0f}亿",
            "sub": f"上涨 {up_count}/{len(data.get('heatmap', []))}",
            "cls": "up" if positive_flow_total >= 0 else "down",
        },
    ]


def apply_ai_presentation_selection(data: dict, cfg: dict) -> None:
    top = int(cfg.get("market", {}).get("top", 20))
    all_sectors = data.get("sectors", [])
    by_name = {item["name"]: item for item in all_sectors}
    selected_raw = data.pop("selectedSectors", []) or []
    if not selected_raw:
        selected_raw = [item.get("sector") for item in data.get("picks", [])]

    market_order = sorted(
        all_sectors,
        key=lambda item: (safe_float(item.get("today")), safe_float(item.get("d5")), safe_float(item.get("turnover"))),
        reverse=True,
    )
    top_pool = market_order[:top]
    top_names = {item["name"] for item in top_pool}

    selected_names = []
    for item in selected_raw:
        name = str(item.get("name") if isinstance(item, dict) else item or "").strip()
        if name in top_names and name not in selected_names:
            selected_names.append(name)

    data["sectors"] = top_pool
    chosen_names = {item["name"] for item in data["sectors"]}
    if data.get("meta", {}).get("aiStatus") == "ok" and selected_names:
        for item in data["sectors"]:
            badges = item.setdefault("badges", [])
            if item["name"] in selected_names and "AI" not in badges:
                badges.append("AI")
        data["meta"]["screening"] = "AI动态筛选"
    else:
        data.setdefault("meta", {})["screening"] = "规则动态筛选"
    data["meta"]["candidateCount"] = len(all_sectors)
    data["meta"]["reviewScope"] = "全量板块候选复盘"
    data["meta"]["sortKey"] = "today_desc"
    data["meta"]["selectedSectors"] = [item["name"] for item in data["sectors"]]

    picks = []
    for item in data.get("picks", []):
        if item.get("sector") in chosen_names:
            picks.append(item)
    data["picks"] = picks[:6]


def fetch_westock_constituents(sectors: list[dict], trade_date: dt.date, cfg: dict) -> tuple[dict, list[dict]]:
    constituents: dict[str, list[dict]] = {}
    hot: list[dict] = []
    for sector in sectors:
        lead = parse_lead_stock(sector.get("leadStock"))
        stocks = []
        if lead and lead.get("nm"):
            code = westock_search_stock(lead["nm"], cfg)
            value = safe_float(lead.get("v"))
            if code:
                try:
                    filtered = rows_until(westock_kline(code, cfg, limit=18), trade_date)
                    closes = [safe_float(get_field(row, "last", "close", "收盘")) for _, row in filtered]
                    closes = [val for val in closes if val > 0]
                    if len(closes) > 1:
                        value = pct_change(closes, 1)
                except Exception as exc:
                    log(f"westock lead stock kline failed: {lead['nm']}: {exc}")
            stock = {"nm": lead["nm"], "code": code, "v": round(value, 2)}
            stocks.append(stock)
            hot.append({"name": stock["nm"], "sector": sector["name"], "val": stock["v"], "note": sector["name"]})
        constituents[sector["name"]] = stocks
    hot.sort(key=lambda item: item["val"], reverse=True)
    return constituents, hot[:10]


def sync_picks_with_constituents(data: dict) -> None:
    constituents = data.get("constituents", {})
    for pick in data.get("picks", []):
        leaders = constituents.get(pick.get("sector"), [])[:3]
        if not leaders:
            pick.setdefault("stocks", [])
            continue
        dynamic_tags = [{"t": row["nm"], "b": f'{row["v"]:+.1f}%'} for row in leaders if row.get("nm")]
        existing = pick.get("stocks") if isinstance(pick.get("stocks"), list) else []
        seen = {str(item.get("t") or "") for item in existing if isinstance(item, dict)}
        merged = existing[:]
        for tag in dynamic_tags:
            if tag["t"] not in seen:
                merged.insert(0, tag)
                seen.add(tag["t"])
            else:
                for item in merged:
                    if isinstance(item, dict) and item.get("t") == tag["t"] and not item.get("b"):
                        item["b"] = tag["b"]
        pick["stocks"] = merged[:3]


def build_westock_scan(requested: dt.date, cfg: dict) -> dict:
    today = dt.date.today()
    target = min(requested, today)
    fallback = latest_cache(target) or parse_data_js()
    market_cfg = cfg.get("market", {})
    candidate_limit = int(market_cfg.get("westock_candidate_limit", 42))
    batch_size = int(market_cfg.get("westock_batch_size", 8))
    workers = max(1, int(market_cfg.get("westock_kline_workers", 4)))

    candidate_rows, observed_at = fetch_westock_candidate_rows(target, cfg)
    if bool(market_cfg.get("industry_only", True)):
        candidate_rows = [item for item in candidate_rows if is_standard_industry_candidate(item)]
    candidate_rows = sorted(candidate_rows, key=westock_seed_score, reverse=True)[:candidate_limit]
    candidate_rows = [item for item in candidate_rows if item.get("_sourceSymbol")]
    if not candidate_rows:
        raise RuntimeError("WeStock board candidates have no kline symbols")

    histories_by_symbol: dict[str, list[tuple[dt.date, dict]]] = {}
    symbols = [item["_sourceSymbol"] for item in candidate_rows]
    chunks = chunked(symbols, batch_size)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(westock_kline_batch, chunk, cfg): chunk for chunk in chunks}
        for future in as_completed(future_map):
            chunk = future_map[future]
            try:
                histories_by_symbol.update(future.result())
            except Exception as exc:
                log(f"westock board kline batch failed: {','.join(chunk[:3])}: {exc}")
                for symbol in chunk:
                    try:
                        rows = westock_kline(symbol, cfg)
                        if rows:
                            histories_by_symbol[symbol] = rows
                    except Exception as item_exc:
                        log(f"westock board kline failed: {symbol}: {item_exc}")

    histories: dict[str, list[tuple[dt.date, dict]]] = {}
    for item in candidate_rows:
        rows = histories_by_symbol.get(item["_sourceSymbol"])
        if rows:
            histories[item["name"]] = rows

    available_dates = []
    for rows in histories.values():
        found = last_at_or_before(rows, target)
        if found:
            available_dates.append(found[0])
    if not available_dates:
        raise RuntimeError("No WeStock board kline is available before requested date")
    trade_date = max(available_dates)

    sectors_all = []
    for candidate in candidate_rows:
        item = build_westock_sector_item(candidate, histories.get(candidate["name"], []), trade_date)
        if item:
            sectors_all.append(item)
    if not sectors_all:
        raise RuntimeError("No WeStock sector rows can be built")
    sectors_all.sort(key=lambda item: safe_float(item.get("_marketScore")), reverse=True)

    as_of = observed_at[:16] if observed_at else dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    data = {
        "meta": {
            "source": "WeStock Data · 腾讯自选股",
            "asOf": as_of,
            "session": "日期扫描",
            "requestedDate": requested.isoformat(),
            "tradeDate": trade_date.isoformat(),
            "dataStatus": "live",
            "dataProvider": "westock",
            "selectLimit": int(market_cfg.get("top", 20)),
        },
        "indices": fetch_westock_indices(trade_date, cfg, fallback),
        "stats": [],
        "heatmap": [],
        "sectors": copy.deepcopy(sectors_all),
        "_universe": copy.deepcopy(sectors_all),
        "constituents": {},
        "flows": [],
        "signals": [],
        "picks": [],
        "trend": {},
        "tech": [],
        "hotStocks": [],
        "concepts": [],
        "strategy": {},
    }

    finalize_westock_market_view(data, cfg)
    build_rule_analysis(data)
    apply_ai_analysis(data, cfg)
    apply_ai_presentation_selection(data, cfg)
    data["constituents"], data["hotStocks"] = fetch_westock_constituents(data["sectors"], trade_date, cfg)
    finalize_westock_market_view(data, cfg)
    sync_picks_with_constituents(data)
    build_market_signals(data)
    if not data.get("picks"):
        build_rule_analysis(data)
        sync_picks_with_constituents(data)
        build_market_signals(data)

    clean_sector_private_fields(data)
    return data


def fetch_industry_candidates(target: dt.date, cfg: dict) -> tuple[list[dict], dict[str, list[tuple[dt.date, dict]]]]:
    ak = get_ak()
    market_cfg = cfg.get("market", {})
    candidate_count = int(market_cfg.get("industry_candidates", 28))
    history_days = int(market_cfg.get("history_days", 90))
    start = target - dt.timedelta(days=history_days)

    spot = records(ak.stock_board_industry_name_em())
    if not spot:
        raise RuntimeError("AKShare industry list is empty")

    def spot_score(row: dict) -> float:
        return (
            abs(safe_float(get_field(row, "涨跌幅"))) * 3
            + safe_float(get_field(row, "换手率")) * 2
            + abs(safe_float(get_field(row, "涨跌额"))) * 0.2
        )

    spot.sort(key=spot_score, reverse=True)
    names = []
    current_by_name = {}
    for row in spot:
        name = str(get_field(row, "板块名称", "名称") or "").strip()
        if not name or name in current_by_name:
            continue
        current_by_name[name] = row
        names.append(name)
        if len(names) >= candidate_count:
            break

    histories: dict[str, list[tuple[dt.date, dict]]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {
            pool.submit(
                lambda n: records(
                    ak.stock_board_industry_hist_em(
                        symbol=n, start_date=ymd(start), end_date=ymd(target), period="日k", adjust=""
                    )
                ),
                name,
            ): name
            for name in names
        }
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                rows = date_rows(future.result())
                if rows:
                    histories[name] = rows
            except Exception as exc:
                log(f"industry history failed: {name}: {exc}")
    return [current_by_name[name] for name in names], histories


def build_sector_item(name: str, current: dict, hist: list[tuple[dt.date, dict]], trade_date: dt.date) -> dict | None:
    filtered = rows_until(hist, trade_date)
    if not filtered:
        return None
    last_date, last = filtered[-1]
    prev = filtered[-2][1] if len(filtered) > 1 else {}
    close = safe_float(get_field(last, "收盘", "最新价", "close", "收盘价"))
    prev_close = safe_float(get_field(prev, "收盘", "close", "收盘价"), close)
    today = safe_float(get_field(last, "涨跌幅", "涨幅"))
    if today == 0.0 and prev_close:
        today = round((close / prev_close - 1) * 100, 2)

    closes = [safe_float(get_field(row, "收盘", "close", "收盘价")) for _, row in filtered]
    closes = [value for value in closes if value > 0]
    if not closes:
        return None

    dates = [f"{d.month}/{d.day}" for d, _ in filtered[-20:]]
    turnover = safe_float(get_field(last, "换手率"), safe_float(get_field(current, "换手率")))
    item = {
        "name": name,
        "cn": "行业",
        "today": round(today, 2),
        "d5": pct_change(closes, 5),
        "d20": pct_change(closes, min(19, max(len(closes) - 1, 0))),
        "turnover": round(turnover, 2),
        "heat": 0,
        "rank": 0,
        "badges": [],
        "kline": [round(value, 2) for value in closes[-20:]],
        "_techKline": [round(value, 2) for value in closes[-60:]],
        "dates": dates,
        "_tradeDate": last_date.isoformat(),
    }
    if item["today"] >= 4 or item["turnover"] >= 8:
        item["badges"].append("HOT")
    elif item["d5"] >= 3:
        item["badges"].append("UP")
    elif item["d20"] >= 10:
        item["badges"].append("STRONG")
    return item


def fetch_constituents(sectors: list[dict]) -> tuple[dict, list[dict]]:
    ak = get_ak()
    out: dict[str, list[dict]] = {}
    hot: list[dict] = []
    for sector in sectors:
        name = sector["name"]
        try:
            rows = records(ak.stock_board_industry_cons_em(symbol=name))
        except Exception as exc:
            log(f"constituents failed: {name}: {exc}")
            rows = []
        rows.sort(key=lambda row: safe_float(get_field(row, "涨跌幅")), reverse=True)
        stocks = []
        for row in rows[:5]:
            stock = {
                "nm": str(get_field(row, "名称", "股票名称") or ""),
                "code": str(get_field(row, "代码", "股票代码") or ""),
                "v": round(safe_float(get_field(row, "涨跌幅")), 2),
            }
            if stock["nm"]:
                stocks.append(stock)
                hot.append({"name": stock["nm"], "sector": name, "val": stock["v"], "note": name})
        out[name] = stocks
    hot.sort(key=lambda item: item["val"], reverse=True)
    return out, hot[:10]


def fetch_flows(sectors: list[dict], trade_date: dt.date) -> list[dict]:
    ak = get_ak()
    flows = []
    for sector in sectors[:12]:
        name = sector["name"]
        val = None
        try:
            rows = date_rows(records(ak.stock_sector_fund_flow_hist(symbol=name)))
            found = last_at_or_before(rows, trade_date)
            if found:
                _, row = found
                raw = safe_float(get_field(row, "主力净流入-净额", "净流入", "主力净流入"))
                val = round(raw / 10000, 0)
        except Exception as exc:
            log(f"flow failed: {name}: {exc}")
        if val is None:
            val = round(sector["today"] * max(sector["turnover"], 0.2) * 1800, 0)
        flows.append({"name": name, "type": "行业", "val": val})
    flows.sort(key=lambda item: item["val"], reverse=True)
    positives = flows[:5]
    negatives = sorted(flows, key=lambda item: item["val"])[:3]
    seen = set()
    picked = []
    for item in positives + negatives:
        if item["name"] in seen:
            continue
        seen.add(item["name"])
        picked.append(item)
    return picked


def fetch_concepts(target: dt.date, trade_date: dt.date, cfg: dict) -> list[dict]:
    ak = get_ak()
    market_cfg = cfg.get("market", {})
    candidate_count = int(market_cfg.get("concept_candidates", 18))
    history_days = int(market_cfg.get("history_days", 90))
    start = target - dt.timedelta(days=history_days)
    try:
        rows = records(ak.stock_board_concept_name_em())
    except Exception as exc:
        log(f"concept list failed: {exc}")
        return []

    rows.sort(
        key=lambda row: abs(safe_float(get_field(row, "涨跌幅"))) * 2 + safe_float(get_field(row, "换手率")),
        reverse=True,
    )
    concepts = []
    for row in rows[:candidate_count]:
        name = str(get_field(row, "板块名称", "名称") or "").strip()
        if not name:
            continue
        hist = []
        try:
            hist = date_rows(
                records(
                    ak.stock_board_concept_hist_em(
                        symbol=name, start_date=ymd(start), end_date=ymd(target), period="daily", adjust=""
                    )
                )
            )
        except Exception:
            hist = []
        filtered = rows_until(hist, trade_date) if hist else []
        closes = [safe_float(get_field(item, "收盘", "close", "收盘价")) for _, item in filtered]
        last = filtered[-1][1] if filtered else row
        today = safe_float(get_field(last, "涨跌幅"), safe_float(get_field(row, "涨跌幅")))
        turnover = safe_float(get_field(last, "换手率"), safe_float(get_field(row, "换手率")))
        badges = []
        if today >= 4:
            badges.append("HOT")
        elif any(kw in name for kw in HOT_KW):
            badges.append("AI")
        concepts.append(
            {
                "name": name,
                "badges": badges,
                "today": round(today, 2),
                "turnover": round(turnover, 2),
                "d5": pct_change(closes, 5) if closes else None,
                "d20": pct_change(closes, min(19, max(len(closes) - 1, 0))) if closes else None,
                "leader": str(get_field(row, "领涨股票", "领涨股") or ""),
            }
        )
    concepts.sort(key=lambda item: item["today"], reverse=True)
    return concepts[:10]


def fetch_indices(target: dt.date, fallback: dict | None) -> list[dict]:
    ak = get_ak()
    start = target - dt.timedelta(days=12)
    out = []
    for name, en, symbol in INDEX_SYMBOLS:
        try:
            rows = date_rows(records(ak.stock_zh_index_daily_em(symbol=symbol, start_date=ymd(start), end_date=ymd(target))))
            filtered = rows_until(rows, target)
            if len(filtered) < 2:
                continue
            _, last = filtered[-1]
            _, prev = filtered[-2]
            close = safe_float(get_field(last, "收盘", "close", "收盘价"))
            prev_close = safe_float(get_field(prev, "收盘", "close", "收盘价"), close)
            chg = round(close - prev_close, 2)
            pct = round((close / prev_close - 1) * 100, 2) if prev_close else 0.0
            out.append({"name": name, "en": en, "price": round(close, 2), "chg": chg, "pct": pct})
        except Exception as exc:
            log(f"index failed: {name}: {exc}")
    if out:
        return out
    return copy.deepcopy((fallback or {}).get("indices", []))


def build_rule_analysis(data: dict) -> None:
    sectors = data.get("sectors", [])
    flows = data.get("flows", [])
    constituents = data.get("constituents", {})
    if not sectors:
        data["signals"] = []
        data["picks"] = []
        data["strategy"] = {"macro": "", "themes": [], "risks": []}
        return

    flow_by_name = {row["name"]: safe_float(row.get("val")) for row in flows}
    max_flow = max([abs(v) for v in flow_by_name.values()] or [1]) or 1
    scored = []
    for sector in sectors:
        flow_score = flow_by_name.get(sector["name"], 0.0) / max_flow * 25
        score = sector["today"] * 4 + sector["d5"] * 2 + sector["d20"] * 0.8 + sector["turnover"] * 0.6 + flow_score
        scored.append((score, sector))
    scored.sort(key=lambda item: item[0], reverse=True)

    tiers = [
        ("top", "首选方向", "★"),
        ("top", "今日领涨", "★"),
        ("strong", "超配方向", "▲"),
        ("strong", "强势延续", "▲"),
        ("watch", "观察", "◆"),
        ("caution", "风险回避", "!"),
    ]
    picks = []
    for (cls_name, label, mark), (score, sector) in zip(tiers, scored[:6]):
        leaders = constituents.get(sector["name"], [])[:3]
        picks.append(
            {
                "cls": cls_name,
                "score": f"{mark} {int(max(20, min(99, 65 + score)))}",
                "label": label,
                "sector": sector["name"],
                "reason": (
                    f'今日{sector["today"]:+.2f}%，5日{sector["d5"]:+.2f}%，'
                    f'20日{sector["d20"]:+.2f}%，换手{sector["turnover"]:.1f}%'
                ),
                "stocks": [{"t": item["nm"], "b": f'{item["v"]:+.1f}%'} for item in leaders],
            }
        )

    top = scored[0][1]
    up_count = sum(1 for s in sectors if s["today"] > 0)
    down_count = sum(1 for s in sectors if s["today"] < 0)
    best_flow = max(flows, key=lambda item: item.get("val", 0), default=None)
    worst = min(sectors, key=lambda item: item["today"])
    strongest_d20 = max(sectors, key=lambda item: item["d20"])

    signals = [
        {
            "dot": "bullish",
            "cls": "up",
            "text": f'{top["name"]} 今日领涨 {top["today"]:+.2f}%，换手 {top["turnover"]:.1f}%，短线热度居前',
            "val": "LEAD",
        },
        {
            "dot": "bullish" if best_flow and best_flow.get("val", 0) >= 0 else "neutral",
            "cls": "up" if best_flow and best_flow.get("val", 0) >= 0 else "flat",
            "text": f'{best_flow["name"]} 主力资金净流入居前，资金面相对占优' if best_flow else "主力资金数据暂以板块强弱推导",
            "val": f'{best_flow["val"]/10000:+.1f}亿' if best_flow else "FLOW",
        },
        {
            "dot": "neutral",
            "cls": "flat",
            "text": f"活跃板块中上涨 {up_count} 个、下跌 {down_count} 个，结构分化需要结合量能确认",
            "val": f"{up_count}/{len(sectors)}",
        },
        {
            "dot": "bearish",
            "cls": "down",
            "text": f'{worst["name"]} 今日 {worst["today"]:+.2f}%，是样本中最弱方向，短线需回避追跌反抽',
            "val": f'{worst["today"]:+.1f}%',
        },
    ]
    if strongest_d20["d20"] > 0:
        signals.append(
            {
                "dot": "bullish",
                "cls": "up",
                "text": f'{strongest_d20["name"]} 20日涨幅 {strongest_d20["d20"]:+.2f}%，中期相对趋势最强',
                "val": "20D",
            }
        )

    data["picks"] = picks
    data["signals"] = signals[:6]
    data["strategy"] = {
        "macro": (
            f'{data["meta"]["tradeDate"]} 扫描 {len(data.get("heatmap", []))} 个活跃板块，'
            f'样本内<span class="hi">{up_count} 个上涨</span>、{down_count} 个下跌。'
            f'{top["name"]} 以 {top["today"]:+.2f}% 居前，资金与换手变化显示市场仍以结构性轮动为主。'
        ),
        "themes": [
            {"name": f'{picks[0]["sector"]} 强势主线', "desc": picks[0]["reason"], "color": "var(--gold)"},
            {"name": f'{picks[1]["sector"]} 补充方向', "desc": picks[1]["reason"], "color": "var(--accent)"} if len(picks) > 1 else {"name": "补充方向", "desc": "等待更多数据确认", "color": "var(--accent)"},
            {"name": f'{strongest_d20["name"]} 中期趋势', "desc": f'20日表现 {strongest_d20["d20"]:+.2f}%，用于观察趋势延续性', "color": "var(--up)"},
        ],
        "risks": [
            {"mk": "!", "cls": "down", "text": "板块涨幅与换手同时放大时，注意高位分歧和次日承接"},
            {"mk": "!", "cls": "down", "text": f'{worst["name"]} 弱势明显，短线资金偏好尚未修复'},
            {"mk": "◆", "cls": "flat", "text": "本系统仅用于研究扫描，不构成投资建议"},
        ],
    }


def ai_payload(data: dict) -> dict:
    sectors = data.get("sectors", [])[:80]
    return {
        "meta": data.get("meta", {}),
        "indices": data.get("indices", []),
        "sectors": [
            {
                "rank": idx,
                "name": s["name"],
                "type": s.get("cn", "板块"),
                "today": s["today"],
                "d5": s["d5"],
                "d20": s["d20"],
                "turnover": s["turnover"],
                "heat": s["heat"],
                "marketScore": round(safe_float(s.get("_marketScore")), 2),
                "leadStock": s.get("leadStock", ""),
                "mainNetInflow": s.get("_mainNetInflow"),
                "mainNetInflow5d": s.get("_mainNetInflow5d"),
            }
            for idx, s in enumerate(sectors, 1)
        ],
        "flows": data.get("flows", []),
        "concepts": data.get("concepts", [])[:10],
        "hotStocks": data.get("hotStocks", [])[:10],
    }


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            text = match.group(0)
    return json.loads(text)


class LLMDisabled(RuntimeError):
    pass


def call_llm_json(cfg: dict, system_prompt: str, payload_data: dict, max_tokens: int | None = None) -> tuple[dict, str]:
    llm = cfg.get("llm", {})
    api_key = str(llm.get("api_key") or "").strip()
    if not api_key:
        raise LLMDisabled("LLM API key is not configured")
    base_url = str(llm.get("base_url") or "").rstrip("/")
    if not base_url:
        raise LLMDisabled("LLM base_url is not configured")

    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    model = normalize_model_name(llm.get("model") or "glm5")
    request_payload = {
        "model": model,
        "temperature": float(llm.get("temperature", 0.2)),
        "max_tokens": int(max_tokens or llm.get("max_tokens", 1200)),
        "enable_thinking": bool(llm.get("enable_thinking", False)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload_data, ensure_ascii=False)},
        ],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(llm.get("timeout_seconds", 45))) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    return extract_json(content), model


def sanitize_ai_result(raw: dict, data: dict) -> dict:
    valid_sectors = {item["name"] for item in data.get("sectors", [])}
    constituents = data.get("constituents", {})
    result: dict[str, Any] = {}

    selected = []
    raw_selected = raw.get("selectedSectors") or raw.get("selected_sectors") or raw.get("selected")
    if isinstance(raw_selected, list):
        for item in raw_selected:
            name = str(item.get("name") if isinstance(item, dict) else item or "").strip()
            if name in valid_sectors and name not in selected:
                selected.append(name)
            if len(selected) >= int(data.get("meta", {}).get("selectLimit") or 20):
                break
    if selected:
        result["selectedSectors"] = selected

    signals = []
    for item in raw.get("signals", [])[:6]:
        if not isinstance(item, dict):
            continue
        dot = item.get("dot") if item.get("dot") in {"bullish", "bearish", "neutral"} else "neutral"
        cls = item.get("cls") if item.get("cls") in {"up", "down", "flat"} else "flat"
        text = str(item.get("text", "")).strip()
        val = str(item.get("val", "")).strip()[:18]
        if text:
            signals.append({"dot": dot, "cls": cls, "text": text[:120], "val": val or "AI"})
    if signals:
        result["signals"] = signals

    picks = []
    for item in raw.get("picks", [])[:6]:
        if not isinstance(item, dict):
            continue
        sector = str(item.get("sector", "")).strip()
        if sector not in valid_sectors:
            continue
        stocks = item.get("stocks")
        if not isinstance(stocks, list) or not stocks:
            stocks = [{"t": row["nm"], "b": f'{row["v"]:+.1f}%'} for row in constituents.get(sector, [])[:3]]
        clean_stocks = []
        for stock in stocks[:3]:
            if isinstance(stock, dict):
                label = str(stock.get("t") or stock.get("name") or "").strip()
                badge = str(stock.get("b") or stock.get("val") or "").strip()
            else:
                label, badge = str(stock).strip(), ""
            if label:
                clean_stocks.append({"t": label[:16], "b": badge[:12] or None})
        picks.append(
            {
                "cls": item.get("cls") if item.get("cls") in {"top", "strong", "watch", "caution"} else "watch",
                "score": str(item.get("score", "AI"))[:12],
                "label": str(item.get("label", "AI研判"))[:12],
                "sector": sector,
                "reason": str(item.get("reason", ""))[:120],
                "stocks": clean_stocks,
            }
        )
    if picks:
        result["picks"] = picks

    strategy = raw.get("strategy")
    if isinstance(strategy, dict):
        themes = []
        palette = ["var(--gold)", "var(--accent)", "var(--up)"]
        for idx, item in enumerate(strategy.get("themes", [])[:3]):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            desc = str(item.get("desc", "")).strip()
            if name and desc:
                themes.append({"name": name[:30], "desc": desc[:160], "color": palette[idx % len(palette)]})
        risks = []
        for item in strategy.get("risks", [])[:3]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if text:
                risks.append(
                    {
                        "mk": str(item.get("mk", "!"))[:2],
                        "cls": item.get("cls") if item.get("cls") in {"up", "down", "flat"} else "down",
                        "text": text[:150],
                    }
                )
        macro = str(strategy.get("macro", "")).strip()
        if macro and themes and risks:
            result["strategy"] = {"macro": macro[:260], "themes": themes, "risks": risks}
    return result


def apply_ai_analysis(data: dict, cfg: dict) -> None:
    try:
        parsed, model = call_llm_json(
            cfg,
            (
                "你是A股板块扫描分析助手。只根据用户提供的数据输出JSON，不要输出Markdown。"
                "必须保持客观、简洁，结论仅供研究参考，不构成投资建议。"
                "JSON字段为 selectedSectors、signals、picks、strategy。"
                "selectedSectors必须从用户给出的sectors.name中选择20个，按最终页面展示优先级排序，不得编造板块。"
                "signals每项含dot(bullish/bearish/neutral)、cls(up/down/flat)、text、val。"
                "picks每项含cls(top/strong/watch/caution)、score、label、sector、reason、stocks。"
                "picks.sector必须来自selectedSectors；核心picks优先选择leadStock非空的候选，stocks必须使用候选板块的leadStock，不要编造股票。"
                "strategy含macro、themes、risks；themes每项含name、desc；risks每项含mk、cls、text。"
            ),
            ai_payload(data),
        )
        clean = sanitize_ai_result(parsed, data)
        if not clean:
            raise ValueError("AI JSON has no usable fields")
        data.update(clean)
        data.setdefault("meta", {})["aiStatus"] = "ok"
        data.setdefault("meta", {})["aiModel"] = model
    except LLMDisabled:
        data.setdefault("meta", {})["aiStatus"] = "disabled"
    except Exception as exc:
        log(f"AI fallback: {exc}")
        data.setdefault("meta", {})["aiStatus"] = "error"
        data.setdefault("meta", {})["aiError"] = type(exc).__name__


def normalize_chanlun_symbol(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    upper = text.upper()
    exchange_code = re.fullmatch(r"(\d{6})\.(SH|SZ)", upper)
    if exchange_code:
        digits, suffix = exchange_code.groups()
        return f"{'sh' if suffix == 'SH' else 'sz'}{digits}"
    low = text.lower().replace(".", "")
    if re.fullmatch(r"(sh|sz|hk)\w+", low):
        return low
    if upper in {"HSI", "HSTECH"}:
        return upper
    digits = re.sub(r"\D", "", text)
    if re.fullmatch(r"\d{5}", digits):
        return f"hk{digits}"
    if re.fullmatch(r"\d{6}", digits):
        if digits in {"000001", "000300", "000688", "000680"}:
            return f"sh{digits}"
        if digits.startswith("399"):
            return f"sz{digits}"
        return f"sh{digits}" if digits.startswith(("5", "6", "9")) else f"sz{digits}"
    return low


def chanlun_market(symbol: str) -> str:
    low = symbol.lower()
    if low.startswith("hk") or symbol in {"HSI", "HSTECH"}:
        return "港股" if low.startswith("hk") else "指数"
    if low.startswith("sh000") or low.startswith("sz399"):
        return "指数"
    return "A股"


def chanlun_display_code(symbol: str) -> str:
    low = symbol.lower()
    if low.startswith("hk"):
        return low[2:].zfill(5)
    if low.startswith("sh"):
        return f"{low[2:].upper()}.SH"
    if low.startswith("sz"):
        return f"{low[2:].upper()}.SZ"
    return symbol.upper()


def chanlun_unit(market: str) -> str:
    if market == "港股":
        return "HK$"
    if market == "指数":
        return "点"
    return "¥"


def chanlun_stock_item(symbol: str, name: str = "") -> dict:
    symbol = normalize_chanlun_symbol(symbol)
    known = {item["symbol"].lower(): item for item in CHANLUN_DEFAULT_STOCKS}
    if symbol.lower() in known:
        item = copy.deepcopy(known[symbol.lower()])
        if name:
            item["name"] = name
        return item
    market = chanlun_market(symbol)
    return {
        "code": chanlun_display_code(symbol),
        "symbol": symbol,
        "name": name or chanlun_display_code(symbol),
        "market": market,
        "unit": chanlun_unit(market),
    }


def filter_chanlun_market(items: list[dict], market: str) -> list[dict]:
    market = (market or "all").lower()
    if market in {"all", "全部", ""}:
        return items
    mapping = {"a": "A股", "ashare": "A股", "hk": "港股", "index": "指数"}
    target = mapping.get(market, market)
    return [item for item in items if item.get("market") == target]


def chanlun_search(q: str, market: str, cfg: dict) -> list[dict]:
    q = str(q or "").strip()
    defaults = copy.deepcopy(CHANLUN_DEFAULT_STOCKS)
    if not q:
        return filter_chanlun_market(defaults, market)[:100]

    matched = [
        item for item in defaults
        if q.lower() in item["symbol"].lower()
        or q.lower() in item["code"].lower()
        or q in item["name"]
    ]
    try:
        rows = first_table_rows(westock_run(["search", q], cfg))
        seen = {item["symbol"].lower() for item in matched}
        for row in rows:
            code = normalize_chanlun_symbol(str(row.get("code") or row.get("symbol") or ""))
            if not code or code.lower().startswith(("us", "bj")):
                continue
            if code.lower() in seen:
                continue
            name = str(row.get("name") or "").strip()
            item = chanlun_stock_item(code, name)
            if item["market"] in {"A股", "港股", "指数"}:
                matched.append(item)
                seen.add(code.lower())
    except Exception as exc:
        log(f"chanlun search fallback: {exc}")
    return filter_chanlun_market(matched, market)[:80]


def chanlun_cache_path(symbol: str, period: str, requested: dt.date) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", normalize_chanlun_symbol(symbol))
    return CACHE_DIR / f"chanlun_{safe}_{period}_{requested.isoformat()}.json"


def load_chanlun_cache(symbol: str, period: str, requested: dt.date) -> dict | None:
    path = chanlun_cache_path(symbol, period, requested)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("meta", {})["cacheHit"] = True
        return data
    except Exception as exc:
        log(f"chanlun cache read failed: {path.name}: {exc}")
        return None


def write_chanlun_cache(symbol: str, period: str, requested: dt.date, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    data.setdefault("meta", {})["cacheHit"] = False
    with chanlun_cache_path(symbol, period, requested).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def row_to_bar(row: dict, d: dt.date | None = None) -> dict | None:
    date = d or parse_iso_date(get_field(row, "date", "日期", "时间"))
    if not date:
        return None
    open_v = safe_float(get_field(row, "open", "开盘"))
    close_v = safe_float(get_field(row, "last", "close", "收盘", "最新价"))
    high_v = safe_float(get_field(row, "high", "最高"))
    low_v = safe_float(get_field(row, "low", "最低"))
    volume = safe_float(get_field(row, "volume", "成交量"), 0.0)
    if not (open_v and close_v and high_v and low_v):
        return None
    return {
        "date": date.isoformat(),
        "open": round(open_v, 4),
        "high": round(high_v, 4),
        "low": round(low_v, 4),
        "close": round(close_v, 4),
        "volume": int(volume),
    }


def aggregate_weekly_bars(bars: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, int], list[dict]] = {}
    for bar in bars:
        d = parse_iso_date(bar.get("date"))
        if not d:
            continue
        grouped.setdefault((d.isocalendar().year, d.isocalendar().week), []).append(bar)
    out = []
    for _, items in sorted(grouped.items()):
        items.sort(key=lambda item: item["date"])
        out.append(
            {
                "date": items[-1]["date"],
                "open": items[0]["open"],
                "high": max(item["high"] for item in items),
                "low": min(item["low"] for item in items),
                "close": items[-1]["close"],
                "volume": int(sum(safe_float(item.get("volume")) for item in items)),
            }
        )
    return out


def fetch_westock_chanlun_bars(symbol: str, period: str, target: dt.date, cfg: dict) -> list[dict]:
    cl_cfg = cfg.get("chanlun", {})
    limit = int(cl_cfg.get("westock_kline_limit", cl_cfg.get("bars", 220)))
    rows = date_rows(first_table_rows(westock_run(["kline", symbol, "--period", period, "--limit", str(limit)], cfg)))
    bars = []
    for d, row in rows_until(rows, target):
        bar = row_to_bar(row, d)
        if bar:
            bars.append(bar)
    return bars[-int(cl_cfg.get("bars", 220)) :]


def fetch_akshare_chanlun_bars(symbol: str, period: str, target: dt.date, cfg: dict) -> list[dict]:
    ak = get_ak()
    cl_cfg = cfg.get("chanlun", {})
    bars_limit = int(cl_cfg.get("bars", 220))
    start = target - dt.timedelta(days=bars_limit * (10 if period == "week" else 3))
    market = chanlun_market(symbol)
    low = symbol.lower()
    rows: list[dict] = []
    if market == "指数":
        rows = records(ak.stock_zh_index_daily_em(symbol=low, start_date=ymd(start), end_date=ymd(target)))
        bars = [bar for d, row in date_rows(rows) if (bar := row_to_bar(row, d))]
        if period == "week":
            bars = aggregate_weekly_bars(bars)
        return bars[-bars_limit:]
    if market == "港股":
        code = low[2:].zfill(5)
        rows = records(
            ak.stock_hk_hist(
                symbol=code,
                period="weekly" if period == "week" else "daily",
                start_date=ymd(start),
                end_date=ymd(target),
                adjust="qfq",
            )
        )
    else:
        rows = records(
            ak.stock_zh_a_hist(
                symbol=low[2:],
                period="weekly" if period == "week" else "daily",
                start_date=ymd(start),
                end_date=ymd(target),
                adjust="qfq",
            )
        )
    return [bar for d, row in date_rows(rows) if d <= target and (bar := row_to_bar(row, d))][-bars_limit:]


def fetch_chanlun_bars(stock: dict, period: str, requested: dt.date, cfg: dict) -> tuple[list[dict], str, str]:
    target = min(requested, dt.date.today())
    symbol = normalize_chanlun_symbol(stock["symbol"])
    primary = str(cfg.get("market", {}).get("primary_source") or "westock").lower()
    primary_error = ""
    if primary == "westock":
        try:
            bars = fetch_westock_chanlun_bars(symbol, period, target, cfg)
            if len(bars) >= 35:
                return bars, "westock", ""
            primary_error = f"WeStock bars too few: {len(bars)}"
        except Exception as exc:
            primary_error = f"WeStock {type(exc).__name__}: {str(exc)[:160]}"
            log(f"chanlun westock failed: {exc}")
    try:
        bars = fetch_akshare_chanlun_bars(symbol, period, target, cfg)
        if len(bars) >= 35:
            return bars, "akshare", primary_error
        raise RuntimeError(f"AKShare bars too few: {len(bars)}")
    except Exception as exc:
        if primary_error:
            raise RuntimeError(f"{primary_error}; AKShare {type(exc).__name__}: {str(exc)[:160]}") from exc
        raise


def chanlun_merge_bars(bars: list[dict]) -> list[dict]:
    merged = []
    direction = 1
    for idx, bar in enumerate(bars):
        item = {"high": bar["high"], "low": bar["low"], "hiIdx": idx, "loIdx": idx}
        if not merged:
            merged.append(item)
            continue
        last = merged[-1]
        incl = (item["high"] <= last["high"] and item["low"] >= last["low"]) or (
            item["high"] >= last["high"] and item["low"] <= last["low"]
        )
        if incl:
            if len(merged) >= 2:
                direction = 1 if last["high"] > merged[-2]["high"] else -1
            if direction == 1:
                if item["high"] > last["high"]:
                    last["high"], last["hiIdx"] = item["high"], item["hiIdx"]
                if item["low"] > last["low"]:
                    last["low"], last["loIdx"] = item["low"], item["loIdx"]
            else:
                if item["low"] < last["low"]:
                    last["low"], last["loIdx"] = item["low"], item["loIdx"]
                if item["high"] < last["high"]:
                    last["high"], last["hiIdx"] = item["high"], item["hiIdx"]
        else:
            merged.append(item)
    return merged


def chanlun_fractals(merged: list[dict]) -> list[dict]:
    out = []
    for idx in range(1, len(merged) - 1):
        a, b, c = merged[idx - 1], merged[idx], merged[idx + 1]
        if b["high"] > a["high"] and b["high"] > c["high"] and b["low"] > a["low"] and b["low"] > c["low"]:
            out.append({"type": "top", "mIdx": idx, "kIdx": b["hiIdx"], "price": b["high"]})
        elif b["low"] < a["low"] and b["low"] < c["low"] and b["high"] < a["high"] and b["high"] < c["high"]:
            out.append({"type": "bottom", "mIdx": idx, "kIdx": b["loIdx"], "price": b["low"]})
    return out


def chanlun_strokes(fractals: list[dict], min_gap: int) -> list[dict]:
    pts = []
    for item in fractals:
        f = {key: item[key] for key in ("type", "mIdx", "kIdx", "price")}
        if not pts:
            pts.append(f)
            continue
        last = pts[-1]
        if f["type"] == last["type"]:
            if (f["type"] == "top" and f["price"] > last["price"]) or (
                f["type"] == "bottom" and f["price"] < last["price"]
            ):
                pts[-1] = f
        else:
            valid = (f["type"] == "top" and f["price"] > last["price"]) or (
                f["type"] == "bottom" and f["price"] < last["price"]
            )
            if f["mIdx"] - last["mIdx"] >= min_gap and valid:
                pts.append(f)
    return pts


def chanlun_segments(pts: list[dict]) -> list[dict]:
    segs = []
    if len(pts) < 2:
        return segs
    start = 0
    guard = 0
    while start < len(pts) - 1 and guard < 200:
        guard += 1
        direction = 1 if pts[start + 1]["price"] > pts[start]["price"] else -1
        ext = start + 1
        end = -1
        for idx in range(start + 2, len(pts)):
            p = pts[idx]
            if direction == 1:
                if p["type"] == "top" and p["price"] >= pts[ext]["price"]:
                    ext = idx
                if p["type"] == "bottom" and ((ext > start + 1 and p["price"] < pts[ext - 1]["price"]) or p["price"] < pts[start]["price"]):
                    end = ext
                    break
            else:
                if p["type"] == "bottom" and p["price"] <= pts[ext]["price"]:
                    ext = idx
                if p["type"] == "top" and ((ext > start + 1 and p["price"] > pts[ext - 1]["price"]) or p["price"] > pts[start]["price"]):
                    end = ext
                    break
        if end == -1:
            segs.append({"from": start, "to": ext, "dir": direction, "confirmed": False})
            if ext >= len(pts) - 1:
                break
            start = ext
        else:
            segs.append({"from": start, "to": end, "dir": direction, "confirmed": True})
            start = end
    return segs


def chanlun_pivots(pts: list[dict]) -> list[dict]:
    pivots = []
    idx = 0
    while idx + 3 < len(pts):
        highs, lows = [], []
        for step in range(3):
            a, b = pts[idx + step], pts[idx + step + 1]
            highs.append(max(a["price"], b["price"]))
            lows.append(min(a["price"], b["price"]))
        zg, zd = min(highs), max(lows)
        if zg > zd:
            end_pt = idx + 3
            while end_pt + 1 < len(pts):
                a2, b2 = pts[end_pt], pts[end_pt + 1]
                hi, lo = max(a2["price"], b2["price"]), min(a2["price"], b2["price"])
                if hi >= zd and lo <= zg:
                    end_pt += 1
                else:
                    break
            pivots.append(
                {
                    "zg": round(zg, 4),
                    "zd": round(zd, 4),
                    "fromPt": idx,
                    "toPt": end_pt,
                    "startK": pts[idx]["kIdx"],
                    "endK": pts[end_pt]["kIdx"],
                    "strokes": end_pt - idx,
                }
            )
            idx = end_pt
        else:
            idx += 1
    return pivots


def chanlun_macd_series(closes: list[float]) -> dict:
    if not closes:
        return {"dif": [], "dea": [], "hist": []}
    dif, dea, hist = [], [], []
    e12 = e26 = closes[0]
    d = 0.0
    for idx, close in enumerate(closes):
        e12 = closes[0] if idx == 0 else (e12 * 11 + close * 2) / 13
        e26 = closes[0] if idx == 0 else (e26 * 25 + close * 2) / 27
        df = e12 - e26
        d = df if idx == 0 else (d * 8 + df * 2) / 10
        dif.append(round(df, 6))
        dea.append(round(d, 6))
        hist.append(round((df - d) * 2, 6))
    return {"dif": dif, "dea": dea, "hist": hist}


def chanlun_macd_area(macd_data: dict, k1: int, k2: int, sign: int) -> float:
    total = 0.0
    hist = macd_data.get("hist", [])
    for idx in range(max(0, k1), min(len(hist) - 1, k2) + 1):
        if hist[idx] * sign > 0:
            total += abs(hist[idx])
    return total


def chanlun_compare_legs(pts: list[dict], segs: list[dict], macd_data: dict, idx: int) -> dict | None:
    c = segs[idx]
    b = segs[idx - 2] if idx >= 2 else None
    if not b or b["dir"] != c["dir"]:
        return None
    c_end, b_end = pts[c["to"]], pts[b["to"]]
    new_ext = c_end["price"] > b_end["price"] if c["dir"] == 1 else c_end["price"] < b_end["price"]
    area_c = chanlun_macd_area(macd_data, pts[c["from"]]["kIdx"], c_end["kIdx"], c["dir"])
    area_b = chanlun_macd_area(macd_data, pts[b["from"]]["kIdx"], b_end["kIdx"], b["dir"])
    ratio = area_c / area_b if area_b > 0 else 1
    return {
        "dir": c["dir"],
        "newExt": bool(new_ext),
        "areaB": round(area_b, 6),
        "areaC": round(area_c, 6),
        "ratio": round(ratio, 6),
        "detected": bool(new_ext and area_b > 0 and area_c < area_b * 0.95),
        "type": "底背驰" if c["dir"] == -1 else "顶背驰",
        "cFromK": pts[c["from"]]["kIdx"],
        "cToK": c_end["kIdx"],
        "bFromK": pts[b["from"]]["kIdx"],
        "bToK": b_end["kIdx"],
        "cPrice": c_end["price"],
        "bPrice": b_end["price"],
        "segIdx": idx,
        "confirmed": bool(c["confirmed"]),
    }


def chanlun_divergence(pts: list[dict], segs: list[dict], macd_data: dict) -> dict | None:
    if len(segs) < 3:
        return None
    return chanlun_compare_legs(pts, segs, macd_data, len(segs) - 1)


def chanlun_signals(pts: list[dict], segs: list[dict], pivots: list[dict], macd_data: dict) -> list[dict]:
    signals = []
    for idx in range(2, len(segs)):
        cmp_data = chanlun_compare_legs(pts, segs, macd_data, idx)
        if not cmp_data or not cmp_data["detected"]:
            continue
        end_pt = pts[segs[idx]["to"]]
        buy = cmp_data["dir"] == -1
        signals.append(
            {
                "kind": "B1" if buy else "S1",
                "label": "第一类买点" if buy else "第一类卖点",
                "kIdx": end_pt["kIdx"],
                "price": end_pt["price"],
                "forming": idx == len(segs) - 1 and not segs[idx]["confirmed"],
                "facts": {"div": cmp_data},
            }
        )
        p2_idx = segs[idx]["to"] + 2
        if p2_idx < len(pts):
            p2 = pts[p2_idx]
            ok2 = (p2["type"] == "bottom" and p2["price"] > end_pt["price"]) if buy else (
                p2["type"] == "top" and p2["price"] < end_pt["price"]
            )
            if ok2:
                signals.append(
                    {
                        "kind": "B2" if buy else "S2",
                        "label": "第二类买点" if buy else "第二类卖点",
                        "kIdx": p2["kIdx"],
                        "price": p2["price"],
                        "facts": {"ref": {"kIdx": end_pt["kIdx"], "price": end_pt["price"]}, "pull": p2["price"]},
                    }
                )
    for pv in pivots:
        for idx in range(pv["toPt"] + 1, min(len(pts) - 2, pv["toPt"] + 5) + 1):
            p = pts[idx]
            if p["type"] == "top" and p["price"] > pv["zg"]:
                nb = pts[idx + 1]
                if nb["type"] == "bottom" and nb["price"] > pv["zg"]:
                    signals.append(
                        {
                            "kind": "B3",
                            "label": "第三类买点",
                            "kIdx": nb["kIdx"],
                            "price": nb["price"],
                            "facts": {"pivot": pv, "breakPt": {"kIdx": p["kIdx"], "price": p["price"]}, "pull": nb["price"]},
                        }
                    )
                break
            if p["type"] == "bottom" and p["price"] < pv["zd"]:
                nt = pts[idx + 1]
                if nt["type"] == "top" and nt["price"] < pv["zd"]:
                    signals.append(
                        {
                            "kind": "S3",
                            "label": "第三类卖点",
                            "kIdx": nt["kIdx"],
                            "price": nt["price"],
                            "facts": {"pivot": pv, "breakPt": {"kIdx": p["kIdx"], "price": p["price"]}, "pull": nt["price"]},
                        }
                    )
                break
    signals.sort(key=lambda item: (item["kIdx"], item["kind"]))
    out, seen = [], set()
    for item in signals:
        key = f'{item["kind"]}@{item["kIdx"]}'
        if key in seen:
            continue
        seen.add(key)
        item["id"] = key
        out.append(item)
    return out


def chanlun_trend(segs: list[dict], pivots: list[dict]) -> dict:
    if len(pivots) >= 2:
        p1, p2 = pivots[-2], pivots[-1]
        if p2["zd"] > p1["zg"]:
            return {"kind": "up", "text": "上涨趋势", "detail": "相邻两中枢依次上移(后中枢ZD高于前中枢ZG)"}
        if p2["zg"] < p1["zd"]:
            return {"kind": "down", "text": "下跌趋势", "detail": "相邻两中枢依次下移(后中枢ZG低于前中枢ZD)"}
        return {"kind": "range", "text": "盘整", "detail": "相邻中枢区间重叠,走势仍属盘整范畴"}
    if segs:
        return (
            {"kind": "up", "text": "向上盘整", "detail": "当前线段向上,但未形成两个以上同向中枢"}
            if segs[-1]["dir"] == 1
            else {"kind": "down", "text": "向下盘整", "detail": "当前线段向下,但未形成两个以上同向中枢"}
        )
    return {"kind": "range", "text": "盘整", "detail": "结构尚不充分"}


def analyze_chanlun_bars(bars: list[dict], cfg: dict) -> dict:
    merged = chanlun_merge_bars(bars)
    fractals = chanlun_fractals(merged)
    pts = chanlun_strokes(fractals, int(cfg.get("chanlun", {}).get("min_stroke_gap", 4)))
    segs = chanlun_segments(pts)
    pivots = chanlun_pivots(pts)
    macd_data = chanlun_macd_series([safe_float(bar.get("close")) for bar in bars])
    divergence = chanlun_divergence(pts, segs, macd_data)
    signals = chanlun_signals(pts, segs, pivots, macd_data)
    trend = chanlun_trend(segs, pivots)
    tops = sum(1 for item in fractals if item["type"] == "top")
    bottoms = sum(1 for item in fractals if item["type"] == "bottom")
    return {
        "merged": merged,
        "fractals": fractals,
        "pts": pts,
        "segs": segs,
        "pivots": pivots,
        "macd": macd_data,
        "divergence": divergence,
        "signals": signals,
        "trend": trend,
        "stats": {
            "tops": tops,
            "bottoms": bottoms,
            "strokes": max(0, len(pts) - 1),
            "segments": len(segs),
            "pivots": len(pivots),
        },
    }


def fmt_chanlun_price(value: Any) -> str:
    return f"{safe_float(value):,.2f}"


def build_chanlun_verdict(stock: dict, bars: list[dict], analysis: dict) -> dict:
    last = bars[-1]
    n = len(bars)
    signals = analysis.get("signals", [])
    latest = signals[-1] if signals else None
    active = bool(latest and (n - 1 - int(latest["kIdx"])) <= 20)
    div = analysis.get("divergence")
    trend = analysis.get("trend", {})
    last_pv = (analysis.get("pivots") or [])[-1] if analysis.get("pivots") else None
    if last_pv:
        if last["close"] > last_pv["zg"]:
            pivot_rel = "最近中枢上方"
        elif last["close"] < last_pv["zd"]:
            pivot_rel = "最近中枢下方"
        else:
            pivot_rel = "最近中枢区间内"
    else:
        pivot_rel = "无中枢参照"
    if active:
        buy = latest["kind"].startswith("B")
        headline = f'{trend.get("text", "盘整")}中,近端出现{latest["label"]}{"(形成中)" if latest.get("forming") else ""},结构{"偏多" if buy else "偏空"}。'
        body = (
            f'{bars[latest["kIdx"]]["date"]} 于 {fmt_chanlun_price(latest["price"])} 识别出{latest["label"]};'
            f'现价 {fmt_chanlun_price(last["close"])},处于{pivot_rel}。判定依据:{trend.get("detail", "结构尚不充分")}。'
        )
    else:
        headline = f'{trend.get("text", "盘整")}格局,暂无新增买卖点信号。'
        if latest:
            body = (
                f'{trend.get("detail", "结构尚不充分")}。最近一个信号为 {bars[latest["kIdx"]]["date"]} 的'
                f'{latest["label"]}({fmt_chanlun_price(latest["price"])}),距今已 {n - 1 - latest["kIdx"]} 根K线;'
                f'现价处于{pivot_rel},等待新的背驰信号或中枢突破后的回抽确认。'
            )
        else:
            body = (
                f'{trend.get("detail", "结构尚不充分")}。样本期内未出现符合定义的三类买卖点;'
                f'现价处于{pivot_rel},等待新的背驰信号或中枢突破后的回抽确认。'
            )
    risks = []
    if div and div.get("detected") and not div.get("confirmed"):
        risks.append("末段走势未完成,背驰判定将随新K线动态变化")
    if latest and latest.get("forming") and active:
        risks.append(f'{latest["label"]}尚在形成中,需待线段终结确认')
    risks.append("缠论判定存在级别与主观性差异,本页仅为技术结构辅助,不构成投资建议")
    metas = [
        {
            "k": "走势类型",
            "v": trend.get("text", "盘整"),
            "note": f'{analysis.get("stats", {}).get("pivots", 0)} 个中枢参与判定',
            "tone": "var(--up)" if trend.get("kind") == "up" else "var(--down)" if trend.get("kind") == "down" else None,
        },
        {
            "k": "最新信号",
            "v": latest["label"] if latest else "暂无",
            "note": f'{bars[latest["kIdx"]]["date"]} · {fmt_chanlun_price(latest["price"])}' if latest else "样本期内无",
            "tone": "var(--up)" if latest and latest["kind"].startswith("B") else "var(--down)" if latest else None,
        },
        {
            "k": "背驰状态",
            "v": (div["type"] if div and div.get("detected") else "无背驰") if div else "不可比",
            "note": f'c段/b段 MACD 面积比 {(safe_float(div.get("ratio")) * 100):.0f}%' if div else "线段数量不足",
            "tone": "#a63a32" if div and div.get("detected") else None,
        },
        {
            "k": "现价位置",
            "v": pivot_rel,
            "note": f'中枢区间 [{fmt_chanlun_price(last_pv["zd"])} - {fmt_chanlun_price(last_pv["zg"])}]' if last_pv else "—",
        },
    ]
    return {"headline": headline, "body": body, "risk": ";".join(risks) + "。", "metas": metas}


def chanlun_ai_payload(data: dict) -> dict:
    analysis = data.get("analysis", {})
    bars = data.get("bars", [])
    return {
        "meta": data.get("meta", {}),
        "stock": data.get("stock", {}),
        "lastBar": bars[-1] if bars else {},
        "recentBars": bars[-20:],
        "stats": analysis.get("stats", {}),
        "trend": analysis.get("trend", {}),
        "divergence": analysis.get("divergence"),
        "latestPivots": analysis.get("pivots", [])[-3:],
        "latestSignals": analysis.get("signals", [])[-5:],
    }


def apply_chanlun_ai(data: dict, cfg: dict) -> None:
    try:
        parsed, model = call_llm_json(
            cfg,
            (
                "你是缠论技术结构复盘助手。只根据用户提供的K线结构、分型、笔、线段、中枢、背驰和买卖点事实输出JSON。"
                "不要输出Markdown。不要给投资建议、买入卖出指令、收益承诺或仓位建议。"
                "JSON字段仅允许 headline、body、risk、notes。headline和body用于复盘摘要，risk用于风险提示，notes为字符串数组。"
                "必须强调结构信号仅供学习研究和复盘参考。"
            ),
            chanlun_ai_payload(data),
            max_tokens=900,
        )
        verdict = data.setdefault("verdict", {})
        for key, limit in {"headline": 90, "body": 260, "risk": 180}.items():
            value = str(parsed.get(key, "")).strip()
            if value:
                verdict[key] = value[:limit]
        notes = parsed.get("notes")
        if isinstance(notes, list):
            verdict["notes"] = [str(item).strip()[:120] for item in notes[:4] if str(item).strip()]
        data.setdefault("meta", {})["aiStatus"] = "ok"
        data.setdefault("meta", {})["aiModel"] = model
        data["ai"] = {"status": "ok", "model": model}
    except LLMDisabled:
        data.setdefault("meta", {})["aiStatus"] = "disabled"
        data["ai"] = {"status": "disabled"}
    except Exception as exc:
        log(f"chanlun AI fallback: {exc}")
        data.setdefault("meta", {})["aiStatus"] = "error"
        data.setdefault("meta", {})["aiError"] = type(exc).__name__
        data["ai"] = {"status": "error", "error": type(exc).__name__}


def build_chanlun_analysis(symbol: str, period: str, requested: dt.date, cfg: dict, force_refresh: bool = False) -> dict:
    period = period if period in {"day", "week"} else "day"
    normalized = normalize_chanlun_symbol(symbol)
    if not force_refresh:
        cached = load_chanlun_cache(normalized, period, requested)
        if cached:
            return cached
    stock = chanlun_stock_item(normalized)
    bars, provider, primary_error = fetch_chanlun_bars(stock, period, requested, cfg)
    if len(bars) < 35:
        raise RuntimeError(f"Not enough bars for ChanLun analysis: {len(bars)}")
    trade_date = parse_iso_date(bars[-1]["date"]) or requested
    analysis = analyze_chanlun_bars(bars, cfg)
    data = {
        "meta": {
            "source": "WeStock Data · 腾讯自选股" if provider == "westock" else "AKShare · 备选数据源",
            "dataProvider": provider,
            "primaryFallback": primary_error,
            "asOf": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "requestedDate": requested.isoformat(),
            "tradeDate": trade_date.isoformat(),
            "period": period,
            "dataStatus": "live",
            "cacheHit": False,
        },
        "stock": stock,
        "bars": bars,
        "analysis": analysis,
        "verdict": build_chanlun_verdict(stock, bars, analysis),
        "ai": {},
    }
    apply_chanlun_ai(data, cfg)
    write_chanlun_cache(normalized, period, requested, data)
    return data


def build_akshare_scan(requested: dt.date, cfg: dict) -> dict:
    today = dt.date.today()
    target = min(requested, today)
    fallback = latest_cache(target) or parse_data_js()

    spot_rows, histories = fetch_industry_candidates(target, cfg)
    current_by_name = {
        str(get_field(row, "板块名称", "名称") or "").strip(): row
        for row in spot_rows
        if str(get_field(row, "板块名称", "名称") or "").strip()
    }
    available_dates = []
    for rows in histories.values():
        found = last_at_or_before(rows, target)
        if found:
            available_dates.append(found[0])
    if not available_dates:
        raise RuntimeError("No industry history is available before requested date")
    trade_date = max(available_dates)

    sectors_all = []
    for name, hist in histories.items():
        item = build_sector_item(name, current_by_name.get(name, {}), hist, trade_date)
        if item:
            sectors_all.append(item)
    if not sectors_all:
        raise RuntimeError("No sector rows can be built")

    max_turnover = max((item["turnover"] for item in sectors_all), default=1) or 1
    active = sorted(
        sectors_all,
        key=lambda item: abs(item["today"]) * 2.2 + item["turnover"] * 1.4 + abs(item["d5"]) * 0.5,
        reverse=True,
    )
    for idx, item in enumerate(active, 1):
        item["rank"] = idx
        item["heat"] = int(1000 + item["turnover"] / max_turnover * 1429)

    top = int(cfg.get("market", {}).get("top", 12))
    trend_n = int(cfg.get("market", {}).get("trend", 5))
    sectors = active[:top]
    heatmap = [
        {
            "name": item["name"],
            "t": item["today"],
            "d5": item["d5"],
            "d20": item["d20"],
            "heat": item["heat"],
            "rank": item["rank"],
            "turnover": item["turnover"],
        }
        for item in active[:20]
    ]

    constituents, hot_stocks = fetch_constituents(sectors)
    flows = fetch_flows(sectors, trade_date)
    concepts = fetch_concepts(target, trade_date, cfg)
    indices = fetch_indices(trade_date, fallback)

    trend_sectors = sectors[:trend_n]
    longest = max(trend_sectors, key=lambda item: len(item.get("dates", [])), default=None)
    palette = ["#e1322f", "#1657d4", "#b3760b", "#7c3aed", "#008f5d", "#0aa6b8"]
    trend = {
        "dates": (longest or {}).get("dates", []),
        "series": [
            {
                "name": item["name"],
                "color": palette[idx % len(palette)],
                "chg": f'{item["d20"]:+.1f}% (20D)',
                "raw": item["kline"],
            }
            for idx, item in enumerate(trend_sectors)
        ],
    }

    tech = []
    for item in sectors[:3]:
        closes = item.get("_techKline") or item["kline"]
        r6 = rsi(closes)
        dif, dea, m = macd(closes)
        signal = "BULL" if m > 0 and r6 >= 50 else "BEAR" if m < 0 and r6 <= 45 else "NEUTRAL"
        tech.append({"name": item["name"], "rsi6": r6, "dif": dif, "dea": dea, "macd": m, "signal": signal})

    top_sector = sectors[0]
    positive_flow_total = sum(max(safe_float(item.get("val")), 0) for item in flows) / 10000
    data = {
        "meta": {
            "source": "AKShare · 东方财富",
            "asOf": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "session": "日期扫描",
            "requestedDate": requested.isoformat(),
            "tradeDate": trade_date.isoformat(),
            "dataStatus": "live",
        },
        "indices": indices,
        "stats": [
            {"name": "板块数", "en": "BREADTH", "value": str(len(heatmap)), "tag": "活跃板块", "cls": "flat"},
            {
                "name": "今日热度 #1",
                "en": "TOP HEAT",
                "value": top_sector["name"],
                "sub": f'{top_sector["today"]:+.2f}% · 热度{top_sector["heat"]}',
                "cls": "up" if top_sector["today"] >= 0 else "down",
                "accent": True,
            },
            {
                "name": "行业净流入",
                "en": "NET FLOW",
                "value": f"{positive_flow_total:+.0f}亿",
                "sub": f'{top_sector["name"]}居前',
                "cls": "up" if positive_flow_total >= 0 else "down",
            },
        ],
        "heatmap": heatmap,
        "sectors": sectors,
        "constituents": constituents,
        "flows": flows,
        "signals": [],
        "picks": [],
        "trend": trend,
        "tech": tech,
        "hotStocks": hot_stocks,
        "concepts": concepts,
        "strategy": {},
    }
    for item in data["sectors"]:
        item.pop("_tradeDate", None)

    build_rule_analysis(data)
    apply_ai_analysis(data, cfg)

    CACHE_DIR.mkdir(exist_ok=True)
    with (CACHE_DIR / f"scan_{trade_date.isoformat()}.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def build_scan(requested: dt.date, cfg: dict, force_refresh: bool = False) -> dict:
    if not force_refresh:
        cached = load_request_cache(requested)
        if cached:
            return cached

    market_cfg = cfg.get("market", {})
    primary = str(market_cfg.get("primary_source") or "westock").lower()
    primary_error = ""

    if primary == "westock":
        try:
            data = build_westock_scan(requested, cfg)
            write_request_cache(requested, data)
            return data
        except Exception as exc:
            primary_error = f"WeStock {type(exc).__name__}: {str(exc)[:160]}"
            log(f"westock primary failed: {exc}")

    try:
        data = build_akshare_scan(requested, cfg)
        meta = data.setdefault("meta", {})
        meta["dataProvider"] = "akshare"
        if primary_error:
            meta["primaryFallback"] = primary_error
            meta["source"] = f'{meta.get("source", "AKShare")} · WeStock备选失败后启用'
        write_request_cache(requested, data)
        return data
    except Exception as exc:
        if primary_error:
            raise RuntimeError(f"{primary_error}; AKShare {type(exc).__name__}: {str(exc)[:160]}") from exc
        raise


# ═══════════════════════════════════════════════════════════════
# 板块投资决策引擎 (Decision Engine)
# ═══════════════════════════════════════════════════════════════

DECISION_SECTOR_ETF: dict[str, list[dict]] = {
    # Core high-liquidity sectors
    "半导体": [{"etf_code": "512480", "name": "半导体ETF", "liquidity": "高"}],
    "证券": [{"etf_code": "512880", "name": "证券ETF", "liquidity": "高"}],
    "银行": [{"etf_code": "512800", "name": "银行ETF", "liquidity": "高"}],
    "医药": [{"etf_code": "512010", "name": "医药ETF", "liquidity": "高"}],
    "新能源汽车": [{"etf_code": "516850", "name": "新能车ETF", "liquidity": "中"}],
    "军工": [{"etf_code": "512660", "name": "军工ETF", "liquidity": "高"}],
    "消费": [{"etf_code": "159928", "name": "消费ETF", "liquidity": "高"}],
    "光伏": [{"etf_code": "515790", "name": "光伏ETF", "liquidity": "高"}],
    "光伏设备": [{"etf_code": "515790", "name": "光伏ETF", "liquidity": "高"}],
    "芯片": [{"etf_code": "159995", "name": "芯片ETF", "liquidity": "高"}],
    "人工智能": [{"etf_code": "515070", "name": "AI ETF", "liquidity": "中"}],
    "电力": [{"etf_code": "562380", "name": "电力ETF", "liquidity": "中"}],
    "白酒": [{"etf_code": "512690", "name": "酒ETF", "liquidity": "高"}],
    "新能源": [{"etf_code": "516160", "name": "新能源ETF", "liquidity": "中"}],
    "食品饮料": [{"etf_code": "515170", "name": "食饮ETF", "liquidity": "中"}],
    "房地产": [{"etf_code": "512200", "name": "地产ETF", "liquidity": "高"}],
    # 20 scan-cache sectors — all confirmed working via WeStock kline
    "非金属材料Ⅱ": [{"etf_code": "516750", "name": "建材ETF", "liquidity": "低"}],
    "金属新材料": [{"etf_code": "159813", "name": "新材料ETF", "liquidity": "低"}],
    "通信设备": [{"etf_code": "159994", "name": "通信ETF", "liquidity": "高"}],
    "医疗服务": [{"etf_code": "515220", "name": "医疗ETF", "liquidity": "中"}],
    "小金属": [{"etf_code": "159876", "name": "稀土ETF", "liquidity": "中"}],
    "消费电子": [{"etf_code": "159819", "name": "消费电子ETF", "liquidity": "中"}],
    "电子": [{"etf_code": "159519", "name": "电子ETF", "liquidity": "中"}],
    "元件": [{"etf_code": "166025", "name": "元件ETF", "liquidity": "低"}],
    "其他电子Ⅱ": [{"etf_code": "159995", "name": "芯片ETF", "liquidity": "高"}],
    "通用设备": [{"etf_code": "515880", "name": "机械ETF", "liquidity": "中"}],
    "自动化设备": [{"etf_code": "159892", "name": "制造ETF", "liquidity": "中"}],
    "化学制药": [{"etf_code": "159938", "name": "医药ETF", "liquidity": "高"}],
    "乘用车": [{"etf_code": "516110", "name": "汽车ETF", "liquidity": "中"}],
    "有色金属": [{"etf_code": "512400", "name": "有色ETF", "liquidity": "高"}],
    "电网设备": [{"etf_code": "159326", "name": "电网设备ETF", "liquidity": "中"}],
    "中药Ⅱ": [{"etf_code": "501011", "name": "中药ETF", "liquidity": "中"}],
    "医疗器械": [{"etf_code": "159883", "name": "医疗器械ETF", "liquidity": "中"}],
    "电力设备": [{"etf_code": "159637", "name": "电力设备ETF", "liquidity": "中"}],
    "美容护理": [{"etf_code": "159861", "name": "美容ETF", "liquidity": "中"}],
    "通用机械": [{"etf_code": "515880", "name": "机械ETF", "liquidity": "中"}],
}


def _ma(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def calc_atr(bars: list[dict], period: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h = safe_float(bars[i].get("high"))
        lo = safe_float(bars[i].get("low"))
        pc = safe_float(bars[i - 1].get("close"))
        tr = max(h - lo, abs(h - pc), abs(lo - pc)) if h and lo and pc else (h - lo)
        trs.append(tr)
    window = trs[-period:] if len(trs) >= period else trs
    return sum(window) / len(window) if window else 0.0


def calc_adx_dmi(bars: list[dict], period: int = 14) -> dict | None:
    if len(bars) < period + 5:
        return None
    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []
    tr_list: list[float] = []
    for i in range(1, len(bars)):
        h = safe_float(bars[i].get("high"))
        lo = safe_float(bars[i].get("low"))
        ph = safe_float(bars[i - 1].get("high"))
        pl = safe_float(bars[i - 1].get("low"))
        pc = safe_float(bars[i - 1].get("close"))
        up_move = h - ph
        down_move = pl - lo
        plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0.0)
        tr_list.append(max(h - lo, abs(h - pc), abs(lo - pc)))

    def wilder(vals: list[float], n: int) -> list[float]:
        out = [sum(vals[:n])]
        for v in vals[n:]:
            out.append(out[-1] - out[-1] / n + v)
        return out

    if len(tr_list) < period:
        return None
    str14 = wilder(tr_list, period)
    spdm = wilder(plus_dm_list, period)
    smdm = wilder(minus_dm_list, period)
    pdi_list, mdi_list, dx_list = [], [], []
    for atr_v, pdm, mdm in zip(str14, spdm, smdm):
        pdi = 100 * pdm / atr_v if atr_v else 0.0
        mdi = 100 * mdm / atr_v if atr_v else 0.0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0
        pdi_list.append(pdi)
        mdi_list.append(mdi)
        dx_list.append(dx)
    adx = sum(dx_list[-period:]) / period if len(dx_list) >= period else sum(dx_list) / max(len(dx_list), 1)
    return {"adx": round(adx, 2), "plus_di": round(pdi_list[-1], 2), "minus_di": round(mdi_list[-1], 2)}


def zscore_normalize_cross(val: float, all_vals: list[float], clip: float = 2.0) -> float:
    if not all_vals or len(all_vals) < 2:
        return 0.0
    mu = sum(all_vals) / len(all_vals)
    variance = sum((x - mu) ** 2 for x in all_vals) / len(all_vals)
    sigma = variance ** 0.5 or 1.0
    return max(-1.0, min(1.0, (val - mu) / (sigma * clip)))


def hist_rows_to_bars(hist_rows: list[tuple[dt.date, dict]]) -> list[dict]:
    bars = []
    for d, row in hist_rows:
        close = safe_float(get_field(row, "收盘", "close", "last"))
        high = safe_float(get_field(row, "最高", "high"))
        lo = safe_float(get_field(row, "最低", "low"))
        open_v = safe_float(get_field(row, "开盘", "open"))
        volume = safe_float(get_field(row, "成交量", "volume"), 0.0)
        exchange = safe_float(get_field(row, "换手率", "exchange"), 0.0)
        if close > 0:
            bars.append({
                "date": d.isoformat(),
                "open": open_v or close,
                "high": high or close,
                "low": lo or close,
                "close": close,
                "volume": volume,
                "turnover": exchange,
            })
    return bars


def compute_sector_factors(
    hist_rows: list[tuple[dt.date, dict]],
    csi300_rows: list[tuple[dt.date, dict]],
    flow_rows: list[tuple[dt.date, dict]],
    cons_rows: list[dict],
) -> dict:
    bars = hist_rows_to_bars(hist_rows)
    closes = [b["close"] for b in bars]
    turnovers = [b["turnover"] for b in bars]

    ma5_v = _ma(closes, 5)
    ma20_v = _ma(closes, 20)
    ma60_v = _ma(closes, 60)
    if ma5_v and ma20_v and ma60_v:
        if ma5_v > ma20_v > ma60_v:
            trend_ma_align = 1.0
        elif ma5_v < ma20_v < ma60_v:
            trend_ma_align = -1.0
        elif ma5_v > ma20_v:
            trend_ma_align = 0.4
        elif ma5_v < ma20_v:
            trend_ma_align = -0.4
        else:
            trend_ma_align = 0.0
    elif ma5_v and ma20_v:
        trend_ma_align = 0.5 if ma5_v > ma20_v else -0.5
    else:
        trend_ma_align = 0.0

    _, _, macd_hist = macd(closes)

    bar_dicts = [{"high": b["high"], "low": b["low"], "close": b["close"]} for b in bars]
    adx_result = calc_adx_dmi(bar_dicts) if len(bar_dicts) >= 20 else None
    trend_adx = None
    if adx_result:
        adx_v = adx_result["adx"]
        if adx_v > 25:
            trend_adx = 1.0 if adx_result["plus_di"] > adx_result["minus_di"] else -1.0
        else:
            trend_adx = 0.0

    mom_return_20 = pct_change(closes, 20) if len(closes) > 20 else 0.0

    csi_bars = hist_rows_to_bars(csi300_rows)
    csi_closes = [b["close"] for b in csi_bars]
    mom_rs20 = (pct_change(closes, 20) - pct_change(csi_closes, 20)) if (len(closes) > 20 and len(csi_closes) > 20) else 0.0

    flow_main_net = None
    flow_main_net_5d = None
    if flow_rows:
        recent = [r for _, r in flow_rows[-6:]]
        if recent:
            raw_1d = safe_float(get_field(recent[-1], "主力净流入-净额", "主力净流入", "净流入"))
            if raw_1d:
                flow_main_net = raw_1d
            vals_5d = [safe_float(get_field(r, "主力净流入-净额", "主力净流入", "净流入")) for r in recent[-5:]]
            vals_5d = [v for v in vals_5d if v]
            if vals_5d:
                flow_main_net_5d = sum(vals_5d)

    breadth_adv_decline = None
    if cons_rows:
        changes = [safe_float(get_field(r, "涨跌幅")) for r in cons_rows]
        changes = [c for c in changes if c is not None]
        if changes:
            up = sum(1 for c in changes if c > 0)
            down_cnt = sum(1 for c in changes if c < 0)
            breadth_adv_decline = (up - down_cnt) / len(changes)

    crowd_turnover = turnovers[-1] if turnovers else None

    return {
        "trend_ma_align": trend_ma_align,
        "trend_macd_hist": macd_hist,
        "trend_adx": trend_adx,
        "mom_return_20": mom_return_20,
        "mom_rs20": mom_rs20,
        "flow_main_net": flow_main_net,
        "flow_main_net_5d": flow_main_net_5d,
        "breadth_adv_decline": breadth_adv_decline,
        "crowd_turnover": crowd_turnover,
        "last_close": closes[-1] if closes else 0.0,
        "bars": bars,
    }


def score_sector_factors(factors: dict, normalized: dict) -> dict:
    ma_n = normalized.get("trend_ma_align", 0.0) or 0.0
    macd_n = normalized.get("trend_macd_hist") or 0.0
    adx_n = normalized.get("trend_adx")

    trend_score = ma_n * 0.35 + macd_n * 0.35 + (adx_n or 0.0) * (0.30 if adx_n is not None else 0.0)
    if adx_n is None:
        trend_score = ma_n * 0.50 + macd_n * 0.50

    momentum_score = (normalized.get("mom_return_20") or 0.0) * 0.45 + (normalized.get("mom_rs20") or 0.0) * 0.55
    flow_score = (normalized.get("flow_main_net") or 0.0) * 0.55 + (normalized.get("flow_main_net_5d") or 0.0) * 0.45
    breadth_score = normalized.get("breadth_adv_decline") or 0.0
    crowd_score = normalized.get("crowd_turnover") or 0.0
    breadth_low_conf = factors.get("breadth_adv_decline") is None

    composite = (trend_score * 0.30 + momentum_score * 0.25 + flow_score * 0.25 + breadth_score * 0.20)
    confidence = 0.50
    if adx_n is not None:
        confidence += 0.15
    if factors.get("flow_main_net") is not None:
        confidence += 0.20
    if not breadth_low_conf:
        confidence += 0.15

    return {
        "composite": round(max(-1.0, min(1.0, composite)), 4),
        "trend": round(trend_score, 4),
        "momentum": round(momentum_score, 4),
        "flow": round(flow_score, 4),
        "breadth": round(breadth_score, 4),
        "crowd": round(crowd_score, 4),
        "confidence": round(min(1.0, confidence), 3),
        "breadth_low_confidence": breadth_low_conf,
    }


TIER_ORDER = ["强烈看多", "看多", "中性", "看空", "强烈看空"]


def composite_to_tier(composite: float) -> str:
    if composite >= 0.55:
        return "强烈看多"
    if composite >= 0.25:
        return "看多"
    if composite > -0.25:
        return "中性"
    if composite > -0.55:
        return "看空"
    return "强烈看空"


def downgrade_tier(tier: str) -> str:
    idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 2
    return TIER_ORDER[min(idx + 1, len(TIER_ORDER) - 1)]


def check_sector_gates(
    factors: dict,
    hist_rows: list[tuple[dt.date, dict]],
    trade_date: dt.date,
    scores: dict,
) -> list[str]:
    gates = []
    today = dt.date.today()
    if (today - trade_date).days > 3:
        gates.append("SG1:数据可能过期")
    if len(hist_rows) < 45:
        gates.append("SG2:历史数据不足(低置信)")
    if not scores.get("breadth_low_confidence") and scores.get("momentum", 0.0) > 0.3 and scores.get("breadth", 0.0) < -0.3:
        gates.append("SG4:广度背离→降级")
    if scores.get("momentum", 0.0) > 0.3 and scores.get("flow", 0.0) < -0.3:
        gates.append("SG5:资金背离→降级")
    return gates


def compute_decision_price_levels(bars: list[dict]) -> dict | None:
    closes = [b["close"] for b in bars]
    if len(bars) < 2 or not closes:
        return None
    atr14 = calc_atr(bars)
    if not atr14:
        return None
    last_close = closes[-1]
    stop_loss = round(last_close - 1.5 * atr14, 3)
    target_1 = round(last_close + 2.0 * atr14, 3)
    target_2 = round(last_close + 3.5 * atr14, 3)
    risk = last_close - stop_loss
    return {
        "last_close": round(last_close, 3),
        "atr14": round(atr14, 3),
        "entry_low": round(last_close - 0.3 * atr14, 3),
        "entry_high": round(last_close + 0.3 * atr14, 3),
        "stop_loss": stop_loss,
        "target_1": target_1,
        "target_2": target_2,
        "risk_reward": round((target_1 - last_close) / risk, 2) if risk > 0 else 0.0,
        "note": "决策价位非价格预测",
    }


def decision_cache_path(kind: str, key: str, date: dt.date) -> Path:
    safe = re.sub(r"[^\w一-鿿]+", "_", key)
    return CACHE_DIR / f"decision_{kind}_{safe}_{date.isoformat()}.json"


def load_decision_cache(kind: str, key: str, date: dt.date) -> dict | None:
    path = decision_cache_path(kind, key, date)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("meta", {})["cacheHit"] = True
        return data
    except Exception as exc:
        log(f"decision cache read failed: {path.name}: {exc}")
        return None


def write_decision_cache(kind: str, key: str, date: dt.date, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    data.setdefault("meta", {})["cacheHit"] = False
    with decision_cache_path(kind, key, date).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fetch_sector_hist_for_decision(name: str, start: dt.date, target: dt.date, cfg: dict, limit: int = 100) -> list[tuple[dt.date, dict]]:
    primary = str(cfg.get("market", {}).get("primary_source") or "westock").lower()
    if primary == "westock":
        # Check hardcoded ETF map first — reliable direct lookup for all known sectors
        etf_list = DECISION_SECTOR_ETF.get(name, [])
        if etf_list:
            raw_code = etf_list[0]["etf_code"]
            mkt = "sh" if raw_code.startswith(("5", "6")) else "sz"
            symbol = f"{mkt}{raw_code}"
            try:
                rows = westock_kline(symbol, cfg, limit=limit)
                if rows:
                    return rows_until(rows, target)
            except Exception as exc:
                log(f"decision ETF map hist failed: {name} {symbol}: {exc}")
        # Fuzzy search fallback for sectors not in ETF map
        try:
            sym = westock_search_stock(name, cfg)
            if sym:
                rows = westock_kline(sym, cfg, limit=limit)
                if rows:
                    return rows_until(rows, target)
        except Exception as exc:
            log(f"decision westock hist failed: {name}: {exc}")
    ak = get_ak()
    try:
        rows = date_rows(records(ak.stock_board_industry_hist_em(
            symbol=name, start_date=ymd(start), end_date=ymd(target), period="日k", adjust=""
        )))
        return rows_until(rows, target)
    except Exception as exc:
        log(f"decision akshare hist failed: {name}: {exc}")
        return []


def _fetch_csi300_for_decision(target: dt.date, cfg: dict) -> list[tuple[dt.date, dict]]:
    start = target - dt.timedelta(days=200)
    primary = str(cfg.get("market", {}).get("primary_source") or "westock").lower()
    if primary == "westock":
        try:
            rows = westock_kline("sh000300", cfg, limit=100)
            if rows:
                return rows_until(rows, target)
        except Exception:
            pass
    ak = get_ak()
    try:
        rows = date_rows(records(ak.stock_zh_index_daily_em(symbol="sh000300", start_date=ymd(start), end_date=ymd(target))))
        return rows_until(rows, target)
    except Exception as exc:
        log(f"decision CSI300 failed: {exc}")
        return []


def _fetch_sector_flow_for_decision(name: str, target: dt.date, cfg: dict) -> list[tuple[dt.date, dict]]:
    ak = get_ak()
    try:
        rows = date_rows(records(ak.stock_sector_fund_flow_hist(symbol=name)))
        result = rows_until(rows, target)
        if result:
            return result
    except Exception as exc:
        log(f"decision flow AKShare failed: {name}: {exc}")
    # Fallback: WeStock board 行业资金流入 table
    try:
        board_text = westock_run(["board"], cfg)
        for heading, rows in parse_markdown_tables(board_text):
            if "资金流入" in heading and rows and "mainNetInflow" in rows[0]:
                for r in rows:
                    if str(r.get("name") or "").strip() == name:
                        v1 = safe_float(r.get("mainNetInflow"))
                        v5 = safe_float(r.get("mainNetInflow5d"))
                        if v1 or v5:
                            avg5 = (v5 / 5.0) if v5 else (v1 or 0.0)
                            synthetic = []
                            for i in range(5):
                                d = target - dt.timedelta(days=4 - i)
                                synthetic.append((d, {"主力净流入": avg5, "主力净流入-净额": avg5}))
                            if v1:
                                synthetic[-1] = (target, {"主力净流入": v1, "主力净流入-净额": v1})
                            log(f"decision flow WeStock fallback: {name} v1={v1} v5={v5}")
                            return synthetic
    except Exception as exc:
        log(f"decision flow WeStock fallback failed: {name}: {exc}")
    return []


def _fetch_sector_cons_for_decision(name: str, cfg: dict) -> list[dict]:
    """Get sector constituents. Try AKShare first; fall back to WeStock ETF hot-stock list."""
    ak = get_ak()
    try:
        rows = records(ak.stock_board_industry_cons_em(symbol=name))
        if rows:
            return rows
    except Exception as exc:
        log(f"decision cons AKShare failed: {name}: {exc}")
    # Fallback: use WeStock hot stock list via ETF code
    # First try the hardcoded ETF map; then try westock_search_stock to auto-find ETF
    etf_list = DECISION_SECTOR_ETF.get(name, [])
    if etf_list:
        raw_code = etf_list[0]["etf_code"]
        mkt = "sh" if raw_code.startswith(("5", "6")) else "sz"
        symbol = f"{mkt}{raw_code}"
    else:
        # Try to find an ETF for this sector by name search
        found = westock_search_stock(name, cfg)
        if not found:
            return []
        symbol = found
    try:
        out = westock_run(["hot", "stock", "--symbol", symbol, "--limit", "50"], cfg)
        rows = []
        for _, table_rows in parse_markdown_tables(out):
            if table_rows and "zdf" in table_rows[0]:
                for r in table_rows:
                    code = str(r.get("code") or "").strip()
                    if not code or not re.match(r"^(sh|sz)\d{6}$", code):
                        continue
                    rows.append({
                        "代码": code[2:],
                        "名称": str(r.get("name") or "").strip(),
                        "涨跌幅": safe_float(r.get("zdf")),
                    })
                break
        if rows:
            log(f"decision cons WeStock fallback: {name} got {len(rows)} stocks")
        return rows
    except Exception as exc:
        log(f"decision cons WeStock fallback failed: {name}: {exc}")
        return []


def _normalize_factor_list(sectors_factors: list[dict]) -> list[dict]:
    keys = ["trend_macd_hist", "mom_return_20", "mom_rs20",
            "flow_main_net", "flow_main_net_5d", "breadth_adv_decline", "crowd_turnover"]
    all_vals: dict[str, list[float]] = {k: [] for k in keys}
    for sf in sectors_factors:
        for k in keys:
            v = sf.get(k)
            if v is not None:
                all_vals[k].append(v)

    normalized_list = []
    for sf in sectors_factors:
        norm: dict[str, Any] = {}
        norm["trend_ma_align"] = sf.get("trend_ma_align", 0.0)
        norm["trend_adx"] = sf.get("trend_adx")
        for k in keys:
            v = sf.get(k)
            norm[k] = zscore_normalize_cross(v, all_vals[k]) if v is not None else (0.0 if "flow" not in k else None)
        normalized_list.append(norm)
    return normalized_list


def build_decision_rotation(requested: dt.date, cfg: dict, force_refresh: bool = False) -> dict:
    target = min(requested, dt.date.today())
    if not force_refresh:
        cached = load_decision_cache("rotation", "all", target)
        if cached:
            return cached

    ak = get_ak()
    start = target - dt.timedelta(days=120)

    names: list[str] = []
    try:
        spot = records(ak.stock_board_industry_name_em())
        for row in (spot or []):
            name = str(get_field(row, "板块名称", "名称") or "").strip()
            if name and name not in names:
                names.append(name)
    except Exception as exc:
        log(f"decision rotation name_em failed, falling back to scan cache: {exc}")

    if not names:
        scan_cache = latest_cache(target)
        if scan_cache:
            universe = scan_cache.get("_universe") or scan_cache.get("sectors") or []
            names = [str(s.get("name") or "").strip() for s in universe if s.get("name")]
            names = list(dict.fromkeys(names))  # dedup preserving order
            log(f"decision rotation using {len(names)} names from scan cache")

    if not names:
        names = list(DECISION_SECTOR_ETF.keys())
        log(f"decision rotation falling back to hardcoded {len(names)} sectors")

    csi300_rows = _fetch_csi300_for_decision(target, cfg)

    histories: dict[str, list[tuple[dt.date, dict]]] = {}
    flow_data: dict[str, list[tuple[dt.date, dict]]] = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        hist_futures = {pool.submit(_fetch_sector_hist_for_decision, n, start, target, cfg): n for n in names}
        for future in as_completed(hist_futures):
            n = hist_futures[future]
            try:
                rows = future.result()
                if rows:
                    histories[n] = rows
            except Exception as exc:
                log(f"decision rotation hist: {n}: {exc}")

    with ThreadPoolExecutor(max_workers=4) as pool:
        flow_futures = {pool.submit(_fetch_sector_flow_for_decision, n, target, cfg): n for n in names}
        for future in as_completed(flow_futures):
            n = flow_futures[future]
            try:
                rows = future.result()
                if rows:
                    flow_data[n] = rows
            except Exception as exc:
                log(f"decision rotation flow: {n}: {exc}")

    sectors_factors = []
    for name in names:
        hist = histories.get(name, [])
        if not hist:
            continue
        trade_date = hist[-1][0]
        factors = compute_sector_factors(hist, csi300_rows, flow_data.get(name, []), [])
        # Rotation skips constituent fetch — treat breadth as neutral rather than missing
        if factors.get("breadth_adv_decline") is None:
            factors["breadth_adv_decline"] = 0.0
        factors["name"] = name
        factors["trade_date"] = trade_date.isoformat()
        sectors_factors.append(factors)

    if not sectors_factors:
        raise RuntimeError("No sector factor data could be computed")

    normalized_list = _normalize_factor_list(sectors_factors)

    result_sectors = []
    for sf, norm in zip(sectors_factors, normalized_list):
        scores = score_sector_factors(sf, norm)
        trade_date = dt.date.fromisoformat(sf["trade_date"])
        gates = check_sector_gates(sf, histories.get(sf["name"], []), trade_date, scores)
        if any("SG1" in g or "SG2" in g for g in gates):
            tier = "NO_SIGNAL"
        else:
            tier = composite_to_tier(scores["composite"])
            if any("SG4" in g or "SG5" in g for g in gates):
                tier = downgrade_tier(tier)
        result_sectors.append({
            "name": sf["name"],
            "tier": tier,
            "composite": scores["composite"],
            "confidence": scores["confidence"],
            "rs20": round(sf.get("mom_rs20", 0.0), 2),
            "flow_score": scores["flow"],
            "breadth_score": scores["breadth"],
            "breadth_low_confidence": scores["breadth_low_confidence"],
            "gates": gates,
            "group_scores": {k: scores[k] for k in ("trend", "momentum", "flow", "breadth", "crowd")},
            "trade_date": sf["trade_date"],
        })

    active = sorted([s for s in result_sectors if s["tier"] != "NO_SIGNAL"], key=lambda s: s["composite"], reverse=True)
    abstained = [s for s in result_sectors if s["tier"] == "NO_SIGNAL"]
    for idx, s in enumerate(active, 1):
        s["rank"] = idx

    data = {
        "meta": {
            "tradeDate": target.isoformat(),
            "asOf": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "sectorCount": len(active),
            "abstainedCount": len(abstained),
            "cacheHit": False,
        },
        "sectors": active,
        "abstained": abstained,
    }
    write_decision_cache("rotation", "all", target, data)
    return data


def build_decision_sector(name: str, requested: dt.date, cfg: dict, force_refresh: bool = False) -> dict:
    target = min(requested, dt.date.today())
    if not force_refresh:
        cached = load_decision_cache("sector", name, target)
        if cached:
            return cached

    start = target - dt.timedelta(days=120)
    hist = _fetch_sector_hist_for_decision(name, start, target, cfg)
    if not hist:
        raise RuntimeError(f"No history data for sector: {name}")
    trade_date = hist[-1][0]
    csi300_rows = _fetch_csi300_for_decision(target, cfg)
    flow_rows = _fetch_sector_flow_for_decision(name, target, cfg)
    cons_rows = _fetch_sector_cons_for_decision(name, cfg)

    pct_above_ma20: float | None = None
    pct_above_ma60: float | None = None
    top_cons = sorted(cons_rows, key=lambda r: abs(safe_float(get_field(r, "涨跌幅"))), reverse=True)[:20]
    con_symbols = []
    for r in top_cons:
        code = str(get_field(r, "代码", "股票代码") or "").strip()
        if not re.match(r"^\d{6}$", code):
            continue
        if code.startswith(("5", "6", "9")):
            con_symbols.append(f"sh{code}")
        else:
            con_symbols.append(f"sz{code}")
    if con_symbols:
        try:
            batch = westock_kline_batch(con_symbols[:15], cfg, limit=70)
            above20 = above60 = total = 0
            for sym_rows in batch.values():
                filtered = rows_until(sym_rows, target)
                c_closes = [safe_float(get_field(r, "last", "close", "收盘")) for _, r in filtered]
                c_closes = [v for v in c_closes if v > 0]
                if len(c_closes) >= 20:
                    if _ma(c_closes, 20) and c_closes[-1] > (_ma(c_closes, 20) or 0):
                        above20 += 1
                    total += 1
                if len(c_closes) >= 60:
                    if _ma(c_closes, 60) and c_closes[-1] > (_ma(c_closes, 60) or 0):
                        above60 += 1
            if total > 0:
                pct_above_ma20 = round(above20 / total, 3)
                pct_above_ma60 = round(above60 / total, 3)
        except Exception as exc:
            log(f"decision constituent klines failed: {name}: {exc}")

    factors = compute_sector_factors(hist, csi300_rows, flow_rows, cons_rows)
    bars = factors["bars"]

    # Single-sector normalization: sign-based for flow, direct for ma/adx
    flow_n1 = (1.0 if (factors.get("flow_main_net") or 0) > 0 else -1.0) if factors.get("flow_main_net") is not None else 0.0
    flow_n5 = (1.0 if (factors.get("flow_main_net_5d") or 0) > 0 else -1.0) if factors.get("flow_main_net_5d") is not None else 0.0
    closes = [b["close"] for b in bars]
    recent_returns = [pct_change(closes, n) for n in range(1, min(21, len(closes)))]
    norm_mom = zscore_normalize_cross(factors["mom_return_20"], recent_returns) if recent_returns else 0.0
    norm: dict[str, Any] = {
        "trend_ma_align": factors["trend_ma_align"],
        "trend_macd_hist": zscore_normalize_cross(factors["trend_macd_hist"], [factors["trend_macd_hist"]]) if factors["trend_macd_hist"] else 0.0,
        "trend_adx": factors["trend_adx"],
        "mom_return_20": norm_mom,
        "mom_rs20": max(-1.0, min(1.0, factors["mom_rs20"] / 10.0)) if factors["mom_rs20"] else 0.0,
        "flow_main_net": flow_n1,
        "flow_main_net_5d": flow_n5,
        "breadth_adv_decline": factors.get("breadth_adv_decline") or 0.0,
        "crowd_turnover": 0.0,
    }

    scores = score_sector_factors(factors, norm)
    gates = check_sector_gates(factors, hist, trade_date, scores)
    if any("SG1" in g or "SG2" in g for g in gates):
        tier = "NO_SIGNAL"
    else:
        tier = composite_to_tier(scores["composite"])
        if any("SG4" in g or "SG5" in g for g in gates):
            tier = downgrade_tier(tier)

    price_levels = compute_decision_price_levels(bars)

    evidence = ""
    if not any("SG1" in g for g in gates):
        try:
            llm_payload = {
                "sector": name, "tier": tier, "composite": scores["composite"],
                "factors": {
                    "ma_align": factors["trend_ma_align"],
                    "macd_hist": round(factors["trend_macd_hist"], 4),
                    "mom_return_20": round(factors["mom_return_20"], 2),
                    "mom_rs20": round(factors["mom_rs20"], 2),
                    "flow_main_net": factors["flow_main_net"],
                    "breadth_adv_decline": factors["breadth_adv_decline"],
                },
                "gates": gates,
            }
            parsed, _ = call_llm_json(
                cfg,
                "你是A股板块决策分析助手。根据用户提供的板块因子数据，用2-3句简洁中文描述该板块的投资信号与主要依据。"
                "输出JSON: {\"evidence\": \"分析文本（不超过150字）\"}。不得给出价格预测，必须说明仅供研究参考。",
                llm_payload,
                max_tokens=300,
            )
            evidence = str(parsed.get("evidence", "")).strip()[:200]
        except LLMDisabled:
            pass
        except Exception as exc:
            log(f"decision LLM failed: {name}: {exc}")

    cons_result = []
    for r in sorted(cons_rows, key=lambda row: safe_float(get_field(row, "涨跌幅")), reverse=True)[:30]:
        nm = str(get_field(r, "名称", "股票名称") or "").strip()
        code = str(get_field(r, "代码", "股票代码") or "").strip()
        if nm:
            chg = safe_float(get_field(r, "涨跌幅"))
            cons_result.append({"name": nm, "code": code, "change_pct": round(chg, 2)})

    data = {
        "meta": {"tradeDate": trade_date.isoformat(), "asOf": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "cacheHit": False},
        "name": name,
        "tier": tier,
        "composite": scores["composite"],
        "confidence": scores["confidence"],
        "gates": gates,
        "group_scores": {k: scores[k] for k in ("trend", "momentum", "flow", "breadth", "crowd")},
        "factors": {
            "trend_ma_align": {"raw": factors["trend_ma_align"], "norm": norm["trend_ma_align"], "label": "均线排列", "group": "trend"},
            "trend_macd": {"raw": round(factors["trend_macd_hist"], 6), "norm": norm["trend_macd_hist"], "label": "MACD柱", "group": "trend"},
            "trend_adx": {"raw": factors["trend_adx"], "norm": norm.get("trend_adx"), "label": "ADX方向", "group": "trend"},
            "mom_return_20": {"raw": round(factors["mom_return_20"], 2), "norm": norm["mom_return_20"], "label": "20日动量%", "group": "momentum"},
            "mom_rs20": {"raw": round(factors["mom_rs20"], 2), "norm": norm["mom_rs20"], "label": "20日超额收益%", "group": "momentum"},
            "flow_main_net": {"raw": factors["flow_main_net"], "norm": norm["flow_main_net"], "real": factors["flow_main_net"] is not None, "label": "1日主力净流入", "group": "flow"},
            "flow_main_net_5d": {"raw": factors["flow_main_net_5d"], "norm": norm["flow_main_net_5d"], "real": factors["flow_main_net_5d"] is not None, "label": "5日主力净流入", "group": "flow"},
            "breadth_adv_decline": {"raw": factors.get("breadth_adv_decline"), "norm": norm["breadth_adv_decline"], "label": "涨跌家数比", "group": "breadth"},
            "breadth_pct_above_ma20": {"raw": pct_above_ma20, "norm": None if pct_above_ma20 is None else round(pct_above_ma20 * 2 - 1, 3), "label": "站上MA20占比", "group": "breadth"},
            "breadth_pct_above_ma60": {"raw": pct_above_ma60, "norm": None if pct_above_ma60 is None else round(pct_above_ma60 * 2 - 1, 3), "label": "站上MA60占比", "group": "breadth"},
        },
        "target_price": price_levels,
        "etf_candidates": DECISION_SECTOR_ETF.get(name, []),
        "constituents": cons_result,
        "evidence": evidence,
        "disclaimer": "决策支持非投资建议；目标位为决策价位非预测；请核对后自行决策。",
    }
    write_decision_cache("sector", name, target, data)
    return data


def build_decision_stock(symbol: str, requested: dt.date, cfg: dict, force_refresh: bool = False) -> dict:
    target = min(requested, dt.date.today())
    if not force_refresh:
        cached = load_decision_cache("stock", symbol, target)
        if cached:
            return cached

    stock_item = chanlun_stock_item(symbol)
    try:
        bars, _, _ = fetch_chanlun_bars(stock_item, "day", target, cfg)
    except Exception as exc:
        raise RuntimeError(f"Cannot fetch stock bars for {symbol}: {exc}") from exc

    if len(bars) < 20:
        data = {
            "meta": {"tradeDate": target.isoformat(), "cacheHit": False},
            "symbol": symbol, "name": stock_item.get("name", symbol),
            "tier": "LOW_CONFIDENCE", "composite": 0.0, "confidence": 0.3,
            "gates": ["TG3:历史数据不足"], "factors": {}, "target_price": None,
            "disclaimer": "决策支持非投资建议。",
        }
        return data

    closes = [b["close"] for b in bars]
    bar_dicts = [{"high": b["high"], "low": b["low"], "close": b["close"]} for b in bars]

    ma5_v = _ma(closes, 5)
    ma20_v = _ma(closes, 20)
    ma60_v = _ma(closes, 60) if len(closes) >= 60 else None
    if ma5_v and ma20_v and ma60_v:
        ma_align = 1.0 if ma5_v > ma20_v > ma60_v else (-1.0 if ma5_v < ma20_v < ma60_v else 0.0)
    elif ma5_v and ma20_v:
        ma_align = 0.5 if ma5_v > ma20_v else -0.5
    else:
        ma_align = 0.0

    _, _, macd_h = macd(closes)
    adx_result = calc_adx_dmi(bar_dicts) if len(bar_dicts) >= 20 else None
    rsi14 = rsi(closes, 14)
    mom_return_20 = pct_change(closes, 20) if len(closes) > 20 else 0.0

    macd_norm = max(-1.0, min(1.0, macd_h / (abs(macd_h) * 3 or 1.0))) if macd_h else 0.0
    rsi_norm = (rsi14 - 50) / 50.0
    mom_norm = max(-1.0, min(1.0, mom_return_20 / 20.0))
    adx_norm = None
    if adx_result:
        adx_norm = (1.0 if adx_result["adx"] > 25 and adx_result["plus_di"] > adx_result["minus_di"]
                    else -1.0 if adx_result["adx"] > 25 else 0.0)

    trend_score = (ma_align * 0.35 + macd_norm * 0.35 + (adx_norm or 0.0) * 0.30
                   if adx_norm is not None else ma_align * 0.50 + macd_norm * 0.50)
    composite = round(max(-1.0, min(1.0, trend_score * 0.55 + mom_norm * 0.25 + rsi_norm * 0.20)), 4)

    data = {
        "meta": {"tradeDate": target.isoformat(), "asOf": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "cacheHit": False},
        "symbol": symbol, "name": stock_item.get("name", symbol),
        "tier": composite_to_tier(composite),
        "composite": composite,
        "confidence": round(0.5 + (0.15 if adx_norm is not None else 0.0), 3),
        "gates": [],
        "factors": {
            "trend_ma_align": {"raw": ma_align, "norm": ma_align, "label": "均线排列", "group": "trend"},
            "trend_macd": {"raw": round(macd_h, 6), "norm": round(macd_norm, 4), "label": "MACD柱", "group": "trend"},
            "trend_adx": {"raw": adx_result["adx"] if adx_result else None, "norm": adx_norm, "label": "ADX方向", "group": "trend"},
            "mom_return_20": {"raw": round(mom_return_20, 2), "norm": round(mom_norm, 4), "label": "20日动量%", "group": "momentum"},
            "osc_rsi14": {"raw": round(rsi14, 2), "norm": round(rsi_norm, 4), "label": "RSI(14)", "group": "oscillator"},
        },
        "target_price": compute_decision_price_levels(bar_dicts),
        "disclaimer": "决策支持非投资建议；目标位为决策价位非预测。",
    }
    write_decision_cache("stock", symbol, target, data)
    return data


# ═══════════════════════════════════════════════════════════════
#  MARKET REVIEW — 大盘复盘
# ═══════════════════════════════════════════════════════════════

REVIEW_CACHE_DIR = CACHE_DIR / "review"
REVIEW_CACHE_VERSION = "2026-06-19-review-v6-news-aggregate"

REVIEW_INDEX_MAP = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
}


def _review_cache_path(date_str: str) -> Path:
    return REVIEW_CACHE_DIR / f"review_{date_str.replace('-', '')}.json"


def _read_review_cache(date_str: str) -> dict | None:
    p = _review_cache_path(date_str)
    if p.exists():
        try:
            data = json.loads(p.read_text("utf-8"))
            if (
                isinstance(data, dict)
                and data.get("date")
                and data.get("meta", {}).get("cache_version") == REVIEW_CACHE_VERSION
            ):
                return data
        except Exception:
            pass
    return None


def _write_review_cache(date_str: str, data: dict) -> None:
    REVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _review_cache_path(date_str)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def fetch_review_indices() -> list[dict]:
    ak = get_ak()
    try:
        df = ak.stock_zh_index_spot_sina()
        if df is None or df.empty:
            return []
    except Exception as exc:
        log(f"review: index fetch failed: {exc}")
        return []
    results = []
    for code, name in REVIEW_INDEX_MAP.items():
        row = df[df["代码"] == code]
        if row.empty:
            continue
        row = row.iloc[0]
        current = safe_float(row.get("最新价", 0))
        prev_close = safe_float(row.get("昨收", 0))
        high = safe_float(row.get("最高", 0))
        low = safe_float(row.get("最低", 0))
        amplitude = (high - low) / prev_close * 100 if prev_close > 0 else 0.0
        amount_raw = safe_float(row.get("成交额", 0))
        results.append({
            "code": code,
            "name": name,
            "current": round(current, 2),
            "change": round(safe_float(row.get("涨跌额", 0)), 2),
            "change_pct": round(safe_float(row.get("涨跌幅", 0)), 2),
            "open": round(safe_float(row.get("今开", 0)), 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "prev_close": round(prev_close, 2),
            "amount": round(amount_raw / 1e8, 2) if amount_raw > 1e6 else round(amount_raw, 2),
            "amplitude": round(amplitude, 2),
        })
    return results


def _is_kc_cy(code: str) -> bool:
    return code.startswith(("688", "30"))


def _is_bse(code: str) -> bool:
    return code.startswith(("8", "43", "87", "92", "93"))


def _is_st(name: str) -> bool:
    return "ST" in str(name).upper()


def _normalize_stock_code(code: str) -> str:
    return re.sub(r"^(sh|sz|bj)", "", str(code).strip().lower())


def fetch_review_market_stats() -> dict | None:
    ak = get_ak()
    import pandas as pd
    import numpy as np
    try:
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return None
    except Exception as exc:
        log(f"review: market stats fetch failed: {exc}")
        return None

    code_col = next((c for c in ["代码", "股票代码"] if c in df.columns), None)
    name_col = next((c for c in ["名称", "股票名称"] if c in df.columns), None)
    close_col = next((c for c in ["最新价"] if c in df.columns), None)
    pre_close_col = next((c for c in ["昨收"] if c in df.columns), None)
    amount_col = next((c for c in ["成交额"] if c in df.columns), None)
    if not all([code_col, name_col, close_col, pre_close_col, amount_col]):
        log("review: missing expected columns in spot data")
        return None

    up_count = down_count = flat_count = limit_up_count = limit_down_count = 0
    for code_raw, name_raw, current_raw, pre_close_raw, amount_raw in zip(
        df[code_col], df[name_col], df[close_col], df[pre_close_col], df[amount_col]
    ):
        if pd.isna(current_raw) or pd.isna(pre_close_raw) or current_raw in ["-"] or pre_close_raw in ["-"]:
            continue
        if pd.isna(amount_raw) or amount_raw == 0:
            continue
        try:
            current_price = float(current_raw)
            pre_close = float(pre_close_raw)
        except (ValueError, TypeError):
            continue
        if current_price <= 0 or pre_close <= 0:
            continue

        pure_code = _normalize_stock_code(str(code_raw))
        name_str = str(name_raw)
        if _is_bse(pure_code):
            ratio = 0.30
        elif _is_kc_cy(pure_code):
            ratio = 0.20
        elif _is_st(name_str):
            ratio = 0.05
        else:
            ratio = 0.10

        limit_up_price = np.floor(pre_close * (1 + ratio) * 100 + 0.5) / 100.0
        limit_down_price = np.floor(pre_close * (1 - ratio) * 100 + 0.5) / 100.0
        tol_up = round(abs(pre_close * (1 + ratio) - limit_up_price), 10)
        tol_down = round(abs(pre_close * (1 - ratio) - limit_down_price), 10)

        if abs(current_price - limit_up_price) <= tol_up:
            limit_up_count += 1
        if abs(current_price - limit_down_price) <= tol_down:
            limit_down_count += 1
        if current_price > pre_close:
            up_count += 1
        elif current_price < pre_close:
            down_count += 1
        else:
            flat_count += 1

    total_amount = 0.0
    if amount_col in df.columns:
        df[amount_col] = pd.to_numeric(df[amount_col], errors="coerce")
        total_amount = round(df[amount_col].sum() / 1e8, 0)

    return {
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "total_amount": total_amount,
    }


def fetch_review_sector_rankings(n: int = 5) -> dict:
    ak = get_ak()
    try:
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return {"top": [], "bottom": []}
    except Exception as exc:
        log(f"review: sector rankings fetch failed: {exc}")
        return {"top": [], "bottom": []}
    import pandas as pd
    change_col = "涨跌幅"
    name_col = "板块名称"
    df[change_col] = pd.to_numeric(df[change_col], errors="coerce")
    df = df.dropna(subset=[change_col])
    top = df.nlargest(n, change_col)
    bottom = df.nsmallest(n, change_col)
    return {
        "top": [{"name": row[name_col], "change_pct": round(row[change_col], 2)} for _, row in top.iterrows()],
        "bottom": [{"name": row[name_col], "change_pct": round(row[change_col], 2)} for _, row in bottom.iterrows()],
    }


def fetch_review_news(limit: int = 8) -> list[dict]:
    ak = get_ak()
    try:
        df = ak.stock_news_main_cx()
        if df is None or df.empty:
            return []
    except Exception as exc:
        log(f"review: news fetch failed: {exc}")
        return []
    items = []
    for _, row in df.head(limit).iterrows():
        items.append({
            "tag": str(row.get("tag", "")).strip(),
            "summary": str(row.get("summary", "")).strip(),
            "url": str(row.get("url", "")).strip(),
        })
    return items


def _review_source_state(
    provider: str,
    status: str,
    count: int,
    errors: list[str] | None = None,
    scope: str = "",
    fallback_used: bool = False,
) -> dict:
    state = {
        "provider": provider,
        "status": status,
        "count": count,
        "fallback_used": fallback_used,
    }
    if scope:
        state["scope"] = scope
    if errors:
        state["errors"] = [str(error)[:180] for error in errors[-3:]]
    return state


def _review_kline_limit(target: dt.date, minimum: int = 8, maximum: int = 800) -> int:
    calendar_days = max(0, (dt.date.today() - target).days)
    return min(maximum, max(minimum, int(calendar_days * 1.7) + 10))


def _review_row_value(row: dict, *names: str) -> float:
    return safe_float(get_field(row, *names))


def _review_index_item(symbol: str, name: str, rows: list[tuple[dt.date, dict]], target: dt.date) -> tuple[dict, dt.date] | None:
    eligible = rows_until(rows, target)
    if not eligible:
        return None
    trade_date, row = eligible[-1]
    previous = eligible[-2][1] if len(eligible) > 1 else {}
    current = _review_row_value(row, "last", "close", "收盘", "最新价")
    prev_close = _review_row_value(previous, "last", "close", "收盘")
    change = current - prev_close if prev_close else 0.0
    change_pct = change / prev_close * 100 if prev_close else 0.0
    amount_raw = _review_row_value(row, "amount", "成交额")
    closes = [_review_row_value(item, "last", "close", "收盘", "最新价") for _, item in eligible]
    closes = [value for value in closes if value > 0]
    recent_20 = closes[-20:]
    previous_trade_date = eligible[-2][0].isoformat() if len(eligible) > 1 else ""
    high = _review_row_value(row, "high", "最高")
    low = _review_row_value(row, "low", "最低")
    amplitude = (high - low) / prev_close * 100 if prev_close and high and low else 0.0
    return ({
        "code": symbol,
        "name": name,
        "current": round(current, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "open": round(_review_row_value(row, "open", "开盘"), 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "prev_close": round(prev_close, 2),
        "amount": round(amount_raw / 1e8, 2) if amount_raw else None,
        "amplitude": round(amplitude, 2),
        "d5": round(pct_change(closes, 5), 2) if len(closes) > 1 else 0.0,
        "d20": round(pct_change(closes, min(20, len(closes) - 1)), 2) if len(closes) > 1 else 0.0,
        "recent_high_20": round(max(recent_20), 2) if recent_20 else None,
        "recent_low_20": round(min(recent_20), 2) if recent_20 else None,
        "previous_trade_date": previous_trade_date,
        "trade_date": trade_date.isoformat(),
    }, trade_date)


def _fetch_review_indices_westock(target: dt.date, cfg: dict) -> tuple[list[dict], dt.date | None]:
    symbols = list(REVIEW_INDEX_MAP)
    histories = westock_kline_batch(symbols, cfg, limit=_review_kline_limit(target))
    items: list[dict] = []
    dates: list[dt.date] = []
    for symbol, name in REVIEW_INDEX_MAP.items():
        parsed = _review_index_item(symbol, name, histories.get(symbol, []), target)
        if parsed:
            item, trade_date = parsed
            items.append(item)
            dates.append(trade_date)
    return items, max(dates) if dates else None


def _fetch_review_indices_akshare(target: dt.date, cfg: dict) -> tuple[list[dict], dt.date | None]:
    ak = get_ak()
    items: list[dict] = []
    dates: list[dt.date] = []

    def fetch_one(pair: tuple[str, str]) -> tuple[dict, dt.date] | None:
        symbol, name = pair
        rows = date_rows(records(ak.stock_zh_index_daily(symbol=symbol)))
        return _review_index_item(symbol, name, rows, target)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch_one, pair): pair for pair in REVIEW_INDEX_MAP.items()}
        for future in as_completed(futures):
            try:
                parsed = future.result()
                if parsed:
                    item, trade_date = parsed
                    items.append(item)
                    dates.append(trade_date)
            except Exception as exc:
                log(f"review: AKShare index fallback failed {futures[future][0]}: {exc}")
    order = {symbol: idx for idx, symbol in enumerate(REVIEW_INDEX_MAP)}
    items.sort(key=lambda item: order.get(item["code"], 999))
    return items, max(dates) if dates else None


def fetch_review_indices_for_date(target: dt.date, cfg: dict) -> tuple[list[dict], dt.date | None, dict]:
    primary = str(cfg.get("market", {}).get("primary_source") or "westock").lower()
    providers = ["akshare", "westock"] if primary == "akshare" else ["westock", "akshare"]
    errors: list[str] = []
    for index, provider in enumerate(providers):
        try:
            if provider == "westock":
                items, trade_date = _fetch_review_indices_westock(target, cfg)
            else:
                items, trade_date = _fetch_review_indices_akshare(target, cfg)
            if len(items) >= 3 and trade_date:
                status = "fallback" if index else "ok"
                return items, trade_date, _review_source_state(provider, status, len(items), errors, "主要宽基指数", bool(index))
            errors.append(f"{provider}: only {len(items)} indices")
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {str(exc)[:130]}")
            log(f"review: index provider failed: {errors[-1]}")
    return [], None, _review_source_state("none", "unavailable", 0, errors, "主要宽基指数", bool(errors))


def _review_sector_symbols() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for name, etfs in DECISION_SECTOR_ETF.items():
        if not etfs:
            continue
        code = str(etfs[0].get("etf_code") or "").strip()
        if not code:
            continue
        symbol = ("sh" if code.startswith(("5", "6")) else "sz") + code
        if symbol in seen:
            continue
        seen.add(symbol)
        result.append((name, symbol))
    return result


def _review_sector_item(name: str, symbol: str, rows: list[tuple[dt.date, dict]], target: dt.date) -> dict | None:
    eligible = rows_until(rows, target)
    if len(eligible) < 2:
        return None
    trade_date, row = eligible[-1]
    previous = eligible[-2][1]
    current = _review_row_value(row, "last", "close", "收盘")
    prev_close = _review_row_value(previous, "last", "close", "收盘")
    if not current or not prev_close:
        return None
    amount_raw = _review_row_value(row, "amount", "成交额")
    closes = [_review_row_value(item, "last", "close", "收盘") for _, item in eligible]
    closes = [value for value in closes if value > 0]
    return {
        "name": name,
        "symbol": symbol,
        "change_pct": round((current / prev_close - 1) * 100, 2),
        "amount": round(amount_raw / 1e8, 2) if amount_raw else None,
        "d5": round(pct_change(closes, 5), 2) if len(closes) > 1 else 0.0,
        "d20": round(pct_change(closes, min(20, len(closes) - 1)), 2) if len(closes) > 1 else 0.0,
        "trade_date": trade_date.isoformat(),
    }


def _fetch_review_sectors_westock(target: dt.date, cfg: dict) -> list[dict]:
    pairs = _review_sector_symbols()
    symbols = [symbol for _, symbol in pairs]
    histories = westock_kline_batch(symbols, cfg, limit=_review_kline_limit(target))
    return [item for name, symbol in pairs if (item := _review_sector_item(name, symbol, histories.get(symbol, []), target))]


def _fetch_review_sectors_akshare(target: dt.date, cfg: dict) -> list[dict]:
    ak = get_ak()
    pairs = _review_sector_symbols()
    items: list[dict] = []

    def fetch_one(pair: tuple[str, str]) -> dict | None:
        name, symbol = pair
        rows = date_rows(records(ak.fund_etf_hist_sina(symbol=symbol)))
        return _review_sector_item(name, symbol, rows, target)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_one, pair): pair for pair in pairs}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    items.append(item)
            except Exception as exc:
                log(f"review: AKShare ETF fallback failed {futures[future][1]}: {exc}")
    return items


def _fetch_review_sectors_ths(target: dt.date, cfg: dict) -> list[dict]:
    """Fetch real Tonghuashun industry indices instead of ETF proxies."""
    ak = get_ak()
    names = records(ak.stock_board_industry_name_ths())
    workers = max(1, int(cfg.get("market", {}).get("review_sector_workers", 6)))
    start = target - dt.timedelta(days=75)
    items: list[dict] = []

    def fetch_one(row: dict) -> dict | None:
        name = str(row.get("name") or "").strip()
        code = str(row.get("code") or "").strip()
        if not name:
            return None
        df = ak.stock_board_industry_index_ths(symbol=name, start_date=ymd(start), end_date=ymd(target))
        parsed = _review_sector_item(name, code, date_rows(records(df)), target)
        if parsed:
            parsed["classification"] = "同花顺行业"
        return parsed

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, row): row for row in names}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    items.append(item)
            except Exception as exc:
                name = str(futures[future].get("name") or "")
                log(f"review: THS industry failed {name}: {exc}")
    return items


def _fetch_review_sectors_westock_boards(target: dt.date, cfg: dict) -> list[dict]:
    """Fetch WeStock's real industry board indices as the first sector fallback."""
    candidates, _ = fetch_westock_candidate_rows(target, cfg)
    candidates = [item for item in candidates if is_standard_industry_candidate(item) and item.get("_sourceSymbol")]
    if not candidates:
        return []
    symbols = [str(item["_sourceSymbol"]) for item in candidates]
    batch_size = max(10, int(cfg.get("market", {}).get("westock_batch_size", 30)))
    workers = max(1, int(cfg.get("market", {}).get("westock_kline_workers", 4)))
    histories: dict[str, list[tuple[dt.date, dict]]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(westock_kline_batch, group, cfg, _review_kline_limit(target)): group
            for group in chunked(symbols, batch_size)
        }
        for future in as_completed(futures):
            try:
                histories.update(future.result())
            except Exception as exc:
                log(f"review: WeStock industry batch failed: {exc}")
    items = []
    for candidate in candidates:
        symbol = str(candidate["_sourceSymbol"])
        item = _review_sector_item(str(candidate.get("name") or ""), symbol, histories.get(symbol, []), target)
        if item:
            item["classification"] = "WeStock行业板块"
            items.append(item)
    return items


def fetch_review_sector_rankings_for_date(target: dt.date, cfg: dict, n: int = 5) -> tuple[dict, list[dict], dict]:
    providers = [
        ("akshare-ths", _fetch_review_sectors_ths, "同花顺全行业指数"),
        ("westock-board", _fetch_review_sectors_westock_boards, "WeStock真实行业板块"),
        ("westock-etf", _fetch_review_sectors_westock, "行业ETF代理（末级降级）"),
        ("akshare-etf", _fetch_review_sectors_akshare, "行业ETF代理（末级降级）"),
    ]
    errors: list[str] = []
    for index, (provider, fetcher, scope) in enumerate(providers):
        try:
            universe = fetcher(target, cfg)
            if len(universe) >= 10:
                ordered = sorted(universe, key=lambda item: item["change_pct"], reverse=True)
                rankings = {"top": ordered[:n], "bottom": list(reversed(ordered[-n:]))}
                status = "fallback" if index else "ok"
                state = _review_source_state(provider, status, len(universe), errors, scope, bool(index))
                return rankings, universe, state
            errors.append(f"{provider}: only {len(universe)} industries")
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {str(exc)[:130]}")
            log(f"review: sector provider failed: {errors[-1]}")
    return {"top": [], "bottom": []}, [], _review_source_state("none", "unavailable", 0, errors, "行业板块", bool(errors))


def _derive_review_breadth(sector_universe: list[dict], scope: str = "行业板块样本") -> dict | None:
    if not sector_universe:
        return None
    up = sum(1 for item in sector_universe if item.get("change_pct", 0) > 0)
    down = sum(1 for item in sector_universe if item.get("change_pct", 0) < 0)
    flat = len(sector_universe) - up - down
    return {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "limit_up_count": None,
        "limit_down_count": None,
        "limit_available": False,
        "total_amount": 0,
        "scope": scope,
        "sample_size": len(sector_universe),
    }


def _review_stock_symbol(code: str) -> str:
    pure = _normalize_stock_code(code)
    if pure.startswith(("43", "83", "87", "88", "92")):
        return f"bj{pure}"
    if pure.startswith(("5", "6", "9")):
        return f"sh{pure}"
    return f"sz{pure}"


def _review_a_share_universe(cfg: dict) -> tuple[list[dict], bool]:
    cache_path = REVIEW_CACHE_DIR / "a_share_universe.json"
    ttl_days = max(1, int(cfg.get("market", {}).get("review_universe_ttl_days", 7)))
    stale: list[dict] = []
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text("utf-8"))
            stale = cached.get("items", []) if isinstance(cached, dict) else []
            generated = dt.datetime.fromisoformat(str(cached.get("generated_at") or ""))
            if stale and dt.datetime.now() - generated < dt.timedelta(days=ttl_days):
                return stale, True
        except Exception:
            pass
    try:
        rows = records(get_ak().stock_info_a_code_name())
        items = []
        for row in rows:
            code = str(row.get("code") or row.get("代码") or "").strip().zfill(6)
            name = str(row.get("name") or row.get("名称") or "").strip()
            if re.fullmatch(r"\d{6}", code):
                items.append({"code": code, "symbol": _review_stock_symbol(code), "name": name})
        if items:
            REVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"generated_at": dt.datetime.now().isoformat(), "items": items}, ensure_ascii=False), "utf-8")
            return items, False
    except Exception as exc:
        log(f"review: A-share universe refresh failed: {exc}")
    if stale:
        return stale, True
    raise RuntimeError("A-share universe unavailable")


def _fetch_review_technical_snapshot(symbols: list[str], target: dt.date, cfg: dict) -> dict[str, dict]:
    batch_size = max(50, int(cfg.get("market", {}).get("review_breadth_batch_size", 500)))
    workers = max(1, int(cfg.get("market", {}).get("review_breadth_workers", 4)))
    result: dict[str, dict] = {}
    failed_groups: list[list[str]] = []

    def fetch_group(group: list[str]) -> list[dict]:
        text = westock_run(["technical", ",".join(group), "--date", target.isoformat(), "--group", "ma"], cfg)
        return first_table_rows(text)

    def merge_rows(rows: list[dict]) -> None:
        for row in rows:
            if parse_iso_date(row.get("date")) != target:
                continue
            symbol = str(row.get("code") or "").strip().lower()
            close = safe_float(row.get("closePrice"))
            if symbol and close > 0:
                result[symbol] = {"close": close, "name": str(row.get("name") or "").strip()}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_group, group): group for group in chunked(symbols, batch_size)}
        for future in as_completed(futures):
            try:
                merge_rows(future.result())
            except Exception as exc:
                group = futures[future]
                failed_groups.append(group)
                log(f"review: full-A technical batch failed ({len(group)} symbols), scheduling retry: {type(exc).__name__}")
    for failed in failed_groups:
        for group in chunked(failed, max(50, batch_size // 2)):
            try:
                time.sleep(0.15)
                merge_rows(fetch_group(group))
            except Exception as exc:
                log(f"review: full-A technical retry failed ({len(group)} symbols): {type(exc).__name__}")
    return result


def _fetch_review_exchange_turnover(target: dt.date) -> tuple[float, dict]:
    ak = get_ak()
    errors: list[str] = []
    sh_amount = sz_amount = 0.0
    try:
        rows = records(ak.stock_sse_deal_daily(date=ymd(target)))
        row = next((item for item in rows if str(item.get("单日情况")) == "成交金额"), None)
        sh_amount = safe_float((row or {}).get("股票"))
    except Exception as exc:
        errors.append(f"SSE: {type(exc).__name__}")
    try:
        rows = records(ak.stock_szse_summary(date=ymd(target)))
        row = next((item for item in rows if str(item.get("证券类别")) == "股票"), None)
        sz_amount = safe_float((row or {}).get("成交金额")) / 1e8
    except Exception as exc:
        errors.append(f"SZSE: {type(exc).__name__}")
    total = sh_amount + sz_amount
    return round(total, 2), {
        "sse_stock_amount": round(sh_amount, 2),
        "szse_stock_amount": round(sz_amount, 2),
        "unit": "亿元",
        "scope": "沪深交易所股票",
        "errors": errors,
    }


def _review_breadth_cache_path(target: dt.date) -> Path:
    return REVIEW_CACHE_DIR / f"a_share_breadth_{ymd(target)}.json"


def _read_review_breadth_cache(target: dt.date, previous: dt.date) -> tuple[dict, dict] | None:
    path = _review_breadth_cache_path(target)
    if not path.exists():
        return None
    try:
        cached = json.loads(path.read_text("utf-8"))
        breadth = cached.get("breadth") or {}
        if (
            cached.get("cache_version") == REVIEW_CACHE_VERSION
            and breadth.get("previous_trade_date") == previous.isoformat()
            and safe_float(breadth.get("coverage")) >= 95
        ):
            state = _review_source_state("westock-full-a", "ok", int(breadth.get("sample_size") or 0), [], "全A历史收盘", False)
            state.update({"coverage": breadth.get("coverage"), "aggregate_cached": True})
            return breadth, state
    except Exception:
        pass
    return None


def _write_review_breadth_cache(target: dt.date, breadth: dict) -> None:
    REVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_version": REVIEW_CACHE_VERSION,
        "generated_at": dt.datetime.now().isoformat(),
        "breadth": breadth,
    }
    _review_breadth_cache_path(target).write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def _fetch_review_full_a_breadth(trade_date: dt.date, previous_trade_date: dt.date, cfg: dict) -> tuple[dict, dict]:
    cached = _read_review_breadth_cache(trade_date, previous_trade_date)
    if cached:
        return cached
    universe, universe_cached = _review_a_share_universe(cfg)
    symbols = [item["symbol"] for item in universe]
    current = _fetch_review_technical_snapshot(symbols, trade_date, cfg)
    previous = _fetch_review_technical_snapshot(symbols, previous_trade_date, cfg)
    with ThreadPoolExecutor(max_workers=2) as pool:
        turnover_future = pool.submit(_fetch_review_exchange_turnover, trade_date)
        previous_turnover_future = pool.submit(_fetch_review_exchange_turnover, previous_trade_date)
        total_amount, turnover_breakdown = turnover_future.result()
        previous_total_amount, _ = previous_turnover_future.result()

    up = down = flat = limit_up = limit_down = 0
    name_by_symbol = {item["symbol"]: item.get("name", "") for item in universe}
    for symbol in current.keys() & previous.keys():
        close = safe_float(current[symbol].get("close"))
        prev_close = safe_float(previous[symbol].get("close"))
        if close <= 0 or prev_close <= 0:
            continue
        name = current[symbol].get("name") or name_by_symbol.get(symbol, "")
        pure_code = _normalize_stock_code(symbol)
        ratio = 0.30 if _is_bse(pure_code) else 0.20 if _is_kc_cy(pure_code) else 0.05 if _is_st(name) else 0.10
        up_price = math.floor(prev_close * (1 + ratio) * 100 + 0.5) / 100.0
        down_price = math.floor(prev_close * (1 - ratio) * 100 + 0.5) / 100.0
        if abs(close - up_price) <= 0.011:
            limit_up += 1
        if abs(close - down_price) <= 0.011:
            limit_down += 1
        if close > prev_close:
            up += 1
        elif close < prev_close:
            down += 1
        else:
            flat += 1
    sample_size = up + down + flat
    if sample_size < max(1000, int(len(universe) * 0.95)):
        raise RuntimeError(f"full-A coverage too low: {sample_size}/{len(universe)}")
    amount_change_pct = (total_amount / previous_total_amount - 1) * 100 if total_amount and previous_total_amount else None
    breadth = {
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "total_amount": total_amount,
        "previous_total_amount": previous_total_amount,
        "amount_change_pct": round(amount_change_pct, 2) if amount_change_pct is not None else None,
        "turnover_breakdown": turnover_breakdown,
        "scope": "全A历史收盘（沪深北）",
        "turnover_scope": "沪深交易所股票成交额",
        "sample_size": sample_size,
        "universe_size": len(universe),
        "coverage": round(sample_size / len(universe) * 100, 2),
        "previous_trade_date": previous_trade_date.isoformat(),
        "limit_method": "收盘价与法定涨跌停价匹配",
    }
    state = _review_source_state("westock-full-a", "ok", sample_size, [], "全A历史收盘", False)
    state.update({"coverage": breadth["coverage"], "universe_cached": universe_cached})
    _write_review_breadth_cache(trade_date, breadth)
    return breadth, state


def _extract_review_breadth_from_news(trade_date: dt.date, news: list[dict]) -> tuple[dict, dict] | None:
    pairs: dict[tuple[int, int], list[dict]] = {}
    limit_pairs: dict[tuple[int, int], list[dict]] = {}
    for item in news:
        text = str(item.get("summary") or "")
        up_match = re.search(r"(?:全市场\s*)?上涨\s*(?:个股\s*)?[:：]?\s*(\d{3,4})\s*家", text)
        down_match = re.search(r"(?:全市场\s*)?下跌\s*(?:个股\s*)?[:：]?\s*(\d{3,4})\s*家", text)
        if up_match and down_match:
            pair = (int(up_match.group(1)), int(down_match.group(1)))
            if 1000 <= sum(pair) <= 7000:
                pairs.setdefault(pair, []).append(item)
        limit_up = re.search(r"涨停(?:家数)?\s*[:：]?\s*(\d{1,3})\s*家", text)
        limit_down = re.search(r"跌停(?:家数)?\s*[:：]?\s*(\d{1,3})\s*家", text)
        if limit_up and limit_down:
            pair = (int(limit_up.group(1)), int(limit_down.group(1)))
            limit_pairs.setdefault(pair, []).append(item)
    if not pairs:
        return None
    breadth_pair, evidence_items = max(pairs.items(), key=lambda entry: (len(entry[1]), sum(entry[0])))
    limit_pair: tuple[int, int] | None = None
    limit_evidence: list[dict] = []
    if limit_pairs:
        limit_pair, limit_evidence = max(limit_pairs.items(), key=lambda entry: len(entry[1]))
    evidence = []
    for item in evidence_items + limit_evidence:
        value = {"title": item.get("title") or item.get("summary", "")[:80], "url": item.get("url", "")}
        if value not in evidence:
            evidence.append(value)
    up, down = breadth_pair
    breadth = {
        "up_count": up,
        "down_count": down,
        "flat_count": 0,
        "flat_available": False,
        "limit_up_count": limit_pair[0] if limit_pair else None,
        "limit_down_count": limit_pair[1] if limit_pair else None,
        "limit_available": bool(limit_pair),
        "limit_method": "盘后报道数字" if limit_pair else "未检索到一致口径",
        "total_amount": 0,
        "scope": "盘后新闻报道（全市场口径）",
        "sample_size": up + down,
        "reported_date": trade_date.isoformat(),
        "evidence": evidence[:4],
        "confidence": "cross-checked" if len(evidence_items) >= 2 else "single-source",
    }
    state = _review_source_state("news-search-aggregate", "ok", len(evidence), [], "指定日期盘后报道", False)
    state.update({"confidence": breadth["confidence"], "evidence": evidence[:4]})
    return breadth, state


def fetch_review_breadth_for_date(
    trade_date: dt.date,
    previous_trade_date: dt.date | None,
    sector_universe: list[dict],
    sectors_source: dict,
    news: list[dict],
    cfg: dict,
) -> tuple[dict | None, dict]:
    errors: list[str] = []
    extracted = _extract_review_breadth_from_news(trade_date, news)
    if extracted:
        breadth, state = extracted
        total_amount, turnover_breakdown = _fetch_review_exchange_turnover(trade_date)
        previous_total_amount, _ = _fetch_review_exchange_turnover(previous_trade_date) if previous_trade_date else (0.0, {})
        breadth["total_amount"] = total_amount
        breadth["previous_total_amount"] = previous_total_amount
        breadth["amount_change_pct"] = round((total_amount / previous_total_amount - 1) * 100, 2) if total_amount and previous_total_amount else None
        breadth["turnover_breakdown"] = turnover_breakdown
        breadth["turnover_scope"] = "沪深交易所股票成交额"
        breadth["previous_trade_date"] = previous_trade_date.isoformat() if previous_trade_date else ""
        return breadth, state
    errors.append("news-search-aggregate: no consistent up/down pair found")
    sector_scope = str(sectors_source.get("scope") or "行业板块样本")
    breadth = _derive_review_breadth(sector_universe, sector_scope)
    if breadth:
        total_amount, turnover_breakdown = _fetch_review_exchange_turnover(trade_date)
        previous_total_amount, _ = _fetch_review_exchange_turnover(previous_trade_date) if previous_trade_date else (0.0, {})
        breadth["total_amount"] = total_amount
        breadth["previous_total_amount"] = previous_total_amount
        breadth["amount_change_pct"] = round((total_amount / previous_total_amount - 1) * 100, 2) if total_amount and previous_total_amount else None
        breadth["turnover_breakdown"] = turnover_breakdown
        breadth["turnover_scope"] = "沪深交易所股票成交额"
        provider = "sector-etf-proxy" if "ETF" in sector_scope.upper() else "industry-board-proxy"
        return breadth, _review_source_state(provider, "fallback", len(sector_universe), errors, sector_scope, True)
    return None, _review_source_state("none", "unavailable", 0, errors, "市场宽度", bool(errors))


def _fetch_review_news_westock(target: dt.date, cfg: dict, limit: int) -> list[dict]:
    rows = first_table_rows(westock_run(["hot", "news", "--limit", str(max(limit * 4, 24))], cfg))
    items = []
    for row in rows:
        published = dt.datetime.fromtimestamp(safe_float(row.get("publish_time"))).date() if safe_float(row.get("publish_time")) else None
        if published and published > target:
            continue
        title = str(row.get("news_title") or "").strip()
        if title:
            items.append({"tag": str(row.get("source") or "快讯").strip(), "summary": title, "url": "", "published_at": published.isoformat() if published else ""})
        if len(items) >= limit:
            break
    return items


def _fetch_review_news_akshare(target: dt.date, cfg: dict, limit: int) -> list[dict]:
    items = []
    for item in fetch_review_news(max(limit * 4, 24)):
        url = str(item.get("url") or "")
        matched = re.search(r"/(20\d{2}-\d{2}-\d{2})/", url)
        published = parse_iso_date(matched.group(1)) if matched else None
        if published and published > target:
            continue
        item["published_at"] = published.isoformat() if published else ""
        items.append(item)
        if len(items) >= limit:
            break
    return items


def _review_search_queries(target: dt.date) -> list[str]:
    date_cn = f"{target.year}年{target.month}月{target.day}日"
    return [
        f"{date_cn} A股 收评 上涨家数 下跌家数 成交额",
    ]


def _fetch_review_news_search(target: dt.date, cfg: dict, limit: int) -> list[dict]:
    """Search dated market-close coverage; snippets are evidence, not hidden detail aggregation."""
    timeout = int(cfg.get("market", {}).get("http_timeout_seconds", 10))
    cache_path = REVIEW_CACHE_DIR / f"news_search_{ymd(target)}.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text("utf-8"))
            if cached.get("cache_version") == REVIEW_CACHE_VERSION and cached.get("items"):
                return cached["items"][:limit]
        except Exception:
            pass
    items: list[dict] = []
    seen: set[str] = set()
    for query in _review_search_queries(target):
        encoded = urllib.parse.quote(query)
        endpoints = [
            ("sogou-mobile", f"https://m.sogou.com/web/searchList.jsp?keyword={encoded}", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"),
            ("360-search", f"https://www.so.com/s?q={encoded}", "Mozilla/5.0"),
            ("sogou", f"https://www.sogou.com/web?query={encoded}", "Mozilla/5.0"),
        ]
        for provider, url, user_agent in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": user_agent})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    page = resp.read()
                    final_url = resp.geturl()
                if "antispider" in final_url:
                    continue
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(page, "html.parser")
                results_container = soup.select_one("div.results")
                if results_container:
                    aggregate_text = re.sub(r"\s+", " ", results_container.get_text(" ", strip=True)).strip()[:2400]
                    if f"{target.year}年{target.month}月{target.day}日" in aggregate_text:
                        items.append({
                            "tag": "搜索摘要",
                            "summary": aggregate_text,
                            "title": f"{target.isoformat()} A股盘后搜索结果摘要",
                            "url": url,
                            "published_at": target.isoformat(),
                            "query": query,
                            "search_provider": provider,
                        })
                for anchor in soup.select("h3 a")[:12]:
                    title = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
                    href = html_lib.unescape(str(anchor.get("href") or "")).strip()
                    parsed_href = urllib.parse.urlparse(href)
                    query_args = urllib.parse.parse_qs(parsed_href.query)
                    direct = (query_args.get("pcurl") or query_args.get("url") or [""])[0]
                    href = direct or urllib.parse.urljoin(url, href)
                    container = anchor.find_parent("div", class_=re.compile(r"(?:res|vr|result)", re.I)) or anchor.parent
                    snippet = re.sub(r"\s+", " ", container.get_text(" ", strip=True) if container else "").strip()
                    if snippet.startswith(title):
                        snippet = snippet[len(title):].strip()
                    snippet = snippet.split("推荐您搜索", 1)[0].strip()[:1200]
                    key = re.sub(r"\s+", "", title)
                    if not title or key in seen:
                        continue
                    combined = title + " " + snippet + " " + href
                    date_markers = (str(target.year), ymd(target), target.isoformat(), f"{target.month}月{target.day}日")
                    if not any(marker in combined for marker in date_markers):
                        continue
                    years = {int(value) for value in re.findall(r"(?<!\d)(20\d{2})(?!\d)", combined)}
                    if years and target.year not in years:
                        continue
                    seen.add(key)
                    items.append({
                        "tag": "盘后搜索",
                        "summary": f"{title}：{snippet}" if snippet else title,
                        "title": title,
                        "url": href,
                        "published_at": target.isoformat(),
                        "query": query,
                        "search_provider": provider,
                    })
                    if len(items) >= limit:
                        break
                if items:
                    break
            except Exception as exc:
                log(f"review: {provider} search failed: {type(exc).__name__}")
        if items:
            break
    if items:
        REVIEW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"cache_version": REVIEW_CACHE_VERSION, "generated_at": dt.datetime.now().isoformat(), "items": items}, ensure_ascii=False, indent=2), "utf-8")
    return items


def fetch_review_news_for_date(target: dt.date, cfg: dict, limit: int = 8) -> tuple[list[dict], dict]:
    providers = [
        ("web-search", _fetch_review_news_search, "指定日期盘后新闻搜索"),
        ("westock", _fetch_review_news_westock, f"截至 {target.isoformat()}"),
        ("akshare", _fetch_review_news_akshare, f"截至 {target.isoformat()}"),
    ]
    errors: list[str] = []
    for index, (provider, fetcher, scope) in enumerate(providers):
        try:
            items = fetcher(target, cfg, limit)
            if items:
                status = "fallback" if index else "ok"
                return items, _review_source_state(provider, status, len(items), errors, scope, bool(index))
            errors.append(f"{provider}: no news at or before requested date")
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {str(exc)[:130]}")
            log(f"review: news provider failed: {errors[-1]}")
    return [], _review_source_state("none", "unavailable", 0, errors, f"截至 {target.isoformat()}", bool(errors))


def build_review_market_context(indices: list[dict], breadth: dict | None, sectors: dict) -> dict:
    by_name = {item.get("name"): item for item in indices}
    growth_names = ["深证成指", "创业板指", "科创50"]
    value_names = ["上证指数", "上证50", "沪深300"]

    def average(names: list[str]) -> float | None:
        values = [safe_float(by_name[name].get("change_pct")) for name in names if name in by_name]
        return round(sum(values) / len(values), 2) if values else None

    growth_avg = average(growth_names)
    value_avg = average(value_names)
    style_gap = round(growth_avg - value_avg, 2) if growth_avg is not None and value_avg is not None else None
    if style_gap is None:
        style = "数据不足"
    elif style_gap >= 0.7:
        style = "科技成长占优"
    elif style_gap <= -0.7:
        style = "大盘价值占优"
    else:
        style = "风格相对均衡"

    changes = [safe_float(item.get("change_pct")) for item in indices if item.get("change_pct") is not None]
    index_dispersion = round(max(changes) - min(changes), 2) if changes else None
    b = breadth or {}
    up = int(b.get("up_count") or 0)
    down = int(b.get("down_count") or 0)
    participants = up + down
    up_ratio = round(up / participants * 100, 2) if participants else None
    if index_dispersion is not None and index_dispersion >= 2.0:
        tone = "结构性分化"
    elif up_ratio is not None and up_ratio >= 60:
        tone = "普涨偏强"
    elif up_ratio is not None and up_ratio <= 40:
        tone = "普跌偏弱"
    else:
        tone = "震荡分化"
    amount_change = b.get("amount_change_pct")
    volume_state = "数据不足" if amount_change is None else "放量" if amount_change > 3 else "缩量" if amount_change < -3 else "量能持平"
    return {
        "market_tone": tone,
        "style": style,
        "growth_index_avg_pct": growth_avg,
        "value_index_avg_pct": value_avg,
        "style_gap_pct": style_gap,
        "index_dispersion_pct": index_dispersion,
        "up_ratio_pct": up_ratio,
        "limit_balance": int(b.get("limit_up_count") or 0) - int(b.get("limit_down_count") or 0),
        "volume_state": volume_state,
        "top_industries": [item.get("name") for item in sectors.get("top", [])[:3]],
        "bottom_industries": [item.get("name") for item in sectors.get("bottom", [])[:3]],
    }


def compute_market_signal(indices: list[dict], breadth: dict | None) -> dict:
    b = breadth or {}
    up = b.get("up_count", 0)
    down = b.get("down_count", 0)
    participants = up + down
    breadth_score = int(up / participants * 100) if participants > 0 else 50

    index_changes = [idx["change_pct"] for idx in indices if idx.get("change_pct") is not None]
    if index_changes:
        avg_change = sum(index_changes) / len(index_changes)
        index_score = int(max(0, min(100, 50 + avg_change * 12)))
    else:
        index_score = 50

    limit_up = int(b.get("limit_up_count") or 0)
    limit_down = int(b.get("limit_down_count") or 0)
    limit_total = limit_up + limit_down
    limit_score = int(limit_up / limit_total * 100) if limit_total > 0 else 50

    score = int(round(breadth_score * 0.45 + index_score * 0.35 + limit_score * 0.20))

    if score >= 60:
        status = "green"
    elif score >= 40:
        status = "yellow"
    else:
        status = "red"

    if score >= 70:
        temp_label = "强势"
    elif score >= 55:
        temp_label = "偏暖"
    elif score >= 40:
        temp_label = "震荡"
    else:
        temp_label = "偏弱"

    label_map = {"green": "可进攻", "yellow": "需观察", "red": "偏防守"}
    guidance_map = {
        "green": "风险偏好尚可，关注主线延续与仓位纪律。",
        "yellow": "信号分化，控制仓位并等待量价确认。",
        "red": "风险偏高，优先控制回撤，避免追高弱反弹。",
    }

    reasons = []
    if participants > 0:
        up_ratio = up / participants
        if up_ratio >= 0.6:
            reasons.append(f"上涨家数占比 {up_ratio:.0%}，赚钱效应扩散")
        elif up_ratio <= 0.4:
            reasons.append(f"上涨家数占比 {up_ratio:.0%}，亏钱效应较强")
        else:
            reasons.append(f"上涨家数占比 {up_ratio:.0%}，市场分化")
    if index_changes:
        reasons.append(f"主要指数平均涨跌幅 {avg_change:+.2f}%")
    if limit_total > 0:
        reasons.append(f"涨跌停差 {limit_up - limit_down:+d}")
    amount = b.get("total_amount", 0)
    if amount > 0:
        vol_desc = "高活跃度" if amount >= 15000 else "中等活跃" if amount >= 9000 else "缩量观望"
        reasons.append(f"成交额 {amount:.0f} 亿，{vol_desc}")

    return {
        "score": score,
        "temperature": temp_label,
        "status": status,
        "label": label_map[status],
        "guidance": guidance_map[status],
        "reasons": reasons[:4],
    }


def call_llm_text(cfg: dict, system_prompt: str, user_content: str, max_tokens: int = 4000) -> tuple[str, str]:
    llm = cfg.get("llm", {})
    api_key = str(llm.get("api_key") or "").strip()
    if not api_key:
        raise LLMDisabled("LLM API key is not configured")
    base_url = str(llm.get("base_url") or "").rstrip("/")
    if not base_url:
        raise LLMDisabled("LLM base_url is not configured")

    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    model = normalize_model_name(llm.get("model") or "glm5")
    request_payload = {
        "model": model,
        "temperature": float(llm.get("temperature", 0.2)),
        "max_tokens": max_tokens,
        "enable_thinking": bool(llm.get("enable_thinking", False)),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=int(llm.get("timeout_seconds", 60))) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    return content.strip(), model


def _build_review_prompt(
    date_str: str,
    indices: list,
    breadth: dict | None,
    sectors: dict,
    news: list,
    market_context: dict,
    data_sources: dict,
) -> tuple[str, str]:
    b = breadth or {}
    indices_text = ""
    for idx in indices:
        d = "↑" if idx["change_pct"] > 0 else "↓" if idx["change_pct"] < 0 else "-"
        indices_text += (
            f"- {idx['name']}: {idx['current']:.2f} ({d}{abs(idx['change_pct']):.2f}%), "
            f"5日 {safe_float(idx.get('d5')):+.2f}%, 20日 {safe_float(idx.get('d20')):+.2f}%, "
            f"20日区间 {idx.get('recent_low_20', '?')}-{idx.get('recent_high_20', '?')}\n"
        )

    def sector_label(item: dict) -> str:
        return f"{item['name']}(当日 {item['change_pct']:+.2f}%, 5日 {safe_float(item.get('d5')):+.2f}%, 20日 {safe_float(item.get('d20')):+.2f}%)"

    top_text = "、".join([sector_label(s) for s in sectors.get("top", [])[:5]])
    bottom_text = "、".join([sector_label(s) for s in sectors.get("bottom", [])[:5]])

    news_text = ""
    for i, n in enumerate(news[:6], 1):
        tag = n.get("tag", "")
        summary = n.get("summary", "")
        tag_label = f"[{tag}] " if tag else ""
        news_text += f"{i}. {tag_label}{summary}\n"

    amount_change_text = "暂无可比数据" if b.get("amount_change_pct") is None else f"{safe_float(b.get('amount_change_pct')):+.2f}%"
    limit_text = (
        f"- 涨停: {b.get('limit_up_count')} 家 | 跌停: {b.get('limit_down_count')} 家"
        if b.get("limit_up_count") is not None and b.get("limit_down_count") is not None
        else "- 涨跌停: 当前降级口径不可用"
    )
    coverage_text = (
        f"{b.get('sample_size', '?')}/{b.get('universe_size', '?')} ({b.get('coverage', '?')}%)"
        if b.get("coverage") is not None
        else f"报道数 {len(b.get('evidence', []))}，置信度 {b.get('confidence', '未知')}"
    )
    stats_block = f"""## 全市场概况
- 上涨: {b.get('up_count', '?')} 家 | 下跌: {b.get('down_count', '?')} 家 | 平盘: {b.get('flat_count', '?')} 家
{limit_text}
- 沪深股票成交额: {b.get('total_amount', 0):.2f} 亿元 | 较前一交易日: {amount_change_text}
- 宽度口径: {b.get('scope', '未知')} | 证据: {coverage_text}
- 涨跌停口径: {b.get('limit_method', '未知')}""" if b else "## 全市场概况\n（数据暂不可用）"

    sector_block = f"""## 板块表现
领涨: {top_text or '暂无数据'}
领跌: {bottom_text or '暂无数据'}"""

    source_text = "\n".join(
        f"- {key}: provider={value.get('provider')}, scope={value.get('scope')}, status={value.get('status')}, confidence={value.get('confidence', '未标注')}"
        for key, value in data_sources.items()
    )

    system_prompt = """你是一位站在A股全市场视角的盘后复盘分析师。你的任务是解释市场事实、识别风格与广度的背离，不是仅复盘ETF。

【重要】输出要求：
- 必须输出纯 Markdown 文本格式
- 禁止输出 JSON 格式
- 禁止输出代码块
- 只能使用提供的数字与信息，不得编造政策、新闻催化、资金净流入、支撑位或压力位
- 没有直接资金流数据时，必须写“从涨跌结构推断”，不得写成已确认净流入/净流出
- 本次没有主力净流量数据；禁止声称“资金流入/流出、撤离、加仓、增量资金、存量资金迁移”，只能描述价格强弱及其对应的风格特征
- 支撑与压力只能参考给定的20日高低区间，且用“附近”表述
- 观察清单不得自行设定整数关口、成交额门槛或上涨家数门槛；数值条件只能直接引用已提供的当日值、前日值或20日收盘区间
- 新闻只可作为观察线索，除非与价格数据一致，不得声称其为板块涨跌的确定原因
- 每个核心结论要能区分“数据事实”与“分析推断”
- 语气专业、简洁，不给个股买卖建议，不给确定性涨跌预测"""

    user_content = f"""# 今日市场数据

## 日期
{date_str}

## 主要指数
{indices_text or '暂无指数数据'}

{stats_block}

{sector_block}

## 系统计算的全局结构
{json.dumps(market_context, ensure_ascii=False)}

## 数据源口径
{source_text}

## 市场新闻（仅作观察线索）
{news_text or '暂无相关新闻'}

---

# 输出格式模板（请严格按此格式输出）

## {date_str} 大盘复盘

### 一、📊 市场总结
（2–4段：指数结构、全A涨跌宽度、涨跌停、成交额；先给全局结论）

### 二、📈 指数点评
（逐一点评6个宽基指数；总结大盘/成长/价值风格差异）

### 三、💰 资金动向
（分析成交额及其较前日变化、涨跌停结构和市场宽度；无直接流向数据时必须标明为结构推断）

### 四、🔥 热点解读
（分别分析领涨与领跌的真实行业板块；结合5日/20日表现判断延续、加速或仅单日异动）

### 五、🔮 后市展望
（分“短期（1–3个交易日）”和“中期（1–2周）”；用可验证条件描述多空情景，不做确定预测）

### 六、⚠️ 观察清单与风险提示
（给出3–5个下一交易日可跟踪的指标或条件，列出风险；末尾写“仅供参考，不构成投资建议”）

---

请直接输出复盘报告内容，不要输出其他说明文字。"""

    return system_prompt, user_content


def _generate_template_review(date_str: str, indices: list, breadth: dict | None, sectors: dict, market_context: dict) -> str:
    b = breadth or {}
    mood_index = next((idx for idx in indices if idx["code"] == "sh000001"), None)
    if mood_index:
        pct = mood_index["change_pct"]
        mood = "强势上涨" if pct > 1 else "小幅上涨" if pct > 0 else "小幅下跌" if pct > -1 else "明显下跌"
    else:
        mood = "震荡整理"

    indices_text = ""
    for idx in indices:
        d = "↑" if idx["change_pct"] > 0 else "↓" if idx["change_pct"] < 0 else "-"
        indices_text += f"- **{idx['name']}**：{idx['current']:.2f}（{d}{abs(idx['change_pct']):.2f}%），5日 {safe_float(idx.get('d5')):+.2f}%，20日 {safe_float(idx.get('d20')):+.2f}%。\n"

    top_text = "、".join([s["name"] for s in sectors.get("top", [])[:3]])
    bottom_text = "、".join([s["name"] for s in sectors.get("bottom", [])[:3]])

    up = b.get("up_count", 0)
    down = b.get("down_count", 0)
    participation = up + down
    up_ratio = f"{up / participation:.0%}" if participation else "N/A"

    breadth_scope = str(b.get("scope") or "")
    breadth_label = "全市场新闻报道口径" if "全市场" in breadth_scope else "全A" if breadth_scope.startswith("全A") else f"{breadth_scope or '市场'}样本"
    limit_summary = (
        f"涨停 {b.get('limit_up_count')} 家，跌停 {b.get('limit_down_count')} 家。"
        if b.get("limit_up_count") is not None and b.get("limit_down_count") is not None
        else "当前降级口径不提供涨跌停家数。"
    )
    limit_balance_text = (
        f"，涨跌停差 {int(b.get('limit_up_count')) - int(b.get('limit_down_count')):+d}"
        if b.get("limit_up_count") is not None and b.get("limit_down_count") is not None
        else ""
    )

    return f"""## {date_str} 大盘复盘

> A股市场今日呈现**{mood}**态势。

### 一、📊 市场总结
今日A股市场整体{mood}，{breadth_label}上涨 {up} 家、下跌 {down} 家，上涨占比 {up_ratio}。{limit_summary}沪深股票成交 {b.get('total_amount', 0):.0f} 亿元。市场结构判断为**{market_context.get('market_tone', '数据不足')}**，风格为**{market_context.get('style', '数据不足')}**。

### 二、📈 指数点评
{indices_text}

### 三、💰 资金动向
沪深股票成交额 {b.get('total_amount', 0):.0f} 亿元，较前一交易日 {safe_float(b.get('amount_change_pct')):+.2f}%{limit_balance_text}。暂无直接资金流数据，只能从涨跌结构推断风格轮动。

### 四、🔥 热点解读
- **领涨板块**：{top_text or '暂无数据'}
- **领跌板块**：{bottom_text or '暂无数据'}

### 五、🔮 后市展望
- **短期（1–3个交易日）**：观察领涨行业能否扩散，以及指数分化是否收敛。
- **中期（1–2周）**：以成交额、全A上涨占比和领涨行业5日/20日延续性作为验证条件。

### 六、⚠️ 观察清单与风险提示
- 观察成交额是否延续{market_context.get('volume_state', '稳定')}。
- 观察全A上涨占比与领涨行业持续性。
- 警惕指数与市场宽度继续背离。

仅供参考，不构成投资建议。
"""


def _sanitize_review_report(report: str) -> str:
    """Keep price-based inference from being rendered as confirmed capital-flow fact."""
    replacements = {
        "资金撤离迹象明显（基于价格弱势推断）": "价格弱势特征明显，但无法仅凭价格确认实际资金流向",
        "资金撤离": "价格走弱",
        "资金净流入": "价格强势",
        "资金净流出": "价格弱势",
        "增量资金": "新增成交",
        "存量资金": "现有交易",
        "流动性挤出": "相对表现走弱",
    }
    for source, target in replacements.items():
        report = report.replace(source, target)
    return report


def _split_report_sections(report: str) -> list[dict]:
    text = (report or "").strip()
    if not text:
        return []
    matches = list(re.finditer(r"^(#{2,3})\s+(.+?)\s*$", text, flags=re.MULTILINE))
    if not matches:
        return [{"key": "full_review", "title": "复盘正文", "content": text}]
    sections = []
    first = matches[0]
    starts_with_title = first.start() == 0 and first.group(1) == "##"
    content_start = 1 if starts_with_title else 0
    intro_start = first.end() if starts_with_title else 0
    intro_end = matches[1].start() if starts_with_title and len(matches) > 1 else (len(text) if starts_with_title else matches[0].start())
    intro = text[intro_start:intro_end].strip()
    if intro:
        sections.append({"key": "overview", "title": "复盘概览", "content": intro})
    for i, m in enumerate(matches[content_start:], start=content_start):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = m.group(2).strip()
        content = text[start:end].strip()
        if not content:
            continue
        key = re.sub(r"[^0-9a-zA-Z一-鿿]+", "_", title).strip("_").lower()
        sections.append({"key": key or f"section_{i + 1}", "title": title, "content": content})
    return sections


_review_lock = threading.Lock()


def build_market_review(cfg: dict, force: bool = False, date_str: str | None = None) -> dict:
    started_at = dt.datetime.now()
    requested = parse_iso_date(date_str) if date_str else dt.date.today()
    if not requested:
        raise ValueError("复盘日期格式无效，请使用 YYYY-MM-DD")
    if requested > dt.date.today():
        raise ValueError("复盘日期不能晚于今天")
    today_str = requested.isoformat()
    if not force:
        cached = _read_review_cache(today_str)
        if cached:
            cached["meta"] = cached.get("meta", {})
            cached["meta"]["cached"] = True
            return cached

    log(f"review: fetching market data for {today_str}")
    with ThreadPoolExecutor(max_workers=3) as pool:
        indices_future = pool.submit(fetch_review_indices_for_date, requested, cfg)
        sectors_future = pool.submit(fetch_review_sector_rankings_for_date, requested, cfg, 5)
        news_future = pool.submit(fetch_review_news_for_date, requested, cfg, 8)
        indices, index_trade_date, indices_source = indices_future.result()
        sectors, sector_universe, sectors_source = sectors_future.result()
        news, news_source = news_future.result()

    sector_dates = [parse_iso_date(item.get("trade_date")) for item in sector_universe]
    sector_dates = [date for date in sector_dates if date]
    trade_date = index_trade_date or (max(sector_dates) if sector_dates else requested)
    previous_dates = [parse_iso_date(item.get("previous_trade_date")) for item in indices]
    previous_dates = [date for date in previous_dates if date and date < trade_date]
    previous_trade_date = max(previous_dates) if previous_dates else None
    breadth, breadth_source = fetch_review_breadth_for_date(
        trade_date,
        previous_trade_date,
        sector_universe,
        sectors_source,
        news,
        cfg,
    )
    market_context = build_review_market_context(indices, breadth, sectors)
    signal = compute_market_signal(indices, breadth)

    report = ""
    llm_model = ""
    llm_status = "ok"
    llm_error = ""
    try:
        report_date = trade_date.isoformat()
        data_sources = {
            "indices": indices_source,
            "breadth": breadth_source,
            "sectors": sectors_source,
            "news": news_source,
        }
        sys_prompt, user_content = _build_review_prompt(
            report_date,
            indices,
            breadth,
            sectors,
            news,
            market_context,
            data_sources,
        )
        if report_date != today_str:
            user_content = user_content.replace(
                "# 今日市场数据",
                f"# 市场数据\n\n> 用户选择 {today_str}，最近有效交易日为 {report_date}",
                1,
            )
        review_cfg = copy.deepcopy(cfg)
        review_cfg.setdefault("llm", {})["timeout_seconds"] = max(60, int(cfg.get("llm", {}).get("timeout_seconds", 45)))
        report, llm_model = call_llm_text(review_cfg, sys_prompt, user_content, max_tokens=1900)
        report = _sanitize_review_report(report)
        log(f"review: LLM report generated, model={llm_model}, length={len(report)}")
    except LLMDisabled as exc:
        llm_status = "disabled"
        llm_error = str(exc)
        log(f"review: LLM disabled, using template: {exc}")
        report = _generate_template_review(trade_date.isoformat(), indices, breadth, sectors, market_context)
        llm_model = "template"
    except Exception as exc:
        llm_status = "fallback"
        llm_error = f"{type(exc).__name__}: {str(exc)[:180]}"
        log(f"review: LLM failed ({exc}), using template")
        report = _generate_template_review(trade_date.isoformat(), indices, breadth, sectors, market_context)
        llm_model = "template"

    report_sections = _split_report_sections(report)
    completed_at = dt.datetime.now()
    duration_seconds = round((completed_at - started_at).total_seconds(), 2)

    data = {
        "date": today_str,
        "indices": indices,
        "breadth": breadth,
        "sectors": sectors,
        "market_context": market_context,
        "signal": signal,
        "news": news,
        "report": report,
        "report_sections": report_sections,
        "meta": {
            "source": "multi-source",
            "cache_version": REVIEW_CACHE_VERSION,
            "requested_date": today_str,
            "trade_date": trade_date.isoformat(),
            "data_sources": {
                "indices": indices_source,
                "breadth": breadth_source,
                "sectors": sectors_source,
                "news": news_source,
            },
            "llm_model": llm_model,
            "llm_status": llm_status,
            "llm_error": llm_error,
            "generated_at": completed_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration_seconds,
            "cached": False,
        },
    }
    _write_review_cache(today_str, data)
    return data


def list_review_history(limit: int = 14) -> list[dict]:
    if not REVIEW_CACHE_DIR.exists():
        return []
    files = sorted(REVIEW_CACHE_DIR.glob("review_*.json"), reverse=True)
    results = []
    for f in files:
        if len(results) >= limit:
            break
        try:
            d = json.loads(f.read_text("utf-8"))
            if d.get("meta", {}).get("cache_version") != REVIEW_CACHE_VERSION:
                continue
            results.append({
                "date": d.get("date", ""),
                "signal_score": d.get("signal", {}).get("score"),
                "signal_label": d.get("signal", {}).get("label"),
                "temperature": d.get("signal", {}).get("temperature"),
                "llm_model": d.get("meta", {}).get("llm_model"),
                "duration_seconds": d.get("meta", {}).get("duration_seconds"),
                "completed_at": d.get("meta", {}).get("completed_at") or d.get("meta", {}).get("generated_at"),
            })
        except Exception:
            continue
    return results


# ═══════════════════════════════════════════════════════════════
#  STOCK DECISION — 个股决策看板
# ═══════════════════════════════════════════════════════════════

STOCK_DECISION_CACHE_DIR = CACHE_DIR / "stock_decision"
STOCK_DECISION_CACHE_VERSION = "2026-06-29-v1"
STOCK_DECISION_TASKS: dict[str, dict] = {}
_STOCK_DECISION_TASK_LOCK = threading.Lock()
_STOCK_DECISION_TASK_SEQ = 0

def _stock_decision_cache_path(symbol: str, date_str: str) -> Path:
    return STOCK_DECISION_CACHE_DIR / f"{symbol}_{date_str.replace('-', '')}.json"

def _read_stock_decision_cache(symbol: str, date_str: str) -> dict | None:
    p = _stock_decision_cache_path(symbol, date_str)
    if p.exists():
        try:
            data = json.loads(p.read_text("utf-8"))
            if isinstance(data, dict) and data.get("meta", {}).get("cache_version") == STOCK_DECISION_CACHE_VERSION:
                return data
        except Exception:
            pass
    return None

def _write_stock_decision_cache(symbol: str, date_str: str, data: dict) -> None:
    STOCK_DECISION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _stock_decision_cache_path(symbol, date_str)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")

def load_stock_decision_list() -> list[dict]:
    txt_path = Path("/Users/huangzhifang/Desktop/Sequoia-X/tushare_select_stocks.txt")
    if not txt_path.exists():
        txt_path = BASE_DIR / "tushare_select_stocks.txt"
    if not txt_path.exists():
        return []
    stocks = []
    for line in txt_path.read_text("utf-8").strip().splitlines():
        parts = [p.strip() for p in line.strip().split(",") if p.strip()]
        if len(parts) >= 2:
            code = parts[0].strip()
            name = parts[1].strip()
            stocks.append({"code": code, "name": name, "score": 0, "price": None, "change": None, "strategies": {}})
    return stocks

def _calc_ma(values: list, period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period

def _calc_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def _check_turtle_breakout(bars: list) -> bool:
    if len(bars) < 21:
        return False
    highs = [b["high"] for b in bars[-21:-1]]
    highest = max(highs)
    return bars[-1]["close"] > highest

def _check_ma_volume_cross(bars: list) -> bool:
    if len(bars) < 20:
        return False
    closes = [b["close"] for b in bars]
    vols = [b.get("vol", 0) for b in bars]
    ma5 = _calc_ma(closes, 5)
    ma10 = _calc_ma(closes, 10)
    ma20 = _calc_ma(closes, 20)
    if ma5 is None or ma20 is None:
        return False
    prev_closes = closes[:-1]
    prev_ma5 = _calc_ma(prev_closes, 5)
    prev_ma20 = _calc_ma(prev_closes, 20)
    if prev_ma5 is None or prev_ma20 is None:
        return False
    cross_up = prev_ma5 <= prev_ma20 and ma5 > ma20
    avg_vol = sum(vols[-20:]) / 20
    vol_up = vols[-1] > avg_vol * 1.5
    return cross_up and vol_up

def _check_rps_breakout(bars: list) -> bool:
    if len(bars) < 20:
        return False
    closes = [b["close"] for b in bars]
    if closes[-1] != max(closes[-20:]):
        return False
    if len(closes) < 50:
        return True
    ma20 = _calc_ma(closes, 20)
    return ma20 is not None and closes[-1] > ma20

def _check_high_tight_flag(bars: list) -> bool:
    if len(bars) < 30:
        return False
    closes = [b["close"] for b in bars]
    min_price = min(closes[-30:-10])
    max_price = max(closes[-30:-10])
    if min_price == 0:
        return False
    flagpole_gain = (max_price - min_price) / min_price
    if flagpole_gain < 0.9:
        return False
    current = closes[-1]
    pullback = (max_price - current) / max_price
    return pullback < 0.25

def _compute_stock_strategies(bars: list) -> dict:
    return {
        "turtle": _check_turtle_breakout(bars),
        "ma_volume": _check_ma_volume_cross(bars),
        "rps_breakout": _check_rps_breakout(bars),
        "high_tight_flag": _check_high_tight_flag(bars),
    }

def _compute_stock_score(strategies: dict) -> int:
    score = 0
    if strategies.get("turtle"):
        score += 1
    if strategies.get("ma_volume"):
        score += 1
    if strategies.get("rps_breakout"):
        score += 1
    if strategies.get("high_tight_flag"):
        score += 1
    return score

def build_stock_decision_detail(code: str, requested: dt.date, cfg: dict) -> dict:
    date_str = requested.isoformat()
    cached = _read_stock_decision_cache(code, date_str)
    if cached:
        return cached

    stock_item = chanlun_stock_item(code)
    try:
        bars, _, _ = fetch_chanlun_bars(stock_item, "day", requested, cfg)
    except Exception as exc:
        raise RuntimeError(f"Cannot fetch stock bars for {code}: {exc}") from exc

    if len(bars) < 20:
        return {
            "code": code, "name": stock_item.get("name", code),
            "score": 0, "strategies": {}, "klines": [], "signals": [],
            "ma": [], "details": {}, "recommendation": {"text": "历史数据不足，无法分析", "metas": {}},
            "meta": {"cache_version": STOCK_DECISION_CACHE_VERSION}
        }

    closes = [b["close"] for b in bars]
    strategies = _compute_stock_strategies(bars)
    score = _compute_stock_score(strategies)

    ma5 = _calc_ma(closes, 5)
    ma10 = _calc_ma(closes, 10)
    ma20 = _calc_ma(closes, 20)

    klines = []
    for b in bars[-60:]:
        klines.append({
            "date": b["date"],
            "open": b["open"],
            "high": b["high"],
            "low": b["low"],
            "close": b["close"],
            "vol": b.get("vol", 0)
        })

    signals = []
    for i in range(1, len(bars)):
        prev_closes = [b["close"] for b in bars[:i]]
        prev_bars = bars[:i]
        if _check_turtle_breakout(prev_bars):
            signals.append({"date": bars[i]["date"], "type": "buy"})

    recommendation_text = ""
    if score >= 3:
        recommendation_text = "多个策略同时发出买入信号，建议重点关注。海龟突破、均线放量、RPS突破和高而窄旗形均确认，短期看多。"
    elif score >= 2:
        recommendation_text = "两个以上策略发出信号，可适当关注。建议结合大盘走势和板块热点综合判断。"
    elif score >= 1:
        recommendation_text = "单一策略信号，建议观望为主。等待更多确认信号后再考虑介入。"
    else:
        recommendation_text = "当前无明确买入信号，建议保持观望。可关注其他有信号的标的。"

    data = {
        "code": code,
        "name": stock_item.get("name", code),
        "score": score,
        "strategies": strategies,
        "klines": klines,
        "signals": signals,
        "ma": [
            {"label": "MA5", "value": ma5},
            {"label": "MA10", "value": ma10},
            {"label": "MA20", "value": ma20},
        ],
        "details": {
            "RSI(14)": round(_calc_rsi(closes, 14), 2),
            "20日涨幅": round((closes[-1] / closes[-20] - 1) * 100, 2) if len(closes) >= 20 else 0,
        },
        "recommendation": {
            "text": recommendation_text,
            "metas": {
                "策略通过数": f"{score}/4",
                "最新价": f"{closes[-1]:.2f}",
                "MA5": f"{ma5:.2f}" if ma5 else "-",
                "MA20": f"{ma20:.2f}" if ma20 else "-",
            }
        },
        "meta": {"tradeDate": requested.isoformat(), "cache_version": STOCK_DECISION_CACHE_VERSION}
    }

    _write_stock_decision_cache(code, date_str, data)
    return data

def analyze_stock_decision_batch(requested: dt.date, cfg: dict, progress_callback=None) -> list[dict]:
    stocks = load_stock_decision_list()
    results = []
    total = len(stocks)
    for idx, stock in enumerate(stocks, start=1):
        code = stock["code"]
        try:
            detail = build_stock_decision_detail(code, requested, cfg)
            stock["score"] = detail.get("score", 0)
            stock["strategies"] = detail.get("strategies", {})
            stock["price"] = detail.get("klines", [{}])[-1].get("close") if detail.get("klines") else None
            if detail.get("klines") and len(detail["klines"]) >= 2:
                prev_close = detail["klines"][-2]["close"]
                curr_close = detail["klines"][-1]["close"]
                if prev_close > 0:
                    stock["change"] = round((curr_close / prev_close - 1) * 100, 2)
        except Exception as exc:
            log(f"stock-decision: failed for {code}: {exc}")
            stock["error"] = str(exc)
        results.append(stock)
        if progress_callback is not None:
            progress_callback(idx, total, stock, results)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results

def _stock_decision_sorted_results(results: list[dict]) -> list[dict]:
    return sorted(results, key=lambda x: (x.get("score", 0), x.get("change") or -9999), reverse=True)

def _stock_decision_new_task_id() -> str:
    global _STOCK_DECISION_TASK_SEQ
    with _STOCK_DECISION_TASK_LOCK:
        _STOCK_DECISION_TASK_SEQ += 1
        return f"sd-{int(time.time() * 1000)}-{_STOCK_DECISION_TASK_SEQ}"

def _stock_decision_task_payload(task: dict) -> dict:
    done = int(task.get("done", 0))
    total = int(task.get("total", 0))
    percent = round((done / total) * 100, 1) if total else 0.0
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status", "pending"),
        "done": done,
        "total": total,
        "percent": percent,
        "current": task.get("current"),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
        "error": task.get("error"),
        "results": _stock_decision_sorted_results(list(task.get("results", []))),
    }

def _run_stock_decision_task(task_id: str, requested: dt.date, cfg: dict) -> None:
    with _STOCK_DECISION_TASK_LOCK:
        task = STOCK_DECISION_TASKS.get(task_id)
        if not task:
            return
        task["status"] = "running"

    def on_progress(done: int, total: int, stock: dict, results: list[dict]) -> None:
        with _STOCK_DECISION_TASK_LOCK:
            task = STOCK_DECISION_TASKS.get(task_id)
            if not task:
                return
            task["done"] = done
            task["total"] = total
            task["current"] = {"code": stock.get("code"), "name": stock.get("name")}
            task["results"] = _stock_decision_sorted_results(list(results))

    try:
        results = analyze_stock_decision_batch(requested, cfg, progress_callback=on_progress)
        with _STOCK_DECISION_TASK_LOCK:
            task = STOCK_DECISION_TASKS.get(task_id)
            if task is not None:
                task["status"] = "completed"
                task["done"] = len(results)
                task["total"] = len(results)
                task["results"] = results
                task["current"] = None
                task["finished_at"] = dt.datetime.now().isoformat()
    except Exception as exc:
        with _STOCK_DECISION_TASK_LOCK:
            task = STOCK_DECISION_TASKS.get(task_id)
            if task is not None:
                task["status"] = "failed"
                task["error"] = str(exc)
                task["finished_at"] = dt.datetime.now().isoformat()

def start_stock_decision_task(requested: dt.date, cfg: dict) -> dict:
    task_id = _stock_decision_new_task_id()
    stocks = load_stock_decision_list()
    task = {
        "task_id": task_id,
        "status": "pending",
        "done": 0,
        "total": len(stocks),
        "current": None,
        "results": [],
        "error": None,
        "started_at": dt.datetime.now().isoformat(),
        "finished_at": None,
    }
    with _STOCK_DECISION_TASK_LOCK:
        STOCK_DECISION_TASKS[task_id] = task
        stale_ids = [k for k, v in STOCK_DECISION_TASKS.items() if v.get("status") in {"completed", "failed"}]
        for stale_id in stale_ids[:-6]:
            STOCK_DECISION_TASKS.pop(stale_id, None)
    t = threading.Thread(target=_run_stock_decision_task, args=(task_id, requested, cfg), daemon=True)
    t.start()
    return _stock_decision_task_payload(task)

def get_stock_decision_task(task_id: str) -> dict | None:
    with _STOCK_DECISION_TASK_LOCK:
        task = STOCK_DECISION_TASKS.get(task_id)
        if task is None:
            return None
        return _stock_decision_task_payload(task)


class SectorScanHandler(SimpleHTTPRequestHandler):
    server_version = "SectorScan/1.0"

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory or str(BASE_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        log(fmt % args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/scan":
            self.handle_scan(parsed)
            return
        if parsed.path == "/api/chanlun/search":
            self.handle_chanlun_search(parsed)
            return
        if parsed.path == "/api/chanlun/analyze":
            self.handle_chanlun_analyze(parsed)
            return
        if parsed.path == "/api/decision/rotation":
            self.handle_decision_rotation(parsed)
            return
        if parsed.path == "/api/decision/sector":
            self.handle_decision_sector(parsed)
            return
        if parsed.path == "/api/decision/kline":
            self.handle_decision_kline(parsed)
            return
        if parsed.path == "/api/decision/stock":
            self.handle_decision_stock(parsed)
            return
        if parsed.path == "/api/review":
            self.handle_review(parsed)
            return
        if parsed.path == "/api/review/history":
            self.handle_review_history(parsed)
            return
        if parsed.path == "/api/stock-decision/list":
            self.handle_stock_decision_list(parsed)
            return
        if parsed.path == "/api/stock-decision/analyze":
            self.handle_stock_decision_analyze(parsed)
            return
        if parsed.path == "/api/stock-decision/analyze/status":
            self.handle_stock_decision_analyze_status(parsed)
            return
        if parsed.path == "/api/stock-decision/detail":
            self.handle_stock_decision_detail(parsed)
            return
        if not self.prepare_static_path(parsed.path):
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_error(405)
            return
        if not self.prepare_static_path(parsed.path):
            return
        super().do_HEAD()

    def do_OPTIONS(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.send_response(204)
            self.send_cors_headers()
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(405)

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")

    def prepare_static_path(self, raw_path: str) -> bool:
        if raw_path == "/":
            self.path = "/A股板块分析终端.html"
        elif raw_path in {"/chanlun", "/chanlun/"}:
            self.path = "/缠论/index.html"
        elif raw_path in {"/sector", "/sector/"}:
            self.path = "/A股板块分析终端.html"
        elif raw_path in {"/help", "/help/"}:
            self.path = "/help/index.html"
        elif raw_path in {"/decision", "/decision/"}:
            self.path = "/decision/index.html"
        elif raw_path in {"/review", "/review/"}:
            self.path = "/review/index.html"
        elif raw_path in {"/stock-decision", "/stock-decision/"}:
            self.path = "/stock-decision/index.html"
        if self.is_private_path(raw_path):
            self.send_error(404)
            return False
        return True

    def is_private_path(self, raw_path: str) -> bool:
        parts = [part for part in urllib.parse.unquote(raw_path).split("/") if part]
        if not parts:
            return False
        if any(part.startswith(".") for part in parts):
            return True
        return any(part in PRIVATE_NAMES for part in parts)

    def handle_scan(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        requested = parse_request_date((params.get("date") or [None])[0])
        force_refresh = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        with _scan_lock:
            try:
                data = build_scan(requested, cfg, force_refresh=force_refresh)
            except Exception as exc:
                log(f"scan fallback: {exc}")
                data = fallback_data(requested, type(exc).__name__, cfg=cfg)
        self.send_json(data)

    def handle_chanlun_search(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        q = (params.get("q") or [""])[0]
        market = (params.get("market") or ["all"])[0]
        cfg = self.server.config
        try:
            items = chanlun_search(q, market, cfg)
            data = {"items": items, "meta": {"query": q, "market": market, "count": len(items)}}
        except Exception as exc:
            log(f"chanlun search error: {exc}")
            data = {"items": [], "meta": {"query": q, "market": market, "count": 0, "error": type(exc).__name__}}
        self.send_json(data)

    def handle_chanlun_analyze(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        symbol = (params.get("symbol") or ["600519"])[0]
        period = (params.get("period") or ["day"])[0]
        requested = parse_request_date((params.get("date") or [None])[0])
        force_refresh = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        with _scan_lock:
            try:
                data = build_chanlun_analysis(symbol, period, requested, cfg, force_refresh=force_refresh)
            except Exception as exc:
                log(f"chanlun analysis error: {exc}")
                data = {
                    "meta": {
                        "requestedDate": requested.isoformat(),
                        "period": period,
                        "dataStatus": "error",
                        "aiStatus": "fallback",
                        "error": type(exc).__name__,
                        "message": str(exc)[:240],
                    },
                    "stock": chanlun_stock_item(symbol),
                    "bars": [],
                    "analysis": {
                        "merged": [],
                        "fractals": [],
                        "pts": [],
                        "segs": [],
                        "pivots": [],
                        "macd": {"dif": [], "dea": [], "hist": []},
                        "divergence": None,
                        "signals": [],
                        "trend": {"kind": "range", "text": "不可分析", "detail": "数据源暂不可用"},
                        "stats": {"tops": 0, "bottoms": 0, "strokes": 0, "segments": 0, "pivots": 0},
                    },
                    "verdict": {
                        "headline": "暂时无法完成缠论分析。",
                        "body": "行情数据源暂不可用或K线样本不足,请稍后重试或切换标的。",
                        "risk": "本页仅供学习研究和复盘参考,不构成投资建议。",
                        "metas": [],
                    },
                    "ai": {"status": "fallback"},
                }
        self.send_json(data)

    def handle_decision_rotation(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        requested = parse_request_date((params.get("date") or [None])[0])
        force_refresh = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        with _scan_lock:
            try:
                data = build_decision_rotation(requested, cfg, force_refresh=force_refresh)
            except Exception as exc:
                log(f"decision rotation error: {exc}")
                data = {"meta": {"error": type(exc).__name__, "message": str(exc)[:240]}, "sectors": [], "abstained": []}
        self.send_json(data)

    def handle_decision_sector(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        name = (params.get("name") or [""])[0]
        requested = parse_request_date((params.get("date") or [None])[0])
        force_refresh = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        if not name:
            self.send_json({"meta": {"error": "missing name parameter"}, "sectors": []})
            return
        try:
            data = build_decision_sector(name, requested, cfg, force_refresh=force_refresh)
        except Exception as exc:
            log(f"decision sector error: {name}: {exc}")
            data = {"meta": {"error": type(exc).__name__, "message": str(exc)[:240]}, "name": name, "tier": "NO_SIGNAL", "gates": [f"ERROR:{type(exc).__name__}"]}
        self.send_json(data)

    def handle_decision_stock(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        symbol = (params.get("symbol") or [""])[0]
        requested = parse_request_date((params.get("date") or [None])[0])
        force_refresh = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        if not symbol:
            self.send_json({"meta": {"error": "missing symbol parameter"}})
            return
        try:
            data = build_decision_stock(symbol, requested, cfg, force_refresh=force_refresh)
        except Exception as exc:
            log(f"decision stock error: {symbol}: {exc}")
            data = {"meta": {"error": type(exc).__name__, "message": str(exc)[:240]}, "symbol": symbol, "tier": "NO_SIGNAL", "gates": [f"ERROR:{type(exc).__name__}"]}
        self.send_json(data)


    def handle_decision_kline(self, parsed):
        """Return raw OHLCV bars (≤260 days) for a sector or stock."""
        import datetime as _dt
        params = dict(urllib.parse.parse_qsl(parsed.query or ""))
        kind   = params.get("type", "sector")   # "sector" | "stock"
        name   = params.get("name") or params.get("symbol", "")
        date_s = params.get("date") or str(_dt.date.today())
        if not name:
            self.send_json({"bars": [], "error": "name required"}, code=400)
            return
        try:
            target = _dt.date.fromisoformat(date_s)
        except Exception:
            target = _dt.date.today()
        start = target - _dt.timedelta(days=400)
        cfg = self.server.config
        try:
            if kind == "stock":
                sym = name if re.match(r'^(sh|sz)', name) else \
                      (('sh' if name.startswith(('5', '6', '9')) else 'sz') + name) \
                      if re.match(r'^\d{6}$', name) else name
                raw = westock_kline(sym, cfg, limit=300) or []
                rows = rows_until(raw, target)
            else:
                rows = _fetch_sector_hist_for_decision(name, start, target, cfg, limit=300)
            bars = hist_rows_to_bars(rows[-260:])
            self.send_json({"bars": bars, "name": name, "count": len(bars)})
        except Exception as exc:
            log(f"decision kline error [{name}]: {exc}")
            self.send_json({"bars": [], "name": name, "error": str(exc)}, code=500)

    def handle_review(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        date_param = (params.get("date") or [None])[0]
        force = str((params.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
        cfg = self.server.config
        try:
            with _review_lock:
                data = build_market_review(cfg, force=force, date_str=date_param)
            self.send_json(data)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, code=400)
        except Exception as exc:
            log(f"review error: {exc}")
            self.send_json({"error": str(exc)}, code=500)

    def handle_review_history(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        limit = int((params.get("limit") or ["14"])[0])
        try:
            history = list_review_history(limit)
            self.send_json({"history": history})
        except Exception as exc:
            self.send_json({"error": str(exc)}, code=500)

    def handle_stock_decision_list(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            stocks = load_stock_decision_list()
            self.send_json({"stocks": stocks})
        except Exception as exc:
            self.send_json({"error": str(exc)}, code=500)

    def handle_stock_decision_analyze(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        date_str = (params.get("date") or [None])[0]
        requested = parse_request_date(date_str)
        try:
            task = start_stock_decision_task(requested, self.server.config)
            self.send_json(task)
        except Exception as exc:
            self.send_json({"error": str(exc)}, code=500)

    def handle_stock_decision_analyze_status(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        task_id = (params.get("task_id") or [""])[0].strip()
        if not task_id:
            self.send_json({"error": "Missing task_id"}, code=400)
            return
        task = get_stock_decision_task(task_id)
        if task is None:
            self.send_json({"error": "Task not found"}, code=404)
            return
        self.send_json(task)

    def handle_stock_decision_detail(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        code = (params.get("code") or [None])[0]
        date_str = (params.get("date") or [None])[0]
        if not code:
            self.send_json({"error": "Missing stock code"}, code=400)
            return
        requested = parse_request_date(date_str)
        try:
            detail = build_stock_decision_detail(code, requested, self.server.config)
            self.send_json(detail)
        except Exception as exc:
            self.send_json({"error": str(exc)}, code=500)

    def send_json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str, port: int) -> None:
    cfg = load_config()
    patch_requests_timeout(int(cfg.get("market", {}).get("http_timeout_seconds", 10)))
    server = ThreadingHTTPServer((host, port), lambda *args, **kwargs: SectorScanHandler(*args, directory=str(BASE_DIR), **kwargs))
    server.config = cfg
    log(f"serving http://{host}:{port}/A股板块分析终端.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="A股板块扫描本地服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
