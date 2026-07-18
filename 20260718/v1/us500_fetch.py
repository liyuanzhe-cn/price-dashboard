#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
美股Top 500基本面数据抓取脚本 (us500_fetch.py)
================================================
这是一个完全独立于dashboard主程序(server.py)的脚本,不共用进程/内存,通过cron
定时触发,跑完就退出,不常驻。这样即使这个脚本本身出问题(比如卡住、被限流),
也不会影响到现有实时看板的正常运行。

用法:
    python3 us500_fetch.py            # 跑全量500只
    python3 us500_fetch.py --limit 20 # 只跑前20只,用于第一次测试观察实际情况

建议第一次先用 --limit 20 跑一遍,确认没有异常报错、观察实际耗时,再放进cron里
跑全量。

数据来源:
  - 500只股票的名单+市值+现价:stockanalysis.com/list/biggest-companies/
    (这个页面本身是服务器端渲染的,一次请求就能拿到全部500行,不需要翻页抓取)
  - 市盈率/市净率/市销率/Beta/自由现金流/ROE/股份数/负债权益比:雅虎财经
    (通过yfinance库的.info属性,这是比较"重"的接口)
  - 历史最高价(ATH):雅虎财经的历史K线接口

【这次设计的核心降险思路,回应"不能接受被限流/封IP风险"这个前提】
1. ATH计算利用"历史最高价只会创新高、不会消失"这个特性:每个ticker只在
   第一次(本地缓存里完全没有这个ticker的记录时)才去下载全部历史月K线做一次性
   建档,这是最贵的操作。建档完成后,以后每天只需要用一个很轻的"最近5天K线"接口
   去核对"最近有没有创新高",而不是每天都重新拉一遍全部历史——这一项把最耗资源
   的部分从"500次重活"降到了"只在第一次真正发生",之后是几乎零成本的日常校验。
2. 500个ticker之间插入5-10秒随机间隔,不是紧凑连续请求,整个跑一轮大概
   1-1.5小时,访问节奏更接近正常人使用,而不是短时间内的批量轰炸。
3. 熔断机制:连续失败达到一定次数(疑似被限流),自动暂停较长时间冷却后再继续,
   而不是不断重试导致情况更糟。
4. 每个ticker的抓取都包在try/except里,单个失败不会导致整个脚本中断,失败的
   字段会是null,不会用假数据填充。

依赖:
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

import argparse
import json
import os
import random
import re
import sys
import time
import traceback

import requests

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("请先: pip install --break-system-packages yfinance requests beautifulsoup4")

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("请先: pip install --break-system-packages beautifulsoup4")


# ------------------------------------------------------------------
# 配置区
# ------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON_PATH = os.path.join(SCRIPT_DIR, "us500_data.json")
ATH_CACHE_PATH = os.path.join(SCRIPT_DIR, "us500_ath_cache.json")

STOCKANALYSIS_LIST_URL = "https://stockanalysis.com/list/biggest-companies/"

# 每个ticker之间的随机间隔(秒),这是最主要的降险手段之一,不要调得太小
PER_TICKER_DELAY_RANGE = (5, 10)

# 熔断:连续失败这么多次以后,判断可能被限流,暂停较长时间再继续
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN_SEC = 10 * 60  # 冷却10分钟

REQUEST_TIMEOUT_SEC = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------
# 第一步:抓500只股票的名单(名字/市值/现价/涨跌幅/营收)
# ------------------------------------------------------------------

def fetch_top500_list():
    """从stockanalysis.com/list/biggest-companies/抓完整的500行列表。
    这个页面实测是服务器端渲染的,一次请求就能拿到全部内容,不需要翻页。
    表格列:Rank / Symbol / Company Name / Market Cap / Stock Price / % Change / Revenue"""
    r = requests.get(STOCKANALYSIS_LIST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEC)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    rows_out = []
    table = soup.find("table")
    if table is None:
        raise RuntimeError("没有在页面里找到<table>标签,页面结构可能变了,需要重新核对")

    for tr in table.find_all("tr"):
        cells = tr.find_all(["td"])
        if len(cells) < 7:
            continue  # 跳过表头行或者不完整的行
        try:
            rank = int(cells[0].get_text(strip=True))
            symbol = cells[1].get_text(strip=True)
            name = cells[2].get_text(strip=True)
            market_cap_text = cells[3].get_text(strip=True)
            price_text = cells[4].get_text(strip=True)
            change_text = cells[5].get_text(strip=True)
            revenue_text = cells[6].get_text(strip=True)
        except Exception:
            continue
        rows_out.append({
            "rank": rank,
            "symbol": symbol,
            "name": name,
            "market_cap_text": market_cap_text,
            "price_text": price_text,
            "change_text": change_text,
            "revenue_text": revenue_text,
        })

    if len(rows_out) < 100:
        raise RuntimeError(f"只解析到{len(rows_out)}行,明显不对(应该有500行左右),"
                            f"页面结构可能变了,需要重新核对,不继续往下跑")
    return rows_out


