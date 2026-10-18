#!/usr/bin/env python3
# 军事频道 -> mil.json。来源分级 + 多源交叉 + 只留近3天。依赖: feedparser、googlenewsdecoder
import json, re, time, socket, difflib, datetime as dt
from collections import Counter
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (mil bot)"
DAYS = 3        # 只保留近几天
PER_BOARD = 15  # 每个版块最多几条

def gn(q):   # 中文 Google 新闻
    return f"https://news.google.com/rss/search?q={quote(q + f' when:{DAYS}d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
def gne(q):  # 英文 Google 新闻
    return f"https://news.google.com/rss/search?q={quote(q + f' when:{DAYS}d')}&hl=en-US&gl=US&ceid=US:en"

# ---------- 来源分级（按来源名包含关系匹配，不在名单里的来源会被丢弃）----------
OFFICIAL = ["国防部", "外交部", "中国军网", "解放军报", "中央军委", "国务院台办", "海警局",
            "Ministry of Defence", "Department of Defense", "Department of War", "NATO", "Pentagon", "Kremlin"]
MAINSTREAM = ["新华社", "新华网", "央视", "CCTV", "人民日报", "中国新闻网", "澎湃", "环球时报", "联合早报",
              "Reuters", "路透", "Associated Press", "AP News", "BBC", "Bloomberg", "Al Jazeera",
              "The Guardian", "CNN", "Financial Times", "NHK", "Yonhap", "韩联社", "中央社", "法新社", "AFP"]
PRO = ["观察者网", "Defense News", "Breaking Defense", "The War Zone", "Naval News", "Janes", "Defense One",
       "Army Technology", "Military Times", "Stars and Stripes", "The Diplomat", "Air & Space Forces",
       "Military.com", "军事", "国防", "军情", "兵工"]
RANK = {"官方": 3, "媒体": 2, "专业": 1}
def level(src):
    s = src.lower()
    for lv, names in (("官方", OFFICIAL), ("媒体", MAINSTREAM), ("专业", PRO)):
        if any(n.lower() in s for n in names):
            return lv
    return None

# ---------- 噪音词 ----------
NOISE = ["游戏", "手游", "吃鸡", "军模", "模型", "小说", "电影", "影评", "电视剧", "综艺", "抖音", "壁纸",
         "玩具", "盲盒", "吊起来", "打屁股", "校花", "官方版", "高清完整", "六合彩", "特码", "彩票",
         "震惊", "惊天", "细思极恐", "不敢相信", "竟然是"]

# ---------- 版块：(分类, 名称, 搜索词列表, 是否只收官方来源) ----------
BOARDS = [
    ("通报", "官方通报", [gn("国防部 发言人"), gn("国防部 例行记者会"), gn("解放军报"),
                         gne("Ministry of Defence statement"), gne("NATO statement defence")], True),
    ("热点", "台海与南海", [gn("台海 解放军 OR 军演 OR 海警"), gn("南海 菲律宾 OR 海警 OR 仁爱礁 OR 黄岩岛")], False),
    ("热点", "朝鲜半岛", [gn("朝鲜 导弹 OR 试射 OR 军演 OR 韩国 美韩")], False),
    ("热点", "俄乌战场", [gn("乌克兰 俄罗斯 前线 OR 无人机 OR 袭击 OR 停火")], False),
    ("热点", "中东局势", [gn("以色列 OR 伊朗 OR 胡塞 OR 加沙 空袭 OR 袭击 OR 停火")], False),
    ("装备产业", "装备与技术", [gn("新型 战机 OR 舰艇 OR 导弹 OR 无人机 列装 OR 试射 OR 首飞 OR 下水")], False),
    ("装备产业", "军工与军费", [gn("军工 订单 OR 出口 OR 财报"), gn("国防预算 OR 军费 增长")], False),
    ("国际源", "国际权威源（英文）", [gne("site:defensenews.com OR site:breakingdefense.com OR site:twz.com OR site:navalnews.com"),
                                   gne("Reuters military OR defense OR warship OR missile")], False),
]

def pull(url):
    out = []
    for e in feedparser.parse(url, agent=UA).entries:
        title = re.sub(r"\s+", " ", e.get("title", "")).strip()
        src = (e.get("source") or {}).get("title") or ""
        if " - " in title:
            title, s2 = title.rsplit(" - ", 1)
            src = src or s2
        ts = int(time.mktime(e.published_parsed)) if e.get("published_parsed") else 0
        out.append({"t": title, "u": e.get("link", ""), "s": src.strip(), "ts": ts})
    return out

