#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国QDII基金监控脚本 (qdii_fetch.py) — v1.1
================================================
和stock500_fetch.py同一个模式:完全独立于dashboard主程序(server.py),不共用
进程/内存,通过cron定时触发,跑完就退出,不常驻。

数据来源:全部来自天天基金网(eastmoney)的pingzhongdata接口,形如
https://fund.eastmoney.com/pingzhongdata/{code}.js ,这是公开的、不需要登录的
JS文件,一次请求里同时包含:
  - Data_netWorthTrend:完整的单位净值历史(每天一条,{x:时间戳毫秒, y:净值}),
    用来自己算年化波动率/最大回撤/近3月及近1年涨跌幅。
  - fund_minsg:基金公司公开设定的"最小申购金额"(人民币元/次)。

v1.1修正(你反馈的问题):之前"购买限制"这栏是从基金详情页全文文字里搜"限购"
"暂停申购"这类关键词做宽松匹配,你指出这个思路不对——应该直接读pingzhongdata
里现成的 /*最小申购金额*/var fund_minsg="10"; 这个字段,这个数字才是基金公司
公开设定的最小申购起点(人民币元),不需要猜。这版已经改成直接读这个字段,并且
和净值历史合并成一次请求(之前是两个请求,分别打详情页和pingzhongdata,现在
只打pingzhongdata一个URL,请求量减半)。
注意:这个字段只是"最小申购金额起点",不代表"当前是否限购/限购到多少"——
QDII基金的实时限购额度(比如"单日限大额500元")本身经常变动,且通常只在APP/
官网下单页面才会实时提示,这个字段抓不到那类信息,如果你需要那个,需要额外
再确认eastmoney有没有更合适的公开接口。

用法:
    python3 qdii_fetch.py            # 跑全部基金
    python3 qdii_fetch.py --limit 3  # 只跑前3只,第一次测试用

依赖:
    pip install --break-system-packages requests
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

def fetch_pingzhongdata(code):
    """抓 https://fund.eastmoney.com/pingzhongdata/{code}.js 原始文本,一次请求
    同时给fetch_nav_history和fetch_min_purchase_amount复用,不用为了两个不同的
    字段重复请求同一个URL两次。抓不到返回None。"""
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SEC)
        r.raise_for_status()
        return r.text
    except Exception as e:
        _log(f"  抓取pingzhongdata失败({code}): {e}")
        return None


def fetch_nav_history(pingzhong_text, code):
    """从pingzhongdata原始文本里正则提取Data_netWorthTrend这个JS数组
    (单位净值历史,{x:毫秒时间戳, y:净值}),返回按时间正序排好的
    [(datetime, nav), ...]列表。抓不到/解析失败返回空列表,不是抛异常中断整个脚本。"""
    if not pingzhong_text:
        return []
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\])\s*;", pingzhong_text, re.S)
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


def fetch_min_purchase_amount(pingzhong_text, code):
    """v27.1改用你指出的更准确的字段:pingzhongdata这份JS里有一行
    /*最小申购金额*/var fund_minsg="10"; ——这是基金公司公开设定的最小单次
    申购金额(人民币元),不是之前那种"从网页全文里搜关键词猜购买限制"的宽松
    匹配方式,更可靠、也更贴合你说的"中国QDII限额总变化"这个实际使用场景
    (每天登录APP看实时能申购多少,这个"最小申购金额"字段本身不会天天变,
    但比之前瞎猜靠谱)。抓不到返回None。"""
    if not pingzhong_text:
        return None
    m = re.search(r'var\s+fund_minsg\s*=\s*"([^"]*)"', pingzhong_text)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


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
            pingzhong_text = fetch_pingzhongdata(code)
            nav_history = fetch_nav_history(pingzhong_text, code)
            row.update(compute_volatility_stats(nav_history))
            row["nav_points_count"] = len(nav_history)
            row["min_purchase_amount_rmb"] = fetch_min_purchase_amount(pingzhong_text, code)
        except Exception as e:
            _log(f"  处理失败({code}): {e}")
            traceback.print_exc()
            row.update({
                "annualized_volatility_pct": None, "max_drawdown_pct": None,
                "return_3m_pct": None, "return_1y_pct": None,
                "latest_nav": None, "latest_date": None, "nav_points_count": 0,
                "min_purchase_amount_rmb": None,
            })

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