def _parse_money_text(s):
    """把'4.912T' '271.23B' '86.99'这类字符串转成float(美元数值)"""
    if not s or s == "-":
        return None
    m = re.match(r'^-?[\d,.]+', s)
    if not m:
        return None
    try:
        num = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    unit = s[len(m.group(0)):].strip().upper()
    mult = {"T": 1e12, "B": 1e9, "M": 1e6, "K": 1e3, "": 1}.get(unit, 1)
    return num * mult


def _parse_pct_text(s):
    if not s or s == "-":
        return None
    try:
        return float(s.replace("%", "").replace(",", ""))
    except ValueError:
        return None


# ------------------------------------------------------------------
# 第二步:ATH缓存的读写(核心降险机制)
# ------------------------------------------------------------------

def load_ath_cache():
    if not os.path.exists(ATH_CACHE_PATH):
        return {}
    try:
        with open(ATH_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log(f"读取ATH缓存失败,当成空缓存处理: {e}")
        return {}


def save_ath_cache(cache):
    tmp_path = ATH_CACHE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp_path, ATH_CACHE_PATH)


def get_or_update_ath(ticker, ath_cache):
    """核心降险逻辑:
    - 如果这个ticker在缓存里已经有记录,只拉最近5天的K线(很轻),
      看看最近有没有创新高,有就更新缓存,没有就直接用缓存里的旧值。
    - 如果缓存里完全没有这个ticker,才去做一次性的全历史下载建档
      (这是唯一"贵"的操作,而且每个ticker一辈子只做这一次)。
    返回 {"high": float, "date": "YYYY-MM"} 或者 None(彻底失败)。
    """
    cached = ath_cache.get(ticker)
    try:
        if cached is None:
            # 首次建档:唯一的"重"操作,用月线控制数据量
            hist = yf.Ticker(ticker).history(period="max", interval="1mo")
            if hist is None or hist.empty:
                return None
            idx = hist["High"].idxmax()
            result = {"high": float(hist.loc[idx, "High"]), "date": idx.strftime("%Y-%m")}
            ath_cache[ticker] = result
            return result
        else:
            # 已经建过档:只用很轻的"最近5天"去校验有没有创新高
            hist = yf.Ticker(ticker).history(period="5d", interval="1d")
            if hist is not None and not hist.empty:
                recent_high = float(hist["High"].max())
                if recent_high > cached["high"]:
                    recent_idx = hist["High"].idxmax()
                    result = {"high": recent_high, "date": recent_idx.strftime("%Y-%m")}
                    ath_cache[ticker] = result
                    return result
            return cached
    except Exception as e:
        _log(f"  ATH处理失败({ticker}): {e}")
        return cached  # 失败就沿用旧缓存(如果有的话),不是直接丢失历史记录


# ------------------------------------------------------------------
# 第三步:单只股票的基本面数据(雅虎财经.info)
# ------------------------------------------------------------------

