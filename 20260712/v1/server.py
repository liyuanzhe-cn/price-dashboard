#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人参考看板 - 后端数据代理 (v11)
================================
v11改动(回应"请求过于集中"的顾虑 + 新增BTC顶底指标 + 风险指标卡片放大加图表):

1. 调度策略重新设计,分两档:
   - "实时价格"档(BTC/加密货币/股票/指数/贵金属现价):还是60秒左右一次,但同一轮
     里几个子请求(mstr/asst/preferreds/watch/idx/metals)之间插入1-4秒随机间隔,
     不再同时发出去。
   - "每日更新"档(on-chain指标/风险指标/bitcointreasuries/周大福金价/ATH历史最高价):
     这些数据源本身可能一天才更新一次。规则:没抓到过就立刻抓,抓到过就等到每天
     美东时间07:XX(XX是启动时随机出来的分钟数,不同部署不会全部撞在整点)。
     原来那几个不同的REFRESH_SEC(8小时/12小时/3小时/20分钟)都统一成这一套。

2. BTC面板新增6项顶底指标:CVDD、NUPL、RHODL比率、200周均线、盈利中的百分比、
   BTC60日累计涨幅。你给的looknode.com链接我实测过,是纯客户端渲染,静态请求
   拿不到数值,所以没有直接用它——这6项里前5个改用我们已经在用的bgeometrics.com
   /bitcoin-data.com(和MVRV那几个同一个数据源,不是新引入的站点),60日涨幅用
   CoinGecko历史价格自己算。链接还是指向looknode.com方便你看图,但数字来源和
   链接指向的网站不是同一个,这一点说清楚。TODO: cvdd/nupl/rhodl/200周均线/
   盈利占比这5个新endpoint的路径名是根据bgeometrics官网文案推断的,没有实测过,
   抓不到就是null,需要你部署后核对。

3. 股市风险指标卡片整个放大重做:
   - 桌面端自动排成两栏(每张卡片最小440px宽,屏幕够宽会显示2栏,更宽会更多栏);
     手机端自动变成一栏,卡片里的图表图片占满宽度显示,视觉上更大更清楚。
     我没有用CSS强制横屏(这个不可靠、支持不好),而是让图表本身用全宽显示,
     达到"看起来更大"的效果,这点和你想要的"横屏"不完全是一回事,先说清楚。
   - 每张卡片现在会嵌入currentmarketvaluation.com官方的图表图片(从页面里提取的
     真实图片地址,不是我自己画的),外链引用。这几张图是这些网站自己托管在
     imgix这类CDN上的公开图片,通常允许被其他网站外链引用,但我没法在这个环境
     里用真实浏览器验证会不会被防盗链拦截——如果部署后发现图裂了(显示不出来),
     需要告诉我,那样就得改成后端下载图片再转发这种更麻烦的方式。
   - macromicro.me(你提到的另一个巴菲特指标数据源)我尝试访问时直接被识别成
     机器人拦截了,这说明服务器用简单请求大概率也会被拦,所以没有新增这个数据源,
     继续只用currentmarketvaluation.com。

