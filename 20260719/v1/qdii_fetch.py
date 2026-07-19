#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国QDII基金监控脚本 (qdii_fetch.py) — v1
================================================
和stock500_fetch.py同一个模式:完全独立于dashboard主程序(server.py),不共用
进程/内存,通过cron定时触发,跑完就退出,不常驻。

数据来源:
  - 净值历史(用于算波动情况):天天基金网(eastmoney)的pingzhongdata接口,
    形如 https://fund.eastmoney.com/pingzhongdata/{code}.js ,这是公开的、
    不需要登录的JS文件,里面有一个JS变量Data_netWorthTrend记录了完整的
    单位净值历史(每天一条,{x:时间戳毫秒, y:净值, equityReturn:当日涨跌幅%})。
  - 购买限制/申购状态:天天基金网基金详情页 https://fund.eastmoney.com/{code}.html
    的HTML里有"限大额申购"/"暂停申购"/"单日累计限额XX元"这类文字说明。

【关于购买限制这部分的诚实说明】
天天基金网的详情页是有可能随时间改版的,这里用的是"在页面全文里搜关键词
(限购/暂停申购/限额/大额/暂停大额)、截取关键词前后一小段文字"这种偏"宽松"的
解析方式,而不是靠死板的CSS选择器——这样即使页面局部改版,大概率还能抓到那句话,
但相应地也可能抓到不完全相关的文字,或者偶尔抓不到。这部分我没有拿真实网络
访问验证过(当前开发环境没有联网权限),第一次上到你的VPS后,建议先用
--limit 3 跑一遍,人工核对几只基金的purchase_limit_note字段是否讲得通,
不对的话告诉我调整关键词/解析逻辑。

波动情况(年化波动率/最大回撤/近3月及近1年涨跌幅)这部分是基于净值历史自己算的
标准统计量,不依赖网页文字解析,相对可靠。

用法:
    python3 qdii_fetch.py            # 跑全部基金
    python3 qdii_fetch.py --limit 3  # 只跑前3只,第一次测试用

依赖:
    pip install --break-system-packages requests beautifulsoup4
"""

import argparse
import json
import math
import os
import random
import re
import sys
import time
import traceback
from datetime import datetime, timedelta

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("请先: pip install --break-system-packages beautifulsoup4")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON_PATH = os.path.join(SCRIPT_DIR, "cache_qdii.json")

REQUEST_TIMEOUT_SEC = 15
PER_FUND_DELAY_RANGE = (2, 5)  # 每只基金之间的随机间隔,降低被限流的风险

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/",
}

# 名字来自你给的清单,key是基金全名,value是6位基金代码(从你给的pingzhongdata URL里提取)
FUNDS = {
    "大成纳斯达克100ETF联接(QDII)A": "000834",
    "华泰柏瑞纳斯达克100ETF发起式联接(QDII)A": "019524",
    "易方达纳斯达克100ETF联接(QDII-LOF)A(人民币)": "161130",
    "汇添富纳斯达克100ETF发起式联接(QDII)人民币A": "018966",
    "摩根纳斯达克100指数(QDII)人民币A": "019172",
    "南方纳斯达克100指数发起(QDII)A": "016452",
    "华宝纳斯达克精选股票发起式(QDII)C": "017437",
    "嘉实纳斯达克100ETF发起联接(QDII)A人民币": "016532",
    "华宝纳斯达克精选股票发起式(QDII)A": "017436",
    "国泰纳斯达克100指数": "160213",
    "天弘纳斯达克100指数发起[QDII]A": "018043",
    "博时标普500ETF联接A": "050025",
    "天弘标普500发起[QDII-FOF]A": "007721",
    "大成标普500等权重指数[QDII]A人民币": "096001",
    "摩根标普500指数[QDII]人民币A": "017641",
    "天弘标普500发起[QDII-FOF]C": "007722",
    "易方达标普500指数(QDII-LOF)A": "161125",
    "摩根标普500指数[QDII]人民币C": "019305",
    "华夏标普500ETF发起式联接(QDII)A": "018064",
    "大成标普500等权重指数[QDII]C人民币": "008401",
    "国泰标普500ETF发起联接[QDII]A人民币": "017028",
    "易方达标普消费品指数增强(QDII)A(人民币份额)": "118002",
    "南方道琼斯美国精选REIT指数C": "160141",
    "广发道琼斯石油指数(QDII-LOF)C": "004243",
    "银华道琼斯88精选指数": "180003",
    "南方道琼斯美国精选REIT指数A": "160140",
    "宏利印度股票(QDII)C": "026015",
    "工银印度基金人民币": "164824",
    "宏利印度股票(QDII)A": "006105",
}


def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------
# 第一步:净值历史 + 波动情况(pingzhongdata JS)
# ------------------------------------------------------------------

def fetch_nav_history(code):
    """抓 https://fund.eastmoney.com/pingzhongdata/{code}.js ,从里面正则提取
    Data_netWorthTrend这个JS数组(单位净值历史,{x:毫秒时间戳, y:净值}),
    返回按时间正序排好的[(datetime, nav), ...]列表。抓不到/解析失败返回空列表,
    不是抛异常中断整个脚本。"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEC)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        _log(f"  抓取pingzhongdata失败({code}): {e}")
        return []

    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\])\s*;", text, re.S)
    if not m:
        _log(f"  没有在pingzhongdata里找到Data_netWorthTrend({code}),页面结构可能变了")
        return []
    raw = m.group(1)
    try:
        arr = json.loads(raw)
    except Exception as e:
        _log(f"  解析Data_netWorthTrend失败({code}): {e}")
        return []

    out = []
    for item in arr:
        try:
            x = item.get("x")
            y = item.get("y")
            if x is None or y is None:
                continue
            dt = datetime.utcfromtimestamp(x / 1000.0)
            out.append((dt, float(y)))
        except Exception:
            continue
    out.sort(key=lambda p: p[0])
    return out