def bigrams(s):
    s = re.sub(r"[\W_]+", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}

def sim(a, b):
    return len(a & b) / max(1, len(a | b))

def main():
    now = int(time.time())
    dropped = Counter()
    pool = []   # 所有通过筛选的条目，保持版块顺序
    for cat, name, urls, only_off in BOARDS:
        seen = set()
        for url in urls:
            try:
                items = pull(url)
            except Exception as ex:
                print("失败", name, ex)
                continue
            for it in items:
                if not it["t"] or it["t"] in seen or not it["ts"] or it["ts"] < now - DAYS * 86400:
                    continue
                if any(w.lower() in it["t"].lower() for w in NOISE):
                    continue
                lv = level(it["s"])
                if not lv:
                    dropped[it["s"] or "（无来源）"] += 1
                    continue
                if only_off and lv != "官方":
                    continue
                seen.add(it["t"])
                it["lv"], it["board"] = lv, name
                pool.append(it)
        print(name, "候选", sum(1 for x in pool if x["board"] == name))

    # 全局聚类：标题相似的归为同一事件
    clusters = []
    for it in pool:
        bg = bigrams(it["t"])
        for c in clusters:
            if sim(bg, c["bg"]) >= 0.4:
                c["m"].append(it)
                break
        else:
            clusters.append({"bg": bg, "m": [it], "board": it["board"]})

    def fmt(c):
        m = c["m"]
        srcs = {x["s"] for x in m}
        n = len(srcs)
        rep = max(m, key=lambda x: (RANK[x["lv"]], x["ts"]))
        confirmed = n >= 2 and any(x["lv"] in ("官方", "媒体") for x in m)
        if rep["lv"] == "官方":
            tag = "官方发布"
        elif confirmed:
            tag = f"多源确认（{n}家）"
        elif n >= 2:
            tag = f"多家专业媒体（{n}家）"
        else:
            tag = "单一来源，未证实"
        return {"t": rep["t"], "u": rep["u"], "s": f"{rep['lv']} · {rep['s']} · {tag}",
                "ts": rep["ts"], "lv": rep["lv"], "n": n, "ok": confirmed or rep["lv"] == "官方"}

    done = [(c, fmt(c)) for c in clusters]
    boards = []
    top = sorted((f for c, f in done if f["n"] >= 2 and f["ok"]), key=lambda f: (-f["n"], -f["ts"]))[:PER_BOARD]
    boards.append({"cat": "要闻", "name": "多源确认要闻", "items": [dict(f) for f in top]})
    for cat, name, _, _ in BOARDS:
        its = sorted((f for c, f in done if c["board"] == name), key=lambda f: -f["ts"])[:PER_BOARD]
        boards.append({"cat": cat, "name": name, "items": its})

    # Google 新闻跳转链接 -> 原文直链
    try:
        from googlenewsdecoder import gnewsdecoder
        try:
            cache = json.load(open("links6.json", encoding="utf-8"))
        except Exception:
            cache = {}
        cur = {i["u"] for b in boards for i in b["items"]}
        todo = [u for u in cur if "news.google.com" in u and u not in cache][:100]
        t0 = time.time()
        for k in range(0, len(todo), 10):
            if time.time() - t0 > 200:
                break
            chunk = todo[k:k + 10]
            try:
                for u, r in zip(chunk, gnewsdecoder(chunk, interval=1)):
                    if (r.get("success") or r.get("status")) and r.get("decoded_url"):
                        cache[u] = r["decoded_url"]
            except Exception as ex:
                print("解码失败:", ex)
        cache = {u: v for u, v in cache.items() if u in cur}
        for b in boards:
            for i in b["items"]:
                i["u"] = cache.get(i["u"], i["u"])
        json.dump(cache, open("links6.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    except Exception as ex:
        print("链接解码不可用，保留原链接:", ex)

    for b in boards:
        for i in b["items"]:
            i.pop("ok", None)
        print(b["name"], len(b["items"]))
    print("被丢弃最多的来源（若有靠谱来源在这里，可加进名单）:", dropped.most_common(15))
    json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "boards": boards},
              open("mil.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    main()
