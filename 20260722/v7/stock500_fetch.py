#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票1500强基本面数据抓取脚本 (stock500_fetch.py) — v3
================================================
v2:新增股息(dividend_rate/dividend_yield_pct,来自雅虎财经.info)和IPO三项
(ipo_date/ipo_price/ipo_cagr_pct)。IPO日期/价格是复用首次建档ATH时已经下载好的
"全历史月线"第一条记录近似算出来的,只精确到月,不是真实挂牌当天数据;年化涨幅
按实际经过年数做几何平均,不足半年的不计算。注意:v2之前就已经建过档的老ticker,
ipo_date/ipo_price会是null,除非删除stock500_ath_cache.json强制重新全量建档
(见get_or_update_ath函数里的详细说明,这是一次成本较高的操作,不建议轻易做)。

之前叫"美股500强",改成"股票500强"更准确——名单里其实混了台积电(TSM)、ASML这类
在美股交易所挂牌但注册地不在美国的公司,不是严格意义上的"美股"。

这是一个完全独立于dashboard主程序(server.py)的脚本,不共用进程/内存,通过cron
定时触发,跑完就退出,不常驻。这样即使这个脚本本身出问题(比如卡住、被限流),
也不会影响到现有实时看板的正常运行。

用法:
    python3 stock500_fetch.py            # 跑全量1500只
    python3 stock500_fetch.py --limit 20 # 只跑前20只,用于第一次测试观察实际情况

建议第一次先用 --limit 20 跑一遍,确认没有异常报错、观察实际耗时,再放进cron里
跑全量。

数据来源:
  - 1500只股票的名单+市值+现价:Nasdaq公开股票筛选接口，一次批量获取后按市值排序
  - 市盈率/市净率/市销率/Beta/自由现金流/ROE/股份数/负债权益比:雅虎财经
    (通过yfinance库的.info属性,这是比较"重"的接口)
  - 历史最高价(ATH):雅虎财经的历史K线接口

【这次设计的核心降险思路,回应"不能接受被限流/封IP风险"这个前提】
1. ATH计算利用"历史最高价只会创新高、不会消失"这个特性:每个ticker只在
   第一次(本地缓存里完全没有这个ticker的记录时)才去下载全部历史月K线做一次性
   建档,这是最贵的操作。建档完成后,以后每天只需要用一个很轻的"最近5天K线"接口
   去核对"最近有没有创新高",而不是每天都重新拉一遍全部历史——这一项把最耗资源
   的部分从"500次重活"降到了"只在第一次真正发生",之后是几乎零成本的日常校验。
2. 1500个ticker之间插入0.5-2秒随机间隔；连续失败时仍会自动熔断冷却。
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
from datetime import datetime

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
OUTPUT_JSON_PATH = os.path.join(SCRIPT_DIR, "cache_stock.json")
ATH_CACHE_PATH = os.path.join(SCRIPT_DIR, "stock500_ath_cache.json")

TARGET_STOCK_COUNT = 1500
NASDAQ_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks"

# 每个ticker之间随机等待0.5-2秒；仍保留连续失败熔断，遇到限流会自动冷却10分钟。
PER_TICKER_DELAY_RANGE = (0.5, 2)

# 熔断:连续失败这么多次以后,判断可能被限流,暂停较长时间再继续
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN_SEC = 10 * 60  # 冷却10分钟