依赖(和v10一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v10)
================================
v10修复:v9里6个CMV模型的评级词全部抓不到(你反馈的"一个评级都没有,鼠标悬停也没
内容")——真实原因是v9的代码把评级词搜索范围限制在页面前800个字符以内,但实际
评级徽章在页面导航/头部内容之后才出现,根本不在这个范围里,所以全军覆没。
v10改成不限制搜索范围,但用更精确的结构模式("is"后面跟着空行再跟评级词,这是
CMV官方评级徽章固定的排版结构)去匹配,兼顾"抓得到"和"不容易抓错"。

另外这次改动的重点是交互方式:v9把评级说明放在鼠标悬停的title提示里,你反馈不想
要这种交互,想要不用悬停就能直接看到。v10把风险指标从原来的紧凑单行,改成更高的
卡片:名称、数值、评级色块、说明文字全部常驻显示在卡片上,不需要做任何操作。

依赖(和v9一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v9)
================================
v9改动(以中文显示为主,看着更舒适 + 风险指标大幅扩充):
  - "Bitcoin"→"比特币","Strategy"badge→"微策略"。
  - 自选股:"Adobe(ADBE)"→"奥多比(ADBE)";移除"Stretch优先股(STRC)"(它还在优先股
    面板里,只是不在自选股列表重复出现);新增"南希佩洛西(NANC)"——这是Unusual
    Whales的一只ETF,跟踪美国国会民主党议员(以南希·佩洛西为代表)的股票交易。
  - 指数:全部改成中文名,新增日经225(^N225)和DFMREI迪拜房地产指数(DFMREI.AE)。
  - 其他加密货币:重新排序(泰达黄金稳定币在最前),改中文名。注意:你原话写的是
    "ADA改为以太坊(ADA)",这应该是笔误(以太坊已经用在ETH上了),ADA对应的项目叫
    Cardano,中文通常译作"艾达币",按这个改的;HYPE/BNB/BGB/OKB你没有给改名指令,
    保留原样。顺带把加密货币的coingecko_id直接放进后端返回的数据里,前端不用再
    单独维护一份"名字→id"的映射表,以后改名字不会出现两边不同步的问题。
  - 股市风险指标大幅扩充:新增市盈率(P/E10)、标普500市销率(P/S)、10年期美债利率、
    均值回归偏离度、股债收益差,加上原有的巴菲特指标,这6个全部来自
    currentmarketvaluation.com,核实过它们统一用同一套评级体系(官方"Our Ratings"
    页面:按偏离历史均值的标准差数量分5档,强烈低估/低估/合理/高估/强烈高估),
    所以这6个共用同一套解析逻辑和图例,不用分别发明阈值。顺带把之前巴菲特指标
    那个解析bug用这套更可靠的通用逻辑重做了一遍。席勒PE(multpl.com)保留,
    维持它自己原来的3档分区,和上面6个不是同一套体系,不能混着比较。

依赖(和v8一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v8)
================================
v8新增:非交易时段用加密交易所的24/7股票永续合约价格做替代,不再只显示雅虎财经的
昨收价。
  - 数据源:Bitget的USDT永续合约公开行情接口(不需要API Key)。经核实Bitget现在
    确实挂了TSLA/NVDA/AAPL/MSTR/META/GOOGL/AMZN/CRCL等30多个热门美股的永续合约,
    7×24小时交易。
  - 覆盖范围:只覆盖自选股里能对上的美股 + MSTR + ASST。SK海力士/三星/LG/
    Metaplanet(非美股)、指数、贵金属、优先股(STRC/D/F/K)都没有对应产品,
    休市时依然只能看到雅虎财经的昨收价,这是已知的、没有解决的限制。
  - 这不是"同一个东西":加密交易所的股票永续合约是跟踪股价的衍生品,跟交易所
    官方成交价存在正常基差,不是100%相等。前端会在这类价格旁边标一个醒目的
    "夜盘·Bitget"标签,不会不声不响地替换掉,鼠标悬停能看到具体说明。
  - 开盘时段判断:只按"周一到周五,纽约时间9:30-16:00"这个规则,没有排除美股
    法定假日(感恩节、独立日等),那几天会被误判成"开盘中",继续用雅虎财经的
    (过时的)数据,这是刻意的简化。
  - GOOG在Bitget上对应的是GOOGL(A类股,不是我们平时看的C类股),这两者股价
    非常接近但不是同一只股票,这个差异在代码注释里写清楚了,没有隐藏。
  - Gate、Binance这类交易所的同类产品这次没接,只核实清楚了Bitget的公开接口,
    以后需要的话可以再加。

依赖(和v7一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
v7改动(相对v6,修复"旧缓存拖累新代码"这个问题):
  - 加了cache_log.json的schema版本号校验(CACHE_SCHEMA_VERSION)。
    v6虽然把ATH/巴菲特指标/风险分区这些都修好了,但你VPS上原来那份
    cache_log.json是v6之前生成的旧格式(ath是纯数字、risk_indicators没有
    zone字段),因为它的时间戳看起来"还没到重新抓取的时间",v6的代码就
    误信了这份过时数据,导致你看不到任何修复效果——本质上不是v6的逻辑错了,
    是旧缓存把新逻辑"挡在了外面"。
    v7给缓存文件加了版本号,版本号对不上就整份当成不存在,强制立刻重新抓取,
    以后再升级也不会被老缓存坑。
  - 21Shares 相关的历史TODO注释顺便清理了一下,避免看起来像还没删干净
    (实际WATCHLIST字典从v6起就已经没有这一项了)。

依赖(和v6一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
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
    LG/Adobe/Metaplanet,能配中文名的都配了中文名。(21Shares最初曾放了个占位,
    v6已按要求整个删除,详见下方v6说明)
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
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo
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

# 缓存文件的"schema版本号"。每次数据结构有实质性变化(比如这次ath从纯数字改成
# {high,date}对象、risk_indicators加了zone字段),就把这个数字加1。
# 启动时如果发现缓存文件里记录的版本号和这里不一致,会整份缓存当成"不存在"处理,
# 强制所有类别立刻重新抓取一遍——不会出现"旧格式缓存因为时间戳看起来还新,
# 就被新代码误当成可信数据继续沿用"这种情况(这正是这次你反馈的三个问题的根因)。
CACHE_SCHEMA_VERSION = 4  # 这次onchain/风险指标的数据结构都变了(新增字段),版本号加1强制清缓存重来

# TODO: 去 https://portal.bgeometrics.com/login 免费注册后填在这里
BGEOMETRICS_TOKEN = ""

# ------------------------------------------------------------------
# v11重新设计的调度策略(回应你说的"请求过于集中"这个顾虑):
# ------------------------------------------------------------------
# 分两档:
#   "实时价格"档:BTC/加密货币/股票/指数/贵金属现价,还是60秒左右一次,但同一轮里
#     几个子请求之间会插入1-4秒的随机间隔,不再一股脑同时打出去。
#   "每日更新"档:on-chain指标、风险指标、bitcointreasuries、周大福金价、ATH历史最高价——
#     这些数据源本身可能一天就更新一次,没必要频繁请求。规则是:
#       - 如果这类数据从来没抓到过(缓存里没有),立刻抓一次,不等到第二天;
#       - 如果已经抓到过,那就等到"每天美东时间07:XX"这个固定窗口再抓一次,
#         XX是程序每次启动时随机出来的分钟数(0-59),这样不同人的部署不会全部
#         挤在整点抓取,分散服务器压力。同一天只会真正抓取一次。
US_EASTERN = ZoneInfo("America/New_York")
DAILY_JOB_HOUR_ET = 7
_daily_job_minute_offset = random.randint(0, 59)
_log_startup_msg = f"本次启动随机到的每日更新分钟数是: {DAILY_JOB_HOUR_ET:02d}:{_daily_job_minute_offset:02d} (美东时间)"

CRYPTO_REFRESH_SEC = 30            # 所有加密货币(含BTC)批量现价
STOCK_REFRESH_SEC = 60             # 普通股票/指数/优先股/贵金属期货现价
STOCK_FETCH_JITTER_SEC = (1, 4)    # 同一轮里,每个子请求(mstr/asst/preferreds/watch/idx/metals)
                                    # 之间随机插入这么多秒的间隔,不再同时发出去

# ---- ATH(历史最高价)/回撤计算开关 ----
ENABLE_ATH_DRAWDOWN = True
ATH_PER_TICKER_TIMEOUT_SEC = 20  # 单个ticker超过这个时间还没返回就放弃,避免卡住整个ATH线程

ONCHAIN_ENDPOINTS = {
    "mvrv": "mvrv",
    "mvrv_zscore": "mvrv-zscore",
    "realized_price": "realized-price",
    "balanced_price": "balanced-price",
    # 下面5个是v11新加的,同样来自bgeometrics.com/bitcoin-data.com(和上面4个同一个数据源,
    # 不是引入新站点)。TODO: 这几个endpoint的具体路径名是我根据bgeometrics官网的产品介绍
    # 文案推断的,没有实际调用测试过,如果部署后发现某一个一直是null,大概率是路径名不对,
    # 去 https://bitcoin-data.com/api/scalar.html 的交互式文档核对真实路径再改。
    "cvdd": "cvdd",
    "nupl": "nupl",
    "rhodl": "rhodl-ratio",
    "ma_200w": "200-week-moving-average",
    "supply_in_profit_pct": "percent-supply-in-profit",
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
    "奥多比(ADBE)": "ADBE",
    "Metaplanet(3350.T)": "3350.T",
    "南希佩洛西(NANC)": "NANC",  # Unusual Whales跟踪美国国会民主党议员(以南希·佩洛西为代表)股票交易的ETF
}
# MSTR/ASST/STRC 会在refresh_loop里额外合并进watchlist,不在这里重复声明ticker

INDICES = {
    "纳斯达克综合指数": "^IXIC",
    "纳斯达克100指数": "^NDX",
    "标普500指数": "^GSPC",
    "费城半导体指数": "^SOX",
    "罗素2000指数": "^RUT",
    "道琼斯指数": "^DJI",
    "纽约综合指数": "^NYA",
    "韩国KOSPI": "^KS11",
    "印度50指数NIFTY 50": "^NSEI",
    "孟买敏感指数SENSEX": "^BSESN",
    "上证指数": "000001.SS",
    "沪深300": "000300.SS",
    "台湾50(0050)": "0050.TW",  # TODO: 如果指台湾加权指数而非0050 ETF,改成 ^TWII
    "日经指数Nikkei 225": "^N225",
    "DFMREI 迪拜房地产指数": "DFMREI.AE",
}

# ---- 非交易时段用加密交易所24/7股票永续合约价格做替代 ----
# 只覆盖美股(自选股里能对上的那些),指数/贵金属/优先股/非美股(SK海力士、三星、
# LG、Metaplanet)没有对应产品,休市时依然只能看到雅虎财经的昨收价,这是已知限制。
BITGET_TICKERS_URL = "https://api.bitget.com/api/v2/mix/market/tickers"
BITGET_PRODUCT_TYPE = "USDT-FUTURES"

# 我们内部用的ticker -> Bitget永续合约symbol 的映射。大部分是"ticker去掉横杠+USDT"
# 这个规律,但有几个例外需要手动指定(比如GOOG我们用的是Alphabet C类股,Bitget挂的是
# GOOGL,也就是A类股——这两者股价非常接近但不是同一个股票,这个差异我没有替你隐藏)。
BITGET_SYMBOL_OVERRIDES = {
    "GOOG": "GOOGL",   # 注意: Bitget挂的是GOOGL(A类股),不是GOOG(C类股),股价会有细微差异
    "BRK-B": None,     # 没有确认Bitget有挂这个,交给下面的动态检测,查不到就跳过
}

US_MARKET_TZ = ZoneInfo("America/New_York")


def is_us_market_open(now_utc=None):
    """判断美股是否在常规交易时段内(周一到周五,纽约时间9:30-16:00)。
    注意:这里没有排除美股法定假日(比如感恩节、独立日),那几天会被误判成"开盘中",
    继续显示雅虎财经的(过时的)数据,这是刻意的简化,不是没考虑到。"""
    now_utc = now_utc or datetime.now(ZoneInfo("UTC"))
    now_et = now_utc.astimezone(US_MARKET_TZ)
    if now_et.weekday() >= 5:  # 5=周六, 6=周日
        return False
    open_minutes = 9 * 60 + 30
    close_minutes = 16 * 60
    cur_minutes = now_et.hour * 60 + now_et.minute
    return open_minutes <= cur_minutes < close_minutes


def fetch_bitget_stock_perps(tickers):
    """拉Bitget全部USDT永续合约的行情,从里面挑出tickers里我们关心的股票永续合约。
    这是公开接口,不需要API Key。返回 {ticker: {"price":.., "change_pct":.., "bitget_symbol":..}}
    抓不到的(网络问题,或者这个ticker根本没有对应的永续合约)会被跳过,不强行伪造。"""
    try:
        r = requests.get(BITGET_TICKERS_URL, params={"productType": BITGET_PRODUCT_TYPE}, timeout=15)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", [])
        by_symbol = {row["symbol"]: row for row in rows if "symbol" in row}
    except Exception as e:
        _record_error("bitget_stock_perps", e)
        return {}

    out = {}
    for ticker in tickers:
        if not ticker:
            continue
        override = BITGET_SYMBOL_OVERRIDES.get(ticker, "__default__")
        if override is None:
            continue  # 明确标记为"不去查"的,跳过
        base = override if override != "__default__" else ticker
        bitget_symbol = base.replace("-", "").upper() + "USDT"
        row = by_symbol.get(bitget_symbol)
        if not row:
            continue
        try:
            price = float(row.get("lastPr"))
            open24h = float(row.get("open24h") or 0) or None
            change_pct = None
            if open24h:
                change_pct = (price / open24h - 1) * 100
            out[ticker] = {"price": price, "change_pct": change_pct, "bitget_symbol": bitget_symbol}
        except Exception as e:
            _record_error(f"bitget_stock_perps:{bitget_symbol}", e)
    return out
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
ATH_TICKERS = [t for t in ATH_TICKERS if t]  # 兜底过滤None(目前WATCHLIST里已经没有None值了,防御性保留)

# ---- 加密货币(含BTC),CoinGecko批量接口一次拿完 ----
CRYPTO_IDS = {
    "BTC": "bitcoin",  # 这个key必须保持叫"BTC",refresh_loop里靠这个key单独取出来放进STATE["btc"]
    "泰达黄金稳定币(XAUT)": "tether-gold",
    "以太坊(ETH)": "ethereum",
    "艾达币(ADA)": "cardano",  # 你写的是"以太坊(ADA)",这应该是笔误(以太坊已经用在ETH上了),
                              # ADA对应的项目叫Cardano,中文通常译作"艾达币",按这个改的,
                              # 如果你确实想叫别的名字告诉我
    "雪崩协议(AVAX)": "avalanche-2",
    "索拉纳(SOL)": "solana",
    "HYPE": "hyperliquid",
    "BNB": "binancecoin",
    "BGB": "bitget-token",
    "OKB": "okb",  # 注意: OKX是交易所,不是币,平台币正确代码是OKB
}

# ---- 周大福金价 ----
GOLD_RETAIL_URL = "https://www.chowtaifook.com/zh-hk/eshop/realtime-gold-price.html"

# ---- 股市风险指标抓取目标 ----
# 修正版巴菲特指标和Tobin's Q已按你的要求删除,不再抓取也不再放链接。
#
# 这6个(巴菲特指标+这次新加的5个)全部来自currentmarketvaluation.com,核实过官方
# "Our Ratings"页面(currentmarketvaluation.com/about.php#ratings),它们用的是同一套
# 评级体系:按当前值偏离历史均值的标准差数量分5档——
#   强烈低估(<-2个标准差,约2%概率) / 低估(-2~-1,约14%) / 合理(-1~+1,约70%)
#   / 高估(+1~+2,约14%) / 强烈高估(>+2,约2%)
# 所以这6个指标共用同一套解析逻辑(抓页面顶部的评级词+具体数值)和同一套图例,
# 不用每个都单独发明一套阈值。
CMV_RATING_ORDER = ["Strongly Undervalued", "Strongly Overvalued", "Fairly Valued", "Undervalued", "Overvalued"]
CMV_RATING_CN = {
    "Strongly Undervalued": "强烈低估",
    "Undervalued": "低估",
    "Fairly Valued": "合理",
    "Overvalued": "高估",
    "Strongly Overvalued": "强烈高估",
}
CMV_RATING_ZONE = {
    "Strongly Undervalued": "very_low",
    "Undervalued": "low",
    "Fairly Valued": "mid",
    "Overvalued": "high",
    "Strongly Overvalued": "very_high",
}

CMV_MODELS = {
    "buffett_indicator": {
        "url": "https://www.currentmarketvaluation.com/models/buffett-indicator.php",
        "value_regex": r'calculate the Buffett Indicator as\s*([\d.]+)\s*%',
        "unit": "%",
        "name_cn": "巴菲特指标",
        "desc_cn": "美国全市场总市值÷GDP,衡量股市相对经济体量是否过热",
    },
    "price_earnings": {
        "url": "https://www.currentmarketvaluation.com/models/price-earnings.php",
        "value_regex": r'current S&P500 10-year P/E Ratio is\s*([\d.]+)',
        "unit": "",
        "name_cn": "市盈率(P/E10, CAPE)",
        "desc_cn": "标普500现价÷近10年平均每股盈利,和multpl.com的席勒PE是同类指标,来源不同互相印证",
    },
    "price_to_sales": {
        "url": "https://www.currentmarketvaluation.com/models/price-to-sales.php",
        "value_regex": r'Price-to-Sales ratio is\s*([\d.]+)',
        "unit": "",
        "name_cn": "标普500市销率(P/S)",
        "desc_cn": "标普500总市值÷企业前一年总销售额,不看利润只看营收规模",
    },
    "interest_rates": {
        "url": "https://www.currentmarketvaluation.com/models/10y-interest-rates.php",
        "value_regex": r'10Y Treasury bond rate was\s*([\d.]+)\s*%',
        "unit": "%",
        "name_cn": "10年期美债利率",
        "desc_cn": "结合10年期美债利率和标普500偏离趋势线程度,综合判断股市是否过热",
    },
    "mean_reversion": {
        "url": "https://www.currentmarketvaluation.com/models/s&p500-mean-reversion.php",
        "value_regex": r'currently trading\s*([\d.]+)\s*%\s*(?:above|below)',
        "unit": "%",
        "name_cn": "均值回归偏离度",
        "desc_cn": "标普500实际点位偏离长期指数增长趋势线的百分比",
    },
    "earnings_yield_gap": {
        "url": "https://www.currentmarketvaluation.com/models/earnings-yield-gap.php",
        "value_regex": r'current value of\s*(-?[\d.]+)\s*%',
        "unit": "%",
        "name_cn": "股债收益差",
        "desc_cn": "标普500盈利收益率减10年期美债收益率,比较股票和债券的相对吸引力",
    },
}

RISK_INDICATOR_PAGES = {
    "shiller_pe": "https://www.multpl.com/shiller-pe",
}

LINKS = {
    "BTC_MVRV": "https://charts.bgeometrics.com/mvrv.html",
    "BTC_MVRV_Z": "https://charts.bgeometrics.com/mvrv.html",
    "BTC_REALIZED_PRICE": "https://charts.bgeometrics.com/realized-price.html",
    "BTC_BALANCED_PRICE": "https://bitcoin-data.com/",
    "BTC_CVDD": "https://www.looknode.com/zh/chart/CVDD/",
    "BTC_NUPL": "https://www.looknode.com/zh/chart/NUPL/",
    "BTC_RHODL": "https://www.looknode.com/zh/chart/rhodl/",
    "BTC_MA200W": "https://www.looknode.com/zh/chart/TwoHWeekPriceMA/",
    "BTC_SUPPLY_IN_PROFIT": "https://www.looknode.com/zh/chart/percentInProfit/",
    "BTC_60D_RETURN": "https://www.looknode.com/zh/chart/sixtyDaysRaise/",
    "MSTR_TREASURY": TREASURY_PAGES["MSTR"],
    "ASST_TREASURY": TREASURY_PAGES["ASST"],
    "DIGITAL_CREDIT_TEMPLATE": "https://bitcointreasuries.net/digital-credit/{sym}",
    "STOCK_TEMPLATE": "https://stockanalysis.com/stocks/{sym}/",
    "INDEX_TEMPLATE": "https://www.google.com/finance/quote/{sym}",
    "CRYPTO_TEMPLATE": "https://www.coingecko.com/en/coins/{id}",
    "GOLD_RETAIL": GOLD_RETAIL_URL,
    "SHILLER_PE": RISK_INDICATOR_PAGES["shiller_pe"],
    "CMV_RATINGS_GUIDE": "https://www.currentmarketvaluation.com/about.php#ratings",
    **{f"CMV_{k.upper()}": v["url"] for k, v in CMV_MODELS.items()},
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

# 记录每个"每日任务"上次真正跑成功的日期(美东时区,格式YYYY-MM-DD),用来判断
# "今天是不是已经跑过了"。这个也会持久化进cache_log.json,避免重启后同一天内
# 因为_last_fetch里的秒级时间戳被误判成"还没跑过"而重复触发。
_daily_job_last_run_date = {}


def _log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _record_error(where, exc):
    err = f"{where}: {exc}"
    _log("ERROR " + err)
    with STATE_LOCK:
        STATE["errors"] = (STATE["errors"] + [err])[-10:]


def should_run_daily_job(job_name, has_cached_data):
    """判断某个"每日更新"任务现在该不该跑:
    - 如果这类数据从来没抓到过(has_cached_data=False),立刻抓,不等固定窗口;
    - 如果已经抓到过,要等到"每天美东时间07:XX"这个窗口(XX是启动时随机出来的分钟数),
      而且今天(美东时区的今天)还没跑过。
    这样能避免所有部署这套代码的人都挤在整点同时请求同一批数据源,分散服务器压力。"""
    if not has_cached_data:
        return True
    now_et = datetime.now(US_EASTERN)
    today_str = now_et.strftime("%Y-%m-%d")
    if _daily_job_last_run_date.get(job_name) == today_str:
        return False
    return now_et.hour == DAILY_JOB_HOUR_ET and now_et.minute >= _daily_job_minute_offset


def mark_daily_job_done(job_name):
    now_et = datetime.now(US_EASTERN)
    _daily_job_last_run_date[job_name] = now_et.strftime("%Y-%m-%d")


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
            "schema_version": CACHE_SCHEMA_VERSION,
            "saved_at": time.time(),
            "last_fetch": dict(_last_fetch),
            "daily_job_last_run_date": dict(_daily_job_last_run_date),
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

        cached_version = snapshot.get("schema_version")
        if cached_version != CACHE_SCHEMA_VERSION:
            _log(f"缓存文件的schema版本号是{cached_version},当前代码要求{CACHE_SCHEMA_VERSION},"
                 f"不匹配,整份缓存当成不存在处理,所有类别会立刻重新抓取一遍"
                 f"(这就是之前老版本缓存被新代码误用的那个问题,现在自动挡掉了)")
            return

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

        for k, v in (snapshot.get("daily_job_last_run_date") or {}).items():
            _daily_job_last_run_date[k] = v

        age_min = (time.time() - snapshot.get("saved_at", 0)) / 60
        _log(f"已加载缓存日志(cache_log.json),上次保存于约{age_min:.1f}分钟前;"
             f"每日更新类任务会看今天(美东时区)是否已经跑过,不会因为重启就重复触发")
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
            out[name] = {"price": None, "change_pct": None, "ath": None, "ath_change_pct": None,
                         "ath_date": None, "coingecko_id": cg_id}
            continue
        out[name] = {
            "price": row.get("current_price"),
            "change_pct": row.get("price_change_percentage_24h"),
            "ath": row.get("ath"),
            "ath_change_pct": row.get("ath_change_percentage"),  # 负数=距历史高点还差多少百分比
            "ath_date": row.get("ath_date"),  # CoinGecko自带,精确到天,不是月
            "coingecko_id": cg_id,  # 附带这个,前端就不用再单独维护一份名字->id的映射表
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


def fetch_cmv_model(key, cfg):
    """通用解析函数,覆盖currentmarketvaluation.com的6个模型页面(巴菲特指标+这次新加的5个)。
    这几个页面结构高度一致:
    1. 页面顶部固定有一段"...suggests/suggest that the US stock market is\n\n{评级词}",
       评级词是官方"Our Ratings"页面定义的5档之一(Strongly Undervalued/Undervalued/
       Fairly Valued/Overvalued/Strongly Overvalued),我直接抓这个词,不用自己再定义
       一套阈值去猜。
    2. 具体数值用每个模型自己的value_regex单独定位(因为每个模型的原文措辞不同)。
    3. 顺便抓一下"X.X standard deviations"这个数字,作为参考展示,不是必需字段。
    抓不到就是None,不强行凑数。"""
    out = {"value": None, "rating": None, "rating_cn": None, "zone": None, "std_dev": None, "chart_image_url": None}
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        raw_html = r.text
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator="\n")

        # v10修复:v9版本把评级词搜索范围限制在前800个字符,结果页面导航/头部内容
        # 太长,评级词根本不在这个范围内,导致6个指标全部搜不到评级(你反馈的"一个
        # 评级都没有"就是这个原因)。改成不限制范围,但用更精确的结构化模式匹配——
        # CMV官方页面的评级徽章固定是"...is\n\n{评级词}"这种"is后面跟着空行再跟评级词"
        # 的结构,这个模式在正文说明文字里基本不会偶然出现,所以放开范围搜索也不容易
        # 误抓到无关的例子提及。
        rating = None
        m_rating = re.search(
            r'is\s*\n+\s*(Strongly Undervalued|Undervalued|Fairly Valued|Strongly Overvalued|Overvalued)',
            text
        )
        if m_rating:
            rating = m_rating.group(1)
        out["rating"] = rating
        out["rating_cn"] = CMV_RATING_CN.get(rating)
        out["zone"] = CMV_RATING_ZONE.get(rating)

        m = re.search(cfg["value_regex"], text, re.IGNORECASE)
        out["value"] = float(m.group(1)) if m else None

        m2 = re.search(r'([\d.]+)\s+standard deviations?', text, re.IGNORECASE)
        out["std_dev"] = float(m2.group(1)) if m2 else None

        # v11新增:提取模型摘要图表的图片地址,这样前端能直接放大图,不只是显示一个数字。
        # CMV这类模型页面的图表图片托管在cmv.imgix.net上,命名规律是"YYYY-MM-DD-XX-ChartN.png",
        # 页面里同时存在带查询参数的srcset(多种尺寸)和一个"干净"的完整版src(不带查询参数、
        # 不在model-charts子目录下),这里只抓后者,取"最终展示用的那张完整图"。
        # 这些图片是imgix这类CDN托管的公开图片,直接用<img src>外链引用理论上没问题,
        # 但我没法在这个环境里用真实浏览器验证是否会被防盗链拦截,如果部署后图裂了,
        # 需要告诉我换成后端代理转发的方式。
        m_img = re.search(r'src="(https://cmv\.imgix\.net/(?!model-charts)[^"]+\.png)"', raw_html)
        out["chart_image_url"] = m_img.group(1) if m_img else None
    except Exception as e:
        _record_error(f"cmv:{key}", e)
    return out


def fetch_risk_indicators():
    """抓席勒市盈率(multpl.com,和currentmarketvaluation.com的P/E10是同类指标,
    来源不同互相印证) + currentmarketvaluation.com的6个模型(巴菲特指标 + 这次新加的
    市盈率P/E10、市销率P/S、10年期美债利率、均值回归偏离度、股债收益差)。
    修正版巴菲特指标和Tobin's Q已按你的要求整个删除,不再抓取。"""
    out = {"shiller_pe": None, "shiller_pe_zone": None}

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
        # 席勒PE单独维持一套3档分区(不是CMV的5档体系,来源不同):
        # <=25低风险(绿) / 25~35中风险(黄) / >35高风险(红)
        out["shiller_pe_zone"] = _classify_zone(val, 25, 35)
    except Exception as e:
        _record_error("risk_indicator:shiller_pe", e)

    out["cmv"] = {}
    for key, cfg in CMV_MODELS.items():
        out["cmv"][key] = fetch_cmv_model(key, cfg)

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


def fetch_btc_60d_return():
    """BTC过去60天的累计涨跌幅,用CoinGecko的历史价格接口自己算,不依赖bgeometrics
    (bgeometrics免费额度有限,这个能自己算就不占用它的额度)。"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart",
            params={"vs_currency": "usd", "days": 60, "interval": "daily"},
            timeout=15,
        )
        r.raise_for_status()
        prices = r.json().get("prices", [])
        if len(prices) < 2:
            return None
        start_price = prices[0][1]
        end_price = prices[-1][1]
        if not start_price:
            return None
        return (end_price / start_price - 1) * 100
    except Exception as e:
        _record_error("btc_60d_return", e)
        return None


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
    out["btc_60d_return_pct"] = fetch_btc_60d_return()
    return out


def fetch_quotes(ticker_map):
    # 过滤掉ticker为None的占位项(目前WATCHLIST里没有这种情况,防御性保留,
    # 万一以后又加了个没有对应上市标的的条目,不会导致yf.Tickers()报错),
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
                def _jitter():
                    time.sleep(random.uniform(*STOCK_FETCH_JITTER_SEC))

                mstr_q = fetch_quotes({"MSTR": MSTR_TICKER}).get("MSTR", {})
                _jitter()
                asst_q = fetch_quotes({"ASST": ASST_TICKER}).get("ASST", {})
                _jitter()
                preferreds = fetch_quotes(MSTR_PREFERREDS)
                _jitter()
                watch = fetch_quotes(WATCHLIST)
                # MSTR/ASST/STRC 已经在别处抓过了,这里直接复用结果merge进watchlist,
                # 不再对同一个ticker重复发一次yfinance请求
                watch["策略(MSTR)"] = mstr_q
                watch["Strive(ASST)"] = asst_q
                _jitter()
                idx = fetch_quotes(INDICES)
                _jitter()
                metals = fetch_quotes(METALS)

                # ---- 非交易时段用Bitget股票永续合约价格覆盖(仅限美股,见文件头说明) ----
                market_open = is_us_market_open()
                for q in list(watch.values()) + [mstr_q, asst_q]:
                    if isinstance(q, dict):
                        q["price_source"] = "yahoo"
                        q["market_open"] = market_open
                if not market_open:
                    overlay_tickers = [v for v in WATCHLIST.values() if v] + [MSTR_TICKER, ASST_TICKER]
                    bitget_data = fetch_bitget_stock_perps(overlay_tickers)
                    ticker_to_names = {}
                    for name, t in WATCHLIST.items():
                        ticker_to_names.setdefault(t, []).append(name)
                    ticker_to_names.setdefault(MSTR_TICKER, []).append("策略(MSTR)")
                    ticker_to_names.setdefault(ASST_TICKER, []).append("Strive(ASST)")
                    for ticker, bg in bitget_data.items():
                        for name in ticker_to_names.get(ticker, []):
                            if name in watch:
                                watch[name]["price"] = bg["price"]
                                watch[name]["change_pct"] = bg["change_pct"]
                                watch[name]["price_source"] = "bitget_perp_24h"
                                watch[name]["bitget_symbol"] = bg["bitget_symbol"]
                    if ticker_to_names.get(MSTR_TICKER, []) and MSTR_TICKER in bitget_data:
                        bg = bitget_data[MSTR_TICKER]
                        mstr_q["price"] = bg["price"]
                        mstr_q["change_pct"] = bg["change_pct"]
                        mstr_q["price_source"] = "bitget_perp_24h"
                        mstr_q["bitget_symbol"] = bg["bitget_symbol"]
                    if ASST_TICKER in bitget_data:
                        bg = bitget_data[ASST_TICKER]
                        asst_q["price"] = bg["price"]
                        asst_q["change_pct"] = bg["change_pct"]
                        asst_q["price_source"] = "bitget_perp_24h"
                        asst_q["bitget_symbol"] = bg["bitget_symbol"]

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
            if should_run_daily_job("treasury", bool(STATE.get("mstr", {}).get("treasury"))):
                mstr_t = fetch_treasury_page(TREASURY_PAGES["MSTR"])
                asst_t = fetch_treasury_page(TREASURY_PAGES["ASST"])
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["treasury"] = mstr_t
                    STATE.setdefault("asst", {})["treasury"] = asst_t
                _last_fetch["treasury"] = now
                mark_daily_job_done("treasury")
                save_cache_log()
        except Exception as e:
            _record_error("treasury_loop", e)

        try:
            if should_run_daily_job("onchain", bool(STATE.get("onchain"))):
                onchain = fetch_onchain_metrics()
                with STATE_LOCK:
                    STATE["onchain"] = onchain
                _last_fetch["onchain"] = now
                mark_daily_job_done("onchain")
                save_cache_log()
        except Exception as e:
            _record_error("onchain_loop", e)

        try:
            if should_run_daily_job("gold_retail", bool(STATE.get("gold_retail", {}).get("price_rmb_per_gram"))):
                gr = fetch_gold_retail(GOLD_RETAIL_URL)
                with STATE_LOCK:
                    STATE["gold_retail"] = gr
                _last_fetch["gold_retail"] = now
                mark_daily_job_done("gold_retail")
                save_cache_log()
        except Exception as e:
            _record_error("gold_retail_loop", e)

        try:
            if should_run_daily_job("risk_indicator", bool(STATE.get("risk_indicators"))):
                ri = fetch_risk_indicators()
                with STATE_LOCK:
                    STATE["risk_indicators"] = ri
                _last_fetch["risk_indicator"] = now
                mark_daily_job_done("risk_indicator")
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
    价格类数据的刷新。改成"每日更新"档:没抓过就立刻抓,抓过了就等每天固定的
    美东时间07:XX窗口。"""
    while True:
        try:
            if ENABLE_ATH_DRAWDOWN and should_run_daily_job("ath", bool(STATE.get("ath"))):
                _log(f"开始计算ATH,共{len(ATH_TICKERS)}个代码,单个超时{ATH_PER_TICKER_TIMEOUT_SEC}秒...")
                fetch_ath_drawdown(ATH_TICKERS)  # 内部会边算边写STATE,不需要接返回值
                _last_fetch["ath"] = time.time()
                mark_daily_job_done("ath")
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
    _log(_log_startup_msg)
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
