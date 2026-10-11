# 经济频道：采集 -> 来源分级 -> 分类 -> 去重 -> eco.json（与食品站、AI 频道完全分开）。依赖: feedparser
import json, re, time, socket, os, sys, calendar, datetime as dt
from urllib.parse import quote, urlparse
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (eco-news bot)"
g = lambda q, hl, gl, ce: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl={hl}&gl={gl}&ceid={ce}"
zh = lambda q: g(q, "zh-CN", "CN", "CN:zh-Hans")
en = lambda q: g(q, "en-US", "US", "US:en")
FEEDS = [  # 想加来源就加一行 RSS 地址
    zh("国务院 OR 发改委 OR 财政部 OR 商务部 政策 OR 通知 OR 意见 OR 办法 OR 常务会议"), zh("site:xinhuanet.com 经济 OR 政策"),
    zh("site:people.com.cn 经济 OR 政策"), zh("site:gov.cn 政策 OR 通知 OR 意见"),
    zh("央行 OR 人民银行 利率 OR LPR OR 汇率 OR 货币政策"), zh("国家统计局 GDP OR CPI OR PPI OR PMI OR 就业"),
    zh("农业农村部 OR 市场监管总局 OR 生猪 OR 鸡蛋 政策 OR 调控 OR 收储 OR 食品安全"), zh("国家主席 OR 总理 OR 外交部 会见 OR 会谈 OR 访问 OR 峰会"),
    zh("美联储 OR 欧洲央行 OR 美国经济 OR 欧元区 OR 日本经济"), zh("关税 OR 出口管制 OR 贸易协定 中美 OR 欧盟 OR 东盟"), zh("原油 OR 油价 OR 大宗商品 国际经济 展望"),
    en("Federal Reserve OR ECB OR IMF economy outlook"), en("global economy inflation OR tariffs OR trade"), en("China economy policy OR stimulus"),
    "https://www.federalreserve.gov/feeds/press_all.xml", "https://www.ecb.europa.eu/rss/press.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml", "https://www.cnbc.com/id/20910258/device/rss/rss.html"]
ECO = re.compile(r"经济|政策|央行|国务院|发改委|财政|税|关税|贸易|利率|通胀|GDP|CPI|PPI|PMI|汇率|外交|会议|会见|会谈|峰会|美联储|欧洲央行|IMF|世界银行|油价|原油|生猪|鸡蛋|食品安全|economy|economic|inflation|tariff|trade|central bank|\bFed\b|ECB|interest rate|president|summit|recession", re.I)
COLS = [  # 按顺序匹配，先中先得
    ("食品农业与民生", r"食品|农业|农产品|生猪|猪肉|猪价|鸡蛋|蛋价|禽流感|粮食|饲料|豆粕|玉米|预制菜|收储|菜篮子"),
    ("全球贸易与供应链", r"关税|出口管制|贸易战|贸易协定|进口|出口|供应链|航运|tariff|trade war|export control|shipping|supply chain"),
    ("金融与货币", r"央行|利率|LPR|降息|加息|汇率|人民币|债券|股市|A股|货币政策|存款准备金|interest rate|bond|\byen\b|\bdollar\b"),
    ("宏观形势与数据", r"GDP|CPI|PPI|PMI|统计局|通胀|失业|就业|消费|增速|经济数据|inflation|unemployment"),
    ("政治与外交动态", r"外交|会见|会谈|访问|峰会|高层|主席|总理|政治局|常委|全国人大|政协|总统|summit|president|diplomat|foreign minister"),
    ("国际经济", r"美联储|欧洲央行|欧元区|美国经济|日本经济|IMF|世界银行|OPEC|原油|油价|大宗商品|\bFed\b|ECB|economy|recession")]
ORDER = ["国家政策", "宏观形势与数据", "金融与货币", "食品农业与民生", "政治与外交动态", "国际经济", "全球贸易与供应链"]
STRICT = {"国家政策", "政治与外交动态"}           # 这两栏只收官方和权威媒体
SPAM = re.compile(r"九游会|亚博|直播视讯|电竞|体育全站|捕鱼|皇冠|pg电子|斗球|开元棋牌")
OFF_HOST = (".gov.cn", "xinhuanet.com", "news.cn", "people.com.cn", "cctv.com", "federalreserve.gov", "ecb.europa.eu", "imf.org", "worldbank.org", "oecd.org")
OFF_NAME = re.compile(r"新华|人民日报|人民网|央视|中央电视台|国务院|中国政府网|发改委|国家发展|财政部|商务部|央行|中国人民银行|统计局|市场监管|农业农村|外交部|美联储|Federal Reserve|欧洲央行|\bECB\b|\bIMF\b|世界银行|World Bank|OECD", re.I)
MEDIA = re.compile(r"第一财经|财新|澎湃|21世纪|证券时报|中国证券报|上海证券报|经济日报|中国经济网|光明网|中新网|中国新闻网|环球网|央广网|界面|参考消息|联合早报|路透|Reuters|Bloomberg|彭博|BBC|CNBC|金融时报|Financial Times|\bFT\b|华尔街日报|WSJ|美联社|\bAP\b|日经|Nikkei|NHK", re.I)
MEDIA_HOST = ("reuters.com", "bloomberg.com", "bbc.co.uk", "bbc.com", "cnbc.com", "ft.com", "wsj.com", "yicai.com", "caixin.com", "thepaper.cn")
OPINION = re.compile(r"评论|观点|社评|专栏|点评|opinion|\banalysis\b", re.I)
RUMOR = re.compile(r"传闻|据称|爆料|疑似|rumou?r|reportedly|allegedly", re.I)
DOM = re.compile(r"中国|我国|国务院|央行|人民银行|发改委|人民币|国内|全国|财政部|商务部|统计局")
INT = re.compile(r"美国|美联储|欧盟|欧洲|欧元区|日本|俄罗斯|印度|英国|德国|IMF|世界银行|OPEC|\bFed\b|ECB|Federal Reserve|U\.S\.|\bEU\b|tariff", re.I)
RANK = {"官方发布": 2, "权威媒体": 1, "其他来源": 0}

