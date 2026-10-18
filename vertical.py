# 行业垂直站抓取 -> vertical.json
# 只做一件事：把「搜索索引里搜不到」的行业站内容抓回来。
# 独立脚本：失败只影响自己，不碰 data.json，也不影响 fetch.py 主流程。
#
# 现在接了两个站（都实测过）：
#   食品伙伴网 news.foodmate.net  —— 列表页无日期，抓文章页取「时间：YYYY-MM-DD HH:MM」
#   Foodaily  www.foodaily.com    —— /articles?page=N 分页，列表自带 YYYY.MM.DD
import json, re, time, html, datetime as dt
import urllib.request as U
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
CN = dt.timezone(dt.timedelta(hours=8))
NOW = time.time()
HORIZON = 14 * 86400          # 和 fetch.py 保持一致：只保留近 14 天
CAT = "行业垂直"

def get(url, timeout=15):
    """取页面文本。先 utf-8，乱码再退回 gbk。"""
    r = U.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    raw = U.urlopen(r, timeout=timeout).read()
    try:
        t = raw.decode("utf-8")
        if t.count("\ufffd") > 20:          # 替换符太多，说明其实不是 utf-8
            raise UnicodeDecodeError("utf-8", raw, 0, 1, "too many replacement chars")
        return t
    except UnicodeDecodeError:
        return raw.decode("gb18030", "ignore")

def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).replace("\u3000", " ").strip()

def cn_ts(y, mo, d, h=0, mi=0):
    try:
        return int(dt.datetime(int(y), int(mo), int(d), int(h), int(mi), tzinfo=CN).timestamp())
    except Exception:
        return 0

MONTH0 = {}
def month_ts(y, mo):
    """兜底时间：拿不到具体日期时，退到「该月 1 号」。宁可偏旧，也不编造当天。"""
    k = (y, mo)
    if k not in MONTH0:
        MONTH0[k] = cn_ts(y, mo, 1)
    return MONTH0[k]

# ---------------------------------------------------------------- 食品伙伴网
FM_LIST = "https://news.foodmate.net/news/"
FM_A = re.compile(r'(<a[^>]+href="https://news\.foodmate\.net/(\d{4})/(\d{2})/(\d+)\.html"[^>]*>)(.*?)</a>', re.S)
FM_META = re.compile(r"时\s*间[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})"
                     r"[^<]{0,60}?来\s*源[：:]\s*([^<\s&]{2,24})")
FM_TIME = re.compile(r"时\s*间[：:]\s*(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})")

def foodmate(n=24, budget=100):
    h = get(FM_LIST)
    seen, cand = set(), []
    for tag, y, mo, aid, inner in FM_A.findall(h):
        u = f"https://news.foodmate.net/{y}/{mo}/{aid}.html"
        if u in seen:
            continue
        ta = re.search(r'title="([^"]*)"', tag)
        t = clean(ta.group(1)) if ta else ""
        if len(t) < 6:
            t = clean(inner)
        t = re.sub(r"\s+", " ", t)
        if len(t) < 6:
            continue
        seen.add(u)
        cand.append({"t": t, "u": u, "s": "食品伙伴网", "ts": month_ts(y, mo)})
    print(f"  列表页 {len(cand)} 条候选")

    # 列表页按时间倒序，取前面一段去文章页补真实时间
    head, rest = cand[:n], cand[n:]
    t0 = time.time()
    done = 0

    def fix(it):
        try:
            p = get(it["u"], timeout=12)
            m = FM_META.search(p)
            if m:
                ts = cn_ts(*m.group(1, 2, 3, 4, 5))
                src = (m.group(6) or "").strip()
                if src and "食品伙伴网" not in src:
                    it["s"] = src
            else:
                m = FM_TIME.search(p)      # 有「时间」但没有「来源」，常见于转载/评论页
                ts = cn_ts(*m.group(1, 2, 3, 4, 5)) if m else 0
            if ts:
                it["ts"] = ts
            return it, bool(ts)
        except Exception:
            return it, False

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fix, it): it for it in head}
        for f in as_completed(futs):
            if time.time() - t0 > budget:     # 超预算就不再等，剩下的用月份兜底
                continue
            _, ok = f.result()
            done += ok
    print(f"  补到真实时间 {done}/{len(head)} 条")

    out = [it for it in head + rest if it["ts"] >= NOW - HORIZON]
    for it in out:
        it.pop("_y", None); it.pop("_mo", None)
    out.sort(key=lambda x: -x["ts"])
    return out

# ---------------------------------------------------------------- Foodaily
FD_PAGE = "https://www.foodaily.com/articles?page={}"
FD_SEP = re.compile(r'<div class="row news-wrapper">')

def foodaily(pages=2):
    out, seen = [], set()
    for p in range(1, pages + 1):
        try:
            h = get(FD_PAGE.format(p))
        except Exception as ex:
            print(f"  第 {p} 页失败 {ex}")
            continue
        before = len(out)
        for b in FD_SEP.split(h)[1:]:      # [0] 是列表之前的导航，丢掉
            m = re.search(r'/articles/(\d+)', b)
            if not m or m.group(1) in seen:
                continue
            t = re.search(r'<div class="news-title[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S)
            title = re.sub(r"\s+", " ", clean(t.group(1))) if t else ""
            if len(title) < 8:
                continue
            d = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', b)   # news-user-time 里的 YYYY.MM.DD
            ts = cn_ts(*d.group(1, 2, 3)) if d else 0
            if not ts or ts < NOW - HORIZON:
                continue
            seen.add(m.group(1))
            who = re.search(r'el-icon-user[^>]*></i>\s*([^<]{1,20})', b)
            out.append({"t": title, "u": f"https://www.foodaily.com/articles/{m.group(1)}",
                        "s": clean(who.group(1)) if who else "Foodaily", "ts": ts})
        print(f"  第 {p} 页 +{len(out) - before} 条，累计 {len(out)}")
    out.sort(key=lambda x: -x["ts"])
    return out[:30]

# ---------------------------------------------------------------- 主流程
SITES = [("食品伙伴网", foodmate), ("Foodaily", foodaily)]

boards = []
for name, fn in SITES:
    try:
        items = fn()
    except Exception as ex:
        print(f"失败 {name}: {type(ex).__name__} {ex}")
        items = []
    print(f"{name} {len(items)} 条")
    if items:
        boards.append({"cat": CAT, "name": name, "items": items})

json.dump({"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "boards": boards},
          open("vertical.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"vertical.json 写入 {sum(len(b['items']) for b in boards)} 条")
