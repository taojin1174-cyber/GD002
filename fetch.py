# 抓取各榜单 -> data.json（页面数据）+ archive.json（趋势用的历史累积）。依赖: pip install feedparser
import json, re, time, socket, os, datetime as dt
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)  # 单个源卡住时 20 秒后自动跳过

UA = "Mozilla/5.0 (food-hot bot)"
def gn(q):  # Google 新闻 RSS，近 7 天
    return f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"

KW = re.compile(r"预制菜|食品|餐饮|外卖|饮料|零食|调味|冷链|中央厨房|农产品|茶饮|咖啡")
# (分类, 榜单名, RSS 地址, 关键词过滤)  —— 想加榜单就往这里加一行
SOURCES = [
    ("预制菜", "预制菜 · 最新", gn("预制菜"), None),
    ("预制菜", "融资 · 企业 · 财报", gn("预制菜 融资 OR 上市 OR 财报 OR 工厂 OR 布局"), None),
    ("预制菜", "争议与舆情", gn("预制菜 争议 OR 投诉 OR 添加剂 OR 进校园 OR 消费者"), None),
    ("政策标准", "国家标准与规范", gn("预制菜 国家标准 OR 行业标准 OR 团体标准 OR 规范"), None),
    ("政策标准", "监管与法规", gn("预制菜 监管 OR 市场监管总局 OR 食品安全法 OR 明示 OR 通知"), None),
    ("政策标准", "地方政策与产业", gn("预制菜 产业园 OR 补贴 OR 政策 OR 行动方案 OR 扶持"), None),
    ("行业垂直", "食品伙伴网", gn("site:foodmate.net 预制菜"), None),
    ("行业垂直", "餐饮老板内参", gn("餐饮老板内参"), None),
    ("行业垂直", "红餐网", gn("红餐网 预制菜"), None),
    ("食品新闻", "食品行业动态", gn("食品行业 新品 OR 消费趋势 OR 品牌"), None),
    ("食品新闻", "食品安全", gn("食品安全 通报 OR 抽检 OR 召回 OR 曝光"), None),
    ("食品新闻", "餐饮与供应链", gn("餐饮 供应链 中央厨房 OR 团餐 OR 连锁 OR 冷链"), None),
    ("科技商业媒体", "36氪 · 预制菜与食品", gn("site:36kr.com 预制菜 OR 食品 OR 餐饮"), None),
    ("科技商业媒体", "虎嗅 · 预制菜与食品", gn("site:huxiu.com 预制菜 OR 食品 OR 餐饮"), None),
]
TREND_CATS = ("预制菜", "政策标准", "行业垂直")   # 这些分类参与趋势和日报
TOPICS = ["政策", "标准", "监管", "融资", "上市", "出海", "团餐", "零售", "餐饮", "争议",
          "添加剂", "食品安全", "冷链", "中央厨房", "净菜", "外卖", "进校园", "价格", "品牌", "渠道"]

def pull(urls, kw):
    if isinstance(urls, str): urls = [urls]
    out, seen = [], set()
    for url in urls:
        d = feedparser.parse(url, agent=UA)
        print("  来源", url.split("/")[2], len(d.entries))
        for e in d.entries:
            title = re.sub(r"\s+", " ", e.get("title", "")).strip()
            src = e.get("news_source") or (e.get("source") or {}).get("title") or ""
            if " - " in title:  # Google 新闻标题末尾是 " - 来源"
                title, src = title.rsplit(" - ", 1)
            if not title or title in seen or (kw and not kw.search(title)):
                continue
            ts = int(time.mktime(e.published_parsed)) if e.get("published_parsed") else 0
            if ts and ts < time.time() - 14 * 86400:   # 只保留近 14 天
                continue
            seen.add(title)
            out.append({"t": title, "u": e.get("link", ""), "s": src or ("必应" if "bing" in url else ""), "ts": ts})
    out.sort(key=lambda x: -x["ts"])
    return out[:20]