def compute_volatility_stats(nav_history):
    """基于净值历史算:年化波动率、历史最大回撤、近3个月涨跌幅、近1年涨跌幅。
    年化波动率用日收益率标准差×sqrt(242)(A股/QDII基金通常按一年242个交易日估算,
    不是完全精确的242,只是行业里常用的近似值)。样本太短(少于30个净值点)的
    直接返回None,不硬算一个没有统计意义的数字。"""
    out = {
        "annualized_volatility_pct": None,
        "max_drawdown_pct": None,
        "return_3m_pct": None,
        "return_1y_pct": None,
        "latest_nav": None,
        "latest_date": None,
    }
    if len(nav_history) < 2:
        return out

    out["latest_nav"] = nav_history[-1][1]
    out["latest_date"] = nav_history[-1][0].strftime("%Y-%m-%d")

    navs = [p[1] for p in nav_history]

    if len(navs) >= 30:
        daily_returns = [(navs[i] / navs[i - 1] - 1) for i in range(1, len(navs)) if navs[i - 1]]
        if len(daily_returns) >= 20:
            mean = sum(daily_returns) / len(daily_returns)
            var = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std = math.sqrt(var)
            out["annualized_volatility_pct"] = std * math.sqrt(242) * 100

    # 历史最大回撤:遍历净值序列,记录目前为止的历史最高点,算每一点相对最高点的回撤,取最深的一次
    peak = navs[0]
    max_dd = 0.0
    for v in navs:
        if v > peak:
            peak = v
        dd = (v / peak - 1) * 100 if peak else 0
        if dd < max_dd:
            max_dd = dd
    out["max_drawdown_pct"] = max_dd

    latest_dt, latest_nav = nav_history[-1]

    def _return_since(cutoff_dt):
        candidates = [p for p in nav_history if p[0] <= cutoff_dt]
        if not candidates:
            return None
        base_nav = candidates[-1][1]
        if not base_nav:
            return None
        return (latest_nav / base_nav - 1) * 100

    out["return_3m_pct"] = _return_since(latest_dt - timedelta(days=91))
    out["return_1y_pct"] = _return_since(latest_dt - timedelta(days=365))
    return out


# ------------------------------------------------------------------
# 第二步:购买限制/申购状态(基金详情页文字解析,见文件头的说明)
# ------------------------------------------------------------------

PURCHASE_LIMIT_KEYWORDS = ["暂停申购", "暂停大额申购", "限大额申购", "大额限购",
                           "单日累计限额", "单日限额", "限购", "暂停定投"]


def fetch_purchase_limit_note(code):
    """从基金详情页全文文字里搜关键词,截取关键词前后一小段作为"购买限制说明"。
    这是宽松的文字匹配,不是结构化解析,详见文件头的说明。抓不到/没有限购关键词
    的情况下返回None(表示"目前看起来正常申购,或者没抓到相关文字",这两种情况
    这个脚本区分不了,只能老实返回None,不能替你下"正常申购"这个结论)。"""
    url = f"https://fund.eastmoney.com/{code}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEC)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        full_text = soup.get_text(separator=" ", strip=True)
    except Exception as e:
        _log(f"  抓取基金详情页失败({code}): {e}")
        return None

    for kw in PURCHASE_LIMIT_KEYWORDS:
        idx = full_text.find(kw)
        if idx != -1:
            start = max(0, idx - 15)
            end = min(len(full_text), idx + len(kw) + 25)
            snippet = full_text[start:end].strip()
            return snippet
    return None


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="中国QDII基金波动情况+购买限制监控")
    parser.add_argument("--limit", type=int, default=None,
                        help="只处理前N只(用于第一次测试,建议先用--limit 3跑一遍)")
    args = parser.parse_args()

    items = list(FUNDS.items())
    if args.limit:
        items = items[:args.limit]
        _log(f"--limit参数生效,只处理前{len(items)}只(测试模式)")

    results = []
    for i, (name, code) in enumerate(items):
        _log(f"[{i+1}/{len(items)}] 处理 {name}({code})...")
        row = {"name": name, "code": code,
               "eastmoney_url": f"https://fund.eastmoney.com/{code}.html"}
        try:
            nav_history = fetch_nav_history(code)
            row.update(compute_volatility_stats(nav_history))
            row["nav_points_count"] = len(nav_history)
        except Exception as e:
            _log(f"  净值历史处理失败({code}): {e}")
            traceback.print_exc()
            row.update({
                "annualized_volatility_pct": None, "max_drawdown_pct": None,
                "return_3m_pct": None, "return_1y_pct": None,
                "latest_nav": None, "latest_date": None, "nav_points_count": 0,
            })

        time.sleep(random.uniform(*PER_FUND_DELAY_RANGE))

        try:
            row["purchase_limit_note"] = fetch_purchase_limit_note(code)
        except Exception as e:
            _log(f"  购买限制解析失败({code}): {e}")
            row["purchase_limit_note"] = None

        results.append(row)

        if i < len(items) - 1:
            time.sleep(random.uniform(*PER_FUND_DELAY_RANGE))

    output = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(results),
        "funds": results,
    }
    tmp_path = OUTPUT_JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    os.replace(tmp_path, OUTPUT_JSON_PATH)
    _log(f"全部完成,写入 {OUTPUT_JSON_PATH},共{len(results)}条")


if __name__ == "__main__":
    main()
