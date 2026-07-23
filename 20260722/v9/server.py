#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
个人参考看板 - 后端数据代理 (v27)
================================
v27:
1. 自选股新增16只高股息/消费防御类个股:宝洁(PG)、联合利华(UL)、强生(JNJ)、
   可口可乐(KO)、百事(PEP)、雀巢(NESN.SW)、Realty Income(O)、高露洁(CL)、
   Genuine Parts(GPC)、Dover(DOV)、Altria(MO)、Verizon(VZ)、辉瑞制药(PFE)、
   雪佛龙(CVX)、Enbridge(ENB)、AbbVie(ABBV)。
2. 自选ETF新增5只:SGOV/JEPI/JEPQ/DGRO/ALLW——你原话说的是"指数加入",但这5个
   都是ETF不是指数本身,按现有分类放进"自选ETF"板块,如果你要的是它们各自跟踪的
   指数需要告诉我换成^代码。
3. 新增"股息"字段:自选股+自选ETF+指数每天抓一次dividendRate(每股年化股息金额)
   和dividendYield(股息率),前端卡片会展示成"$4.23 (2.82%)"这种格式,没有分红
   的标的不展示这一行。
4. QDII基金监控是独立新脚本qdii_fetch.py(和stock500_fetch.py同一个模式,cron
   定时、不共用进程),配套新增/qdii.html和/cache_qdii.json两个纯读路由。
5. 股票500强(stock500_fetch.py)新增IPO上市日期/IPO价格/IPO至今年化涨幅这3个
   字段,复用已有的ATH建档逻辑(月线全历史第一条记录近似IPO,精确到月不到天)。

依赖(和v26一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v26)
================================
v26:分类修正——南希佩洛西(NANC)、每日两倍做空/做多微策略(SMST/MSTX)这三个
之前放错地方了,它们本身就是ETF,不是个股,这次从"自选股"挪到了"自选ETF"。
自选股新增4只:埃森哲(ACN)、耐克(NKE)、高通(QCOM)、纽蒙特(NEM)。
这次同样不需要重置cache_log.json,只是WATCHLIST/ETF_WATCHLIST这两个字典的
成员调整,不涉及数据结构变化。

依赖(和v25一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v25)
================================
v25:
1. 自选股加入英特尔——你写的"INTL"应该是笔误,英特尔真正的代码是INTC,按这个处理。
2. 新增"自选ETF"这个独立板块(和自选股分开,各自按距ATH跌幅排序),包含
   IVE/QQQ/SQQQ/GSG/VOOV/XLP/XLV/XLE/VDC/DBMF这10只ETF。ETF没有Bitget股票
   永续合约,不做"非交易时段夜盘价格覆盖"这个逻辑(那个只对个股有效)。
这次数据结构只是新增了一个"etf_watchlist"字段,不影响"每日更新"档的调度判断,
不需要重置cache_log.json。

依赖(和v24一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v24)
================================
v24这次是配合新增的"股票500强"独立页面(stock.html + stock500_fetch.py)做的调整,
dashboard本身的数据逻辑没有变化:

1. 新增两个纯读文件的静态路由:/stock.html 和 /cache_stock.json。这两个不会
   触发任何抓取动作,cache_stock.json是完全独立的stock500_fetch.py脚本(通过
   cron定时,和这个server.py进程不共用内存/进程)生成的,server.py这里只是原样
   把文件内容读出来返回,零额外负担。

2. 删除了v22加的"服务器渲染长图"(/export.png,靠wkhtmltoimage+PIL那一套)——
   按你的要求,浏览器截图(html2canvas)够用又不占服务器资源,服务器端这条路
   就整个删掉了,包括相关的Pillow/wkhtmltoimage依赖检查代码。如果你的VPS上
   之前装过wkhtmltopdf,现在不需要了,可以卸载(不卸载也没影响,只是没用了)。

依赖(比v22少了Pillow和wkhtmltopdf,这两个不再需要):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v22)
================================
v22:

1. BTC面板新增比特币市值、BTC市占率(含/不含稳定币)、TOTAL2市值、TOTAL3市值。
   你给的bitbo.io和TradingView这两个链接实测都是纯客户端渲染,和之前fuckbtc/
   looknode是同一类问题,抓不到具体数值。改用CoinGecko的/global接口(免费公开,
   和现价同一个数据源)自己算:总市值×BTC占比=BTC市值,总市值-BTC市值=TOTAL2,
   再减ETH市值=TOTAL3。"不含稳定币"的市占率额外用了CoinGecko稳定币分类市值
   做分母调整。这几项5分钟刷新一次(比价格慢,偏宏观慢变量,而且分类接口比较重)。

2. 新增"浏览器截图导出"按钮,用html2canvas直接截取浏览器实际渲染的页面
   (不是服务器端重新渲染一遍),这样截图和你看到的一模一样。原来的"服务器渲染
   长图"(wkhtmltoimage+PIL那套)保留作为备用方案——如果页面太长导致
   html2canvas在你的浏览器上失败(比如碰到canvas尺寸上限),可以切换用那个。

依赖(和v21一致,html2canvas是前端CDN引入,不需要在VPS上装):
    pip install --break-system-packages requests yfinance beautifulsoup4 Pillow
    apt install wkhtmltopdf
"""

"""
个人参考看板 - 后端数据代理 (v21)
================================
v21改了两大块:

1. 9个链上指标的三色解释,全部按你给的具体阈值重写:
   MVRV(<0.9/0.9~1.8/>1.8)、MVRV-Z(<0/0~5/>5)、Realized Price(改成显示
   MVRV=0.9/1.8对应的具体价位,而不是单纯比值)、Balanced Price(改成显示
   "有没有跌破+距离多少美元")、CVDD(改成显示"现价在其上方/下方多少%")、
   60日涨幅(新增>100%极高风险这个第4档,颜色上和50~100%共用红色,文字里
   区分)、SOPR(<0.95/0.95~1.05/>1.05)、Puell Multiple(<0.5/0.5~2.5/>2.5)。
   新增NUPL(5档,颜色只有3种,红黄各覆盖两档,文字里区分具体是哪一档)、
   RHODL比率(<350/350~50000/>50000)、盈利中的百分比(<50/50~85/>85)这三个
   之前没做解释的。
   顺便把取值逻辑改成用一个通用的提取函数,不再对每个字段单独写死key名——
   之前这里有潜在的隐患:bgeometrics原始数据里不同指标的字段名不统一
   (比如RHODL的字段叫rhodlRatio,NUPL的字段就叫nupl本身),如果之前某个
   字段解析出来一直是null,可能就是这个原因,这次一并修了。

2. 页面上原来那些技术性备注(数据来源、抓取频率、防盗链问题之类的说明文字)
   全部从index.html里挪出来了,汇总进一个单独的文本文件,页面最底部右下角
   加了一个不起眼的灰色"下载说明日志"链接,点击会下载完整的技术备注,不影响
   正常看板阅读。顺带修正了一处过时内容——MSTR基准早就从v18开始改成
   "2020-08-11开盘价$14.20,不需要×10换算",但页面上那条sub小字还停留在
   更早版本"收盘价$124.70,需要×10"的旧说法,这次一起改对了。

3. X推文滚动展示这个功能:查证了一下,2026年Nitter这类免费第三方抓取
   基本已经失效或极不稳定(X官方这几年反抓取收得很紧),没有做,这个我会
   在对话里单独跟你说清楚现状和可选方案,不在这次代码改动范围内。

依赖(和v20一致):
    pip install --break-system-packages requests yfinance beautifulsoup4 Pillow
    apt install wkhtmltopdf
"""

"""
个人参考看板 - 后端数据代理 (v20)
================================
v20这次改了5点:

1. 新增股票的ATH数据缺失问题:根因是ATH计算走"每日更新"档,判断"今天跑没跑过"是
   按整批(ATH_TICKERS这个大列表)算的,新增股票后如果当天整批已经跑过,新股票会被
   误判成"不用跑、等明天"。v20给ath_loop加了一段:不管今天整批跑没跑,只要发现
   STATE["ath"]里缺失的代码,立刻单独补算,不用等明天。

2. SMST/MSTX改名为"每日两倍做空微策略(SMST)"/"每日两倍做多微策略(MSTX)"。

3&4. "自选股"改名"自选股(按跌幅排序)","指数"改名"指数(按跌幅排序)"——你原话
   写的是"指数基金也按照跌幅排序,改名为自选股(按照跌幅排序)",这里按"指数(按跌幅
   排序)"处理,应该是笔误(不然两个板块会重名)。顺带给指数也加上了和自选股一样的
   按距ATH跌幅排序逻辑(之前指数没有排序)。

5. 给MVRV/MVRV-Z/Realized Price/Balanced Price/200周均线/60日累计涨幅/SOPR/
   Puell Multiple/CVDD这9个指标各配一句话解释,红(过热)/黄(中性)/绿(熊市)三色。
   具体分界线(比如MVRV>3.5算过热)是我自己综合判断定的经验区间,不是某个单一
   权威来源认证过的标准,不同分析师的具体数字会有出入,只是给你一个直观参考,
   不是唯一"正确答案"。

6. 新增"导出长图"功能。技术方案按你说的:每个板块单独生成HTML,用wkhtmltoimage
   渲染成PNG(宽度固定800px),再用PIL纵向拼接。这个我在自己的沙盒环境里用真实的
   wkhtmltoimage+Pillow实测跑通了完整流程(不是纸上谈兵),效果符合预期。
   VPS上需要额外装两个东西:
     - wkhtmltoimage: Ubuntu上 `apt install wkhtmltopdf` (这个包名字虽然叫
       wkhtmltopdf,但会一并装上wkhtmltoimage这个可执行文件)
     - Pillow: `pip install --break-system-packages Pillow`
   如果这两个没装,程序不会崩溃,只是导出功能会被自动关闭(启动日志里会有警告),
   看板其他部分不受影响。前端加了"导出长图"按钮,点击后调用新增的/export.png接口。

依赖(比v19多了Pillow和系统的wkhtmltoimage):
    pip install --break-system-packages requests yfinance beautifulsoup4 Pillow
    apt install wkhtmltopdf
"""

"""
个人参考看板 - 后端数据代理 (v19)
================================
v19:自选股新增20个标的(甲骨文、IBM、闪迪、镁光、超微电脑、思科、加拿大金矿、
SMST、MSTX、礼来、Visa、PayPal、Palantir、爱马仕、LVMH、三菱商事、软银集团、
丰田、索尼、博通、沃尔玛)。亚马逊之前已经在列表里,没有重复添加。
几个需要你确认的地方(不是我瞎猜,是真实存在歧义,写在代码TODO里了):
  - "三菱"按三菱商事(8058.T)处理,三菱集团旗下还有三菱电机/三菱重工/三菱UFJ银行
    等独立上市公司,如果你要的是别的具体某一家需要告诉我改。
  - 丰田/索尼用的是纽约上市ADR代码(TM/SONY),不是东京原始代码,两者价格联动
    但不完全等同一份股票。