REQUEST_TIMEOUT_SEC = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# 常见中文名人工表。没有把握时保留英文全称；股票代码永远独立保存，不参与翻译。
CHINESE_NAMES = {
    "AAPL":"苹果", "MSFT":"微软", "GOOG":"谷歌C类", "GOOGL":"谷歌A类", "AMZN":"亚马逊",
    "META":"Meta平台", "NVDA":"英伟达", "TSLA":"特斯拉", "BRK.B":"伯克希尔·哈撒韦B类",
    "BRK/B":"伯克希尔·哈撒韦B类", "BRK/A":"伯克希尔·哈撒韦A类",
    "AVGO":"博通", "ORCL":"甲骨文", "CRM":"赛富时", "SAP":"思爱普", "NOW":"ServiceNow",
    "IBM":"国际商业机器", "MU":"美光科技", "AMD":"超威半导体", "INTC":"英特尔",
    "QCOM":"高通", "CSCO":"思科", "NFLX":"奈飞", "WMT":"沃尔玛", "JPM":"摩根大通",
    "V":"维萨", "MA":"万事达卡", "KO":"可口可乐", "PEP":"百事公司", "MCD":"麦当劳",
    "NKE":"耐克", "DIS":"迪士尼", "BA":"波音", "GE":"通用电气", "XOM":"埃克森美孚",
    "CVX":"雪佛龙", "JNJ":"强生", "PFE":"辉瑞", "LLY":"礼来", "ABBV":"艾伯维",
    "NVO":"诺和诺德", "TM":"丰田汽车", "SONY":"索尼", "BABA":"阿里巴巴",
    "TSM":"台积电", "ASML":"阿斯麦", "ADBE":"奥多比", "ADSK":"欧特克",
    "PLTR":"帕兰提尔", "COIN":"Coinbase",
}
SECTOR_CN = {
    "Technology":"信息技术", "Financial Services":"金融", "Healthcare":"医疗保健",
    "Consumer Cyclical":"可选消费", "Consumer Defensive":"必需消费",
    "Communication Services":"通信服务", "Industrials":"工业", "Energy":"能源",
    "Basic Materials":"基础材料", "Real Estate":"房地产", "Utilities":"公用事业",
}
INDUSTRY_CN = {
    "Software - Application":"应用软件", "Software - Infrastructure":"基础软件",
    "Semiconductors":"半导体", "Semiconductor Equipment & Materials":"半导体设备与材料",
    "Computer Hardware":"计算机硬件", "Consumer Electronics":"消费电子",
    "Internet Content & Information":"互联网内容与信息", "Information Technology Services":"IT服务",
    "Communication Equipment":"通信设备", "Banks - Diversified":"综合银行",
    "Credit Services":"信贷服务", "Drug Manufacturers - General":"综合制药",
    "Auto Manufacturers":"汽车制造", "Oil & Gas Integrated":"综合油气",
    "Airports & Air Services":"机场与航空服务", "Aluminum":"铝业",
    "Apparel Manufacturing":"服装制造", "Broadcasting":"广播电视", "Chemicals":"化学品",
    "Consulting Services":"咨询服务", "Department Stores":"百货商店",
    "Education & Training Services":"教育与培训服务", "Electronics & Computer Distribution":"电子与计算机分销",
    "Furnishings, Fixtures & Appliances":"家具、装饰与家电", "Gambling":"博彩",
    "Insurance - Reinsurance":"再保险", "Insurance - Specialty":"专业保险", "Leisure":"休闲娱乐",
    "Lumber & Wood Production":"木材生产", "Marine Shipping":"海运", "Oil & Gas Drilling":"油气钻探",
    "Other Precious Metals & Mining":"其他贵金属与采矿", "Packaging & Containers":"包装与容器",
    "Paper & Paper Products":"造纸与纸制品", "Personal Services":"个人服务",
    "Pollution & Treatment Controls":"污染治理设备", "Publishing":"出版",
    "REIT - Hotel & Motel":"酒店与汽车旅馆REIT", "REIT - Mortgage":"抵押贷款REIT",
    "REIT - Office":"办公地产REIT", "REIT - Residential":"住宅地产REIT",
    "Recreational Vehicles":"休闲车辆", "Security & Protection Services":"安防服务",
    "Silver":"白银矿业", "Solar":"太阳能", "Tools & Accessories":"工具与配件",
    "Utilities - Regulated Water":"受监管供水",
}
INDUSTRY_OVERRIDES_CN = {
    "SAP":"企业软件", "CRM":"客户关系管理软件", "NOW":"企业工作流软件",
    "ORCL":"数据库与企业软件", "MSFT":"云计算与企业软件", "ADBE":"创意软件",
    "ADSK":"工程设计软件", "MU":"存储芯片", "NVDA":"AI与图形芯片",
    "AMD":"CPU与GPU芯片", "INTC":"CPU与晶圆制造", "TSM":"晶圆代工",
    "ASML":"光刻设备", "AVGO":"通信与定制芯片",
}


