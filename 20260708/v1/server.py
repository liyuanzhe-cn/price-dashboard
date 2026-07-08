#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人参考看板 - 后端数据代理 (v3)
================================
v3新增(相对v2,对应你重新设计的JSON schema里新加的几类):
  - 贵金属:黄金/白银/铂金/钯金/铜 走雅虎财经期货代码,黄金稳定币(XAUT)走CoinGecko,
    锂给LIT ETF,周大福金价单独抓官网(风险较高,见下方TODO),没有强行凑一个不存在的统一现货源。
  - 指数新增 PHLX半导体(^SOX)/罗素2000(^RUT)/道琼斯(^DJI)/纽约综合(^NYA)。
  - 其他加密货币(ETH/ADA/AVAX/SOL/HYPE/BNB/BGB/OKB):换成CoinGecko的
    /coins/markets批量接口,一次请求拿到所有币种的现价+24h涨跌+历史最高价(ATH)+
    距ATH跌幅,不用逐个再调一次,比v2里単独调BTC价格的方式更省请求次数。
  - "最高点下跌幅度":加密货币直接用CoinGecko自带的ath_change_percentage字段;
    股票/指数/贵金属期货没有现成接口,改成用yfinance拉全历史(用月线而不是日线,
    减少数据量)算出历史最高收盘价,一天算一次,不是每次刷新都算。
  - 股市风险指标:席勒市盈率(multpl.com)和巴菲特指标(currentmarketvaluation.com)
    做了抓取尝试;"修正版巴菲特指标"和Tobin's Q没有做自动抓取,只给链接,原因见下方说明。

⚠️ 关于VPS资源的诚实提醒(你之前那台是1核/969MB内存):
  v3新增的"历史最高价"计算,需要对大约28个股票/指数/期货代码分别下载全历史数据
  (哪怕用月线降低数据量),这个动作一天只跑一次,但跑的时候会有一次性的CPU/内存
  峰值,跑完那几分钟之内内存占用可能会明显上升。如果你观察到这个动作让VPS变卡,
  可以把下面的 ENABLE_ATH_DRAWDOWN 改成 False 整个关掉这个功能,不影响其他部分。

依赖(新增 lxml 用于稍微更快地解析,可选,不装也能跑,只是慢一点):
    pip install --break-system-packages requests yfinance beautifulsoup4

运行:
    python3 server.py
    默认监听 0.0.0.0:8899

需要你确认/核实的地方(重要)(全部搜索 "TODO" 可定位):
  1. bitcointreasuries.net 这两个页面看起来是SvelteKit做的,我拿到的内容是
     经过某种渲染/文本抽取后的结果,证明了关键字段确实以文本形式存在于返回内容里。
     但我没法在这个环境里直接用 requests.get() 实测这个页面返回的是"完整渲染后的HTML"
     还是"只有JS骨架、内容要等JS跑完才有"。如果你跑起来发现 mstr/asst 部分一直是null,
     大概率是后者(客户端渲染),需要换成无头浏览器(如 playwright)方案,告诉我我再改。
  2. 抓取用的是正则在纯文本上匹配"标签名+紧跟着的值",bitcointreasuries.net如果改版
     (哪怕只是换个措辞,比如"BTC Holdings"变成"Bitcoin Holdings"),这里就会解析失败。
     解析失败时对应字段会是null,前端会显示"--",不会用假数据填充。
  3. MVRV系列的BGeometrics token、SPCX无公开行情、STRC/D/F/K/ASST/BRK-B等ticker假设——
     这几条和v1版本一致,详见文件里其余TODO。
  4. 周大福金价(chowtaifook.com)、multpl.com、currentmarketvaluation.com 这三个新
     抓取目标,我同样没法在这个环境里用requests.get()实测是否是客户端渲染。如果这几项
     一直是null,原因和排查方式跟bitcointreasuries一样(见上面第1条),不再重复写。
  5. "修正版巴菲特指标"(gurufocus的TMC/(GDP+Fed资产)版本)和Tobin's Q,我没有做自动
     抓取——gurufocus对爬虫的防护比较重,容易连基础版巴菲特指标一起抓失败,Tobin's Q
     那几个数据源本身更新频率是季度且我查证时发现常见页面数据有异常,权衡下这两项
     只给你链接,不在后端做自动化,前端会显示"点击查看"而不是一个数字。
