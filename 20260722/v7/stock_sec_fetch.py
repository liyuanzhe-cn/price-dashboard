#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEC基本面增量抓取器（配合 stock500_fetch.py / stock.html）

特点：
  - 每次只处理一个公司事实JSON，常驻内存很小；
  - 默认每次处理100家公司，完成后原子写入缓存，可反复运行续传；
  - 默认约2次/秒，远低于SEC公开的10次/秒上限；
  - 不保存庞大的原始companyfacts，只保存计算后的精简结果；
  - 外国公司、ETF、银行或XBRL标签不足时保留null，不伪造数据。

首次测试：
  SEC_USER_AGENT="PriceDashboard liyuanzhe0@gmail.com" \
    python3 stock_sec_fetch.py --batch-size 10

继续下一批：
  SEC_USER_AGENT="PriceDashboard liyuanzhe0@gmail.com" \
    python3 stock_sec_fetch.py --batch-size 100

每周全量刷新：
  SEC_USER_AGENT="PriceDashboard liyuanzhe0@gmail.com" \
    nohup python3 stock_sec_fetch.py --refresh --all > stock_sec_fetch.log 2>&1 &
"""

import argparse
import gzip
import json
import math
import os
import random
import time
import zlib
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_CACHE_PATH = os.path.join(SCRIPT_DIR, "cache_stock.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "cache_sec_fundamentals.json")
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
REQUEST_DELAY = (0.45, 0.65)
TIMEOUT = 30
SAVE_EVERY = 10

HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json",
}

TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
        "SalesRevenueNet", "SalesRevenueGoodsNet",
    ],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ],
    "sbc": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    "diluted_shares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation": [
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    ],
    "interest_expense": ["InterestExpenseNonOperating", "InterestExpense"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_term_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
    "debt": ["LongTermDebtAndFinanceLeaseObligationsCurrent", "ShortTermBorrowings"],
    "long_term_debt": [
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtNoncurrent",
    ],
}


def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def atomic_json_dump(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as exc:
        log(f"读取{os.path.basename(path)}失败：{exc}")
        return default


def get_json(url, retries=4):
    for attempt in range(retries):
        try:
            request = Request(url, headers=HEADERS)
            with urlopen(request, timeout=TIMEOUT) as response:
                body = response.read()
                encoding = response.headers.get("Content-Encoding", "").lower()
                if encoding == "gzip":
                    body = gzip.decompress(body)
                elif encoding == "deflate":
                    body = zlib.decompress(body)
                return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code not in (403, 429) and exc.code < 500:
                raise
            if attempt == retries - 1:
                raise
            wait = min(60, 3 * (2 ** attempt)) + random.random()
            log(f"HTTP {exc.code}，{wait:.1f}秒后重试")
            time.sleep(wait)
        except (URLError, TimeoutError, ValueError) as exc:
            if attempt == retries - 1:
                raise
            wait = min(30, 2 * (2 ** attempt)) + random.random()
            log(f"请求失败：{exc}；{wait:.1f}秒后重试")
            time.sleep(wait)
    return None


def normalize_symbol(symbol):
    return (symbol or "").upper().replace("/", ".").replace("-", ".")


def build_cik_map(payload):
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    positions = {name: i for i, name in enumerate(fields)}
    result = {}
    for row in rows:
        try:
            ticker = normalize_symbol(row[positions["ticker"]])
            cik = str(row[positions["cik"]]).zfill(10)
            exchange = row[positions["exchange"]] if "exchange" in positions else None
            if ticker:
                result[ticker] = {"cik": cik, "exchange": exchange}
        except (KeyError, IndexError, TypeError):
            continue
    return result


def fact_units(companyfacts, tag, unit):
    fact = ((companyfacts.get("facts") or {}).get("us-gaap") or {}).get(tag) or {}
    units = fact.get("units") or {}
    if unit in units:
        return units[unit]
    if unit == "USD":
        for key, values in units.items():
            if key.startswith("USD"):
                return values
    if unit == "shares":
        for key, values in units.items():
            if "shares" in key.lower():
                return values
    return []


def annual_series(companyfacts, tag_names, unit="USD"):
    """返回{财年: 值}。只选10-K/20-F/40-F且约一年期间的最新申报。"""
    for tag in tag_names:
        candidates = {}
        for item in fact_units(companyfacts, tag, unit):
            form = item.get("form")
            start, end = item.get("start"), item.get("end")
            if form not in ("10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"):
                continue
            if not start or not end:
                continue
            try:
                days = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                period_year = int(end[:4])
                value = float(item["val"])
            except (ValueError, TypeError, KeyError):
                continue
            if not 250 <= days <= 450 or not math.isfinite(value):
                continue
            old = candidates.get(period_year)
            if old is None or (item.get("filed") or "") > old[0]:
                candidates[period_year] = (item.get("filed") or "", value, end)
        if len(candidates) >= 1:
            return {year: {"value": row[1], "end": row[2]} for year, row in candidates.items()}
    return {}


def latest_instant(companyfacts, tag_names, unit="USD"):
    for tag in tag_names:
        rows = []
        for item in fact_units(companyfacts, tag, unit):
            if item.get("form") not in (
                "10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"
            ):
                continue
            try:
                value = float(item["val"])
            except (ValueError, TypeError, KeyError):
                continue
            if math.isfinite(value) and item.get("end"):
                rows.append((item["end"], item.get("filed") or "", value))
        if rows:
            rows.sort()
            return {"value": rows[-1][2], "end": rows[-1][0]}
    return None


def latest_common_year(*series):
    common = set(series[0]) if series else set()
    for values in series[1:]:
        common &= set(values)
    return max(common) if common else None


def percent(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator * 100
    return round(value, 4) if math.isfinite(value) else None


def ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator
    return round(value, 4) if math.isfinite(value) else None


def cagr(latest, earliest, years):
    if latest is None or earliest is None or latest <= 0 or earliest <= 0 or years <= 0:
        return None
    return round(((latest / earliest) ** (1 / years) - 1) * 100, 4)


def calculate_metrics(companyfacts, market_cap, cik, exchange):
    revenue = annual_series(companyfacts, TAGS["revenue"])
    ocf = annual_series(companyfacts, TAGS["operating_cash_flow"])
    capex = annual_series(companyfacts, TAGS["capex"])
    shares = annual_series(companyfacts, TAGS["diluted_shares"], "shares")
    sbc = annual_series(companyfacts, TAGS["sbc"])
    operating_income = annual_series(companyfacts, TAGS["operating_income"])
    depreciation = annual_series(companyfacts, TAGS["depreciation"])
    interest = annual_series(companyfacts, TAGS["interest_expense"])

    fcf = {}
    for year in set(ocf) & set(capex):
        fcf[year] = {
            "value": ocf[year]["value"] - abs(capex[year]["value"]),
            "end": max(ocf[year]["end"], capex[year]["end"]),
        }

    latest_year = latest_common_year(revenue, fcf)
    as_of = revenue[latest_year]["end"] if latest_year is not None else None
    revenue_cagr = None
    if revenue:
        newest = max(revenue)
        if newest - 3 in revenue:
            revenue_cagr = cagr(revenue[newest]["value"], revenue[newest - 3]["value"], 3)

    fcf_per_share = {}
    for year in set(fcf) & set(shares):
        if shares[year]["value"]:
            fcf_per_share[year] = fcf[year]["value"] / shares[year]["value"]
    fcf_ps_cagr = None
    if fcf_per_share:
        newest = max(fcf_per_share)
        if newest - 3 in fcf_per_share:
            fcf_ps_cagr = cagr(fcf_per_share[newest], fcf_per_share[newest - 3], 3)

    diluted_cagr = None
    if shares:
        newest = max(shares)
        if newest - 3 in shares:
            diluted_cagr = cagr(shares[newest]["value"], shares[newest - 3]["value"], 3)

    cash = latest_instant(companyfacts, TAGS["cash"])
    investments = latest_instant(companyfacts, TAGS["short_term_investments"])
    debt_current = latest_instant(companyfacts, TAGS["debt"])
    debt_long = latest_instant(companyfacts, TAGS["long_term_debt"])
    cash_total = (cash or {}).get("value", 0) + (investments or {}).get("value", 0)
    debt_total = (debt_current or {}).get("value", 0) + (debt_long or {}).get("value", 0)
    net_debt = debt_total - cash_total

    ebitda_year = latest_common_year(operating_income, depreciation)
    ebitda = None
    if ebitda_year is not None:
        ebitda = operating_income[ebitda_year]["value"] + abs(depreciation[ebitda_year]["value"])
    interest_year = latest_common_year(operating_income, interest)

    result = {
        "cik": cik,
        "exchange": exchange,
        "sec_filer": True,
        "revenue_cagr_3y_pct": revenue_cagr,
        "fcf_margin_ttm_pct": percent(fcf[latest_year]["value"], revenue[latest_year]["value"]) if latest_year is not None else None,
        "fcf_per_share_ttm": round(fcf_per_share[latest_year], 4) if latest_year in fcf_per_share else None,
        "fcf_per_share_cagr_3y_pct": fcf_ps_cagr,
        "sbc_to_revenue_pct": percent(sbc[latest_year]["value"], revenue[latest_year]["value"]) if latest_year in sbc and latest_year in revenue else None,
        "diluted_shares_cagr_3y_pct": diluted_cagr,
        "net_debt_to_ebitda": ratio(net_debt, ebitda),
        "interest_coverage": ratio(
            operating_income[interest_year]["value"], abs(interest[interest_year]["value"])
        ) if interest_year is not None else None,
        "capex_to_revenue_pct": percent(abs(capex[latest_year]["value"]), revenue[latest_year]["value"]) if latest_year in capex and latest_year in revenue else None,
        "fcf_yield_pct": percent(fcf[latest_year]["value"], market_cap) if latest_year is not None else None,
        "source": "SEC companyfacts",
        "as_of": as_of,
        # 第一版采用最近完整财年，字段名暂时兼容前端的TTM命名；此字段明确真实口径。
        "period_type": "FY",
        "currency": "USD",
    }
    return result


def save_output(results, started_at):
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "refresh_started_at": started_at,
        "source": "SEC companyfacts",
        "period_type": "FY",
        "count": len(results),
        "stocks": results,
    }
    atomic_json_dump(OUTPUT_PATH, payload)


def main():
    parser = argparse.ArgumentParser(description="增量抓取SEC基本面")
    parser.add_argument("--batch-size", type=int, default=100, help="本次最多处理多少家公司，默认100")
    parser.add_argument("--all", action="store_true", help="本次处理全部尚未完成的公司")
    parser.add_argument("--refresh", action="store_true", help="清空旧SEC结果，开始新一轮全量刷新")
    args = parser.parse_args()

    if "@" not in SEC_USER_AGENT or len(SEC_USER_AGENT.split()) < 2:
        raise SystemExit("SEC_USER_AGENT必须包含程序名和真实联系邮箱")
    stock_payload = load_json(STOCK_CACHE_PATH, {})
    stocks = stock_payload.get("stocks") or []
    if not stocks:
        raise SystemExit(f"找不到股票数据：{STOCK_CACHE_PATH}")

    old = {} if args.refresh else load_json(OUTPUT_PATH, {}).get("stocks", {})
    results = old if isinstance(old, dict) else {}
    started_at = datetime.now(timezone.utc).isoformat()

    log("下载SEC ticker/CIK映射")
    ticker_payload = get_json(TICKER_MAP_URL)
    if not ticker_payload:
        raise SystemExit("无法取得SEC ticker/CIK映射")
    cik_map = build_cik_map(ticker_payload)

    pending = [s for s in stocks if normalize_symbol(s.get("symbol")) not in results]
    if not args.all:
        pending = pending[:max(0, args.batch_size)]
    log(f"股票总数{len(stocks)}，已有{len(results)}，本次处理{len(pending)}")

    for index, stock in enumerate(pending, 1):
        symbol = normalize_symbol(stock.get("symbol"))
        mapping = cik_map.get(symbol)
        if not mapping:
            results[symbol] = {
                "cik": None, "sec_filer": False, "source": "SEC ticker map",
                "as_of": None, "period_type": None, "currency": None,
            }
            log(f"[{index}/{len(pending)}] {symbol}：无SEC CIK")
        else:
            cik = mapping["cik"]
            try:
                facts = get_json(COMPANY_FACTS_URL.format(cik=cik))
                if facts:
                    results[symbol] = calculate_metrics(
                        facts, stock.get("market_cap"), cik, mapping.get("exchange")
                    )
                    log(f"[{index}/{len(pending)}] {symbol}：完成")
                else:
                    results[symbol] = {
                        "cik": cik, "sec_filer": True, "source": "SEC companyfacts",
                        "as_of": None, "period_type": None, "currency": "USD",
                        "error": "companyfacts_not_found",
                    }
                    log(f"[{index}/{len(pending)}] {symbol}：无companyfacts")
            except Exception as exc:
                log(f"[{index}/{len(pending)}] {symbol}：失败，留待下次重试：{exc}")
                time.sleep(5 + random.random())
                continue
            time.sleep(random.uniform(*REQUEST_DELAY))

        if index % SAVE_EVERY == 0:
            save_output(results, started_at)

    save_output(results, started_at)
    log(f"已写入{OUTPUT_PATH}，累计{len(results)}家公司")


if __name__ == "__main__":
    main()