# ---- 把 Google 新闻的跳转链接换成原文直链（国内不翻墙也能直接打开）----
def resolve_links(boards, limit=120, budget=240):
    try:
        from googlenewsdecoder import gnewsdecoder
    except Exception as ex:
        print("链接解码库不可用，保留原链接:", ex); return
    try: cache = json.load(open("links.json", encoding="utf-8"))
    except Exception: cache = {}
    items = [it for b in boards for it in b["items"]]
    cur = {it["u"] for it in items}
    todo = list(dict.fromkeys(u for u in cur if "news.google.com" in u and u not in cache))[:limit]
    t0 = time.time()
    for i in range(0, len(todo), 10):      # 每次最多解 10 条，总耗时不超过 budget 秒
        if time.time() - t0 > budget: break
        chunk = todo[i:i + 10]
        try: res = gnewsdecoder(chunk, interval=1)
        except Exception as ex: print("解码失败:", ex); continue
        for u, r in zip(chunk, res):
            if (r.get("success") or r.get("status")) and r.get("decoded_url"): cache[u] = r["decoded_url"]
    cache = {u: v for u, v in cache.items() if u in cur}   # 只保留榜单里还在用的
    n = 0
    for it in items:
        if it["u"] in cache: it["u"] = cache[it["u"]]; n += 1
    json.dump(cache, open("links.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"直链 {n}/{len(items)} 条")

boards = []
for cat, name, url, kw in SOURCES:
    try: items = pull(url, kw)
    except Exception as ex: print("失败", name, ex); items = []
    boards.append({"cat": cat, "name": name, "items": items}); print(name, len(items))

resolve_links(boards)
now = int(time.time())
# ---- 历史累积（每周趋势）：按标题去重，保留 90 天 ----
try: arch = json.load(open("archive.json", encoding="utf-8"))
except Exception: arch = []
have = {a["t"] for a in arch}
for b in boards:
    if b["cat"] in TREND_CATS:
        for it in b["items"]:
            if it["t"] not in have and it["ts"]:
                have.add(it["t"]); arch.append({"t": it["t"], "ts": it["ts"], "k": [k for k in TOPICS if k in it["t"]]})
arch = [a for a in arch if a["ts"] > now - 90 * 86400]
json.dump(arch, open("archive.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

cn = dt.timezone(dt.timedelta(hours=8))
mon = (dt.datetime.now(cn) - dt.timedelta(days=dt.datetime.now(cn).weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
starts = [mon - dt.timedelta(weeks=i) for i in range(7, -1, -1)]      # 最近 8 周
tot = {k: 0 for k in TOPICS}; ser = {k: [0] * 8 for k in TOPICS}
for a in arch:
    for i in range(8):
        s = starts[i].timestamp()
        if s <= a["ts"] < s + 7 * 86400:
            for k in a["k"]: ser[k][i] += 1; tot[k] += 1
top = [k for k in sorted(tot, key=lambda k: -tot[k]) if tot[k]][:6]
trend = {"weeks": [s.strftime("%m-%d") for s in starts], "series": {k: ser[k] for k in top}}

# ---- 每日日报（规则生成，非 AI）----
def uniq(cats, n):
    seen, out = set(), []
    for b in boards:
        if b["cat"] in cats:
            for i in b["items"]:
                if i["t"] not in seen: seen.add(i["t"]); out.append(i)
    return sorted(out, key=lambda x: -x["ts"])[:n]
new24 = [i for i in uniq(TREND_CATS, 999) if i["ts"] > now - 86400]
hot = sorted(((k, sum(1 for i in new24 if k in i["t"])) for k in TOPICS), key=lambda x: -x[1])
hot = [f"{k}({n})" for k, n in hot if n][:5]
head, pol = uniq(("预制菜",), 5), uniq(("政策标准",), 3)
date = dt.datetime.now(cn).strftime("%Y-%m-%d")
summary = f"过去 24 小时预制菜相关新动态 {len(new24)} 条。" + (f"热词：{'、'.join(hot)}。" if hot else "")
text = f"【预制菜日报 {date}】\n{summary}\n\n头条：\n" + "\n".join(f"{n+1}. {i['t']}\n{i['u']}" for n, i in enumerate(head)) \
     + "\n\n政策动向：\n" + ("\n".join(f"- {i['t']}\n{i['u']}" for i in pol) or "- 暂无")
digest = {"date": date, "summary": summary, "head": head, "pol": pol, "text": text}

json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "boards": boards, "trend": trend, "digest": digest},
          open("data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