def fetch_fundamentals(ticker):
    """P/E、P/B、P/S、Beta、自由现金流、ROE、股份数、负债权益比。
    这几个字段yfinance的.info字典里名字分别是:
    trailingPE, priceToBook, priceToSalesTrailing12Months, beta, freeCashflow,
    returnOnEquity, sharesOutstanding, debtToEquity。
    某个字段没有就是None,不强行凑数。"""
    out = {
        "pe_ratio": None, "pb_ratio": None, "ps_ratio": None, "beta": None,
        "free_cash_flow": None, "roe": None, "shares_outstanding": None, "debt_to_equity": None,
    }
    try:
        info = yf.Ticker(ticker).info
        out["pe_ratio"] = info.get("trailingPE")
        out["pb_ratio"] = info.get("priceToBook")
        out["ps_ratio"] = info.get("priceToSalesTrailing12Months")
        out["beta"] = info.get("beta")
        out["free_cash_flow"] = info.get("freeCashflow")
        out["roe"] = info.get("returnOnEquity")
        out["shares_outstanding"] = info.get("sharesOutstanding")
        out["debt_to_equity"] = info.get("debtToEquity")
    except Exception as e:
        _log(f"  基本面抓取失败: {e}")
    return out


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="美股Top 500基本面数据抓取")
    parser.add_argument("--limit", type=int, default=None,
                        help="只处理前N只(用于第一次测试,建议先用--limit 20跑一遍)")
    args = parser.parse_args()

    _log("开始抓取500强股票名单...")
    try:
        rows = fetch_top500_list()
    except Exception as e:
        _log(f"抓取股票名单失败,整个脚本终止: {e}")
        traceback.print_exc()
        sys.exit(1)
    _log(f"拿到{len(rows)}行数据")

    if args.limit:
        rows = rows[:args.limit]
        _log(f"--limit参数生效,只处理前{len(rows)}只(测试模式)")

    ath_cache = load_ath_cache()
    results = []
    consecutive_failures = 0

    for i, row in enumerate(rows):
        ticker = row["symbol"]
        _log(f"[{i+1}/{len(rows)}] 处理 {ticker} ({row['name']})...")

        row_failed = False
        try:
            fundamentals = fetch_fundamentals(ticker)
            ath_info = get_or_update_ath(ticker, ath_cache)

            market_cap = _parse_money_text(row["market_cap_text"])
            price = _parse_money_text(row["price_text"])  # 现价本身没有单位后缀,这个函数同样适用
            change_pct = _parse_pct_text(row["change_text"])
            revenue = _parse_money_text(row["revenue_text"])

            ath_dd_pct = None
            if price is not None and ath_info and ath_info.get("high"):
                ath_dd_pct = (price / ath_info["high"] - 1) * 100

            results.append({
                "rank": row["rank"],
                "symbol": ticker,
                "name": row["name"],
                "market_cap": market_cap,
                "price": price,
                "change_pct": change_pct,
                "revenue": revenue,
                "ath": ath_info.get("high") if ath_info else None,
                "ath_date": ath_info.get("date") if ath_info else None,
                "ath_drawdown_pct": ath_dd_pct,
                **fundamentals,
            })

            if fundamentals.get("pe_ratio") is None and ath_info is None:
                row_failed = True  # 两个关键部分都没拿到,算作这一轮失败,用于熔断判断
        except Exception as e:
            _log(f"  处理{ticker}整体失败: {e}")
            row_failed = True
            results.append({
                "rank": row["rank"], "symbol": ticker, "name": row["name"],
                "market_cap": None, "price": None, "change_pct": None, "revenue": None,
                "ath": None, "ath_date": None, "ath_drawdown_pct": None,
                "pe_ratio": None, "pb_ratio": None, "ps_ratio": None, "beta": None,
                "free_cash_flow": None, "roe": None, "shares_outstanding": None, "debt_to_equity": None,
            })

        if row_failed:
            consecutive_failures += 1
        else:
            consecutive_failures = 0

        if consecutive_failures >= CIRCUIT_BREAKER_FAILURE_THRESHOLD:
            _log(f"连续{consecutive_failures}次失败,疑似被限流,暂停{CIRCUIT_BREAKER_COOLDOWN_SEC}秒冷却...")
            time.sleep(CIRCUIT_BREAKER_COOLDOWN_SEC)
            consecutive_failures = 0

        # 定期把已经算好的ATH缓存落盘,不用等全部跑完才存,防止脚本中途被打断丢失进度
        if (i + 1) % 20 == 0:
            save_ath_cache(ath_cache)

        if i < len(rows) - 1:
            time.sleep(random.uniform(*PER_TICKER_DELAY_RANGE))

    save_ath_cache(ath_cache)

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(results),
        "stocks": results,
    }
    tmp_path = OUTPUT_JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    os.replace(tmp_path, OUTPUT_JSON_PATH)
    _log(f"全部完成,写入 {OUTPUT_JSON_PATH},共{len(results)}条")


if __name__ == "__main__":
    main()
