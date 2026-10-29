#!/usr/bin/env python3
# 「火爆」分类：排队 / 爆满 / 抢购类新闻 -> 追加进 data.json（放在 extra.py 之后运行）
import json, re, time, socket
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
DAYS, PER = 7, 15
gn = lambda q: f"https://news.google.com/rss/search?q={quote(q + f' when:{DAYS}d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
bd = lambda q: "https://www.baidu.com/s?wd=" + quote(q)

# ---- 观察名单：想盯哪个品牌，直接往这里加 ----
BRANDS = ["金粒门", "柠檬向右", "久食山", "零食很忙", "赵一鸣", "钱大妈", "山姆", "盒马", "胖东来",
          "霸王茶姬", "蜜雪冰城", "古茗", "老乡鸡", "海底捞"]
GROUPS = [BRANDS[i:i + 5] for i in range(0, len(BRANDS), 5)]
BOARDS = [
    ("排队热点 · 最新", [gn("排队 OR 排长队 OR 一座难求 OR 开业排队 餐饮 OR 零食 OR 烘焙 OR 茶饮 OR 新品"),
                        gn("首店 OR 新店 开业 排队 品牌"), gn("site:winshang.com 排队 品牌")]),
    ("新鲜零食与短保", [gn("新鲜零食 OR 短保 OR 鲜卤 OR 现烤 排队 OR 爆满 OR 火爆")]),
    ("品牌观察名单", [gn("(" + " OR ".join(g) + ") 排队 OR 爆满 OR 抢购 OR 开业") for g in GROUPS]),
    ("抢购与断货", [gn("爆款 OR 新品 抢购 OR 售罄 OR 断货 OR 秒空 零食 OR 山姆 OR 盒马 OR 茶饮")]),
    ("退潮与争议", [gn("排队 冷清 OR 退潮 OR 闭店 OR 雇人 OR 黄牛 餐饮 OR 零食 OR 茶饮")]),
]
NEED = re.compile(r"排队|排长队|长队|等位|取号|爆满|一座难求|爆单|售罄|断货|抢购|秒空|限流")
FOOD = re.compile(r"餐|食|饮|茶|咖啡|零食|烘焙|面包|蛋糕|火锅|烧烤|烧腊|卤|小吃|预制菜|熟食|山姆|盒马|超市|新品|首店|开业|门店|品牌")
BAD = re.compile(r"医院|挂号|核酸|疫苗|春运|高速|驾考|政务|购房|楼盘|演唱会|手机|发布会|彩票|航班|机场|火车|门票|景区|游戏|电影|吊起来|打屁股|校花|六合彩|特码|博彩")
NEG = re.compile(r"冷清|退潮|闭店|关店|雇人|黄牛|遇冷|凉了|翻车|道歉|质疑")

def pull(url):
    for k in range(2):
        d = feedparser.parse(url, agent=UA)
        print(f"  [状态 {d.get('status', '?')}] {len(d.entries)} 条  {url[33:90]}")
        if d.entries:
            break
        time.sleep(4)
    out = []
    for e in d.entries:
        t, s = re.sub(r"\s+", " ", e.get("title", "")).strip(), ""
        if " - " in t:
            t, s = t.rsplit(" - ", 1)
        ts = int(time.mktime(e.published_parsed)) if e.get("published_parsed") else 0
        out.append({"t": t, "u": e.get("link", ""), "s": s.strip(), "ts": ts})
    return out

def bigrams(s):
    s = re.sub(r"[\W_]+", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

def main():
    try:
        D = json.load(open("data.json", encoding="utf-8"))
    except Exception as ex:
        print("读不到 data.json，跳过:", ex)
        return
    now, pool, seen = int(time.time()), [], []
    for name, urls in sorted(BOARDS, key=lambda x: x[0] == "排队热点 · 最新"):  # 先处理专门的版块，通用版块最后兜底
        n0 = len(pool)
        for url in urls:
            try:
                items = pull(url)
            except Exception as ex:
                print("失败", name, ex)
                continue
            time.sleep(1.5)
            for it in items:
                t = it["t"]
                if not t or not it["ts"] or it["ts"] < now - DAYS * 86400:
                    continue
                if not (NEED.search(t) and FOOD.search(t)) or BAD.search(t):
                    continue
                bg = bigrams(t)
                if any(len(bg & s) / max(1, len(bg | s)) >= 0.5 for s in seen):
                    continue
                seen.append(bg)
                it["board"] = "退潮与争议" if NEG.search(t) else name
                pool.append(it)
        print(name, "新增", len(pool) - n0)

    # 历史累积（30 天），用来统计品牌提及
    try:
        arch = json.load(open("queue_archive.json", encoding="utf-8"))
    except Exception:
        arch = []
    have = {a["t"] for a in arch}
    for it in pool:
        if it["t"] not in have:
            have.add(it["t"])
            arch.append({"t": it["t"], "ts": it["ts"]})
    arch = [a for a in arch if a["ts"] > now - 30 * 86400]
    json.dump(arch, open("queue_archive.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    rank = []
    for b in BRANDS:
        n = sum(1 for a in arch if b in a["t"] and a["ts"] > now - 7 * 86400)
        p = sum(1 for a in arch if b in a["t"] and now - 14 * 86400 < a["ts"] <= now - 7 * 86400)
        if n:
            rank.append((n, p, b))
    rank.sort(reverse=True)

    out = []
    if rank:
        out.append({"cat": "火爆", "name": "品牌排队榜（近7天提及）", "items": [
            {"t": b + (" ▲" if n > p else " ▼" if n < p else ""), "u": bd(b + " 排队"),
             "s": f"近7天 {n} 条 · 前7天 {p} 条", "ts": 0} for n, p, b in rank[:12]]})
    for name, _ in BOARDS:
        its = sorted((x for x in pool if x["board"] == name), key=lambda x: -x["ts"])[:PER]
        out.append({"cat": "火爆", "name": name, "items": [{"t": x["t"], "u": x["u"], "s": x["s"], "ts": x["ts"]} for x in its]})

    # Google 新闻跳转链接 -> 原文直链（缓存 links7.json）
    try:
        from googlenewsdecoder import gnewsdecoder
        try:
            cache = json.load(open("links7.json", encoding="utf-8"))
        except Exception:
            cache = {}
        cur = {i["u"] for b in out for i in b["items"]}
        todo = [u for u in cur if "news.google.com" in u and u not in cache][:60]
        t0 = time.time()
        for k in range(0, len(todo), 10):
            if time.time() - t0 > 150:
                break
            c = todo[k:k + 10]
            try:
                for u, r in zip(c, gnewsdecoder(c, interval=1)):
                    if (r.get("success") or r.get("status")) and r.get("decoded_url"):
                        cache[u] = r["decoded_url"]
            except Exception as ex:
                print("解码失败:", ex)
        cache = {u: v for u, v in cache.items() if u in cur}
        for b in out:
            for i in b["items"]:
                i["u"] = cache.get(i["u"], i["u"])
        json.dump(cache, open("links7.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    except Exception as ex:
        print("链接解码不可用，保留原链接:", ex)

    D["boards"] = [b for b in D["boards"] if b.get("cat") != "火爆"]
    k = next((i for i, b in enumerate(D["boards"]) if b["cat"] != "预制菜"), len(D["boards"]))
    D["boards"][k:k] = out
    json.dump(D, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("火爆分类已写入：", [(b["name"], len(b["items"])) for b in out])

if __name__ == "__main__":
    main()