def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------
# 第一步:抓1500只股票的名单(名字/市值/现价/涨跌幅)
# ------------------------------------------------------------------

def fetch_top1500_list():
    """从Nasdaq公开股票筛选接口一次获取全市场名单，在本机按市值排序后取前1500。
    StockAnalysis公开HTML固定每页500行，后续页由内部JS加载，不适合作为1500名单源。
    Nasdaq返回约7000行JSON但体积不大；只请求一次，不给VPS增加持续负担。"""
    params = {"tableonly": "true", "limit": TARGET_STOCK_COUNT, "offset": 0, "download": "true"}
    r = requests.get(NASDAQ_SCREENER_URL, params=params, headers={
        **HEADERS, "Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com"
    }, timeout=30)
    r.raise_for_status()
    raw_rows = ((r.json().get("data") or {}).get("rows") or [])
    parsed = []
    for row in raw_rows:
        try:
            market_cap = float(row.get("marketCap") or 0)
            symbol = (row.get("symbol") or "").strip()
            name = (row.get("name") or "").strip()
            # 排除优先股、强制可转优先股、权证和认股权；普通ADR/存托股仍保留。
            excluded = re.search(r'preferred stock|mandatory convertible|\bwarrants?\b|\bright(s)?\b', name, re.I)
            if excluded:
                continue
            if not symbol or market_cap <= 0:
                continue
            parsed.append((market_cap, row))
        except Exception:
            continue
    parsed.sort(key=lambda item: item[0], reverse=True)
    rows_out = []
    for rank, (market_cap, row) in enumerate(parsed[:TARGET_STOCK_COUNT], 1):
        rows_out.append({
            "rank": rank,
            "symbol": row.get("symbol", "").strip(),
            "name": row.get("name", "").strip(),
            "market_cap_text": str(market_cap),
            "price_text": (row.get("lastsale") or "").replace("$", "").strip(),
            "change_text": row.get("pctchange") or "",
            "revenue_text": "-",  # Nasdaq名单不含营收，下面复用Yahoo info中的totalRevenue
        })
    if len(rows_out) < TARGET_STOCK_COUNT:
        raise RuntimeError(f"Nasdaq名单只解析到{len(rows_out)}行,少于目标{TARGET_STOCK_COUNT}行,不覆盖旧缓存")
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


def yahoo_symbol(symbol):
    """stockanalysis.com用的股票代码格式和雅虎财经不完全一样——比如伯克希尔B类股
    stockanalysis.com写作"BRK.B",但雅虎财经要用连字符"BRK-B"才能查到,不然会报
    "possibly delisted; no timezone found"这种错误(你实测跑出来的BRK.B就是这个
    原因,不是网络问题,是符号格式不对)。这个规律通常适用于所有"股票代码里带
    点号表示股份类别"的情况(比如BF.B、PBR.A这些),统一把点号换成连字符再去查
    雅虎财经,但展示给你看的时候还是用原始的symbol(带点号那个),不影响你识别。"""
    return symbol.replace(".", "-").replace("/", "-")


