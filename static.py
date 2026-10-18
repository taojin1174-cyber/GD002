#!/usr/bin/env python3
"""静态页生成：today.html + d/YYYY-MM-DD.html + sitemap.xml

为什么需要它：站点主体是纯前端渲染，爬虫抓到的是一张空壳。
这里把 data.json 里的内容直接写成 HTML，爬虫和分享卡片都能看到真实标题。

- 不依赖任何第三方库，只用标准库
- 读不到 data.json 就直接退出，不碰任何已有文件
- 产物：today.html（今日全部）、d/YYYY-MM-DD.html（每日归档）、sitemap.xml
"""
import json, os, re, html, datetime as dt

SITE = "https://gd008.bbroot.com"
CN = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime.now(CN)
PER_BOARD = 8           # 每个榜单在静态页里最多列几条
ARCHIVE_DAYS = 14       # 生成最近多少天的归档页
MAX_DAYS = 14

def save_if_changed(path, text):
    """内容没变就不写：避免每小时都产生一次无意义的 git 变更。"""
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except Exception:
        pass
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True

def load(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def esc(s):
    return html.escape(str(s or ""), quote=True)

def ago(ts):
    if not ts:
        return ""
    m = (NOW.timestamp() - ts) / 60
    if m < 1:
        return "刚刚"
    if m < 60:
        return f"{int(m)} 分钟前"
    if m < 1440:
        return f"{int(m / 60)} 小时前"
    return f"{int(m / 1440)} 天前"

def day_of(ts):
    return dt.datetime.fromtimestamp(ts, CN).strftime("%Y-%m-%d")

# ---------------------------------------------------------------- 页面模板
CSS = """
:root{color-scheme:dark;--bg:#141a17;--card:#1b2320;--line:#2b3632;--ink:#e6ece9;--mute:#93a39c;--acc:#e2603f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
header{border-bottom:1px solid var(--line);padding:14px 18px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:17px;margin:0}
header .sub{color:var(--mute);font-size:13px}
header a{color:var(--acc);text-decoration:none;font-size:13px}
main{max-width:900px;margin:0 auto;padding:8px 18px 60px}
section{margin:22px 0}
h2{font-size:14px;margin:0 0 8px;padding-bottom:6px;border-bottom:1px solid var(--line);color:var(--ink);display:flex;justify-content:space-between;gap:10px}
h2 small{color:var(--mute);font-weight:400;font-size:12px;white-space:nowrap}
ul{list-style:none;margin:0;padding:0}
li{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);align-items:flex-start}
li:last-child{border-bottom:0}
li img{width:52px;height:52px;object-fit:cover;border-radius:6px;flex:none;background:var(--card)}
li .tx{flex:1;min-width:0}
li a{color:var(--ink);text-decoration:none;font-weight:500}
li a:hover{color:var(--acc)}
li .m{display:block;color:var(--mute);font-size:12px;margin-top:2px}
li .d{display:block;color:var(--mute);font-size:12.5px;margin-top:3px}
footer{color:var(--mute);font-size:12px;padding:26px 18px 40px;text-align:center;border-top:1px solid var(--line);margin-top:20px}
footer a{color:var(--mute)}
.days{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 0}
.days a{font-size:12.5px;color:var(--mute);border:1px solid var(--line);border-radius:12px;padding:2px 10px;text-decoration:none}
.days a:hover{color:var(--acc)}
"""

def page(title, desc, body, canonical, days=None, og_img="", items=None):
    graph = [{
        "@type": "WebSite", "name": "热点观察 · 预制菜与食品行业",
        "url": SITE + "/", "inLanguage": "zh-CN", "description": desc,
    }]
    if items:                          # ItemList：让搜索引擎看到"这是一个资讯列表页"
        graph.append({
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1, "url": it.get("u") or "",
                 "name": it.get("t") or ""}
                for n, it in enumerate(items[:20])
            ],
        })
    ld = {"@context": "https://schema.org", "@graph": graph}
    img_meta = f'<meta property="og:image" content="{esc(og_img)}">' if og_img else ""
    day_nav = ""
    if days:
        day_nav = '<div class="days"><span style="color:var(--mute);font-size:12.5px">往日归档：</span>' + \
            "".join(f'<a href="{SITE}/d/{d}.html">{d[5:]}</a>' for d in days[:MAX_DAYS]) + "</div>"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#141a17">
<meta property="og:type" content="website">
<meta property="og:site_name" content="热点观察">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
{img_meta}
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>热点观察 · 预制菜与食品行业</h1>
  <span class="sub">{esc(title)}</span>
  <a href="/">← 打开交互版</a>
  <a href="/rd.html">研发工作台</a>
