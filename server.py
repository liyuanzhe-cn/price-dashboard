#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人参考看板 - 后端数据代理 (v2)
================================
改动(相对v1):
  - MSTR / ASST 不再依赖手动输入 BTC持仓/股数/债务。
    改为直接抓取 bitcointreasuries.net 上两个公司页面里已经算好的字段:
    BTC Holdings / BTC Value / Total Cost Basis / Avg Cost per BTC /
    Market Cap / Enterprise Value / mNAV(EV) / mNAV(Basic) / mNAV(Diluted) /
    BTC per Share(Basic) / BTC per Share(Diluted)
  - STRC/STRD/STRF/STRK 仍走雅虎财经拿现价+涨跌幅,链接改成指向
    bitcointreasuries.net/digital-credit/{TICKER}(该页面本身还会显示Yield/Rate,
    只是价格字段是前端异步加载的,静态抓不到,所以价格还是走雅虎)。

依赖:
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

CRYPTO_REFRESH_SEC = 30            # BTC现价
STOCK_REFRESH_SEC = 60             # 普通股票/指数/优先股现价
TREASURY_REFRESH_SEC = 20 * 60     # bitcointreasuries.net 抓取频率(你说60秒或几小时都行,
                                    # 这里默认20分钟,避免频繁请求同一个页面被限流/封IP;
                                    # 想要更快就调小这个数字)
ONCHAIN_REFRESH_SEC = 8 * 3600     # MVRV系列,受BGeometrics免费额度限制,不要调快

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
    "KOSPI": "^KS11",
    "NIFTY 50": "^NSEI",
    "SENSEX": "^BSESN",
    "上证指数": "000001.SS",
    "沪深300": "000300.SS",
    "台湾50(0050)": "0050.TW",  # TODO: 如果指台湾加权指数而非0050 ETF,改成 ^TWII
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
    "links": LINKS,
    "errors": [],
}

_last_fetch = {"crypto": 0, "stock": 0, "onchain": 0, "treasury": 0}


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

def fetch_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()["bitcoin"]
    return {"price_usd": data["usd"], "change_24h_pct": data.get("usd_24h_change")}


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


def _find_after_label(text, label, pattern, flags=0):
    """在纯文本里找 label 之后第一处匹配 pattern 的内容(容忍中间有换行/空白)"""
    m = re.search(re.escape(label) + r'\s*\n*\s*' + pattern, text, flags)
    return m.group(1) if m else None


def fetch_treasury_page(url):
    """抓取 bitcointreasuries.net 的公司页面,解析出BTC持仓/市值/mNAV等已算好的字段。
    解析不到的字段一律返回None,不用假数据填充。"""
    out = {
        "btc_holdings": None, "btc_value": None, "total_cost_basis": None, "avg_cost_per_btc": None,
        "market_cap": None, "enterprise_value": None,
        "mnav_ev": None, "mnav_basic": None, "mnav_diluted": None,
        "btc_per_share_basic": None, "btc_per_share_diluted": None,
        "as_of": None,
    }
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r'\n{2,}', '\n', text)  # 压缩多余空行,方便正则匹配

    raw = {}
    raw["btc_holdings"] = _find_after_label(text, "BTC Holdings", r'(₿[\d,\.]+)')
    raw["as_of"] = _find_after_label(text, "As of", r'([^\n]+)')
    raw["btc_value"] = _find_after_label(text, "BTC Value", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["total_cost_basis"] = _find_after_label(text, "Total Cost Basis", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["avg_cost_per_btc"] = _find_after_label(text, "Avg Cost / BTC", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["market_cap"] = _find_after_label(text, "Market Cap", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["enterprise_value"] = _find_after_label(text, "Enterprise Value", r'(\$[\d,\.]+\s*[BMK]?)')
    raw["mnav_ev"] = _find_after_label(text, "mNAV (EV)", r'([\d\.]+×)')
    raw["mnav_basic"] = _find_after_label(text, "mNAV (Basic)", r'([\d\.]+×)')
    raw["mnav_diluted"] = _find_after_label(text, "mNAV (Diluted)", r'([\d\.]+×)')
    raw["btc_per_share_basic"] = _find_after_label(text, "BTC / Share (Basic)", r'([\d\.]+)')
    raw["btc_per_share_diluted"] = _find_after_label(text, "BTC / Share (Diluted)", r'([\d\.]+)')

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
    return out


# ------------------------------------------------------------------
# 后台刷新循环
# ------------------------------------------------------------------

def refresh_loop():
    while True:
        now = time.time()

        try:
            if now - _last_fetch["crypto"] >= CRYPTO_REFRESH_SEC:
                btc = fetch_btc_price()
                with STATE_LOCK:
                    STATE["btc"] = btc
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
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["quote"] = mstr_q
                    STATE.setdefault("asst", {})["quote"] = asst_q
                    STATE["mstr_preferreds"] = preferreds
                    STATE["watchlist"] = watch
                    STATE["indices"] = idx
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