def get_or_update_ath(ticker, ath_cache, yf_ticker=None):
    """核心降险逻辑:
    - 如果这个ticker在缓存里已经有记录,只拉最近5天的K线(很轻),
      看看最近有没有创新高,有就更新缓存,没有就直接用缓存里的旧值。
    - 如果缓存里完全没有这个ticker,才去做一次性的全历史下载建档
      (这是唯一"贵"的操作,而且每个ticker一辈子只做这一次)。
    返回 {"high": float, "date": "YYYY-MM", "ipo_date":.., "ipo_price":..} 或者 None(彻底失败)。
    注意:缓存的key用原始ticker(比如"BRK.B"),但真正去请求雅虎财经用yf_ticker
    (比如"BRK-B")——这两者可能不一样,原因见yahoo_symbol()函数的说明。

    v27新增ipo_date/ipo_price:复用首次建档时已经下载好的"全历史月线"数据,
    第一条记录的日期/收盘价近似当作IPO日期/IPO价格——这是近似值,只精确到月
    (月线粒度),不是真实的挂牌当天开盘价,而且雅虎财经的历史数据本身也不一定
    从IPO当天开始(部分公司历史数据起点比实际IPO晚)。

    v27.1修复:你反馈IPO这几列一直是"--",原因是v27上线前你本地已经有一份
    stock500_ath_cache.json(几乎全部500只都已经建过档),而v27的代码只在
    "首次建档"(cached is None)这个分支里才会顺带算ipo_date/ipo_price——已经
    建过档的股票会一直走"只查最近5天"这条轻量路径,永远不会补上IPO字段,
    等于这次改动对你来说形同虚设。这次改成:已经建过档、但缓存里没有ipo_date
    这个key的,自动触发一次"补建档"(和首次建档一样贵,要下载一次全历史月线),
    补完之后存进缓存,以后就和正常ticker一样只走轻量路径了。
    注意:这意味着v27.1这一轮跑stock500_fetch.py,几乎全部500只都要重新走一次
    "贵"操作,耗时会明显长于日常更新(参考首次建档的量级,大概1~1.5小时),
    这是获取IPO数据必须付出的一次性代价,只会发生这一次。
    """
    yf_ticker = yf_ticker or ticker
    cached = ath_cache.get(ticker)
    try:
        if cached is None or "ipo_date" not in cached:
            # 首次建档 或者 老缓存缺IPO字段需要补建档:都要走这条"贵"路径
            hist = yf.Ticker(yf_ticker).history(period="max", interval="1mo")
            if hist is None or hist.empty:
                return cached  # 补建档失败就沿用旧缓存(如果有的话),不是直接丢失
            idx = hist["High"].idxmax()
            new_high = float(hist.loc[idx, "High"])
            new_date = idx.strftime("%Y-%m")
            # 补建档场景下,如果旧缓存里的历史最高价比这次重新算出来的还高(理论上不该发生,
            # 除非中间有拆股之类的调整导致重算结果和之前不一致),保守起见取两者中较高的那个,
            # 不让"距ATH跌幅"因为这次补建档反而变得不准
            if cached and cached.get("high", 0) > new_high:
                new_high = cached["high"]
                new_date = cached.get("date", new_date)
            result = {"high": new_high, "date": new_date}
            first_idx = hist.index[0]
            first_close = hist["Close"].iloc[0]
            if first_close is not None and first_close == first_close:  # 排除NaN
                result["ipo_date"] = first_idx.strftime("%Y-%m")
                result["ipo_price"] = float(first_close)
            ath_cache[ticker] = result
            return result
        else:
            # 已经建过档:只用很轻的"最近5天"去校验有没有创新高
            hist = yf.Ticker(yf_ticker).history(period="5d", interval="1d")
            if hist is not None and not hist.empty:
                recent_high = float(hist["High"].max())
                if recent_high > cached["high"]:
                    recent_idx = hist["High"].idxmax()
                    result = {"high": recent_high, "date": recent_idx.strftime("%Y-%m")}
                    # ipo_date/ipo_price不受"创新高"影响,原样保留旧缓存里的值(可能没有,见上面说明)
                    if "ipo_date" in cached:
                        result["ipo_date"] = cached["ipo_date"]
                        result["ipo_price"] = cached["ipo_price"]
                    ath_cache[ticker] = result
                    return result
            return cached
    except Exception as e:
        _log(f"  ATH处理失败({ticker}): {e}")
        return cached  # 失败就沿用旧缓存(如果有的话),不是直接丢失历史记录


# ------------------------------------------------------------------
# 第三步:单只股票的基本面数据(雅虎财经.info)
# ------------------------------------------------------------------

CURRENCY_USD_QUOTED = {  # Yahoo这类pair是"1美元=多少外币",本币金额要"除以"汇率换算成美元
    "KRW": "KRW=X", "JPY": "JPY=X", "TWD": "TWD=X", "CNY": "CNY=X",
    "HKD": "HKD=X", "CHF": "CHF=X", "INR": "INR=X", "MXN": "MXN=X", "SEK": "SEK=X",
}
CURRENCY_FOREIGN_QUOTED = {  # 这类pair是"1单位外币=多少美元",本币金额要"乘以"汇率
    "EUR": "EURUSD=X", "GBP": "GBPUSD=X", "AUD": "AUDUSD=X",
}