"""

import json
import re
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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

PORT = 8899

# TODO: 去 https://portal.bgeometrics.com/login 免费注册后填在这里
BGEOMETRICS_TOKEN = ""

CRYPTO_REFRESH_SEC = 30            # 所有加密货币(含BTC)批量现价
STOCK_REFRESH_SEC = 60             # 普通股票/指数/优先股/贵金属期货现价
TREASURY_REFRESH_SEC = 20 * 60     # bitcointreasuries.net 抓取频率(你说60秒或几小时都行,
                                    # 这里默认20分钟,避免频繁请求同一个页面被限流/封IP;
                                    # 想要更快就调小这个数字)
ONCHAIN_REFRESH_SEC = 8 * 3600     # MVRV系列,受BGeometrics免费额度限制,不要调快
GOLD_RETAIL_REFRESH_SEC = 3 * 3600 # 周大福金价,零售报价一天变几次而已,不用太频繁
RISK_INDICATOR_REFRESH_SEC = 12 * 3600  # 巴菲特指标/席勒PE,本身按周更新,不用太频繁

# ---- ATH(历史最高价)/回撤计算开关 ----
# 这是v3新增的、相对"重"的功能:对下面ATH_TICKERS里每个代码下载全历史月线数据,
# 算出历史最高收盘价。一天只跑一次,但跑的时候有一次性资源峰值。
# 如果你的VPS跑起来觉得卡,把这里改成 False 就能整个关掉,不影响看板其他部分。
ENABLE_ATH_DRAWDOWN = True
ATH_REFRESH_SEC = 24 * 3600

ONCHAIN_ENDPOINTS = {
    "mvrv": "mvrv",
    "mvrv_zscore": "mvrv-zscore",
    "realized_price": "realized-price",
    "balanced_price": "balanced-price",
}

TREASURY_PAGES = {
    "MSTR": "https://bitcointreasuries.net/public-companies/strategy",
    "ASST": "https://bitcointreasuries.net/public-companies/strive",
}

MSTR_PREFERREDS = {
    "STRC": "STRC",
    "STRD": "STRD",
    "STRF": "STRF",
    "STRK": "STRK",
}

MSTR_TICKER = "MSTR"
ASST_TICKER = "ASST"

WATCHLIST = {
    "BRKB": "BRK-B",
    "TSLA": "TSLA",
    "GOOG": "GOOG",
    "CRCL": "CRCL",
    "COIN": "COIN",
    "HOOD": "HOOD",
    "NVDA": "NVDA",
    "ARM": "ARM",
    "AMD": "AMD",
    "SPCX": "SPCX",  # TODO: SpaceX目前未公开上市,大概率抓不到实时股价
}

INDICES = {
    "NASDAQ Composite": "^IXIC",
    "NASDAQ 100": "^NDX",
    "S&P 500": "^GSPC",
    "PHLX Semiconductor": "^SOX",
    "Russell 2000": "^RUT",
    "Dow Jones": "^DJI",
    "NYSE Composite": "^NYA",
    "KOSPI": "^KS11",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "上证指数": "000001.SS",
    "沪深300": "000300.SS",
    "台湾50(0050)": "0050.TW",  # TODO: 如果指台湾加权指数而非0050 ETF,改成 ^TWII
}

# ---- 贵金属(雅虎财经期货/ETF代码) ----
METALS = {
    "黄金": "GC=F",
    "白银": "SI=F",
    "铂金": "PL=F",
    "钯金": "PA=F",
    "铜": "HG=F",
    "锂(LIT ETF代理)": "LIT",
}

# ---- 需要计算"历史最高价/距ATH跌幅"的股票/指数/贵金属代码 ----
ATH_TICKERS = list(WATCHLIST.values()) + list(INDICES.values()) + list(METALS.values())

# ---- 加密货币(含BTC),CoinGecko批量接口一次拿完 ----
CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "SOL": "solana",
    "HYPE": "hyperliquid",
    "BNB": "binancecoin",
    "BGB": "bitget-token",
    "OKB": "okb",  # 注意: OKX是交易所,不是币,平台币正确代码是OKB
    "XAUT": "tether-gold",  # 黄金稳定币
}

# ---- 周大福金价 ----
GOLD_RETAIL_URL = "https://www.chowtaifook.com/zh-hk/eshop/realtime-gold-price.html"

# ---- 股市风险指标抓取目标 ----
RISK_INDICATOR_PAGES = {
    "shiller_pe": "https://www.multpl.com/shiller-pe",
    "buffett_indicator": "https://www.currentmarketvaluation.com/models/buffett-indicator.php",
}
# 修正版巴菲特指标 / Tobin's Q 没有做自动抓取,只放链接(原因见文件头说明)
RISK_INDICATOR_LINKS_ONLY = {
    "modified_buffett_indicator": "https://www.gurufocus.com/stock-market-valuations.php",
    "tobins_q": "https://www.advisorperspectives.com/dshort/updates/",
}

LINKS = {
    "BTC_MVRV": "https://charts.bgeometrics.com/mvrv.html",
    "BTC_MVRV_Z": "https://charts.bgeometrics.com/mvrv.html",
    "BTC_REALIZED_PRICE": "https://charts.bgeometrics.com/realized-price.html",
    "BTC_BALANCED_PRICE": "https://bitcoin-data.com/",
    "MSTR_TREASURY": TREASURY_PAGES["MSTR"],
    "ASST_TREASURY": TREASURY_PAGES["ASST"],
    "DIGITAL_CREDIT_TEMPLATE": "https://bitcointreasuries.net/digital-credit/{sym}",
    "STOCK_TEMPLATE": "https://stockanalysis.com/stocks/{sym}/",
    "INDEX_TEMPLATE": "https://www.google.com/finance/quote/{sym}",
    "CRYPTO_TEMPLATE": "https://www.coingecko.com/en/coins/{id}",
    "GOLD_RETAIL": GOLD_RETAIL_URL,
    "SHILLER_PE": RISK_INDICATOR_PAGES["shiller_pe"],
    "BUFFETT_INDICATOR": RISK_INDICATOR_PAGES["buffett_indicator"],
    "MODIFIED_BUFFETT_INDICATOR": RISK_INDICATOR_LINKS_ONLY["modified_buffett_indicator"],
    "TOBINS_Q": RISK_INDICATOR_LINKS_ONLY["tobins_q"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# ------------------------------------------------------------------
# 全局状态(内存缓存,无持久化)
# ------------------------------------------------------------------

STATE_LOCK = threading.Lock()
STATE = {
    "updated_at": None,
    "btc": {},
    "onchain": {},
    "mstr": {},          # 现价 + bitcointreasuries抓取字段
    "asst": {},
    "mstr_preferreds": {},
    "watchlist": {},
    "indices": {},
    "metals": {},         # 贵金属(期货/ETF)
    "gold_retail": {},    # 周大福金价
    "crypto_extra": {},   # 其他加密货币(ETH/ADA/AVAX/SOL/HYPE/BNB/BGB/OKB/XAUT)
    "risk_indicators": {},  # 巴菲特指标/席勒PE(自动抓取) + 修正版/Tobin's Q(仅链接)
    "ath": {},            # 各代码的历史最高收盘价(月线),ENABLE_ATH_DRAWDOWN=False时为空
    "links": LINKS,
    "errors": [],
}

_last_fetch = {"crypto": 0, "stock": 0, "onchain": 0, "treasury": 0,
               "gold_retail": 0, "risk_indicator": 0, "ath": 0}


def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _record_error(where, exc):
    err = f"{where}: {exc}"
    _log("ERROR " + err)
    with STATE_LOCK:
        STATE["errors"] = (STATE["errors"] + [err])[-10:]


# ------------------------------------------------------------------
# 抓取函数
# ------------------------------------------------------------------

def fetch_crypto_batch(id_map):
    """用CoinGecko的/coins/markets批量接口,一次请求拿到所有币种的:
    现价、24h涨跌幅、历史最高价(ath)、距ATH跌幅(ath_change_percentage,已经是CoinGecko
    算好的现成字段,不需要自己再计算一遍)。
    id_map: {显示名: coingecko_id}"""
    ids = ",".join(id_map.values())
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "ids": ids, "price_change_percentage": "24h"}
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    rows = {row["id"]: row for row in r.json()}
    out = {}
    for name, cg_id in id_map.items():
        row = rows.get(cg_id)
        if not row:
            out[name] = {"price": None, "change_pct": None, "ath": None, "ath_change_pct": None}
            continue
        out[name] = {
            "price": row.get("current_price"),
            "change_pct": row.get("price_change_percentage_24h"),
            "ath": row.get("ath"),
            "ath_change_pct": row.get("ath_change_percentage"),  # 负数=距历史高点还差多少百分比
        }
    return out


def fetch_gold_retail(url):
    """抓周大福官网的实时金价页面,找'XXXX元/克'这种格式的数字。
    这个页面我没法在这个环境里实测是静态渲染还是客户端渲染,抓不到就是None,
    不会拿旧数字或编一个数字填充。"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        raw = _find_value_near_label(lines, "足金", r'([\d,\.]+)\s*元')
        if raw is None:
            m = re.search(r'([\d,\.]{3,})\s*元\s*/?\s*克', text)
            raw = m.group(1) if m else None
        price = float(raw.replace(",", "")) if raw else None
        return {"price_rmb_per_gram": price}
    except Exception as e:
        _record_error("gold_retail", e)
        return {"price_rmb_per_gram": None}


