#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import copy
import datetime as dt
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
    {"code": "600519", "symbol": "sh600519", "name": "贵州茅台", "market": "A股", "unit": "¥"},
    {"code": "300750", "symbol": "sz300750", "name": "宁德时代", "market": "A股", "unit": "¥"},
    {"code": "601318", "symbol": "sh601318", "name": "中国平安", "market": "A股", "unit": "¥"},
    {"code": "600036", "symbol": "sh600036", "name": "招商银行", "market": "A股", "unit": "¥"},
    {"code": "002594", "symbol": "sz002594", "name": "比亚迪", "market": "A股", "unit": "¥"},
    {"code": "688981", "symbol": "sh688981", "name": "中芯国际", "market": "A股", "unit": "¥"},
    {"code": "00700", "symbol": "hk00700", "name": "腾讯控股", "market": "港股", "unit": "HK$"},
    {"code": "09988", "symbol": "hk09988", "name": "阿里巴巴", "market": "港股", "unit": "HK$"},
    {"code": "03690", "symbol": "hk03690", "name": "美团", "market": "港股", "unit": "HK$"},
    {"code": "01810", "symbol": "hk01810", "name": "小米集团", "market": "港股", "unit": "HK$"},
    {"code": "000001.SH", "symbol": "sh000001", "name": "上证指数", "market": "指数", "unit": "点"},
    {"code": "399001.SZ", "symbol": "sz399001", "name": "深证成指", "market": "指数", "unit": "点"},
    {"code": "399006.SZ", "symbol": "sz399006", "name": "创业板指", "market": "指数", "unit": "点"},
    {"code": "000300.SH", "symbol": "sh000300", "name": "沪深300", "market": "指数", "unit": "点"},
    {"code": "000688.SH", "symbol": "sh000688", "name": "科创50", "market": "指数", "unit": "点"},
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
    low = text.lower().replace(".", "")
    if re.fullmatch(r"(sh|sz|hk)\w+", low):
        return low
    upper = text.upper()
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
        return filter_chanlun_market(defaults, market)[:20]

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
    return filter_chanlun_market(matched, market)[:30]


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

    def send_json(self, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
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