_fx_rate_cache = {"USD": 1.0}  # 整个脚本运行期间复用,同一种货币只查一次汇率,不是每只股票都查


def get_usd_conversion_rate(currency_code):
    """把currency_code这种货币的金额换算成美元要乘的系数。同一种货币在整个脚本
    运行期间只会真正发一次网络请求查汇率,之后都从这个内存里的_fx_rate_cache复用,
    不会因为500家公司里有50家都是韩元计价就查50次汇率——汇率不会因为查的是哪家
    公司而变化,没必要重复查。"""
    if not currency_code or currency_code == "USD":
        return 1.0
    if currency_code in _fx_rate_cache:
        return _fx_rate_cache[currency_code]
    rate = None
    try:
        if currency_code in CURRENCY_USD_QUOTED:
            hist = yf.Ticker(CURRENCY_USD_QUOTED[currency_code]).history(period="5d")
            if hist is not None and not hist.empty:
                usd_per_unit = 1.0 / float(hist["Close"].iloc[-1])
                rate = usd_per_unit
        elif currency_code in CURRENCY_FOREIGN_QUOTED:
            hist = yf.Ticker(CURRENCY_FOREIGN_QUOTED[currency_code]).history(period="5d")
            if hist is not None and not hist.empty:
                rate = float(hist["Close"].iloc[-1])
        else:
            _log(f"  没有配置{currency_code}这个货币的汇率换算pair,自由现金流这项会保留原币种数值不做转换,"
                 f"需要你告诉我补上这个货币")
    except Exception as e:
        _log(f"  查{currency_code}汇率失败: {e}")
    if rate is None:
        rate = 1.0  # 查不到就不换算,保留原始数值,不是当成0处理(避免"看起来正常但其实是错的0")
    _fx_rate_cache[currency_code] = rate
    return rate