def fetch_risk_indicators():
    """抓席勒市盈率(multpl.com)和巴菲特指标(currentmarketvaluation.com)。
    修正版巴菲特指标和Tobin's Q没有做自动抓取,见文件头说明。"""
    out = {"shiller_pe": None, "buffett_indicator": None}

    try:
        r = requests.get(RISK_INDICATOR_PAGES["shiller_pe"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        m = re.search(r'Current\s+Shiller\s+PE\s+Ratio\s+is\s+([\d.]+)', text, re.IGNORECASE)
        if not m:
            m = re.search(r'\b([2-9]\d\.\d{1,2})\b', text)
        out["shiller_pe"] = float(m.group(1)) if m else None
    except Exception as e:
        _record_error("risk_indicator:shiller_pe", e)

    try:
        r = requests.get(RISK_INDICATOR_PAGES["buffett_indicator"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        m = re.search(r'Buffett\s+Indicator\s+as\s+([\d.]+)%', text, re.IGNORECASE)
        if not m:
            m = re.search(r'currently\s+at\s+([\d.]+)%', text, re.IGNORECASE)
        out["buffett_indicator"] = float(m.group(1)) if m else None
    except Exception as e:
        _record_error("risk_indicator:buffett_indicator", e)

    return out


def fetch_ath_drawdown(tickers):
    """对每个代码下载全历史月线收盘价,取最大值作为历史最高价。
    用月线而不是日线是为了减少一次性下载的数据量/内存占用,代价是极端情况下
    某个单日历史高点可能被月度收盘价"抹平"、算出来的ATH略微偏低,这是在资源
    有限的VPS上的取舍。逐个ticker顺序处理、处理完立刻丢弃DataFrame。"""
    out = {}
    for sym in tickers:
        try:
            hist = yf.Ticker(sym).history(period="max", interval="1mo")
            if hist is None or hist.empty:
                out[sym] = None
                continue
            out[sym] = float(hist["Close"].max())
            del hist
        except Exception as e:
            out[sym] = None
            _record_error(f"ath:{sym}", e)
    return out


def fetch_onchain_metrics():
    out = {}
    for key, endpoint in ONCHAIN_ENDPOINTS.items():
        try:
            url = f"https://api.bgeometrics.com/v1/{endpoint}"
            headers = {}
            params = {}
            if BGEOMETRICS_TOKEN:
                headers["Authorization"] = f"Bearer {BGEOMETRICS_TOKEN}"
            else:
                params["token"] = ""
            r = requests.get(url, headers=headers, params=params, timeout=10)
            r.raise_for_status()
            payload = r.json()
            latest = payload
            if isinstance(payload, list) and payload:
                latest = payload[-1]
            out[key] = latest
        except Exception as e:
            out[key] = None
            _record_error(f"onchain:{key}", e)
    return out


def fetch_quotes(ticker_map):
    symbols = list(ticker_map.values())
    result = {}
    try:
        tk = yf.Tickers(" ".join(symbols))
        for name, sym in ticker_map.items():
            try:
                t = tk.tickers.get(sym)
                fi = t.fast_info

                def _get(fi, *names):
                    for n in names:
                        try:
                            v = fi[n]
                            if v is not None:
                                return v
                        except Exception:
                            pass
                    return None

                price = _get(fi, "lastPrice", "last_price")
                prev_close = _get(fi, "previousClose", "previous_close", "regularMarketPreviousClose")
                chg_pct = None
                if price is not None and prev_close:
                    chg_pct = (price - prev_close) / prev_close * 100
                result[name] = {"symbol": sym, "price": price, "prev_close": prev_close, "change_pct": chg_pct}
            except Exception as e:
                result[name] = {"symbol": sym, "price": None, "prev_close": None, "change_pct": None}
                _record_error(f"quote:{sym}", e)
    except Exception as e:
        _record_error("fetch_quotes:batch", e)
    return result


# ---- bitcointreasuries.net 解析 ----

_MONEY_RE = r'\$?([\d][\d,\.]*)\s*([BMK]?)'
_MULT_UNIT = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def _parse_money(raw):
    """把 '$53.1B' / '$75,646' / '36.3B' 这类字符串转成float(美元数值)"""
    if raw is None:
        return None
    m = re.search(_MONEY_RE, raw)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    unit = m.group(2).upper()
    return num * _MULT_UNIT.get(unit, 1)


def _parse_btc(raw):
    """把 '₿847,363' 转成 float"""
    if raw is None:
        return None
    m = re.search(r'([\d][\d,\.]*)', raw)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _parse_multiple(raw):
    """把 '1.08×' 转成 1.08"""
    if raw is None:
        return None
    m = re.search(r'([\d.]+)', raw)
    if not m:
        return None
    return float(m.group(1))


def _find_value_near_label(lines, label, value_regex, window=8):
    """在按行拆分的文本里找包含 label 的行,然后在该行及其后window行内
    找第一处匹配 value_regex 的内容。比"必须紧跟在label后面"更宽松,
    能容忍标签和数值之间夹着图标文字/提示语/涨跌幅小标签等内容。
    如果 label 在文本里出现多次,第一次出现附近找不到值不会直接放弃,
    会继续尝试下一次出现。"""
    n = len(lines)
    for i, line in enumerate(lines):
        if label in line:
            for j in range(i, min(i + 1 + window, n)):
                m = re.search(value_regex, lines[j])
                if m:
                    return m.group(1)
    return None


def fetch_treasury_page(url):
    """抓取 bitcointreasuries.net 的公司页面,解析出BTC持仓/市值/mNAV等已算好的字段。
    解析不到的字段一律返回None,不用假数据填充。
    如果 mNAV(EV)/mNAV(Basic)/mNAV(Diluted)/BTC Holdings 直接解析失败,但 Market Cap /
    Enterprise Value / BTC Value 抓到了,会用这几个已抓到的数字反推出来,并在
    estimated_fields 里标记是"推算值"而不是网站原始数字,前端需要区分展示。"""
    out = {
        "btc_holdings": None, "btc_value": None, "total_cost_basis": None, "avg_cost_per_btc": None,
        "market_cap": None, "enterprise_value": None,
        "mnav_ev": None, "mnav_basic": None, "mnav_diluted": None,
        "btc_per_share_basic": None, "btc_per_share_diluted": None,
        "as_of": None,
        "estimated_fields": [],
    }
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    raw = {}
    raw["btc_holdings"] = _find_value_near_label(lines, "BTC Holdings", r'(₿[\d,\.]+)')
    raw["as_of"] = _find_value_near_label(lines, "As of", r'As of\s*(.+)')
    raw["btc_value"] = _find_value_near_label(lines, "BTC Value", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["total_cost_basis"] = _find_value_near_label(lines, "Total Cost Basis", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["avg_cost_per_btc"] = _find_value_near_label(lines, "Avg Cost / BTC", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["market_cap"] = _find_value_near_label(lines, "Market Cap", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["enterprise_value"] = _find_value_near_label(lines, "Enterprise Value", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["mnav_ev"] = _find_value_near_label(lines, "mNAV (EV)", r'([\d\.]+)\s*[×xX]')
    raw["mnav_basic"] = _find_value_near_label(lines, "mNAV (Basic)", r'([\d\.]+)\s*[×xX]')
    raw["mnav_diluted"] = _find_value_near_label(lines, "mNAV (Diluted)", r'([\d\.]+)\s*[×xX]')
    raw["btc_per_share_basic"] = _find_value_near_label(lines, "BTC / Share (Basic)", r'([\d\.]+)')
    raw["btc_per_share_diluted"] = _find_value_near_label(lines, "BTC / Share (Diluted)", r'([\d\.]+)')

    out["btc_holdings"] = _parse_btc(raw["btc_holdings"])
    out["as_of"] = raw["as_of"]
    out["btc_value"] = _parse_money(raw["btc_value"])
    out["total_cost_basis"] = _parse_money(raw["total_cost_basis"])
    out["avg_cost_per_btc"] = _parse_money(raw["avg_cost_per_btc"])
    out["market_cap"] = _parse_money(raw["market_cap"])
    out["enterprise_value"] = _parse_money(raw["enterprise_value"])
    out["mnav_ev"] = _parse_multiple(raw["mnav_ev"])
    out["mnav_basic"] = _parse_multiple(raw["mnav_basic"])
    out["mnav_diluted"] = _parse_multiple(raw["mnav_diluted"])
    out["btc_per_share_basic"] = _parse_multiple(raw["btc_per_share_basic"])
    out["btc_per_share_diluted"] = _parse_multiple(raw["btc_per_share_diluted"])

    # ---- 兜底推算:直接解析失败,但其他字段够用时,用已抓到的数字反推 ----
    if out["btc_holdings"] is None and out["btc_value"] is not None:
        with STATE_LOCK:
            live_btc_price = STATE.get("btc", {}).get("price_usd")
        if live_btc_price:
            out["btc_holdings"] = out["btc_value"] / live_btc_price
            out["estimated_fields"].append("btc_holdings")

    if out["mnav_ev"] is None and out["enterprise_value"] is not None and out["btc_value"]:
        out["mnav_ev"] = out["enterprise_value"] / out["btc_value"]
        out["estimated_fields"].append("mnav_ev")

    if out["mnav_basic"] is None and out["market_cap"] is not None and out["btc_value"]:
        out["mnav_basic"] = out["market_cap"] / out["btc_value"]
        out["estimated_fields"].append("mnav_basic")

    if (out["mnav_diluted"] is None and out["mnav_basic"] is not None
            and out["btc_per_share_basic"] and out["btc_per_share_diluted"]):
        ratio = out["btc_per_share_basic"] / out["btc_per_share_diluted"]
        out["mnav_diluted"] = out["mnav_basic"] * ratio
        out["estimated_fields"].append("mnav_diluted")

    return out


# ------------------------------------------------------------------
# 后台刷新循环
# ------------------------------------------------------------------

def refresh_loop():
    while True:
        now = time.time()

        try:
            if now - _last_fetch["crypto"] >= CRYPTO_REFRESH_SEC:
                crypto = fetch_crypto_batch(CRYPTO_IDS)
                with STATE_LOCK:
                    btc_row = crypto.get("BTC", {})
                    STATE["btc"] = {
                        "price_usd": btc_row.get("price"),
                        "change_24h_pct": btc_row.get("change_pct"),
                        "ath": btc_row.get("ath"),
                        "ath_change_pct": btc_row.get("ath_change_pct"),
                    }
                    STATE["crypto_extra"] = {k: v for k, v in crypto.items() if k != "BTC"}
                _last_fetch["crypto"] = now
        except Exception as e:
            _record_error("crypto_loop", e)

        try:
            if now - _last_fetch["stock"] >= STOCK_REFRESH_SEC:
                mstr_q = fetch_quotes({"MSTR": MSTR_TICKER}).get("MSTR", {})
                asst_q = fetch_quotes({"ASST": ASST_TICKER}).get("ASST", {})
                preferreds = fetch_quotes(MSTR_PREFERREDS)
                watch = fetch_quotes(WATCHLIST)
                idx = fetch_quotes(INDICES)
                metals = fetch_quotes(METALS)
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["quote"] = mstr_q
                    STATE.setdefault("asst", {})["quote"] = asst_q
                    STATE["mstr_preferreds"] = preferreds
                    STATE["watchlist"] = watch
                    STATE["indices"] = idx
                    STATE["metals"] = metals
                _last_fetch["stock"] = now
        except Exception as e:
            _record_error("stock_loop", e)

        try:
            if now - _last_fetch["treasury"] >= TREASURY_REFRESH_SEC:
                mstr_t = fetch_treasury_page(TREASURY_PAGES["MSTR"])
                asst_t = fetch_treasury_page(TREASURY_PAGES["ASST"])
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["treasury"] = mstr_t
                    STATE.setdefault("asst", {})["treasury"] = asst_t
                _last_fetch["treasury"] = now
        except Exception as e:
            _record_error("treasury_loop", e)

        try:
            if now - _last_fetch["onchain"] >= ONCHAIN_REFRESH_SEC:
                onchain = fetch_onchain_metrics()
                with STATE_LOCK:
                    STATE["onchain"] = onchain
                _last_fetch["onchain"] = now
        except Exception as e:
            _record_error("onchain_loop", e)

        try:
            if now - _last_fetch["gold_retail"] >= GOLD_RETAIL_REFRESH_SEC:
                gr = fetch_gold_retail(GOLD_RETAIL_URL)
                with STATE_LOCK:
                    STATE["gold_retail"] = gr
                _last_fetch["gold_retail"] = now
        except Exception as e:
            _record_error("gold_retail_loop", e)

        try:
            if now - _last_fetch["risk_indicator"] >= RISK_INDICATOR_REFRESH_SEC:
                ri = fetch_risk_indicators()
                with STATE_LOCK:
                    STATE["risk_indicators"] = ri
                _last_fetch["risk_indicator"] = now
        except Exception as e:
            _record_error("risk_indicator_loop", e)

        try:
            if ENABLE_ATH_DRAWDOWN and now - _last_fetch["ath"] >= ATH_REFRESH_SEC:
                ath = fetch_ath_drawdown(ATH_TICKERS)
                with STATE_LOCK:
                    STATE["ath"] = ath
                _last_fetch["ath"] = now
        except Exception as e:
            _record_error("ath_loop", e)

        with STATE_LOCK:
            STATE["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        time.sleep(5)


# ------------------------------------------------------------------
# HTTP服务
# ------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/data":
            with STATE_LOCK:
                snapshot = json.loads(json.dumps(STATE))
            self._send_json(snapshot)
            return
        if path in ("/", "/index.html"):
            try:
                with open("index.html", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({"error": "index.html not found next to server.py"}, 404)
            return
        self._send_json({"error": "not found"}, 404)


def main():
    t = threading.Thread(target=refresh_loop, daemon=True)
    t.start()
    _log(f"启动: http://0.0.0.0:{PORT}  (数据接口: /api/data, 页面: /)")
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
