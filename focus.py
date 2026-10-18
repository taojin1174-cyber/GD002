# 重点来源：Readhub / AIBase / 机器之心 / Foodaily / FBIF / FoodNavigator，各取最新 10 条
# 在 ai.py 之后运行：食品类写入 data.json，AI 类写入 ai.json，放在页面最前面的「重点来源」标签
import json, re, time, socket, calendar
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (focus bot)"
zh = lambda q: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
en = lambda q: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=en-US&gl=US&ceid=US:en"
AIRE = re.compile(r"AI|人工智能|大模型|模型|智能体|机器人|算力|GPT|OpenAI|DeepSeek|Claude|Gemini", re.I)
SRC = [  # (放到哪个频道, 榜单名, [订阅地址], 标题过滤)  —— 顺序即显示顺序
    ("ai", "Readhub · AI 热点", [zh("site:readhub.cn")], AIRE),
    ("ai", "AIBase · 模型与工具", [zh("site:aibase.com")], None),
    ("food", "Foodaily · 食品新品与趋势", [zh("site:foodaily.com")], None),
    ("food", "FBIF · 食品创新与消费", [zh("site:fbifood.com")], None),
    ("ai", "机器之心 · 技术与科研", [zh("site:jiqizhixin.com")], None),
    ("food", "FoodNavigator · 海外食品（英文）", [en("site:foodnavigator.com"), en("site:foodnavigator-asia.com")], None)]

def pull(urls, flt):
    out, seen = [], set()
    for u in urls:
        for e in feedparser.parse(u, agent=UA).entries:
            t = re.sub(r"\s+", " ", e.get("title", "")).strip()
            if " - " in t: t = t.rsplit(" - ", 1)[0]
            ts = calendar.timegm(e.published_parsed) if e.get("published_parsed") else 0
            if t and ts and t not in seen and (not flt or flt.search(t)): seen.add(t); out.append({"t": t, "u": e.get("link", ""), "ts": ts})
    return sorted(out, key=lambda x: -x["ts"])[:14]

res = {"ai": [], "food": []}
for dest, name, urls, flt in SRC:
    try: items = pull(urls, flt)
    except Exception as ex: print("失败", name, ex); items = []
    print(name, len(items))
    for i in items: i["s"] = name.split(" · ")[0].split("（")[0]
    res[dest].append({"cat": "重点来源", "name": name, "items": items})

try: cache = json.load(open("links4.json", encoding="utf-8"))   # Google 跳转链接 -> 原文直链
except Exception: cache = {}
allit = [i for b in res["ai"] + res["food"] for i in b["items"]]
todo = list(dict.fromkeys(i["u"] for i in allit if "news.google.com" in i["u"] and i["u"] not in cache))[:60]
try:
    from googlenewsdecoder import gnewsdecoder
    for k in range(0, len(todo), 10):
        c = todo[k:k + 10]
        try:
            for u, x in zip(c, gnewsdecoder(c, interval=1)):
                if (x.get("success") or x.get("status")) and x.get("decoded_url"): cache[u] = x["decoded_url"]
        except Exception as ex: print("解码失败:", ex)
except Exception as ex: print("解码库不可用:", ex)
cur = {i["u"] for i in allit}; cache = {u: v for u, v in cache.items() if u in cur}
json.dump(cache, open("links4.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
for i in allit: i["u"] = cache.get(i["u"], i["u"])

for path, key in (("data.json", "food"), ("ai.json", "ai")):
    try: D = json.load(open(path, encoding="utf-8"))
    except Exception: continue
    D["boards"] = [b for b in D["boards"] if b["cat"] != "重点来源"]
    D["boards"][0:0] = res[key]
    json.dump(D, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
