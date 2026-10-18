#!/usr/bin/env python3
# 军事频道 -> mil.json。来源分级 + 多源交叉 + 只留近3天。依赖: feedparser、googlenewsdecoder
import json, re, time, socket, datetime as dt
from collections import Counter
from urllib.parse import quote
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
DAYS = 3        # 只保留近几天
PER_BOARD = 15  # 每个版块最多几条

def gn(q):   # 中文 Google 新闻
    return f"https://news.google.com/rss/search?q={quote(q + f' when:{DAYS}d')}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
def gne(q):  # 英文 Google 新闻
    return f"https://news.google.com/rss/search?q={quote(q + f' when:{DAYS}d')}&hl=en-US&gl=US&ceid=US:en"

# ---------- 来源分级（按来源名包含关系匹配）----------
OFFICIAL = ["国防部", "外交部", "中国军网", "解放军报", "中央军委", "国务院台办", "海警局",
            "Ministry of Defence", "Department of Defense", "Department of War", "NATO", "Pentagon",
            "Kremlin", "GOV.UK", "defense.gov", "war.gov"]
MAINSTREAM = ["新华社", "新华网", "Xinhua", "央视", "CCTV", "CGTN", "人民日报", "中国新闻网", "中新网", "澎湃",
              "环球时报", "环球网", "联合早报", "中国日报", "China Daily", "参考消息", "界面新闻", "财新",
              "第一财经", "光明网", "国际在线", "海外网", "央广网", "新京报", "中国青年报", "凤凰网",
              "南华早报", "South China Morning Post", "SCMP", "中央社", "韩联社", "Yonhap", "日经", "Nikkei",
              "Straits Times", "塔斯社", "TASS", "法新社", "AFP", "Reuters", "路透", "Associated Press",
              "AP News", "BBC", "Bloomberg", "Al Jazeera", "The Guardian", "CNN", "Financial Times", "NHK",
              "NPR", "PBS", "Axios", "Times of Israel", "Kyiv Independent", "Ukrinform"]
PRO = ["观察者网", "Defense News", "Breaking Defense", "The War Zone", "twz.com", "Naval News", "Janes", "Jane's",
       "Defense One", "Army Technology", "Naval Technology", "Air Force Technology", "Military Times",
       "Stars and Stripes", "The Diplomat", "Air & Space Forces", "Military.com", "The Defense Post",
       "Military Watch", "Task & Purpose", "Aviation Week", "Flight Global", "Navy Times", "The Drive",
       "军事", "国防", "军情", "兵工"]
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
    d = None
    for attempt in range(3):       # 被限流时返回空列表，重试几次
        d = feedparser.parse(url, agent=UA)
        n = len(d.entries)
        print(f"  [状态 {d.get('status', '?')}] {n} 条  尝试{attempt + 1}  {url[33:100]}")
        if n:
            break
        time.sleep(4)
    out = []
    for e in d.entries:
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
    pool, unl = [], []   # pool: 来源在名单内；unl: 来源未分级（放进“待核实线索”）
    seen_all = set()
    for cat, name, urls, only_off in BOARDS:
        st = Counter()
        seen = set()
        for url in urls:
            try:
                items = pull(url)
            except Exception as ex:
                print("失败", name, ex)
                continue
            time.sleep(1.5)
            for it in items:
                st["原始"] += 1
                if not it["t"] or it["t"] in seen or not it["ts"]:
                    continue
                if it["ts"] < now - DAYS * 86400:
                    st["过旧"] += 1
                    continue
                if any(w.lower() in it["t"].lower() for w in NOISE):
                    st["噪音"] += 1
                    continue
                lv = level(it["s"])
                seen.add(it["t"])
                if not lv:
                    st["来源未分级"] += 1
                    dropped[it["s"] or "（无来源）"] += 1
                    if not only_off and it["t"] not in seen_all:
                        seen_all.add(it["t"])
                        it["board"] = name
                        unl.append(it)
                    continue
                if only_off and lv != "官方":
                    st["非官方"] += 1