def fetch_fundamentals(ticker, display_ticker=None):
    """P/E、P/B、P/S、Beta、自由现金流、ROE、股份数、负债权益比。
    这几个字段yfinance的.info字典里名字分别是:
    trailingPE, priceToBook, priceToSalesTrailing12Months, beta, freeCashflow,
    returnOnEquity, sharesOutstanding, debtToEquity。
    某个字段没有就是None,不强行凑数。

    v2修复:P/E、P/B、P/S、ROE、负债权益比这几个都是"比率",分子分母是同一种货币,
    货币换算不影响比率大小,不存在问题。股份数是"数量"也不涉及货币。真正受"不同国家
    货币面值差异悬殊"影响的,只有自由现金流(free_cash_flow)这一项原始金额——
    比如韩元计价的公司,原始数字会是天文数字级别但换算成美元后其实很普通,如果不做
    换算,直接按数字大小排序会让韩元/日元这类"面值小、数字大"的货币计价公司排名
    虚高。这次加了货币换算,用info里的financialCurrency字段判断原始计价货币,
    非美元的话按当前汇率换算成美元等值。"""
    out = {
        "pe_ratio": None, "pb_ratio": None, "ps_ratio": None, "beta": None,
        "free_cash_flow": None, "roe": None, "shares_outstanding": None, "debt_to_equity": None,
        "financial_currency": None, "fcf_fx_rate_applied": None,
        "dividend_rate": None, "dividend_yield_pct": None,
        "chinese_name": None, "sector": None, "sector_cn": None,
        "industry": None, "industry_cn": None,
        "revenue": None,
    }
    try:
        info = yf.Ticker(ticker).info
        display_ticker = display_ticker or ticker
        sector = info.get("sector")
        industry = info.get("industry")
        out["chinese_name"] = CHINESE_NAMES.get(display_ticker)
        out["sector"] = sector
        out["sector_cn"] = SECTOR_CN.get(sector, sector)
        out["industry"] = industry
        out["industry_cn"] = INDUSTRY_OVERRIDES_CN.get(display_ticker, INDUSTRY_CN.get(industry, industry))
        out["revenue"] = info.get("totalRevenue")
        out["pe_ratio"] = info.get("trailingPE")
        out["pb_ratio"] = info.get("priceToBook")
        out["ps_ratio"] = info.get("priceToSalesTrailing12Months")
        out["beta"] = info.get("beta")
        out["roe"] = info.get("returnOnEquity")
        out["shares_outstanding"] = info.get("sharesOutstanding")
        out["debt_to_equity"] = info.get("debtToEquity")

        out["dividend_rate"] = info.get("dividendRate")
        # v27.1修复:雅虎财经dividendYield字段现在返回的已经是百分比数值本身
        # (比如0.49就是0.49%,不是0.49的小数形式),之前×100导致NVDA显示成
        # 不合理的49.00%,这里改成直接原样使用
        out["dividend_yield_pct"] = info.get("dividendYield")

        fcf_raw = info.get("freeCashflow")
        currency = info.get("financialCurrency")
        out["financial_currency"] = currency
        if fcf_raw is not None:
            rate = get_usd_conversion_rate(currency)
            out["free_cash_flow"] = fcf_raw * rate
            out["fcf_fx_rate_applied"] = rate if currency and currency != "USD" else None
    except Exception as e:
        _log(f"  基本面抓取失败: {e}")
    return out


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="美国上市股票Top 1500基本面数据抓取")
    parser.add_argument("--limit", type=int, default=None,
                        help="只处理前N只(用于第一次测试,建议先用--limit 20跑一遍)")
    args = parser.parse_args()

    _log(f"开始抓取市值前{TARGET_STOCK_COUNT}股票名单...")
    try:
        rows = fetch_top1500_list()
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
        yf_ticker = yahoo_symbol(ticker)  # 查雅虎财经用这个转换后的符号,展示/缓存key还是用原始ticker
        _log(f"[{i+1}/{len(rows)}] 处理 {ticker} ({row['name']})...")

        row_failed = False
        try:
            fundamentals = fetch_fundamentals(yf_ticker, display_ticker=ticker)
            ath_info = get_or_update_ath(ticker, ath_cache, yf_ticker=yf_ticker)

            market_cap = _parse_money_text(row["market_cap_text"])
            price = _parse_money_text(row["price_text"])  # 现价本身没有单位后缀,这个函数同样适用
            change_pct = _parse_pct_text(row["change_text"])
            revenue = _parse_money_text(row["revenue_text"])

            ath_dd_pct = None
            if price is not None and ath_info and ath_info.get("high"):
                ath_dd_pct = (price / ath_info["high"] - 1) * 100

            # v27新增:IPO至今年化涨幅(CAGR),用ipo_price(近似值,见get_or_update_ath里的说明)
            # 和现价算出总倍数,再按实际经过的年数开方年化。年数不足0.5年的不计算(避免刚上市
            # 没几个月就用年化拉爆的极端数字,意义不大反而容易误导)。
            ipo_date = ath_info.get("ipo_date") if ath_info else None
            ipo_price = ath_info.get("ipo_price") if ath_info else None
            ipo_cagr_pct = None
            if ipo_date and ipo_price and price is not None and ipo_price > 0:
                try:
                    ipo_dt = datetime.strptime(ipo_date, "%Y-%m")
                    years = (datetime.now() - ipo_dt).days / 365.25
                    if years >= 0.5:
                        ipo_cagr_pct = ((price / ipo_price) ** (1 / years) - 1) * 100
                except Exception:
                    pass

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
                "ipo_date": ipo_date,
                "ipo_price": ipo_price,
                "ipo_cagr_pct": ipo_cagr_pct,
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
                "ipo_date": None, "ipo_price": None, "ipo_cagr_pct": None,
                "pe_ratio": None, "pb_ratio": None, "ps_ratio": None, "beta": None,
                "free_cash_flow": None, "roe": None, "shares_outstanding": None, "debt_to_equity": None,
                "dividend_rate": None, "dividend_yield_pct": None,
                "chinese_name": CHINESE_NAMES.get(ticker), "sector": None, "sector_cn": None,
                "industry": None, "industry_cn": None,
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
