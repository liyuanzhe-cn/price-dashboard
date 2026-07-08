#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人参考看板 - 后端数据代理 (v6)
================================
v6改动(相对v5,修复实际bug + 按反馈调整):
  - ATH计算改成独立后台线程(ath_loop),不再放在主刷新循环里。之前它是阻塞式的,
    对~30个代码逐个下载全历史数据,如果中间某个请求卡住,会拖慢整个主循环,
    价格类数据也会跟着卡住不刷新——这是"自选股/指数/贵金属/MSTR/ASST都看不到
    距历史高点"最可能的真实原因,不是没算,是被卡住了一直没跑完。
  - 每个ticker的历史数据下载加了20秒超时(ATH_PER_TICKER_TIMEOUT_SEC),
    不会无限等下去。
  - 改成"边算边写":每算完一个ticker就立刻更新STATE和缓存,不用等30个
    全部跑完才一次性显示,这样就算这一轮没跑完,已经算出来的那些也能看到。
  - ATH刷新间隔从24小时改成12小时(按你的要求)。
  - 巴菲特指标解析重写:之前的正则会在页面上抓到不相关的百分比数字
    (你反馈实际网站显示237.24%,我们抓出来是4.5%),现在用更精确的短语
    定位+合理性区间校验(30%-500%),抓不到或者数字不合理就直接给None,
    不会硬凑一个错误数字出来显示。
  - 巴菲特指标/席勒PE 新增三档风险分区(低/中/高),前端用绿/黄/红三色展示。
  - 修正版巴菲特指标、Tobin's Q 已按你的要求整个删除。
  - 21Shares 已按你的要求整个删除(不再留占位)。