这次数据结构没有变化,不需要重置cache_log.json。

依赖(和v18一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v18)
================================
v18(这轮是在另一个聊天窗口讨论确认的,这里整理落地):

1. MSTR/BTC对比基准换成2020-08-11开盘价(不是收盘价),数据来自TradingView:
   BTC=$11,899.87,MSTR=$14.20(复权后)。因为TradingView默认显示的历史价格是
   拆股复权后的,这个$14.20已经是和现在雅虎财经拿到的现价同一个复权口径,所以
   之前"现价×10换算成拆股前价格"那个逻辑整个去掉了,直接相除比较。

2. MVRV换源:改用looknode-proxy的mCapRealizedRatio(本质就是市值/已实现市值,
   等同MVRV),这个endpoint返回全部历史数据,显式用时间戳(t字段)取值最大的
   那条,不假设数组顺序。

3. MVRV-Z换源:改用你自己搭的另一个Cloudflare Worker(btc-cache),返回格式
   干净:{"mvrvz":..., "ts":...}。

4. Realized Price不再单独抓取一个数据源,改成用"现价÷MVRV(上面新源)"反推
   ——这是数学定义本身就成立的关系(MVRV=市值/已实现市值=价格/实现价格),
   不是近似值。

5. 新增200日均线(不是替换200周均线,是新加一行),用OKX的日K线接口,和200周
   均线用同一套逻辑,只是bar参数从1W换成1D,取最近200根不刻意排除当天。

依赖(和v17一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v17)
================================
v17:你提供的完整Request URL(looknode-proxy.corms-cushier-0l.workers.dev)我验证过了,
是真实可用的公开JSON接口,不是猜测。这是fuckbtc.com作者自己搭的Cloudflare Worker
代理,转发looknode的数据。用它覆盖了SOPR和Puell Multiple(这两个之前一直是
bgeometrics的猜测路径,没确认过对不对),顺带也覆盖了Balanced Price做交叉验证。
没有覆盖MVRV,因为bgeometrics的mvrv这个endpoint已经确认能正常抓到了,不需要
额外来源。

诚实说明一个资源上的取舍:这个代理返回的是"从比特币诞生至今"的完整历史数组
(可能有大几千条数据),不是只给最新一条,所以这几个请求下载的数据量比bgeometrics
那种"只给当天数值"的接口大不少。因为这几个都在"每日更新"档里,一天只请求一次,
这个额外开销可以接受,但如果你的VPS流量比较敏感,这点需要你知道。

依赖(和v16一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v16)
================================
v16修正了我上一轮的一个不准确判断:你用DevTools Network面板证明了fuckbtc.com
其实是有后端数据的,只是首屏HTML确实是空的、要等页面里的JS跑起来后再去问后端要数据——
我之前只用简单请求去抓静态HTML,自然什么都拿不到,这不代表"这个网站没有数据",
是我这边的判断不够全面。

从你截图里几个接口的返回格式,认出来3个其实是独立、文档公开的知名免费API,不需要
依赖fuckbtc.com自己的后端域名(那个我没找到确切地址):
  - fng/?limit=1 返回格式和alternative.me的恐惧贪婪指数API一模一样,直接换用这个。
  - candles?instId=BTC-USDT&bar=1W 这个参数写法是OKX交易所公开行情API的标准格式,
    200周均线直接用OKX拉200根周K线自己算,不用再猜bgeometrics的路径。
  - 减半倒计时用mempool.space查当前区块高度,自己按比特币协议规则(每210,000个
    区块减半)算倒计时,同样独立公开。

balancedPrice/sopr/puellMultiple/mCapRealizedRatio这几个看起来是fuckbtc.com自己的
后端接口,我没能确定具体域名(截图里只看到相对路径),这几个继续走bgeometrics
(已经加过的sopr/puell-multiple猜测路径),没有强行去猜fuckbtc.com的域名。如果你
之后想要更保险的交叉验证,把某个请求的完整Request URL发我,我可以再加一层。

依赖(和v15一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v15)
================================
v15新增:

1. BTC面板新增SOPR、Puell Multiple、减半倒计时、恐惧贪婪指数——你提到的fuckbtc.com
   主站我重新实测过了,还是纯客户端渲染,静态请求抓不到任何数值(200周均线/Balanced
   Price/SOPR/Puell Multiple/减半倒计时/恐惧贪婪指数在那个页面全部是"--"占位符),
   没有改用它。这4个新指标改用bgeometrics(和MVRV那几个同一数据源),endpoint路径
   同样是推断的,需要你部署后核对。

