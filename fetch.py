# 抓取各榜单 -> data.json。依赖: pip install feedparser
import json, re, time, datetime as dt
from urllib.parse import quote
import feedparser

UA = "Mozilla/5.0 (food-hot bot)"
def gn(q):  # Google 新闻 RSS，近 7 天
    return f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

KW = re.compile(r"预制菜|食品|餐饮|外卖|饮料|零食|调味|冷链|中央厨房|农产品|茶饮|咖啡")
# (分类, 榜单名, RSS 地址, 关键词过滤)  —— 想加榜单就往这里加一行
SOURCES = [
    ("预制菜", "预制菜 · 最新", gn("预制菜"), None),
    ("预制菜", "政策与标准", gn("预制菜 国家标准 OR 政策 OR 监管 OR 规范"), None),
    ("预制菜", "融资 · 企业 · 财报", gn("预制菜 融资 OR 上市 OR 财报 OR 工厂 OR 布局"), None),
    ("预制菜", "争议与舆情", gn("预制菜 争议 OR 投诉 OR 添加剂 OR 进校园 OR 消费者"), None),
    ("食品新闻", "食品行业动态", gn("食品行业 新品 OR 消费趋势 OR 品牌"), None),
    ("食品新闻", "食品安全", gn("食品安全 通报 OR 抽检 OR 召回 OR 曝光"), None),
    ("食品新闻", "餐饮与供应链", gn("餐饮 供应链 中央厨房 OR 团餐 OR 连锁 OR 冷链"), None),
    ("科技商业媒体", "36氪 · 食品相关", "https://36kr.com/feed", KW),
    ("科技商业媒体", "虎嗅 · 食品相关", "https://www.huxiu.com/rss/0.xml", KW),
]
# 预制菜方向分析：统计这些主题词在「预制菜」榜单标题中出现的次数
TOPICS = ["政策", "标准", "监管", "融资", "上市", "出海", "团餐", "零售", "餐饮", "争议",
          "添加剂", "食品安全", "冷链", "中央厨房", "净菜", "外卖", "进校园", "价格", "品牌", "渠道"]

def pull(url, kw):
    d = feedparser.parse(url, agent=UA)
    out, seen = [], set()
    for e in d.entries:
        title = re.sub(r"\s+", " ", e.get("title", "")).strip()
        src = ""
        if " - " in title:  # Google 新闻标题末尾是 " - 来源"
            title, src = title.rsplit(" - ", 1)
        if not title or title in seen or (kw and not kw.search(title)):
            continue
        seen.add(title)
        ts = int(time.mktime(e.published_parsed)) if e.get("published_parsed") else 0
        out.append({"t": title, "u": e.get("link", ""), "s": src, "ts": ts})
    out.sort(key=lambda x: -x["ts"])
    return out[:20]

boards, counts = [], {k: 0 for k in TOPICS}
for cat, name, url, kw in SOURCES:
    try:
        items = pull(url, kw)
    except Exception as ex:
        print("失败", name, ex); items = []
    boards.append({"cat": cat, "name": name, "items": items})
    if cat == "预制菜":
        for it in items:
            for k in TOPICS:
                if k in it["t"]: counts[k] += 1
    print(name, len(items))

topics = sorted(([k, n] for k, n in counts.items() if n), key=lambda x: -x[1])
json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "boards": boards, "topics": topics},
          open("data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