依赖(和v5一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
v5改动(相对v4,修复一个实际的bug):
  - 之前算"历史最高价"用的是月线的收盘价(Close)取最大值,这是错的——如果某个月
    冲高之后又回落收盘,月线收盘价会把那个盘中高点"抹平",算出来的ATH会偏低。
    黄金实际ATH你记得在5600左右,之前算出来才4714左右;白银你记得110左右,
    之前算出来才78左右——都是这个bug导致的,不是数据源的问题。
    v5改成用月线的"最高价"(High)取最大值,不会再有这个问题。
  - 新增"历史最高价出现在哪个月"这个字段。加密货币直接用CoinGecko自带的
    ath_date(精确到天);股票/指数/贵金属期货因为只下载了月线,只能精确到月,
    不能精确到具体哪一天,这一点前端会标注清楚,不会假装精确到天。
  - 因为计算方式变了,之前缓存在cache_log.json里的ATH数值是用旧的(错误的)
    算法算出来的,不会自动纠正——需要你换成这次一起给你的、内容为空的
    cache_log.json,强制服务重启后立刻用新算法重新算一遍,不要偷懒手动改旧文件。

依赖(和v4一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
v4新增(相对v3):
  - MSTR / ASST 面板增加"距历史高点"(复用ATH_TICKERS机制,和其他股票用同一套
    月线历史数据计算方式)。
  - 自选股大幅扩充:MSTR/ASST/STRC/AAPL/MSFT/META/NFLX/AMZN/XOM/SK海力士/三星/
    LG/Adobe/Metaplanet,能配中文名的都配了中文名。21Shares因为本身是私人公司、
    没有统一对应的上市标的,没有替你猜一个,留空待你确认。
  - MSTR/ASST/STRC 在自选股列表里复用了别处已经抓到的现价,不重复发请求。
  - 自选股按"距历史高点跌幅"从大到小排序(跌得最狠的排最前面)。
  - 新增缓存日志(cache_log.json,和server.py同目录):记录每类数据"上次真正
    抓取成功的时间+内容",进程重启时会先读回这个文件,避免重启导致所有数据
    (包括那些有严格频率限制的)立刻被重新请求一遍。

依赖(和v3一致):
    pip install --break-system-packages requests yfinance beautifulsoup4

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

关于VPS资源的诚实提醒(你之前那台是1核/969MB内存):
  v3新增的"历史最高价"计算,需要对大约30个股票/指数/期货代码分别下载全历史数据
  (哪怕用月线降低数据量),这个动作一天只跑一次,但跑的时候会有一次性的CPU/内存
  峰值,跑完那几分钟之内内存占用可能会明显上升。如果你观察到这个动作让VPS变卡,
  可以把下面的 ENABLE_ATH_DRAWDOWN 改成 False 整个关掉这个功能,不影响其他部分。

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
import os
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

# 缓存日志文件:记录每类数据"上次真正抓到的时间+内容",和server.py放同一目录。
# 目的是应对"进程重启"这个场景——如果没有这个文件,每次重启(比如你手动重启服务、
# 或者服务因为某种原因崩溃重启)都会让 _last_fetch 归零,导致所有数据(包括那些
# 受严格频率限制的,比如bitcointreasuries.net/BGeometrics/gurufocus)立刻被重新
# 请求一遍,短时间内重启几次就可能把额度用光、被限流。有这个文件之后,启动时会先
# 把上次的真实抓取时间读回来,该等的继续等,不会因为重启就"重新计时"。
CACHE_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_log.json")

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
ATH_REFRESH_SEC = 12 * 3600  # 按你的要求从24小时改成12小时,这个数据本身不常变
ATH_PER_TICKER_TIMEOUT_SEC = 20  # 单个ticker超过这个时间还没返回就放弃,避免卡住整个ATH线程

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

# 自选股:字典的key就是前端展示用的名字,能配中文的配中文(格式"中文名(TICKER)"),
# 没有约定俗成中文名的就用英文/ticker本身,不硬翻译。
# 注意:MSTR/ASST/STRC 在别的板块已经抓过一次现价了(mstr_q/asst_q/preferreds),
# 这里不重复调用yfinance,而是在refresh_loop里直接把已经抓到的结果merge进来,
# 避免对同一个ticker重复发请求(呼应你说的"网站请求次数有限制"这个顾虑)。
WATCHLIST = {
    "伯克希尔B(BRKB)": "BRK-B",
    "特斯拉(TSLA)": "TSLA",
    "谷歌(GOOG)": "GOOG",
    "Circle(CRCL)": "CRCL",
    "Coinbase(COIN)": "COIN",
    "Robinhood(HOOD)": "HOOD",
    "英伟达(NVDA)": "NVDA",
    "Arm(ARM)": "ARM",
    "AMD": "AMD",
    "SpaceX(SPCX)": "SPCX",  # 2026年6月12日已IPO上市,不再是"未公开上市"
    "苹果(AAPL)": "AAPL",
    "微软(MSFT)": "MSFT",
    "Meta(META)": "META",
    "奈飞(NFLX)": "NFLX",
    "亚马逊(AMZN)": "AMZN",
    "埃克森美孚(XOM)": "XOM",
    "SK海力士(000660.KS)": "000660.KS",
    "三星电子(005930.KS)": "005930.KS",
    # TODO: "LG"本身有歧义——LG电子(消费电子,066570.KS) vs LG集团控股公司(003550.KS)。
    # 这里按更常被普通人理解的"LG电子"处理,如果你实际想要控股公司请告诉我改成003550.KS。
    "LG电子(066570.KS)": "066570.KS",
    "Adobe(ADBE)": "ADBE",
    "Metaplanet(3350.T)": "3350.T",
}
# MSTR/ASST/STRC 会在refresh_loop里额外合并进watchlist,不在这里重复声明ticker

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
# MSTR/ASST 单独加进来(对应你说的"MSTR和ASST需要增加距历史高点")
ATH_TICKERS = list(WATCHLIST.values()) + list(INDICES.values()) + list(METALS.values()) + [MSTR_TICKER, ASST_TICKER]
ATH_TICKERS = [t for t in ATH_TICKERS if t]  # 过滤掉21Shares那个None占位

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
# 修正版巴菲特指标和Tobin's Q已按你的要求删除,不再抓取也不再放链接。
RISK_INDICATOR_PAGES = {
    "shiller_pe": "https://www.multpl.com/shiller-pe",
    "buffett_indicator": "https://www.currentmarketvaluation.com/models/buffett-indicator.php",
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
# 缓存日志:持久化"上次抓取时间+数据",应对进程重启
# ------------------------------------------------------------------

def _cache_snapshot():
    """从STATE里摘出需要持久化的部分,组织成方便下次读回的结构"""
    with STATE_LOCK:
        return {
            "crypto": {"btc": STATE["btc"], "crypto_extra": STATE["crypto_extra"]},
            "stock": {
                "mstr_quote": STATE.get("mstr", {}).get("quote"),
                "asst_quote": STATE.get("asst", {}).get("quote"),
                "mstr_preferreds": STATE["mstr_preferreds"],
                "watchlist": STATE["watchlist"],
                "indices": STATE["indices"],
                "metals": STATE["metals"],
            },
            "onchain": STATE["onchain"],
            "treasury": {
                "mstr": STATE.get("mstr", {}).get("treasury"),
                "asst": STATE.get("asst", {}).get("treasury"),
            },
            "gold_retail": STATE["gold_retail"],
            "risk_indicators": STATE["risk_indicators"],
            "ath": STATE["ath"],
        }


def save_cache_log():
    """把当前STATE和_last_fetch写到磁盘上的一个JSON文件里。
    用"先写临时文件再rename"的方式,避免进程如果刚好在写的时候被杀掉,
    导致缓存文件本身损坏、下次读不出来。"""
    try:
        snapshot = {
            "saved_at": time.time(),
            "last_fetch": dict(_last_fetch),
            "data": _cache_snapshot(),
        }
        tmp_path = CACHE_LOG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False)
        os.replace(tmp_path, CACHE_LOG_PATH)
    except Exception as e:
        _record_error("save_cache_log", e)


def load_cache_log():
    """启动时读回上次的缓存。核心逻辑很简单:把_last_fetch设成"上次真正抓到的
    那个时间点"(而不是0,也不是"现在"),这样每类数据各自的刷新频率判断
    (now - _last_fetch >= 对应REFRESH_SEC)会自动算对——
    - 如果距离上次抓取还没到该类别的刷新间隔,不会立刻重新请求,沿用缓存内容展示;
    - 如果已经超过该类别的刷新间隔(哪怕缓存是几天前的),会在下一轮循环里正常
      重新抓取,不会死抱着过期数据不放。
    同时,不管新不新,都会先把缓存内容读进STATE,这样刚重启的那几秒到几分钟里,
    页面上看到的是"上次的真实数据",而不是一片空白的"--"。"""
    if not os.path.exists(CACHE_LOG_PATH):
        _log("没有找到缓存日志文件,本次是首次启动,会立刻抓取一遍所有数据")
        return
    try:
        with open(CACHE_LOG_PATH, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        data = snapshot.get("data", {})
        last_fetch = snapshot.get("last_fetch", {})

        with STATE_LOCK:
            if data.get("crypto"):
                STATE["btc"] = data["crypto"].get("btc", {}) or {}
                STATE["crypto_extra"] = data["crypto"].get("crypto_extra", {}) or {}
            if data.get("stock"):
                s = data["stock"]
                STATE.setdefault("mstr", {})["quote"] = s.get("mstr_quote")
                STATE.setdefault("asst", {})["quote"] = s.get("asst_quote")
                STATE["mstr_preferreds"] = s.get("mstr_preferreds") or {}
                STATE["watchlist"] = s.get("watchlist") or {}
                STATE["indices"] = s.get("indices") or {}
                STATE["metals"] = s.get("metals") or {}
            if data.get("onchain"):
                STATE["onchain"] = data["onchain"]
            if data.get("treasury"):
                STATE.setdefault("mstr", {})["treasury"] = data["treasury"].get("mstr")
                STATE.setdefault("asst", {})["treasury"] = data["treasury"].get("asst")
            if data.get("gold_retail"):
                STATE["gold_retail"] = data["gold_retail"]
            if data.get("risk_indicators"):
                STATE["risk_indicators"] = data["risk_indicators"]
            if data.get("ath"):
                STATE["ath"] = data["ath"]

        for k, v in last_fetch.items():
            if k in _last_fetch:
                _last_fetch[k] = v

        age_min = (time.time() - snapshot.get("saved_at", 0)) / 60
        _log(f"已加载缓存日志(cache_log.json),上次保存于约{age_min:.1f}分钟前;"
             f"各类数据会按各自的刷新间隔判断是否需要立刻重新抓取,不会因为重启就被强制重新计时")
    except Exception as e:
        _record_error("load_cache_log", e)


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
            "ath_date": row.get("ath_date"),  # CoinGecko自带,精确到天,不是月
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


def _classify_zone(value, low_max, mid_max):
    """通用的三档风险分区:<=low_max 低风险(绿) / <=mid_max 中风险(黄) / 其余 高风险(红)。
    value为None时返回None,前端会显示"--"而不是硬套一个颜色。"""
    if value is None:
        return None
    if value <= low_max:
        return "low"
    if value <= mid_max:
        return "mid"
    return "high"


def fetch_risk_indicators():
    """抓席勒市盈率(multpl.com)和巴菲特指标(currentmarketvaluation.com)。
    v6修复:之前巴菲特指标解析抓错了地方(页面上随便一个不相关的百分比数字被误当成
    指标本身,你反馈看到4.5%而实际网站显示237.24%)。这次改成:
    1. 优先用更具体的短语("we calculate the Buffett Indicator as XX%")定位;
    2. 定位不到就在"Buffett Indicator"这个短语附近一个较小的窗口内找百分比数字;
    3. 不管走哪条路径抓到的数字,都会做合理性校验(巴菲特指标正常在30%-500%之间,
       席勒PE正常在3-100之间),超出范围直接丢弃当None处理,不会把明显不对的数字
       糊弄着显示出来。
    修正版巴菲特指标和Tobin's Q已按你的要求整个删除,不再抓取。"""
    out = {"shiller_pe": None, "buffett_indicator": None}

    try:
        r = requests.get(RISK_INDICATOR_PAGES["shiller_pe"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        m = re.search(r'Current\s+Shiller\s+PE\s+Ratio\s+is\s+([\d.]+)', text, re.IGNORECASE)
        val = float(m.group(1)) if m else None
        if val is None or not (3 <= val <= 100):
            val = None
        out["shiller_pe"] = val
    except Exception as e:
        _record_error("risk_indicator:shiller_pe", e)

    try:
        r = requests.get(RISK_INDICATOR_PAGES["buffett_indicator"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")

        val = None
        m = re.search(r'calculate\s+the\s+Buffett\s+Indicator\s+as\s+([\d.]+)\s*%', text, re.IGNORECASE)
        if m:
            val = float(m.group(1))

        if val is None:
            # 备用:在"Buffett Indicator"这个短语出现的地方,往后一个较小窗口内
            # (300字符)找第一个百分比数字,而不是在全文任意位置乱抓
            for m2 in re.finditer(r'Buffett\s+Indicator', text, re.IGNORECASE):
                window = text[m2.end(): m2.end() + 300]
                m3 = re.search(r'([\d]{2,3}(?:\.\d+)?)\s*%', window)
                if m3:
                    candidate = float(m3.group(1))
                    if 30 <= candidate <= 500:  # 合理性校验,排除掉明显不是这个指标的数字
                        val = candidate
                        break

        if val is not None and not (30 <= val <= 500):
            val = None  # 兜底再校验一次,不管走了哪条路径

        out["buffett_indicator"] = val
    except Exception as e:
        _record_error("risk_indicator:buffett_indicator", e)

    # 分区判定,前端直接用这个字段上色,不用自己再算一遍阈值
    # 席勒PE: <=25低风险(绿) / 25~35中风险(黄) / >35高风险(红)
    # 巴菲特指标: <=115%低风险(绿) / 115~165%中风险(黄) / >165%高风险(红)
    # 这两组阈值参考的是marketcrash.net和litefinance两个来源里给出的常见分区,
    # 不同机构口径会有出入,不代表唯一"标准答案",只是给你一个直观的三色参考。
    out["shiller_pe_zone"] = _classify_zone(out["shiller_pe"], 25, 35)
    out["buffett_indicator_zone"] = _classify_zone(out["buffett_indicator"], 115, 165)

    return out


def fetch_ath_drawdown(tickers):
    """对每个代码下载全历史月线数据,取每根月K线"最高价"(High)里的最大值作为
    历史最高价——之前v4版本用的是"收盘价"(Close)取最大值,这是个实际的bug:
    如果某个月内冲高后又回落收盘,月线收盘价会把那个盘中高点"抹平",算出来的
    ATH会偏低(黄金/白银反馈的偏差就是这个原因)。用High就不会有这个问题。
    同时记录这个最高价出现在哪个月,方便你核对。
    注意:因为是月线颗粒度,只能精确到"哪个月",不能精确到具体哪一天。

    v6改动:
    - 每个ticker单独限时(ATH_PER_TICKER_TIMEOUT_SEC),避免某一个网络请求
      卡住不动、拖慢或卡死整个ATH计算(这是之前"自选股/指数/贵金属看不到
      距历史高点"的最可能原因——不是没算,是被卡住了一直没算完)。
    - 改成每算完一个ticker就立刻写一次STATE["ath"][sym]并存一次缓存日志,
      而不是等30个全部算完才一次性写入。这样哪怕这次运行中途失败或者
      跑得比较慢,已经算出来的那些ticker也能马上在页面上看到,不用干等
      "全部或者一个都没有"。
    - 这个函数本身现在跑在独立的后台线程里(见ath_loop),不再阻塞主刷新
      循环,价格类数据不会因为ATH计算慢而被拖慢。"""
    for sym in tickers:
        try:
            hist = yf.Ticker(sym).history(period="max", interval="1mo", timeout=ATH_PER_TICKER_TIMEOUT_SEC)
            if hist is None or hist.empty:
                result = None
            else:
                idx = hist["High"].idxmax()
                result = {
                    "high": float(hist.loc[idx, "High"]),
                    "date": idx.strftime("%Y-%m"),
                }
                del hist
        except Exception as e:
            result = None
            _record_error(f"ath:{sym}", e)

        with STATE_LOCK:
            STATE.setdefault("ath", {})[sym] = result
        save_cache_log()


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
    # 过滤掉ticker为None的占位项(比如"21Shares(待确认具体标的)"),
    # 这些不发请求,直接在结果里给null,前端会显示"--"
    real_map = {name: sym for name, sym in ticker_map.items() if sym}
    symbols = list(real_map.values())
    result = {name: {"symbol": None, "price": None, "prev_close": None, "change_pct": None}
               for name in ticker_map if not ticker_map[name]}
    if not symbols:
        return result
    try:
        tk = yf.Tickers(" ".join(symbols))
        for name, sym in real_map.items():
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
                        "ath_date": btc_row.get("ath_date"),
                    }
                    STATE["crypto_extra"] = {k: v for k, v in crypto.items() if k != "BTC"}
                _last_fetch["crypto"] = now
                save_cache_log()
        except Exception as e:
            _record_error("crypto_loop", e)

        try:
            if now - _last_fetch["stock"] >= STOCK_REFRESH_SEC:
                mstr_q = fetch_quotes({"MSTR": MSTR_TICKER}).get("MSTR", {})
                asst_q = fetch_quotes({"ASST": ASST_TICKER}).get("ASST", {})
                preferreds = fetch_quotes(MSTR_PREFERREDS)
                watch = fetch_quotes(WATCHLIST)
                # MSTR/ASST/STRC 已经在别处抓过了,这里直接复用结果merge进watchlist,
                # 不再对同一个ticker重复发一次yfinance请求
                watch["策略(MSTR)"] = mstr_q
                watch["Strive(ASST)"] = asst_q
                watch["Stretch优先股(STRC)"] = preferreds.get("STRC", {})
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
                save_cache_log()
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
                save_cache_log()
        except Exception as e:
            _record_error("treasury_loop", e)

        try:
            if now - _last_fetch["onchain"] >= ONCHAIN_REFRESH_SEC:
                onchain = fetch_onchain_metrics()
                with STATE_LOCK:
                    STATE["onchain"] = onchain
                _last_fetch["onchain"] = now
                save_cache_log()
        except Exception as e:
            _record_error("onchain_loop", e)

        try:
            if now - _last_fetch["gold_retail"] >= GOLD_RETAIL_REFRESH_SEC:
                gr = fetch_gold_retail(GOLD_RETAIL_URL)
                with STATE_LOCK:
                    STATE["gold_retail"] = gr
                _last_fetch["gold_retail"] = now
                save_cache_log()
        except Exception as e:
            _record_error("gold_retail_loop", e)

        try:
            if now - _last_fetch["risk_indicator"] >= RISK_INDICATOR_REFRESH_SEC:
                ri = fetch_risk_indicators()
                with STATE_LOCK:
                    STATE["risk_indicators"] = ri
                _last_fetch["risk_indicator"] = now
                save_cache_log()
        except Exception as e:
            _record_error("risk_indicator_loop", e)

        # 注意:ATH计算不在这里了,挪到独立的ath_loop线程里跑,见文件底部main()。
        # 原因:对~30个代码逐个下载全历史数据,哪怕加了超时,总耗时也可能到
        # 分钟级别,写在这个主循环里会话价格类数据(60秒该刷新的那些)一起被拖慢。

        with STATE_LOCK:
            STATE["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        time.sleep(5)


def ath_loop():
    """独立的后台线程,专门跑ATH(历史最高价)计算,不和主刷新循环共用一个线程,
    这样哪怕这里跑得很慢(逐个ticker网络请求),也不会拖慢BTC/股票/指数这些
    价格类数据的刷新。"""
    while True:
        now = time.time()
        try:
            if ENABLE_ATH_DRAWDOWN and now - _last_fetch["ath"] >= ATH_REFRESH_SEC:
                _log(f"开始计算ATH,共{len(ATH_TICKERS)}个代码,单个超时{ATH_PER_TICKER_TIMEOUT_SEC}秒...")
                fetch_ath_drawdown(ATH_TICKERS)  # 内部会边算边写STATE,不需要接返回值
                _last_fetch["ath"] = now
                _log("ATH计算完成一轮")
        except Exception as e:
            _record_error("ath_loop", e)
        time.sleep(60)  # 这个线程本身检查频率可以放松,不用像主循环那样5秒一次


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
    load_cache_log()
    t = threading.Thread(target=refresh_loop, daemon=True)
    t.start()
    t2 = threading.Thread(target=ath_loop, daemon=True)
    t2.start()
    _log(f"启动: http://0.0.0.0:{PORT}  (数据接口: /api/data, 页面: /)")
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