def tier(it):  # 按来源分级（规则判断，不等于独立核实）
    h = urlparse(it["u"]).netloc
    if any(h.endswith(x) for x in OFF_HOST) or OFF_NAME.search(it["s"]): return "官方发布"
    if any(h.endswith(x) for x in MEDIA_HOST) or MEDIA.search(it["s"]): return "权威媒体"
    return "其他来源"
def bg(s):
    s = re.sub(r"[\W_]+", "", s.lower()); return {s[i:i + 2] for i in range(len(s) - 1)}

now = time.time(); items = []
for url in FEEDS:
    try: d = feedparser.parse(url, agent=UA)
    except Exception as ex: print("失败", url[:50], ex); continue
    print(urlparse(url).netloc, len(d.entries))
    for e in d.entries:
        t = re.sub(r"\s+", " ", e.get("title", "")).strip(); s = ""
        if " - " in t and "news.google.com" in url: t, s = t.rsplit(" - ", 1)
        s = s or (e.get("source") or {}).get("title") or urlparse(url).netloc.replace("www.", "")
        ts = calendar.timegm(e.published_parsed) if e.get("published_parsed") else 0
        if t and ts and ts > now - 7 * 86400 and not SPAM.search(t) and (ECO.search(t) or "news.google.com" not in url):
            items.append({"t": t, "u": e.get("link", ""), "s": s, "ts": ts})

items.sort(key=lambda x: -x["ts"]); ev = []
for it in items:   # 事件去重：不同媒体改写的同一件事合并
    gs = bg(it["t"])
    for e in ev:
        if len(gs & e["g"]) / (len(gs | e["g"]) or 1) >= .5: e["it"].append(it); break
    else: ev.append({"g": gs, "it": [it]})
reps = []
for e in ev:
    for it in e["it"]: it["tier"] = tier(it)
    r = max(e["it"], key=lambda i: (RANK[i["tier"]], i["ts"])); r["n"] = len({i["s"] for i in e["it"]}); reps.append(r)
reps = sorted(reps, key=lambda x: -x["ts"])[:250]
if len(reps) < 5 and os.path.exists("eco.json"): print("本次数据过少，保留上次的 eco.json"); sys.exit(0)

try: cache = json.load(open("links5.json", encoding="utf-8"))   # Google 跳转链接 -> 原文直链
except Exception: cache = {}
todo = [r["u"] for r in reps if "news.google.com" in r["u"] and r["u"] not in cache][:60]
try:
    from googlenewsdecoder import gnewsdecoder
    for k in range(0, len(todo), 10):
        c = todo[k:k + 10]
        try:
            for u, x in zip(c, gnewsdecoder(c, interval=1)):
                if (x.get("success") or x.get("status")) and x.get("decoded_url"): cache[u] = x["decoded_url"]
        except Exception as ex: print("解码失败:", ex)
except Exception as ex: print("解码库不可用:", ex)
cur = {r["u"] for r in reps}; cache = {u: v for u, v in cache.items() if u in cur}
json.dump(cache, open("links5.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

boards = {c: [] for c in ORDER}
for r in reps:
    col = next((c for c, p in COLS if re.search(p, r["t"], re.I)), None)
    if col is None: col = "国际经济" if not re.search(r"[\u4e00-\u9fff]", r["t"]) else "国家政策"
    cjk = re.search(r"[\u4e00-\u9fff]", r["t"])   # 外国的利率、通胀等归「国际经济」
    if col in ("宏观形势与数据", "金融与货币") and (not cjk or (INT.search(r["t"]) and not DOM.search(r["t"]))): col = "国际经济"
    if col in STRICT and r["tier"] == "其他来源": continue
    dm, it_ = bool(DOM.search(r["t"])), bool(INT.search(r["t"]))
    reg = "国内+国际" if dm and it_ else "国内" if dm else "国际" if it_ else "地区未标注"
    flag = (" · 待核实" if RUMOR.search(r["t"]) else "") + (" · 评论观点" if OPINION.search(r["t"]) else "")
    tag = f"{r['s']} · {reg} · {r['tier']}{flag}" + (f" · {r['n']}家报道" if r["n"] > 1 else "")
    boards[col].append({"t": r["t"], "u": cache.get(r["u"], r["u"]), "s": tag, "ts": r["ts"]})
out = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "title": "经济观察 · 政策与国际",
       "boards": [{"cat": c, "name": c, "items": boards[c][:30]} for c in ORDER]}
json.dump(out, open("eco.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("完成：", {c: len(boards[c]) for c in ORDER})