</header>
<main>
{body}
{day_nav}
</main>
<footer>
静态页由抓取任务自动生成，每次更新数据时重建。<br>
交互版（可搜索 / 收藏 / 看趋势图）：<a href="/">{SITE}</a>
</footer>
</body>
</html>
"""

def render_day(day, boards, days):
    """把某一天的条目渲染成 section 列表。"""
    secs, picked = [], []
    for b in boards:
        its = [i for i in b.get("items", []) if i.get("ts") and day_of(i["ts"]) == day]
        if not its:
            continue
        its.sort(key=lambda x: -x["ts"])
        lis = []
        for i in its[:PER_BOARD]:
            img = f'<img src="{esc(i["img"])}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">' if i.get("img") else ""
            dsc = f'<span class="d">{esc(i["d"])}</span>' if i.get("d") else ""
            lis.append(
                f'<li>{img}<div class="tx">'
                f'<a href="{esc(i.get("u") or "#")}" target="_blank" rel="noopener noreferrer">{esc(i.get("t"))}</a>'
                f'{dsc}<span class="m">{esc(i.get("s"))} · {esc(ago(i["ts"]))}</span>'
                f'</div></li>')
            picked.append(i)
        secs.append(f'<section><h2>{esc(b.get("cat"))} · {esc(b.get("name"))}'
                    f'<small>共 {len(its)} 条</small></h2><ul>{"".join(lis)}</ul></section>')
    return "".join(secs), picked

def brief(t, n=22):
    """取标题主干做描述，去掉「| 栏目名」这类尾巴，避免描述被截断在半个词上。"""
    t = re.sub(r"[|｜:：].*$", "", t or "").strip()
    return t[:n]

def build(day, boards, days):
    body, picked = render_day(day, boards, days)
    if not picked:
        return None
    picked.sort(key=lambda x: -x["ts"])
    top = "、".join(brief(x["t"]) for x in picked[:4])
    desc = f"{day} 预制菜与食品行业热点，共 {len(picked)} 条。{top}"
    og = next((x["img"] for x in picked if x.get("img")), "")
    title = f"{day} 食品与预制菜热点汇总 · 热点观察"
    return page(title, desc[:150], body, f"{SITE}/d/{day}.html", days, og, picked)

def build_today(boards, days):
    day = NOW.strftime("%Y-%m-%d")
    body, picked = render_day(day, boards, days)
    if not picked:                      # 今天还没数据就退回最近一天
        day = days[0] if days else day
        body, picked = render_day(day, boards, days)
    if not picked:
        return None, day
    picked.sort(key=lambda x: -x["ts"])
    top = "、".join(brief(x["t"]) for x in picked[:4])
    desc = f"每日更新的预制菜与食品行业热点，今日 {len(picked)} 条。{top}"
    og = next((x["img"] for x in picked if x.get("img")), "")
    return page(f"今日食品与预制菜热点（{day}）· 热点观察", desc[:150], body,
                f"{SITE}/today.html", days, og, picked), day

def main():
    data = load("data.json")
    if not data or not data.get("boards"):
        print("data.json 不存在或没有 boards，跳过静态页")
        return
    boards = data["boards"]
    # 所有有内容的日期，新到旧
    ds = sorted({day_of(i["ts"]) for b in boards for i in b.get("items", []) if i.get("ts")}, reverse=True)
    ds = ds[:ARCHIVE_DAYS]
    if not ds:
        print("没有带时间戳的条目，跳过")
        return
    os.makedirs("d", exist_ok=True)

    today = NOW.strftime("%Y-%m-%d")
    # 只归档「已经结束」的日期：当天那页每小时都在变，没必要每轮重写一遍，
    # 否则一年下来 git 历史会被同一页的几十个版本撑爆。当天内容由 today.html 承担。
    made = 0
    for day in ds:
        if day >= today:
            continue
        h = build(day, boards, ds)
        if h and save_if_changed(os.path.join("d", f"{day}.html"), h):
            made += 1

    today_html, used = build_today(boards, ds)
    if today_html:
        save_if_changed("today.html", today_html)

    # sitemap：首页 + 静态页 + 归档页（带 lastmod）
    urls = [("/", today), ("/rd.html", "2026-10-01"), ("/today.html", today)]
    urls += [(f"/d/{d}.html", d) for d in ds if d < today]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, lm in urls:
        pr = "1.0" if p == "/" else ("0.8" if p == "/today.html" else "0.6")
        sm.append(f"  <url><loc>{SITE}{p}</loc><lastmod>{lm}</lastmod>"
                  f"<changefreq>{'hourly' if p == '/' else 'daily'}</changefreq>"
                  f"<priority>{pr}</priority></url>")
    sm.append("</urlset>")
    save_if_changed("sitemap.xml", "\n".join(sm) + "\n")

    print(f"静态页完成：today.html（{used}）+ {made} 个归档页 + sitemap {len(urls)} 条 URL")

if __name__ == "__main__":
    main()
