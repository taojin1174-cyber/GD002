# 原料专题（猪肉/鸡肉/鸡蛋）+ 品类热度。在 fetch.py 之后运行：读 data.json，追加榜单后写回。
import json, re, time, socket
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (food-hot bot)"
gn = lambda q: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
bd = lambda q: "https://www.baidu.com/s?wd=" + quote(q)   # 百度搜索，国内可直接打开
RAW = {  # 原料: [(榜单名, 搜索词)] —— 想加榜单就加一行
 "猪肉": [("价格行情", "猪价 OR 生猪价格 OR 猪肉价格 行情"), ("新品与爆款", "猪肉 预制菜 新品 OR 爆款 OR 上市"), ("供应与风险", "生猪 非洲猪瘟 OR 产能调控 OR 供应 OR 进口")],
 "鸡肉": [("价格行情", "白羽鸡 OR 肉鸡 OR 鸡肉 价格 行情"), ("新品与爆款", "鸡肉 预制菜 新品 OR 爆款 OR 鸡胸肉"), ("供应与风险", "肉鸡 OR 鸡肉 禽流感 OR 供应 OR 进口 OR 种鸡")],
 "鸡蛋": [("价格行情", "鸡蛋价格 OR 蛋价 行情"), ("新品与爆款", "鸡蛋 新品 OR 爆款 OR 蛋制品 OR 预制菜"), ("供应与风险", "蛋鸡 OR 鸡蛋 供应 OR 禽流感 OR 存栏")]}
DISH = {  # 要统计热度的品类关键词，可自行增删
 "猪肉": "红烧肉 梅菜扣肉 东坡肉 糖醋里脊 锅包肉 回锅肉 小酥肉 肉丸 狮子头 香肠 腊肠 培根 火腿 猪蹄 排骨 叉烧 卤肉 肉松 饺子 包子".split(),
 "鸡肉": "鸡胸肉 鸡腿 鸡翅 炸鸡 烤鸡 盐焗鸡 口水鸡 辣子鸡 宫保鸡丁 黄焖鸡 白切鸡 手撕鸡 鸡排 鸡块 鸡米花 鸡爪 凤爪 鸡汤 咖喱鸡 大盘鸡".split(),
 "鸡蛋": "卤蛋 溏心蛋 茶叶蛋 蛋饺 蛋羹 蒸蛋 蛋挞 蛋卷 蛋黄酥 蛋炒饭 煎蛋 荷包蛋 皮蛋 咸蛋 鸡蛋灌饼 液态蛋 低温蛋 蛋白".split()}

def pull(url):
    out, seen = [], set()
    for e in feedparser.parse(url, agent=UA).entries:
        t, s = re.sub(r"\s+", " ", e.get("title", "")).strip(), ""
        if " - " in t: t, s = t.rsplit(" - ", 1)
        ts = int(time.mktime(e.published_parsed)) if e.get("published_parsed") else 0
        if not t or t in seen or (ts and ts < time.time() - 14 * 86400): continue
        seen.add(t); out.append({"t": t, "u": e.get("link", ""), "s": s, "ts": ts})
    return sorted(out, key=lambda x: -x["ts"])[:20]

def resolve(items, limit=60):  # Google 跳转链接 -> 原文直链（用单独的缓存 links2.json）
    try: cache = json.load(open("links2.json", encoding="utf-8"))
    except Exception: cache = {}
    cur = {i["u"] for i in items}
    todo = [u for u in cur if "news.google.com" in u and u not in cache][:limit]
    try:
        from googlenewsdecoder import gnewsdecoder
        for k in range(0, len(todo), 10):
            c = todo[k:k + 10]
            try:
                for u, r in zip(c, gnewsdecoder(c, interval=1)):
                    if (r.get("success") or r.get("status")) and r.get("decoded_url"): cache[u] = r["decoded_url"]
            except Exception as ex: print("解码失败:", ex)
    except Exception as ex: print("解码库不可用:", ex)
    cache = {u: v for u, v in cache.items() if u in cur}
    for i in items: i["u"] = cache.get(i["u"], i["u"])
    json.dump(cache, open("links2.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

D = json.load(open("data.json", encoding="utf-8"))
mine = set(RAW) | {"品类热度"}
D["boards"] = [b for b in D["boards"] if b["cat"] not in mine]
new = []
for raw, bs in RAW.items():
    for name, q in bs:
        try: items = pull(gn(q))
        except Exception as ex: print("失败", raw, name, ex); items = []
        print(raw, name, len(items)); new.append({"cat": raw, "name": name, "items": items})
resolve([i for b in new for i in b["items"]])

# 历史累积（30 天）：所有榜单标题，用来统计品类热度
now = int(time.time())
try: arch = json.load(open("archive2.json", encoding="utf-8"))
except Exception: arch = []
have = {a["t"] for a in arch}
for b in D["boards"] + new:
    for i in b["items"]:
        if i["t"] not in have and i["ts"]: have.add(i["t"]); arch.append({"t": i["t"], "ts": i["ts"]})
arch = [a for a in arch if a["ts"] > now - 30 * 86400]
json.dump(arch, open("archive2.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

heat = []
for raw, ds in DISH.items():
    rows = []
    for d in ds:
        n = sum(1 for a in arch if d in a["t"] and a["ts"] > now - 7 * 86400)
        p = sum(1 for a in arch if d in a["t"] and now - 14 * 86400 < a["ts"] <= now - 7 * 86400)
        if n: rows.append((n, p, d))
    rows.sort(reverse=True)
    heat.append({"cat": "品类热度", "name": f"{raw} · 热门品类（近7天提及）", "items": [
        {"t": d + (" ▲" if p and n > p else " ▼" if p and n < p else ""), "u": bd(d + " 预制菜"), "s": f"近7天 {n} 条 · 前7天 {p} 条", "ts": 0} for n, p, d in rows[:10]]})
k = next((n for n, b in enumerate(D["boards"]) if b["cat"] != "预制菜"), len(D["boards"]))
D["boards"][k:k] = heat + new
json.dump(D, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