2. NUPL/RHODL/Percent Supply in Profit换源——严格说不是换源,这几个本来就是走
   bgeometrics,之前失败大概率是被429限流干扰,真实原因还没完全确认。这次顺便把
   200周均线(ma_200w)和盈利占比(supply_in_profit_pct)这两个的endpoint路径换了
   个新猜测(参考bgeometrics图表页面叫"Supply in Profit Loss"而不是"Percent Supply
   in Profit"的命名规律)。

3. MSTR面板新增"自2020-08-11采纳比特币策略以来"的涨跌幅对比——MSTR涨跌幅(用你
   给的$124.70拆股前基准,现价×10换算成拆股前等值价格)、BTC同期涨跌幅(用你给的
   $11,410.53基准)、两者比值。这两个基准价格是写死的历史常量,不是每次重新抓取。

4. MSTR面板新增Beta系数、市值(雅虎财经)——用yfinance比较"重"的.info接口,放进
   每日更新档,不是每60秒都调用。

5. MSTR面板新增STRC股息率、单券Runway、全局Runway、官方mNAV——数据源是
   mstr.fuckbtc.com。重要说明:strategy.com/strc本身我实测过是纯客户端渲染的
   React应用,静态请求抓不到任何数据,所以没法直接用你给的strategy.com/strc这个
   链接;但mstr.fuckbtc.com(飞轮监控盘那个子站,注意不是fuckbtc.com主站)刚好是
   服务器端渲染的,而且它本身就是从strategy.com官网和SEC 8-K文件整理过来的,所以
   退而求其次用这个聚合页作为数据源,不是原始一手数据。

依赖(和v14一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v14)
================================
v14说明:v13那个调度bug修复后,MVRV/MVRV-Z/Realized Price/Balanced Price/NUPL/RHODL/
200周均线/盈利占比这8个走bgeometrics的指标,这次是真的被重新请求了,但撞上了
bgeometrics免费额度的限流(429错误)——今天为了排查问题反复重启了好几次服务,
每次重启都会一次性把9个bgeometrics接口全部请求一遍,几次累加就把每小时8次/
每天15次的免费额度打光了。这不是代码逻辑的bug,是配额被打满了,过一段时间
(下一个整点,或者第二天)配额恢复后应该会自动好。

v14加了两个小改进,降低以后再撞到限流的概率:
  1. 9个bgeometrics请求之间插入1-2秒随机间隔,不再瞬间并发全部打出去。
  2. 只要这一轮里遇到一次429,后面的请求直接跳过不再尝试(反正大概率也是429),
     省下配额,而不是明知会失败还硬发。

治本的办法没有变:去 https://portal.bgeometrics.com/login 免费注册账号拿
BGEOMETRICS_TOKEN 填到配置里,注册用户的配额通常比匿名访问宽松很多,这个需要
你自己去注册,我没法代劳。

依赖(和v13一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v13)
================================
v13修复一个贯穿前几轮的架构级bug,这很可能才是CVDD/NUPL/RHODL/200周均线/盈利占比
以及巴菲特指标/席勒PE一直显示"--"的真正原因:

"每日更新"档的调度逻辑,判断"这类数据是不是已经抓到过"用的是bool(STATE.get(...))——
但即使抓取全部失败,STATE里对应的字典也会是{"字段名": None, ...}这种非空字典,
bool()判断永远是True。这导致系统从第一次抓取失败开始,就一直以为"已经有数据了",
在同一天内(默认要等到第二天美东07:XX)不会再重新尝试——哪怕后来我把抓取逻辑的
bug真的修好了,新代码也要等到第二天才会被真正执行到,之前几轮看起来"修复没生效",
很可能不是新代码没生效,是压根没跑到。
v13加了_has_any_value()这个辅助函数,判断字典里是不是至少有一个字段真的抓到了值
(不只是字典本身非空),用这个替换掉所有"是否已有数据"的判断,从根源解决。

顺便核实了你给的几个新数据源:bitbo.io、bitcoinmagazinepro.com、coinglass.com
和之前的looknode.com一样是客户端渲染,静态请求抓不到数值,没有采用。
axeladlerjr.com的CVDD页面例外——实测是服务器端渲染,正文里有"CVDD is $44,667"
这样的明确文本,换成了这个作为CVDD的主要来源。NUPL/RHODL/200周均线/盈利占比
暂时还是走bgeometrics(endpoint路径仍是推断,未100%验证),但这次那个调度bug
修复后,应该终于会被真正重新尝试抓取,能不能抓到需要你部署后实测。

依赖(和v12一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

"""
个人参考看板 - 后端数据代理 (v12)
================================
v12修复(4个问题):
  1. 巴菲特指标数值一直是"--"的真正原因找到了:之前的正则匹配的是"we calculate
     the Buffett Indicator as XX%"这句话,但这句话只存在于页面meta description
     标签的属性里,不在正文可见文本中——BeautifulSoup的get_text()只提取文本节点,
     压根读不到meta标签属性,所以这个正则在正文里永远匹配不到,不是网络问题。
     改成匹配正文里真实存在的"The current ratio of 219% is approximately..."这句,
     加了一个匹配公式行"Buffett Indicator = $69.15T / $31.57T = 219%"的备用正则。
  2. 席勒市盈率换源:之前用的multpl.com一直抓不到数据(截图显示"暂无数据"),
     换成in2013dollars.com,这个页面正文有一句很干净的"The Shiller PE is 41.02
     as of the beginning of this month."可以直接匹配。
  3. 前端加了"首次加载快速重试":之前页面一打开如果后端刚好还没跑完第一轮抓取,
     会显示一片"--",还要等满60秒倒计时才能看到数据——现在如果发现BTC价格这类
     基本字段还是空的,会改成3秒后很快再问一次(最多重试15次,不会无限快速轮询),
     不用死等一整个60秒周期。这不是后端行为的改变(后端本来就是"有数据立刻返回,
     没数据就是没有",不存在阻塞等待),纯粹是前端轮询节奏的问题。
  4. 股市风险指标卡片里的官方图表整个删掉了——之前(v11)嵌进去的外链图片显示
     不出来,大概率是被防盗链拦截,与其挂一堆裂图不如不放,恢复成纯文字卡片
     (数值+评级+说明文字),和v10一样。

依赖(和v11一致):
    pip install --break-system-packages requests yfinance beautifulsoup4
"""

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
CACHE_SCHEMA_VERSION = 11  # v21按新阈值重写了explanations,新增NUPL/RHODL/盈利占比的解释,版本号加1

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
MARKET_OVERVIEW_REFRESH_SEC = 5 * 60  # BTC市占率/TOTAL2/TOTAL3,偏宏观慢变量,不用跟价格一样30秒刷新
STOCK_REFRESH_SEC = 60             # 普通股票/指数/优先股/贵金属期货现价
STOCK_FETCH_JITTER_SEC = (1, 4)    # 同一轮里,每个子请求(mstr/asst/preferreds/watch/idx/metals)
                                    # 之间随机插入这么多秒的间隔,不再同时发出去

# ---- ATH(历史最高价)/回撤计算开关 ----
ENABLE_ATH_DRAWDOWN = True
ATH_PER_TICKER_TIMEOUT_SEC = 20  # 单个ticker超过这个时间还没返回就放弃,避免卡住整个ATH线程
ATH_ADJUSTMENT_VERSION = 2       # v2=日线High + auto_adjust=True + repair=True，统一拆股复权口径

ONCHAIN_ENDPOINTS = {
    "mvrv": "mvrv",
    "mvrv_zscore": "mvrv-zscore",
    "realized_price": "realized-price",
    "balanced_price": "balanced-price",
    # 下面几个同样来自bgeometrics.com/bitcoin-data.com(和上面4个同一个数据源,不是新站点)。
    # TODO: 这几个endpoint路径是根据bgeometrics官网图表页面的命名规律推断的,
    # mvrv/mvrv-zscore/realized-price/balanced-price/cvdd/nupl/rhodl-ratio这7个
    # 已经实测确认能抓到(nupl和rhodl之前被429限流干扰过,现在已确认路径本身是对的)。
    # ma_200w和supply_in_profit_pct这两个之前一直是null,这次按bgeometrics图表页面
    # 叫"Supply in Profit Loss"(不是"Percent Supply in Profit")、"200 week MA"的命名
    # 规律换了个新猜测,还是没有100%验证过,如果还是null需要你去
    # https://bitcoin-data.com/api/scalar.html 核对真实路径。
    "cvdd": "cvdd",
    "nupl": "nupl",
    "rhodl": "rhodl-ratio",
    "ma_200w": "200-week-ma",
    "supply_in_profit_pct": "supply-in-profit",
    # 这4个是v15新加的,同样是猜测路径,同样需要你部署后核对:
    "sopr": "sopr",
    "puell_multiple": "puell-multiple",
    # fear_greed 和 halving 不走这里的bgeometrics猜测路径了,v16改用两个确认可靠的
    # 独立公开API(alternative.me和mempool.space),见下面的fetch_fear_greed_alt()和
    # fetch_halving_countdown_mempool()两个函数。
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

# ---- MSTR"采纳比特币策略"以来 vs BTC同期涨跌幅对比 ----
# 这两个基准价格是你直接给的历史事实,不是需要每次重新抓取的实时数据(历史收盘价
# 不会变),所以直接写成常量。
# MSTR 2020-08-11 收盘 $124.70 是"1:10拆股前"的价格——MSTR在2024年8月完成过一次
# 10:1拆股,所以要用"现价×10"换算成拆股前的等值价格,才能跟这个$124.70基准直接比较。
MSTR_ANCHOR_DATE = "2020-08-11"
# v18更新:换成2020-08-11的开盘价(不是收盘价),数据来自TradingView。
# 注意:TradingView默认显示的历史价格是"拆股复权后"的,MSTR在2024年8月完成过10:1拆股,
# 这个$14.20是复权后的等值价格(对应拆股前约$142左右),跟我们现在从雅虎财经拿到的
# 现价是同一个复权口径,所以不再需要"现价×10"这个换算了,直接相除比较就行。
MSTR_ANCHOR_PRICE = 14.20   # 2020-08-11开盘价(拆股复权后)
BTC_ANCHOR_PRICE = 11899.87  # 同一天BTC开盘价


def compute_since_mstr_adoption(mstr_price_now, btc_price_now):
    """算MSTR自宣布采纳比特币策略(2020-08-11)以来的涨跌幅、BTC同期涨跌幅、
    以及两者的比值。用的是上面写死的历史锚点价格,不需要额外请求。"""
    out = {"mstr_return_pct": None, "btc_return_pct": None, "ratio": None}
    try:
        if mstr_price_now is not None:
            out["mstr_return_pct"] = (mstr_price_now / MSTR_ANCHOR_PRICE - 1) * 100
        if btc_price_now is not None:
            out["btc_return_pct"] = (btc_price_now / BTC_ANCHOR_PRICE - 1) * 100
        if out["mstr_return_pct"] is not None and out["btc_return_pct"] not in (None, 0):
            out["ratio"] = out["mstr_return_pct"] / out["btc_return_pct"]
    except Exception as e:
        _record_error("compute_since_mstr_adoption", e)
    return out
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
    "赛富时(CRM)": "CRM",
    "ServiceNow(NOW)": "NOW",
    "思爱普(SAP)": "SAP",
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
    "Autodesk(ADSK)": "ADSK",
    "Metaplanet(3350.T)": "3350.T",
    # 南希佩洛西(NANC)已经移到ETF_WATCHLIST(它本身是ETF,不是个股)
    "甲骨文(ORCL)": "ORCL",
    "IBM": "IBM",
    "闪迪(SNDK)": "SNDK",  # 2025年2月从西部数据(WDC)拆分独立上市
    "镁光(MU)": "MU",
    "超微电脑(SMCI)": "SMCI",
    "思科(CSCO)": "CSCO",
    "加拿大金矿(EQX)": "EQX",  # Equinox Gold Corp
    "Gold Fields(GFI)": "GFI",
    # SMST/MSTX已经移到ETF_WATCHLIST(它们本身是ETF,不是个股)
    "埃森哲(ACN)": "ACN",
    "耐克(NKE)": "NKE",
    "高通(QCOM)": "QCOM",
    "纽蒙特(NEM)": "NEM",
    # 亚马逊(AMZN)已经在上面了,这次不重复添加
    "礼来(LLY)": "LLY",
    "Visa(V)": "V",
    "PayPal(PYPL)": "PYPL",
    "Palantir(PLTR)": "PLTR",
    "爱马仕(RMS.PA)": "RMS.PA",  # 巴黎证交所原始上市
    "LVMH(MC.PA)": "MC.PA",  # 巴黎证交所原始上市
    # TODO: "三菱"本身有歧义——三菱集团旗下三菱商事/三菱电机/三菱重工/三菱UFJ银行是各自
    # 独立上市的公司,这里按最常被理解为"三菱"的三菱商事处理,如果你要的是别的具体某一家,
    # 告诉我改成对应代码(如三菱电机6503.T、三菱重工7011.T、三菱UFJ银行8306.T)。
    "三菱商事(8058.T)": "8058.T",
    "软银集团(9984.T)": "9984.T",
    # TODO: 丰田/索尼这两个用的是纽约上市的ADR代码,不是东京原始上市代码,两者价格联动
    # 但不完全等同一份股票,这是默认选择,如果你要东京原始代码(7203.T/6758.T)告诉我换。
    "丰田(TM)": "TM",
    "索尼(SONY)": "SONY",
    "博通(AVGO)": "AVGO",
    "沃尔玛(WMT)": "WMT",
    "英特尔(INTC)": "INTC",  # 你写的是"INTL",应该是笔误,英特尔真正的代码是INTC,按这个处理
    # ---- v27新增:高股息/消费防御类个股 ----
    "宝洁(PG)": "PG",
    "联合利华(UL)": "UL",  # 纽交所ADR;伦敦/阿姆斯特丹原始上市代码是ULVR.L/UNA.AS,这里用美股ADR
    "强生(JNJ)": "JNJ",
    "可口可乐(KO)": "KO",
    "百事(PEP)": "PEP",
    "雀巢(NESN)": "NESN.SW",  # 瑞士证交所原始上市,雅虎财经代码是NESN.SW(不是裸的NESN)
    "Realty Income(O)": "O",  # 房地产投资信托基金REIT
    "高露洁(CL)": "CL",
    "Genuine Parts(GPC)": "GPC",
    "Dover(DOV)": "DOV",
    "Altria(MO)": "MO",
    "Verizon(VZ)": "VZ",
    "辉瑞制药(PFE)": "PFE",
    "雪佛龙(CVX)": "CVX",
    "Enbridge(ENB)": "ENB",
    "AbbVie(ABBV)": "ABBV",
}

# 自选ETF,单独一个字典,前端会分成独立的"自选ETF"板块展示,不和上面的个股混在一起排序
ETF_WATCHLIST = {
    "标普500价值股(IVE)": "IVE",         # iShares 标普500价值股 ETF
    "纳指100(QQQ)": "QQQ",              # 景顺纳斯达克100指数ETF
    "标普高盛商品指数(GSG)": "GSG",       # iShares 标普高盛商品指数ETF
    "标普500价值(VOOV)": "VOOV",         # 先锋标普500价值指数ETF
    "必需消费品(XLP)": "XLP",            # SPDR必需性消费类股精选行业ETF
    "医疗保健(XLV)": "XLV",              # SPDR医疗保健ETF
    "能源(XLE)": "XLE",                 # 能源精选行业SPDR基金
    "消费品(VDC)": "VDC",                # 先锋消费品指数基金ETF
    "管理期货策略(DBMF)": "DBMF",         # iMGP DBi管理期货策略主动型ETF
    "南希佩洛西(NANC)": "NANC",           # Unusual Whales跟踪美国国会民主党议员(以南希·佩洛西为代表)股票交易的ETF
    # ---- v27新增:你说的"指数"实际都是ETF(不是指数本身),分类上放在自选ETF里,
    # 和上面IVE/QQQ这些同类,如果你确实是想要跟踪同名指数(而非这几只基金本身)
    # 需要告诉我换成对应的^指数代码 ----
    "短期国债ETF(SGOV)": "SGOV",           # iShares 0-3个月美国国债ETF
    "摩根大通股权溢价收益ETF(JEPI)": "JEPI",  # JPMorgan Equity Premium Income ETF
    "摩根大通纳指溢价收益ETF(JEPQ)": "JEPQ",  # JPMorgan Nasdaq Equity Premium Income ETF
    "股息成长ETF(DGRO)": "DGRO",            # iShares Core Dividend Growth ETF
    "全天候策略ETF(ALLW)": "ALLW",           # SSGA SPDR Bridgewater All Weather ETF
    "七巨头ETF(MAGS)": "MAGS",               # Roundhill Magnificent Seven ETF
}

# 每日重置杠杆产品单独展示，不参与普通股票/ETF的ATH回撤排序。
# 长期收益会受到每日复利路径和波动损耗影响，不能把“距离ATH”直接当作买入规则。
LEVERAGED_ETFS = {
    "每日三倍做多纳指100(TQQQ)": "TQQQ",
    "每日三倍做空纳指100(SQQQ)": "SQQQ",
    "每日三倍做多标普500(UPRO)": "UPRO",
    "每日两倍做多标普500(SSO)": "SSO",
    "每日两倍做多微策略(MSTX)": "MSTX",
    "每日两倍做空微策略(SMST)": "SMST",
}

# 数字资产财库(DAT)公司。这里只抓证券行情与ATH，不再为每家公司抓
# bitcointreasuries详情页，避免1 vCPU / 512MB VPS承担大量网页解析。
DAT_COMPANIES = {
    "Strategy": "MSTR",
    "Twenty One Capital": "XXI",
    "Metaplanet": "MPJPY",
    "MARA Holdings": "MARA",
    "Bullish": "BLSH",
    "Strive": "ASST",
    "Riot Platforms": "RIOT",
    "CleanSpark": "CLSK",
    "Hut 8": "HUT",
    "Trump Media": "DJT",
    "Block": "XYZ",
}
DAT_COMPANY_TYPES = {
    "Strategy": "比特币财库公司",
    "Twenty One Capital": "比特币财库公司",
    "Metaplanet": "比特币财库公司",
    "MARA Holdings": "比特币矿企",
    "Bullish": "加密资产交易平台",
    "Strive": "资管与比特币财库",
    "Riot Platforms": "比特币矿企",
    "CleanSpark": "比特币矿企",
    "Hut 8": "比特币矿企与数据中心",
    "Trump Media": "媒体与加密金融",
    "Block": "支付与金融科技",
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
# 重新启用夜盘，但不再根据任意股票代码自动拼接“USDT”。交易所可能存在与股票代码
# 同名的普通加密资产（此前CVX就因此显示成约1美元），现在只允许明确核实过的合约。
# 覆盖前还会与Yahoo正式价格比较，偏差过大时拒绝使用。
ENABLE_BITGET_STOCK_OVERLAY = True
BITGET_STOCK_SYMBOLS = {
    "TSLA": "TSLAUSDT",
    "NVDA": "NVDAUSDT",
    "AAPL": "AAPLUSDT",
    "MSTR": "MSTRUSDT",
    "META": "METAUSDT",
    "GOOG": "GOOGLUSDT",  # Bitget是GOOGL(A类)，主页GOOG是C类；两者接近但并非同一证券
    "AMZN": "AMZNUSDT",
    "CRCL": "CRCLUSDT",
    "COIN": "COINUSDT",
}
BITGET_MAX_DEVIATION_FROM_YAHOO = 0.20
GATE_SPOT_TICKERS_URL = "https://api.gateio.ws/api/v4/spot/tickers"
GATE_XSTOCK_SYMBOLS = {
    "TSLA": "TSLAX_USDT",
    "NVDA": "NVDAX_USDT",
    "AAPL": "AAPLX_USDT",
    "META": "METAX_USDT",
    "HOOD": "HOODX_USDT",
    "GOOG": "GOOGLX_USDT",
    "CRCL": "CRCLX_USDT",
    "COIN": "COINX_USDT",
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
        bitget_symbol = BITGET_STOCK_SYMBOLS.get(ticker)
        if not bitget_symbol:
            continue
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


def bitget_price_is_plausible(bitget_price, yahoo_price):
    """Bitget候选价格必须与Yahoo最近正式价格处于同一数量级。
    这不是判断正常基差，而是专门阻止CVX同名币之类的错误映射。"""
    try:
        bitget_price = float(bitget_price)
        yahoo_price = float(yahoo_price)
        if bitget_price <= 0 or yahoo_price <= 0:
            return False
        return abs(bitget_price / yahoo_price - 1) <= BITGET_MAX_DEVIATION_FROM_YAHOO
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def fetch_gate_xstock_prices(tickers):
    """Gate xStocks现货公开行情。逐个指定交易对，避免512MB VPS下载全站ticker大JSON。"""
    out = {}
    for ticker in tickers:
        pair = GATE_XSTOCK_SYMBOLS.get(ticker)
        if not pair:
            continue
        try:
            r = requests.get(
                GATE_SPOT_TICKERS_URL,
                params={"currency_pair": pair},
                headers={"Accept": "application/json", **HEADERS},
                timeout=10,
            )
            r.raise_for_status()
            rows = r.json()
            row = rows[0] if isinstance(rows, list) and rows else None
            if not row or row.get("currency_pair") != pair:
                continue
            price = float(row.get("last"))
            change_pct = float(row["change_percentage"]) if row.get("change_percentage") not in (None, "") else None
            out[ticker] = {
                "price": price,
                "change_pct": change_pct,
                "gate_symbol": pair,
            }
        except Exception as e:
            _record_error(f"gate_xstocks:{pair}", e)
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
ATH_TICKERS = list(WATCHLIST.values()) + list(ETF_WATCHLIST.values()) + list(DAT_COMPANIES.values()) + list(INDICES.values()) + list(METALS.values()) + [MSTR_TICKER, ASST_TICKER]
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
    "白银Ondo代币(SLVON)": "ishares-silver-trust-ondo-tokenized-stock",
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
        # v12修复:原来的正则匹配的是"we calculate the Buffett Indicator as XX%"这句话,
        # 但这句话实际上只存在于页面的meta description标签属性里,不在正文可见文本中——
        # BeautifulSoup的get_text()只提取文本节点,不会读meta标签的属性内容,所以这个正则
        # 在正文里永远匹配不到,这就是之前巴菲特指标数值一直是"--"的真实原因(不是网络问题)。
        # 改成匹配正文里实际存在的"The current ratio of 219% is approximately..."这句,
        # 备用正则匹配"Buffett Indicator = $69.15T / $31.57T = 219%"这个公式行。
        "value_regex": r'current ratio of\s*([\d.]+)\s*%\s*is approximately',
        "value_regex_fallback": r'Buffett Indicator\s*=\s*\$[\d.]+T\s*/\s*\$[\d.]+T\s*=\s*([\d.]+)\s*%',
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
    "shiller_pe": "https://www.in2013dollars.com/us-economy/shiller-pe",
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
    "BTC_MA200D": "https://www.okx.com/zh-hans/trade-market/latest-price/btc-usdt",
    "BTC_SUPPLY_IN_PROFIT": "https://www.looknode.com/zh/chart/percentInProfit/",
    "BTC_60D_RETURN": "https://www.looknode.com/zh/chart/sixtyDaysRaise/",
    "BTC_MCAP": "https://www.coingecko.com/en/coins/bitcoin",
    "BTC_DOMINANCE": "https://charts.bitbo.io/bitcoin-dominance/",
    "TOTAL2": "https://www.tradingview.com/symbols/TOTAL2/",
    "TOTAL3": "https://www.tradingview.com/symbols/TOTAL3/",
    "BTC_SOPR": "https://charts.bgeometrics.com/sopr.html",
    "BTC_PUELL": "https://charts.bgeometrics.com/puell_multiple.html",
    "BTC_HALVING": "https://mempool.space/",
    "BTC_FEAR_GREED": "https://alternative.me/crypto/fear-and-greed-index/",
    "MSTR_FLYWHEEL": "https://mstr.fuckbtc.com/",
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
    # ---- v27新增:友情链接 ----
    "FRIEND_AHR999": "https://9992100.xyz/btc/#radar",
    "FRIEND_FUCKBTC": "https://fuckbtc.com/",
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
    "etf_watchlist": {},
    "leveraged_etfs": {},
    "dat_companies": {},
    "indices": {},
    "metals": {},         # 贵金属(期货/ETF)
    "gold_retail": {},    # 周大福金价
    "crypto_extra": {},   # 其他加密货币(ETH/ADA/AVAX/SOL/HYPE/BNB/BGB/OKB/XAUT)
    "risk_indicators": {},  # 巴菲特指标/席勒PE(自动抓取) + 修正版/Tobin's Q(仅链接)
    "ath": {},            # 各代码的历史最高收盘价(月线),ENABLE_ATH_DRAWDOWN=False时为空
    "dividends": {},      # v27新增:自选股/自选ETF/指数的股息率+股息金额,每日更新一次
    "links": LINKS,
    "errors": [],
}

_last_fetch = {"crypto": 0, "stock": 0, "onchain": 0, "treasury": 0,
               "gold_retail": 0, "risk_indicator": 0, "ath": 0, "market_overview": 0}

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


def _has_any_value(d):
    """判断一个(可能嵌套的)字典里,是不是至少有一个字段的值不是None。
    这是v13的关键修复:之前判断"这类数据是否已经抓到过"用的是bool(STATE.get(...))——
    但STATE里的字典即使抓取全部失败,也会是{"字段名": None, ...}这种非空字典,
    bool()判断永远是True。这导致"每日更新"的调度逻辑从一开始就认为"已经有数据了",
    哪怕实际上全是null,也不会在同一天内重新尝试抓取——即使后端代码的抓取逻辑
    后来被修好了,也要等到第二天的07:XX窗口才会真正执行到新代码,这很可能是过去
    几轮"修复"看起来没生效的真正原因,不是新代码没生效,是压根没跑到。"""
    if not d:
        return False
    for v in d.values():
        if isinstance(v, dict):
            if _has_any_value(v):
                return True
        elif v is not None:
            return True
    return False


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
                "etf_watchlist": STATE["etf_watchlist"],
                "leveraged_etfs": STATE["leveraged_etfs"],
                "dat_companies": STATE["dat_companies"],
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
                STATE["etf_watchlist"] = s.get("etf_watchlist") or {}
                STATE["leveraged_etfs"] = s.get("leveraged_etfs") or {}
                STATE["dat_companies"] = s.get("dat_companies") or {}
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

def fetch_btc_dominance_total23():
    """比特币市场占有率(含/不含稳定币)、比特币市值、TOTAL2/TOTAL3市值。
    你给的bitbo.io和TradingView这两个链接我实测过,都是纯客户端渲染/JS图表,
    静态请求抓不到具体数值,和之前fuckbtc.com/looknode.com是同一类问题。
    改用CoinGecko的/global接口(我们已经在用的同一个数据源,免费公开,不需要
    API Key)——它直接给"全球加密货币总市值"和"BTC/ETH市值占比",再配合它的
    稳定币分类市值,就能自己算出这5项,不用碰那两个抓不到数据的网站。
    TOTAL2/TOTAL3是TradingView上的习惯叫法,含义分别是"总市值减去BTC"和
    "总市值减去BTC和ETH"。"""
    out = {
        "btc_market_cap": None, "total_market_cap": None,
        "btc_dominance_incl_stablecoins": None, "btc_dominance_excl_stablecoins": None,
        "total2_market_cap": None, "total3_market_cap": None,
    }
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=15)
        r.raise_for_status()
        data = r.json().get("data", {})
        total_cap = data.get("total_market_cap", {}).get("usd")
        btc_dom_pct = data.get("market_cap_percentage", {}).get("btc")
        eth_dom_pct = data.get("market_cap_percentage", {}).get("eth")
        if total_cap is None or btc_dom_pct is None:
            return out

        btc_cap = total_cap * btc_dom_pct / 100
        eth_cap = total_cap * (eth_dom_pct or 0) / 100

        out["total_market_cap"] = total_cap
        out["btc_market_cap"] = btc_cap
        out["btc_dominance_incl_stablecoins"] = btc_dom_pct
        out["total2_market_cap"] = total_cap - btc_cap
        out["total3_market_cap"] = total_cap - btc_cap - eth_cap

        # 稳定币分类市值,用来算"不含稳定币"的BTC市占率
        try:
            r2 = requests.get("https://api.coingecko.com/api/v3/coins/categories", timeout=15)
            r2.raise_for_status()
            categories = r2.json()
            stablecoin_cap = None
            for cat in categories:
                if (cat.get("id") or "").lower() == "stablecoins" or (cat.get("name") or "").lower() == "stablecoins":
                    stablecoin_cap = cat.get("market_cap")
                    break
            if stablecoin_cap and total_cap > stablecoin_cap:
                out["btc_dominance_excl_stablecoins"] = btc_cap / (total_cap - stablecoin_cap) * 100
        except Exception as e:
            _record_error("btc_dominance:stablecoins_category", e)
    except Exception as e:
        _record_error("btc_dominance_total23", e)
    return out


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
    out = {"value": None, "rating": None, "rating_cn": None, "zone": None, "std_dev": None}
    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
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
        if not m and cfg.get("value_regex_fallback"):
            m = re.search(cfg["value_regex_fallback"], text, re.IGNORECASE)
        out["value"] = float(m.group(1)) if m else None

        m2 = re.search(r'([\d.]+)\s+standard deviations?', text, re.IGNORECASE)
        out["std_dev"] = float(m2.group(1)) if m2 else None
    except Exception as e:
        _record_error(f"cmv:{key}", e)
    return out


def fetch_risk_indicators():
    """抓席勒市盈率(in2013dollars.com,和currentmarketvaluation.com的P/E10是同类指标,
    来源不同互相印证) + currentmarketvaluation.com的6个模型(巴菲特指标 + 这次新加的
    市盈率P/E10、市销率P/S、10年期美债利率、均值回归偏离度、股债收益差)。
    修正版巴菲特指标和Tobin's Q已按你的要求整个删除,不再抓取。"""
    out = {"shiller_pe": None, "shiller_pe_zone": None}

    try:
        r = requests.get(RISK_INDICATOR_PAGES["shiller_pe"], headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        # v12换源:之前用的multpl.com一直抓不到(显示"暂无数据"),换成in2013dollars.com,
        # 这个页面正文里有一句很干净的"The Shiller PE is 41.02 as of the beginning of
        # this month."可以直接匹配。
        m = re.search(r'The\s+Shiller\s+PE\s+is\s+([\d.]+)', text, re.IGNORECASE)
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
    """下载全历史日线，以显式拆股复权后的High计算ATH。

    必须让现价和ATH处于同一股份口径。旧版月线在部分海外股票（例如3350.T）
    会保留拆股前价格，导致现价约239、ATH却数万的假回撤。这里显式指定
    auto_adjust=True，并启用yfinance价格修复；日线还能把ATH日期精确到天。

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
            ticker = yf.Ticker(sym)
            try:
                hist = ticker.history(
                    period="max", interval="1d", auto_adjust=True, repair=True,
                    actions=False, timeout=ATH_PER_TICKER_TIMEOUT_SEC,
                )
            except (TypeError, ModuleNotFoundError):
                # repair=True在部分yfinance版本会调用SciPy；512MB VPS不需要为此安装
                # 重型SciPy。缺少SciPy或旧版不支持repair时，退回显式拆股复权日线。
                hist = ticker.history(
                    period="max", interval="1d", auto_adjust=True,
                    actions=False, timeout=ATH_PER_TICKER_TIMEOUT_SEC,
                )
            if hist is None or hist.empty:
                result = None
            else:
                idx = hist["High"].idxmax()
                result = {
                    "high": float(hist.loc[idx, "High"]),
                    "date": idx.strftime("%Y-%m-%d"),
                    "currency": infer_quote_currency(sym),
                    "adjustment": "split_adjusted_daily_high",
                    "adjustment_version": ATH_ADJUSTMENT_VERSION,
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


def fetch_mstr_flywheel():
    """从 mstr.fuckbtc.com 抓STRC相关的股息率和Runway信息。
    注意:这个页面和fuckbtc.com主站不一样——主站(fuckbtc.com)是纯客户端渲染,
    静态请求全部抓不到;但这个子站(mstr.fuckbtc.com)实测是服务器端渲染,正文里
    有明文的具体数字,可以直接抓。
    它本身也不是原始数据源,是从strategy.com官网和SEC 8-K文件整理过来的二手聚合页,
    strategy.com自己的页面(比如strategy.com/strc)是纯客户端渲染抓不到的,所以只能
    退而求其次用这个聚合页。"""
    out = {
        "strc_dividend_rate_pct": None, "strc_price": None,
        "strc_runway_months": None, "global_runway_months": None,
        "mnav_official": None, "as_of": None,
    }
    try:
        r = requests.get("https://mstr.fuckbtc.com/", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

        m = re.search(r'STRC\s*·\s*Stretch\s*\(?Perp\)?\s*\n*\s*([\d.]+)%\s*股息\s*@\s*\$?([\d.]+)', text)
        if m:
            out["strc_dividend_rate_pct"] = float(m.group(1))
            out["strc_price"] = float(m.group(2))

        m2 = re.search(r'STRC-only runway\s*\n*\s*([\d.]+)\s*mo', text)
        if m2:
            out["strc_runway_months"] = float(m2.group(1))

        m3 = re.search(r'Global runway\s*\n*\s*([\d.]+)\s*mo', text)
        if m3:
            out["global_runway_months"] = float(m3.group(1))

        m4 = re.search(r'mNAV\s*·\s*EV\s*\n*\s*([\d.]+)x', text)
        if m4:
            out["mnav_official"] = float(m4.group(1))

        m5 = re.search(r'^LIVE\s+(.+)$', text, re.MULTILINE)
        if m5:
            out["as_of"] = m5.group(1)
    except Exception as e:
        _record_error("mstr_flywheel", e)
    return out


def fetch_fear_greed_alt():
    """恐惧贪婪指数,来自alternative.me——这是一个独立、文档公开、长期稳定的免费API,
    不依赖fuckbtc.com或bgeometrics那两个不确定的路径。"""
    try:
        r = requests.get("https://api.alternative.me/fng/", params={"limit": 1}, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        if data:
            return {"value": float(data[0]["value"]), "classification": data[0]["value_classification"]}
    except Exception as e:
        _record_error("fear_greed_alt", e)
    return None


def fetch_halving_countdown_mempool():
    """减半倒计时,当前区块高度来自mempool.space(独立、文档公开的免费API),
    减半区块号按比特币协议规则算(每210,000个区块减半一次),不需要额外请求。"""
    try:
        r = requests.get("https://mempool.space/api/blocks/tip/height", timeout=10)
        r.raise_for_status()
        current_height = int(r.text.strip())
        next_halving_block = ((current_height // 210000) + 1) * 210000
        blocks_remaining = next_halving_block - current_height
        # 平均出块时间按10分钟估算,这是比特币协议的目标值,实际会有波动
        days_remaining = blocks_remaining * 10 / (60 * 24)
        return {
            "current_height": current_height,
            "next_halving_block": next_halving_block,
            "blocks_remaining": blocks_remaining,
            "days_remaining": days_remaining,
        }
    except Exception as e:
        _record_error("halving_countdown_mempool", e)
    return None


def fetch_200w_ma_okx():
    """200周均线,用OKX公开行情接口(不需要API Key)拉200根周K线,取收盘价算简单
    移动平均。这是独立、文档公开的公开市场数据接口,不依赖fuckbtc.com或bgeometrics
    那个不确定的路径。"""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/market/candles",
            params={"instId": "BTC-USDT", "bar": "1W", "limit": "200"},
            timeout=15,
        )
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", [])
        if not rows:
            return None
        closes = [float(row[4]) for row in rows]  # OKX candle格式: [ts,o,h,l,close,vol,...]
        return sum(closes) / len(closes)
    except Exception as e:
        _record_error("ma_200w_okx", e)
    return None


def fetch_200d_ma_okx():
    """200日均线,v18新增,和200周均线用同一个OKX接口,只是bar换成1D。
    取的是最近200根日K线(不刻意排除今天,你确认过对4年周期HODL策略来说这点误差
    不影响判断)。"""
    try:
        r = requests.get(
            "https://www.okx.com/api/v5/market/candles",
            params={"instId": "BTC-USDT", "bar": "1D", "limit": "200"},
            timeout=15,
        )
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", [])
        if not rows:
            return None
        closes = [float(row[4]) for row in rows]
        return sum(closes) / len(closes)
    except Exception as e:
        _record_error("ma_200d_okx", e)
    return None


def fetch_mvrv_z_btc_cache():
    """MVRV-Z换源,来自你自己搭的Cloudflare Worker(btc-cache),已实测格式干净:
    {"mvrvz":0.3741,"ts":...},不需要额外解析。"""
    try:
        r = requests.get("https://btc-cache.corms-cushier-0l.workers.dev/latest", timeout=15)
        r.raise_for_status()
        payload = r.json()
        val = payload.get("mvrvz")
        return float(val) if val is not None else None
    except Exception as e:
        _record_error("mvrv_z_btc_cache", e)
    return None


def fetch_mvrv_looknode():
    """MVRV换源,来自looknode-proxy的mCapRealizedRatio(市值/已实现市值,本质就是
    MVRV)。这个endpoint返回的是从比特币诞生至今的完整历史数组,不假设数组本身按
    时间顺序排列,显式用时间戳(t)取最大的那一条,更稳妥。"""
    try:
        r = requests.get(f"{LOOKNODE_PROXY_BASE}/mCapRealizedRatio", headers=HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if not data:
            return None
        latest = max(data, key=lambda point: point.get("t", 0))
        val = latest.get("v")
        return float(val) if val is not None else None
    except Exception as e:
        _record_error("mvrv_looknode", e)
    return None


LOOKNODE_PROXY_BASE = "https://looknode-proxy.corms-cushier-0l.workers.dev"


def fetch_looknode_proxy_latest(metric_path):
    """从fuckbtc.com作者自己搭的Cloudflare Worker代理抓数据——这个我已经用真实请求
    验证过,是可以直接访问的公开JSON接口,不需要看fuckbtc.com页面本身的JS。
    返回的是从比特币诞生至今的完整历史数组,我们只要最新(最后)一条。
    格式:{"code":100,"message":"操作成功","data":[{"t":时间戳(毫秒),"v":数值}, ...]}"""
    try:
        r = requests.get(f"{LOOKNODE_PROXY_BASE}/{metric_path}", headers=HEADERS, timeout=15)
        r.raise_for_status()
        payload = r.json()
        data = payload.get("data", [])
        if data:
            latest = data[-1]
            if latest.get("v") is not None:
                return {"value": latest.get("v"), "t": latest.get("t")}
    except Exception as e:
        _record_error(f"looknode_proxy:{metric_path}", e)
    return None


def fetch_cvdd_axeladler():
    """CVDD换成从axeladlerjr.com抓——这个页面实测是服务器端渲染的,正文里有明确的
    'CVDD is $44,667'这样的文本可以直接匹配,不像bitbo.io/bitcoinmagazinepro.com/
    coinglass.com那几个(都是客户端渲染,抓不到数值)。这是CVDD的主要来源,不再单纯
    依赖bgeometrics那个未经验证的cvdd endpoint。"""
    try:
        r = requests.get("https://axeladlerjr.com/charts/bitcoin-cvdd/", headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        m = re.search(r'CVDD is\s*\$?([\d,]+)', text)
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception as e:
        _record_error("cvdd:axeladlerjr", e)
    return None


def _classify_ratio(current, ref, ref_name, green_max, red_min, unit="x"):
    """通用的"现价/参照值"三色分类:低于green_max算熊市区间(绿),高于red_min算过热(红),
    中间算中性(黄)。这里的green_max/red_min是我自己综合判断定的经验区间,不是某个
    单一权威来源认证过的标准阈值,不同分析师给的具体数字会有出入,这里只是给你一个
    直观的参考,不代表唯一"正确答案"。"""
    if current is None or ref in (None, 0):
        return None
    ratio = current / ref
    if ratio >= red_min:
        zone = "red"
        desc = "过热"
    elif ratio <= green_max:
        zone = "green"
        desc = "熊市区间"
    else:
        zone = "yellow"
        desc = "中性"
    return {"zone": zone, "text": f"现价是{ref_name}的{ratio:.2f}{unit},{desc}"}


def _classify_absolute(value, green_max, red_min, name, unit=""):
    """通用的"绝对数值"三色分类,逻辑同上,只是不需要现价参照,直接用数值本身分档。"""
    if value is None:
        return None
    if value >= red_min:
        zone, desc = "red", "过热"
    elif value <= green_max:
        zone, desc = "green", "熊市区间"
    else:
        zone, desc = "yellow", "中性"
    return {"zone": zone, "text": f"{name}={value:.3f}{unit},{desc}"}


def _extract_value_py(obj):
    """从bgeometrics那种结构不完全统一的原始payload里,通用地把数值提取出来
    (镜像前端JS的extractOnchainValue逻辑)。比如RHODL的原始字段叫"rhodlRatio",
    NUPL的原始字段就叫"nupl",这里不针对每个字段单独写死key名,而是找第一个
    看起来像"数值"的字段。"""
    if obj is None:
        return None
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and re.search(r'value|price|mvrv|score|nupl|rhodl|ratio|sopr|puell', k, re.IGNORECASE):
                return v
    return None


def build_onchain_explanations(out, live_btc_price):
    """给链上指标各配一句话解释+三色分类(红=过热/黄=中性/绿=熊市/低估),供前端直接
    展示,不需要前端自己再算一遍阈值。v21按你给的具体阈值重写,这些数字是你确认过的,
    不是我随便定的,但仍然是"经验区间"性质,不代表某个绝对精确的科学分界线。"""
    exp = {}

    # MVRV: <0.9低估(绿) · 0.9~1.8中立(黄) · >1.8高估(红)
    mvrv_val = _extract_value_py(out.get("mvrv"))
    if mvrv_val is not None:
        if mvrv_val > 1.8:
            exp["mvrv"] = {"zone": "red", "text": f"MVRV={mvrv_val:.3f},高估(>1.8)"}
        elif mvrv_val < 0.9:
            exp["mvrv"] = {"zone": "green", "text": f"MVRV={mvrv_val:.3f},低估(<0.9)"}
        else:
            exp["mvrv"] = {"zone": "yellow", "text": f"MVRV={mvrv_val:.3f},中立(0.9~1.8)"}
    else:
        exp["mvrv"] = None

    # MVRV-Z: <0极度低估(绿) · 0~5中立(黄) · >5高估(红)
    mvrv_z_val = _extract_value_py(out.get("mvrv_zscore"))
    if mvrv_z_val is not None:
        if mvrv_z_val > 5:
            exp["mvrv_zscore"] = {"zone": "red", "text": f"MVRV-Z={mvrv_z_val:.3f},高估(>5)"}
        elif mvrv_z_val < 0:
            exp["mvrv_zscore"] = {"zone": "green", "text": f"MVRV-Z={mvrv_z_val:.3f},极度低估(<0)"}
        else:
            exp["mvrv_zscore"] = {"zone": "yellow", "text": f"MVRV-Z={mvrv_z_val:.3f},中立(0~5)"}
    else:
        exp["mvrv_zscore"] = None

    # Realized Price: 换成显示"MVRV=0.9/1.8对应的具体价位"这种更直观的表述,
    # 而不是单纯的比值描述;分区判断沿用MVRV本身的0.9/1.8分界线。
    realized_val = _extract_value_py(out.get("realized_price"))
    if realized_val and live_btc_price:
        price_low = realized_val * 0.9
        price_high = realized_val * 1.8
        if live_btc_price < price_low:
            zone = "green"
        elif live_btc_price > price_high:
            zone = "red"
        else:
            zone = "yellow"
        exp["realized_price"] = {"zone": zone, "text": f"90%实现价格为${price_low:,.0f},180%实现价格为${price_high:,.0f}"}
    else:
        exp["realized_price"] = None

    # Balanced Price: 重点是"有没有跌破",跌破通常代表深熊绝对底部;
    # 没跌破就显示离它还有多少美元的距离。
    balanced_val = _extract_value_py(out.get("balanced_price"))
    if balanced_val and live_btc_price:
        gap = live_btc_price - balanced_val
        if gap < 0:
            exp["balanced_price"] = {"zone": "green", "text": "已跌破Balanced Price,通常代表深熊绝对底部区域"}
        else:
            exp["balanced_price"] = {"zone": "yellow", "text": f"距离Balanced Price还有${gap:,.0f}美元"}
    else:
        exp["balanced_price"] = None

    # CVDD: 现价在这条"历史铁底"上方/下方多少个百分点
    cvdd_val = out.get("cvdd")
    if cvdd_val and live_btc_price:
        pct = (live_btc_price / cvdd_val - 1) * 100
        zone = "green" if pct < 0 else "yellow"
        direction = "上方" if pct >= 0 else "下方"
        exp["cvdd"] = {"zone": zone, "text": f"CVDD是目前有效的历史铁底,现价在其{direction}{abs(pct):.1f}%"}
    else:
        exp["cvdd"] = None

    # 200周均线保留原来"现价是多少倍"的表述方式,你没有单独给这项新阈值,沿用旧的
    ma_200w_val = out.get("ma_200w")
    exp["ma_200w"] = _classify_ratio(live_btc_price, ma_200w_val, "200周均线", green_max=1, red_min=3)

    # 60日累计涨幅: <-20%安全区(绿) · -20~50%中立(黄) · 50~100%风险(红) · >100%极高风险(红,文字额外标注)
    return_60d = out.get("btc_60d_return_pct")
    if return_60d is not None:
        if return_60d > 100:
            exp["btc_60d_return"] = {"zone": "red", "text": f"60日涨幅{return_60d:.1f}%,极高风险(>100%)"}
        elif return_60d > 50:
            exp["btc_60d_return"] = {"zone": "red", "text": f"60日涨幅{return_60d:.1f}%,风险区间(50~100%)"}
        elif return_60d < -20:
            exp["btc_60d_return"] = {"zone": "green", "text": f"60日涨幅{return_60d:.1f}%,安全区(<-20%)"}
        else:
            exp["btc_60d_return"] = {"zone": "yellow", "text": f"60日涨幅{return_60d:.1f}%,中立(-20%~50%)"}
    else:
        exp["btc_60d_return"] = None

    # SOPR: =1是卖出盈亏分界线,<0.95恐慌(绿) · 0.95~1.05中立(黄) · >1.05高估(红)
    sopr_val = _extract_value_py(out.get("sopr"))
    if sopr_val is not None:
        if sopr_val > 1.05:
            exp["sopr"] = {"zone": "red", "text": f"SOPR={sopr_val:.3f},高估(>1.05)。SOPR=1是链上持币者卖出时的盈亏分界线"}
        elif sopr_val < 0.95:
            exp["sopr"] = {"zone": "green", "text": f"SOPR={sopr_val:.3f},恐慌(<0.95)。SOPR=1是链上持币者卖出时的盈亏分界线"}
        else:
            exp["sopr"] = {"zone": "yellow", "text": f"SOPR={sopr_val:.3f},中立(0.95~1.05)"}
    else:
        exp["sopr"] = None

    # Puell Multiple: <0.5矿工投降底部(绿) · 0.5~2.5中立(黄) · >2.5高估(红)
    puell_val = _extract_value_py(out.get("puell_multiple"))
    if puell_val is not None:
        if puell_val > 2.5:
            exp["puell_multiple"] = {"zone": "red", "text": f"Puell Multiple={puell_val:.3f},高估(>2.5)"}
        elif puell_val < 0.5:
            exp["puell_multiple"] = {"zone": "green", "text": f"Puell Multiple={puell_val:.3f},矿工投降的底部区间(<0.5)"}
        else:
            exp["puell_multiple"] = {"zone": "yellow", "text": f"Puell Multiple={puell_val:.3f},中立(0.5~2.5)"}
    else:
        exp["puell_multiple"] = None

    # NUPL: 5档,但我们只有3种颜色,红/黄各覆盖其中两档,具体是哪一档在文字里区分
    # <0(恐慌/底部,绿) · 0~0.25(怀疑,黄) · 0.25~0.5(乐观/中立,黄) ·
    # 0.5~0.75(信念/高估,红) · >0.75(极度贪婪/顶部,红)
    nupl_val = _extract_value_py(out.get("nupl"))
    if nupl_val is not None:
        if nupl_val > 0.75:
            exp["nupl"] = {"zone": "red", "text": f"NUPL={nupl_val:.3f},极度贪婪/顶部(>0.75)"}
        elif nupl_val > 0.5:
            exp["nupl"] = {"zone": "red", "text": f"NUPL={nupl_val:.3f},信念/高估(0.5~0.75)"}
        elif nupl_val > 0.25:
            exp["nupl"] = {"zone": "yellow", "text": f"NUPL={nupl_val:.3f},乐观/中立(0.25~0.5)"}
        elif nupl_val >= 0:
            exp["nupl"] = {"zone": "yellow", "text": f"NUPL={nupl_val:.3f},怀疑(0~0.25)"}
        else:
            exp["nupl"] = {"zone": "green", "text": f"NUPL={nupl_val:.3f},恐慌/底部(<0)"}
    else:
        exp["nupl"] = None

    # RHODL比率: 接近绿色通道(<350)底部低估 · 接近红色通道(>50000)顶部高估
    rhodl_val = _extract_value_py(out.get("rhodl"))
    if rhodl_val is not None:
        if rhodl_val > 50000:
            exp["rhodl"] = {"zone": "red", "text": f"RHODL比率={rhodl_val:,.0f},接近红色通道,顶部高估(>50000)"}
        elif rhodl_val < 350:
            exp["rhodl"] = {"zone": "green", "text": f"RHODL比率={rhodl_val:,.0f},接近绿色通道,底部低估(<350)"}
        else:
            exp["rhodl"] = {"zone": "yellow", "text": f"RHODL比率={rhodl_val:,.0f},中间区间"}
    else:
        exp["rhodl"] = None

    # 盈利中的百分比: <50底部极度悲观(绿) · 50~85中立(黄) · >85阶段性/周期性顶部(红)
    supply_val = _extract_value_py(out.get("supply_in_profit_pct"))
    if supply_val is not None:
        if supply_val > 85:
            exp["supply_in_profit_pct"] = {"zone": "red", "text": f"盈利占比{supply_val:.1f}%,阶段性/周期性顶部信号(>85)"}
        elif supply_val < 50:
            exp["supply_in_profit_pct"] = {"zone": "green", "text": f"盈利占比{supply_val:.1f}%,底部极度悲观(<50)"}
        else:
            exp["supply_in_profit_pct"] = {"zone": "yellow", "text": f"盈利占比{supply_val:.1f}%,中立(50~85)"}
    else:
        exp["supply_in_profit_pct"] = None

    return exp


def fetch_onchain_metrics():
    out = {}
    rate_limited = False
    for key, endpoint in ONCHAIN_ENDPOINTS.items():
        if rate_limited:
            # v14新增:一旦这一轮里遇到过429(限流),后面几个大概率也会是429,
            # 干脆不再继续尝试,省下配额留给下一次真正该跑的时候,而不是明知
            # 会失败还硬发8次请求
            out[key] = None
            continue
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
            if "429" in str(e):
                rate_limited = True
        # v14新增:每个请求之间插入1-2秒随机间隔,不要瞬间把9个请求一起打出去。
        # bgeometrics免费额度本来就很紧(每小时8次/每天15次),瞬间并发比均匀分布
        # 更容易被判定成异常流量,即使总数没超限额也可能触发额外的限流。
        # TODO: 这里最治本的办法是去 https://portal.bgeometrics.com/login 免费注册
        # 一个账号拿BGEOMETRICS_TOKEN填到上面,注册用户的配额通常比匿名访问宽松很多。
        time.sleep(random.uniform(1, 2))

    # CVDD优先用axeladlerjr.com的结果覆盖(更可信),bgeometrics那份留着做兜底,
    # 如果axeladlerjr抓失败(返回None),就保留上面bgeometrics可能抓到的值,不强行覆盖成None
    cvdd_val = fetch_cvdd_axeladler()
    if cvdd_val is not None:
        out["cvdd"] = cvdd_val
    out["btc_60d_return_pct"] = fetch_btc_60d_return()

    # v16新增:这3个直接用独立公开API,不走bgeometrics那条不确定的猜测路径
    out["fear_greed"] = fetch_fear_greed_alt()
    out["halving"] = fetch_halving_countdown_mempool()
    ma_200w_okx = fetch_200w_ma_okx()
    if ma_200w_okx is not None:
        out["ma_200w"] = ma_200w_okx  # 优先用OKX算出来的这个覆盖bgeometrics那份(如果有的话)

    # v17新增:用fuckbtc.com作者的looknode-proxy覆盖SOPR/Puell Multiple(这两个之前
    # 一直没确认过bgeometrics的猜测路径对不对),顺带也覆盖Balanced Price做交叉验证。
    # 没有覆盖MVRV,因为bgeometrics的mvrv这个endpoint已经确认能用了,不需要额外来源。
    sopr_val = fetch_looknode_proxy_latest("sopr")
    if sopr_val is not None:
        out["sopr"] = sopr_val
    puell_val = fetch_looknode_proxy_latest("puellMultiple")
    if puell_val is not None:
        out["puell_multiple"] = puell_val
    balanced_val = fetch_looknode_proxy_latest("balancedPrice")
    if balanced_val is not None:
        out["balanced_price"] = balanced_val

    # v18新增:MVRV/MVRV-Z换成你确认的两个稳定源,200日均线新增(不替换200周均线),
    # Realized Price改成用新MVRV反推(现价÷MVRV)。
    mvrv_new = fetch_mvrv_looknode()
    if mvrv_new is not None:
        out["mvrv"] = {"value": mvrv_new}  # 包一层"value"字段,匹配前端extractOnchainValue的通用解析逻辑

    mvrv_z_new = fetch_mvrv_z_btc_cache()
    if mvrv_z_new is not None:
        out["mvrv_zscore"] = {"value": mvrv_z_new}

    ma_200d = fetch_200d_ma_okx()
    if ma_200d is not None:
        out["ma_200d"] = ma_200d

    # Realized Price = 现价 ÷ MVRV,需要当前BTC现价(从STATE里读,不重新发请求)。
    # 只有这次新抓到的MVRV(mvrv_new)成功时才反推,不去尝试解析旧bgeometrics那种
    # 嵌套结构做兜底,保持逻辑简单。
    try:
        with STATE_LOCK:
            live_btc_price = STATE.get("btc", {}).get("price_usd")
        if live_btc_price and mvrv_new:
            out["realized_price"] = {"value": live_btc_price / mvrv_new}
    except Exception as e:
        _record_error("realized_price_derive", e)

    # v20新增:给9个指标配一句话解释+三色分类(红/黄/绿),需要结合现价,所以放在
    # 这几个值都算完之后统一算。
    try:
        with STATE_LOCK:
            live_btc_price_for_exp = STATE.get("btc", {}).get("price_usd")
        out["explanations"] = build_onchain_explanations(out, live_btc_price_for_exp)
    except Exception as e:
        _record_error("build_onchain_explanations", e)
        out["explanations"] = {}

    return out


def fetch_dividends(ticker_map):
    """批量抓取股息(分红)信息,和beta/市值一样用.info这个"重"接口,所以放进
    "每日更新"档,不跟股价一样每次刷新都调用。返回 {name: {"rate":.., "yield_pct":..}}。
    rate是雅虎财经的dividendRate(每股每年派息的美元/本币金额),yield_pct是
    股息率百分比数字(比如0.49表示0.49%,不是49%)。
    没有分红的公司(比如很多成长股)这两个字段会是None,前端会显示"--"或者
    直接不展示这一行,不会伪造成0(0和"没有这个数据"是两回事)。

    v27.1修复:之前这里错误地把dividendYield当成"0.0049这种小数,要×100变成
    百分比"来处理,但实测(你反馈NVDA显示49.00%这个明显不合理的数字)发现雅虎
    财经现在这个字段返回的已经是百分比数值本身(比如0.49就直接表示0.49%,不是
    0.49%的百分之一),不需要再乘100。这里改成直接原样使用,不做任何换算。"""
    out = {}
    for name, sym in ticker_map.items():
        if not sym:
            out[name] = {"rate": None, "yield_pct": None}
            continue
        try:
            info = yf.Ticker(sym).info
            rate = info.get("dividendRate")
            yield_pct = info.get("dividendYield")  # 已经是百分比数值本身,不做换算
            out[name] = {"rate": rate, "yield_pct": yield_pct}
        except Exception as e:
            out[name] = {"rate": None, "yield_pct": None}
            _record_error(f"dividend:{sym}", e)
    return out


def fetch_yahoo_beta_marketcap(ticker):
    """抓Beta系数和市值,这两个字段在yfinance里要用比较"重"的.info属性
    (会多打好几个Yahoo财经的接口,不像fast_info那么轻量),所以放进"每日更新"档,
    不跟股价一样每60秒都调用一次,减少对雅虎财经的请求压力。"""
    out = {"beta": None, "market_cap": None}
    try:
        info = yf.Ticker(ticker).info
        out["beta"] = info.get("beta")
        out["market_cap"] = info.get("marketCap")
    except Exception as e:
        _record_error(f"yahoo_beta_marketcap:{ticker}", e)
    return out


def infer_quote_currency(symbol):
    """Yahoo fast_info偶尔不返回currency；按交易所后缀提供保守回退。"""
    symbol = (symbol or "").upper()
    suffix_map = {
        ".T": "JPY", ".KS": "KRW", ".KQ": "KRW", ".PA": "EUR", ".AS": "EUR",
        ".DE": "EUR", ".MI": "EUR", ".SW": "CHF", ".L": "GBP", ".AE": "AED",
        ".SS": "CNY", ".SZ": "CNY", ".TW": "TWD", ".HK": "HKD",
    }
    for suffix, currency in suffix_map.items():
        if symbol.endswith(suffix):
            return currency
    return "USD"


def fetch_quotes(ticker_map):
    # 过滤掉ticker为None的占位项(目前WATCHLIST里没有这种情况,防御性保留,
    # 万一以后又加了个没有对应上市标的的条目,不会导致yf.Tickers()报错),
    # 这些不发请求,直接在结果里给null,前端会显示"--"
    real_map = {name: sym for name, sym in ticker_map.items() if sym}
    symbols = list(real_map.values())
    result = {name: {"symbol": None, "price": None, "prev_close": None, "change_pct": None, "currency": None}
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
                currency = _get(fi, "currency") or infer_quote_currency(sym)
                chg_pct = None
                if price is not None and prev_close:
                    chg_pct = (price - prev_close) / prev_close * 100
                result[name] = {
                    "symbol": sym, "price": price, "prev_close": prev_close,
                    "change_pct": chg_pct, "currency": currency,
                }
            except Exception as e:
                result[name] = {
                    "symbol": sym, "price": None, "prev_close": None,
                    "change_pct": None, "currency": infer_quote_currency(sym),
                }
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
                    # 注意:这里不能直接整个替换STATE["btc"],要保留market_overview那几个
                    # 字段(它们是单独5分钟刷新一次的,如果这里整个覆盖掉,会被这个30秒
                    # 一次的循环冲掉)
                    prev_overview = {
                        k: STATE.get("btc", {}).get(k)
                        for k in ("btc_market_cap", "total_market_cap",
                                  "btc_dominance_incl_stablecoins", "btc_dominance_excl_stablecoins",
                                  "total2_market_cap", "total3_market_cap")
                    }
                    STATE["btc"] = {
                        "price_usd": btc_row.get("price"),
                        "change_24h_pct": btc_row.get("change_pct"),
                        "ath": btc_row.get("ath"),
                        "ath_change_pct": btc_row.get("ath_change_pct"),
                        "ath_date": btc_row.get("ath_date"),
                        **prev_overview,
                    }
                    STATE["crypto_extra"] = {k: v for k, v in crypto.items() if k != "BTC"}
                _last_fetch["crypto"] = now
                save_cache_log()
        except Exception as e:
            _record_error("crypto_loop", e)

        try:
            # BTC市占率/TOTAL2/TOTAL3不需要跟价格一样30秒刷新一次(这几个是偏宏观的
            # 慢变量,而且/coins/categories这个接口本身比较"重"),单独给5分钟间隔
            if now - _last_fetch["market_overview"] >= MARKET_OVERVIEW_REFRESH_SEC:
                overview = fetch_btc_dominance_total23()
                with STATE_LOCK:
                    STATE["btc"].update(overview)
                _last_fetch["market_overview"] = now
                save_cache_log()
        except Exception as e:
            _record_error("market_overview_loop", e)

        try:
            if now - _last_fetch["stock"] >= STOCK_REFRESH_SEC:
                def _jitter():
                    time.sleep(random.uniform(*STOCK_FETCH_JITTER_SEC))

                mstr_q = fetch_quotes({"MSTR": MSTR_TICKER}).get("MSTR", {})
                _jitter()
                preferreds = fetch_quotes(MSTR_PREFERREDS)
                _jitter()
                watch = fetch_quotes(WATCHLIST)
                # MSTR/STRC 已经在别处抓过了,这里直接复用结果merge进watchlist,
                # 不再对同一个ticker重复发一次yfinance请求
                watch["策略(MSTR)"] = mstr_q
                _jitter()
                idx = fetch_quotes(INDICES)
                _jitter()
                metals = fetch_quotes(METALS)
                _jitter()
                etf_watch = fetch_quotes(ETF_WATCHLIST)  # ETF没有Bitget股票永续合约,不做夜盘价格覆盖
                _jitter()
                leveraged_etfs = fetch_quotes(LEVERAGED_ETFS)
                _jitter()
                dat_companies = fetch_quotes(DAT_COMPANIES)
                for company_name, quote in dat_companies.items():
                    if isinstance(quote, dict):
                        quote["company_type"] = DAT_COMPANY_TYPES.get(company_name, "其他")

                # ---- 非交易时段用Bitget股票永续合约价格覆盖(仅限美股,见文件头说明) ----
                market_open = is_us_market_open()
                for q in list(watch.values()) + [mstr_q]:
                    if isinstance(q, dict):
                        q["price_source"] = "yahoo"
                        q["market_open"] = market_open
                if ENABLE_BITGET_STOCK_OVERLAY and not market_open:
                    overlay_tickers = [v for v in WATCHLIST.values() if v] + [MSTR_TICKER]
                    bitget_data = fetch_bitget_stock_perps(overlay_tickers)
                    ticker_to_names = {}
                    for name, t in WATCHLIST.items():
                        ticker_to_names.setdefault(t, []).append(name)
                    ticker_to_names.setdefault(MSTR_TICKER, []).append("策略(MSTR)")
                    for ticker, bg in bitget_data.items():
                        for name in ticker_to_names.get(ticker, []):
                            if name in watch:
                                if not bitget_price_is_plausible(bg["price"], watch[name].get("price")):
                                    _record_error(
                                        f"bitget_stock_perps:rejected:{ticker}",
                                        ValueError(f"Bitget={bg['price']}, Yahoo={watch[name].get('price')}")
                                    )
                                    continue
                                watch[name]["price"] = bg["price"]
                                watch[name]["change_pct"] = bg["change_pct"]
                                watch[name]["price_source"] = "bitget_perp_24h"
                                watch[name]["bitget_symbol"] = bg["bitget_symbol"]
                    # Gate作为第二来源：Bitget没有返回或被校验拒绝时才使用，不来回跳源。
                    gate_needed = [
                        ticker for ticker in GATE_XSTOCK_SYMBOLS
                        if any(
                            name in watch and watch[name].get("price_source") == "yahoo"
                            for name in ticker_to_names.get(ticker, [])
                        )
                    ]
                    gate_data = fetch_gate_xstock_prices(gate_needed)
                    for ticker, gate in gate_data.items():
                        for name in ticker_to_names.get(ticker, []):
                            if name not in watch or watch[name].get("price_source") != "yahoo":
                                continue
                            if not bitget_price_is_plausible(gate["price"], watch[name].get("price")):
                                _record_error(
                                    f"gate_xstocks:rejected:{ticker}",
                                    ValueError(f"Gate={gate['price']}, Yahoo={watch[name].get('price')}")
                                )
                                continue
                            watch[name]["price"] = gate["price"]
                            watch[name]["change_pct"] = gate["change_pct"]
                            watch[name]["price_source"] = "gate_xstock_24h"
                            watch[name]["gate_symbol"] = gate["gate_symbol"]
                    if ticker_to_names.get(MSTR_TICKER, []) and MSTR_TICKER in bitget_data:
                        bg = bitget_data[MSTR_TICKER]
                        if bitget_price_is_plausible(bg["price"], mstr_q.get("price")):
                            mstr_q["price"] = bg["price"]
                            mstr_q["change_pct"] = bg["change_pct"]
                            mstr_q["price_source"] = "bitget_perp_24h"
                            mstr_q["bitget_symbol"] = bg["bitget_symbol"]

                with STATE_LOCK:
                    btc_price_now = STATE.get("btc", {}).get("price_usd")
                    since_adoption = compute_since_mstr_adoption(mstr_q.get("price"), btc_price_now)
                    STATE.setdefault("mstr", {})["quote"] = mstr_q
                    STATE.setdefault("mstr", {})["since_adoption"] = since_adoption
                    STATE["mstr_preferreds"] = preferreds
                    STATE["watchlist"] = watch
                    STATE["etf_watchlist"] = etf_watch
                    STATE["leveraged_etfs"] = leveraged_etfs
                    STATE["dat_companies"] = dat_companies
                    STATE["indices"] = idx
                    STATE["metals"] = metals
                _last_fetch["stock"] = now
                save_cache_log()
        except Exception as e:
            _record_error("stock_loop", e)

        try:
            if should_run_daily_job("mstr_flywheel", _has_any_value(STATE.get("mstr", {}).get("flywheel"))):
                flywheel = fetch_mstr_flywheel()
                yahoo_extra = fetch_yahoo_beta_marketcap(MSTR_TICKER)
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["flywheel"] = flywheel
                    STATE.setdefault("mstr", {})["yahoo_extra"] = yahoo_extra
                mark_daily_job_done("mstr_flywheel")
                save_cache_log()
        except Exception as e:
            _record_error("mstr_flywheel_loop", e)

        try:
            if should_run_daily_job("treasury", _has_any_value(STATE.get("mstr", {}).get("treasury"))):
                mstr_t = fetch_treasury_page(TREASURY_PAGES["MSTR"])
                with STATE_LOCK:
                    STATE.setdefault("mstr", {})["treasury"] = mstr_t
                _last_fetch["treasury"] = now
                mark_daily_job_done("treasury")
                save_cache_log()
        except Exception as e:
            _record_error("treasury_loop", e)

        try:
            if should_run_daily_job("onchain", _has_any_value(STATE.get("onchain"))):
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
            if should_run_daily_job("risk_indicator", _has_any_value(STATE.get("risk_indicators"))):
                ri = fetch_risk_indicators()
                with STATE_LOCK:
                    STATE["risk_indicators"] = ri
                _last_fetch["risk_indicator"] = now
                mark_daily_job_done("risk_indicator")
                save_cache_log()
        except Exception as e:
            _record_error("risk_indicator_loop", e)

        try:
            # v27新增:自选股+自选ETF+指数的股息(分红)信息,每天更新一次,
            # 用yfinance的.info这个"重"接口,不适合像股价那样60秒刷新一次
            if should_run_daily_job("dividends", _has_any_value(STATE.get("dividends"))):
                div_map = {}
                div_map.update(WATCHLIST)
                div_map.update(ETF_WATCHLIST)
                div_map.update(LEVERAGED_ETFS)
                div_map.update(INDICES)
                dividends = fetch_dividends(div_map)
                with STATE_LOCK:
                    STATE["dividends"] = dividends
                _last_fetch["dividends"] = now
                mark_daily_job_done("dividends")
                save_cache_log()
        except Exception as e:
            _record_error("dividends_loop", e)

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
    美东时间07:XX窗口。
    v20新增:自选股新增了ticker以后,如果"今天的整批"已经跑过了,新增的这几个
    ticker会被should_run_daily_job判定成"不用跑、等明天"——但这样体验不好
    (新加的股票要等到第二天才有距ATH数据)。所以额外加一段检查:不管今天整批
    跑没跑过,只要发现ATH_TICKERS里有STATE["ath"]里完全没有的代码,就单独马上
    补算这几个,不用等明天。"""
    while True:
        try:
            if ENABLE_ATH_DRAWDOWN and should_run_daily_job("ath", _has_any_value(STATE.get("ath"))):
                _log(f"开始计算ATH,共{len(ATH_TICKERS)}个代码,单个超时{ATH_PER_TICKER_TIMEOUT_SEC}秒...")
                fetch_ath_drawdown(ATH_TICKERS)  # 内部会边算边写STATE,不需要接返回值
                _last_fetch["ath"] = time.time()
                mark_daily_job_done("ath")
                _log("ATH计算完成一轮")
            elif ENABLE_ATH_DRAWDOWN:
                with STATE_LOCK:
                    existing_keys = set(STATE.get("ath", {}).keys())
                with STATE_LOCK:
                    existing_ath = dict(STATE.get("ath", {}))
                missing = [
                    t for t in ATH_TICKERS
                    if t not in existing_keys
                    or not isinstance(existing_ath.get(t), dict)
                    or existing_ath[t].get("adjustment_version") != ATH_ADJUSTMENT_VERSION
                ]
                if missing:
                    _log(f"发现{len(missing)}个新增/尚未计算过ATH的代码,单独补算(不等明天): {missing}")
                    fetch_ath_drawdown(missing)
                    save_cache_log()
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
        if path == "/stock.html":
            try:
                with open("stock.html", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({"error": "stock.html not found next to server.py"}, 404)
            return
        if path == "/cache_stock.json":
            # 这个文件是独立的stock500_fetch.py脚本(通过cron定时)生成的,server.py这里
            # 只是原样读文件返回,不会触发抓取,不会增加主循环负担。
            try:
                with open("cache_stock.json", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({"error": "cache_stock.json还没生成,先手动跑一次 python3 stock500_fetch.py --limit 20 测试"}, 404)
            return
        if path == "/cache_sec_fundamentals.json":
            # SEC基本面由独立的stock_sec_fetch.py分批生成。这里只读文件并原样返回，
            # 不在server.py进程里抓取或计算，避免增加512MB VPS的常驻内存压力。
            try:
                with open("cache_sec_fundamentals.json", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({
                    "error": "cache_sec_fundamentals.json还没生成,先运行stock_sec_fetch.py"
                }, 404)
            return
        if path == "/qdii.html":
            # v27新增:中国QDII基金监控页面,和stock.html同一个模式——server.py只是
            # 原样读文件返回,数据抓取是独立的qdii_fetch.py脚本(cron定时)在做。
            try:
                with open("qdii.html", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({"error": "qdii.html not found next to server.py"}, 404)
            return
        if path == "/cache_qdii.json":
            try:
                with open("cache_qdii.json", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                self._send_json({"error": "cache_qdii.json还没生成,先手动跑一次 python3 qdii_fetch.py 测试"}, 404)
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
        if path == "/methodology.txt":
            body = METHODOLOGY_LOG_TEXT.format(generated_at=time.strftime("%Y-%m-%d %H:%M:%S")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="dashboard_methodology.txt"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
