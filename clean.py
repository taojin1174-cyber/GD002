#!/usr/bin/env python3
"""后处理：过滤噪音/spam、去重、英文标题翻译、今日要点、更新时间。
放在 eco.py 之后运行。没有 ANTHROPIC_API_KEY 时，只做过滤和去重。"""
import json, os, re, hashlib, difflib, urllib.request
from datetime import datetime, timezone, timedelta

FILES = {"food": "data.json", "ai": "ai.json", "eco": "eco.json", "mil": "mil.json"}
TITLE_KEYS = ("title", "t", "name")
URL_KEYS = ("url", "link", "href")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BJ = timezone(timedelta(hours=8))

# ---------- 规则（以后直接在这里加词） ----------
SPAM = [  # 所有频道通用：色情、赌博、导流
    "吊起来", "打屁股", "校花", "官方版", "高清完整", "免费观看", "在线观看",
    "六合彩", "6合彩", "特码", "彩票", "博彩", "赌场", "澳门赌", "葡京",
    "成人", "裸聊", "约炮", "福利姬", "资源分享", "网盘", "磁力",
]
NOISE_FOOD = [  # 食品频道：影视、饭圈、无关热点（注意别误伤食材词，如「粉丝」）
    "短剧", "古代", "穿越", "重生", "小说", "剧情", "预告", "追剧", "神之八秒",
    "断刹", "尊界", "饭圈", "演唱会",
]
NOISE_ECO = [  # 经济频道：娱乐、体育、社会八卦
    "明星", "出轨", "离婚", "演唱会", "综艺", "八卦", "恋情", "塌房", "爆料",
    "世界杯", "NBA", "英超", "电竞", "游戏", "手游",
]
NOISE = {"food": NOISE_FOOD, "ai": [], "eco": NOISE_ECO, "mil": []}

# ---------- 工具函数 ----------
def tkey(d):
    for k in TITLE_KEYS:
        if isinstance(d.get(k), str) and d[k].strip():
            return k
    return None

def ukey(d):
    for k in URL_KEYS:
        if isinstance(d.get(k), str):
            return k
    return None

def norm(s):
    return re.sub(r"[\W_]+", "", s.lower())

def has_cjk(s):
    return re.search(r"[\u4e00-\u9fff]", s) is not None

def bad(title, channel):
    return any(w.lower() in title.lower() for w in SPAM + NOISE.get(channel, []))

def walk(obj):
    """找出所有“元素是带标题的 dict”的列表，原地可改。"""
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj) and any(tkey(x) for x in obj):
            yield obj
        for x in obj:
            yield from walk(x)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk(v)

def dedupe_boards(data):
    """跨榜单去重：同一条新闻只保留在靠前的榜单里（榜单顺序=优先级）。"""
    seen, removed = set(), 0
    boards = data.get("boards") if isinstance(data, dict) else None
    if not boards:
        return 0
    for b in boards:
        keep = []
        for it in b.get("items", []):
            k = tkey(it)
            n = norm(it[k]) if k else ""
            if n and n in seen:
                removed += 1
                continue
            if n:
                seen.add(n)
            keep.append(it)
        b["items"] = keep
    return removed

def clean_list(lst, channel):
    kept, seen_url, seen_title = [], set(), []
    for it in lst:
        k = tkey(it)
        if not k:
            kept.append(it)
            continue
        title = it[k].strip()
        uk = ukey(it)
        url = it.get(uk, "") if uk else ""
        if bad(title, channel):
            continue
        if uk and url and not url.startswith(("http://", "https://", "/")):
            continue
        if url and url in seen_url:
            continue
        n = norm(title)
        if n and any(n == m or difflib.SequenceMatcher(None, n, m).ratio() > 0.85 for m in seen_title):
            continue
        if url:
            seen_url.add(url)
        seen_title.append(n)
        kept.append(it)
    return kept

# ---------- Claude API ----------
def claude(prompt, max_tokens=2000):
    if not API_KEY:
        return None
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)["content"][0]["text"]
    except Exception as e:
        print("API 调用失败:", e)
        return None

def parse_json(text):
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else []
    except Exception:
        return []

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, obj):
    """紧凑写回（不留缩进，省 25% 以上流量）；内容没变就不动文件。"""
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == txt:
                return
    except Exception:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)

# ---------- 翻译（带缓存，只翻新标题） ----------
def translate(all_items):
    cache = load("translate_cache.json", {})
    todo = {}
    for it in all_items:
        k = tkey(it)
        t = it[k]
        if has_cjk(t):
            continue
        h = hashlib.sha1(t.encode()).hexdigest()[:16]
        if h in cache:
            it["title_en"] = t
            it[k] = cache[h]
        else:
            todo[h] = t
    items = list(todo.items())[:60]  # 每次最多翻 60 条，控制成本
    for i in range(0, len(items), 20):
        batch = items[i:i + 20]
        lines = "\n".join(f"{n}. {t}" for n, (_, t) in enumerate(batch))
        out = claude("把下列英文新闻标题翻译成简洁准确的中文，保留公司/产品名。"
                     "只返回 JSON 数组：[{\"i\":编号,\"zh\":\"译文\"}]，不要其他文字。\n" + lines)
        for r in parse_json(out):
            try:
                cache[batch[r["i"]][0]] = r["zh"].strip()
            except Exception:
                pass
    save("translate_cache.json", cache)
    for it in all_items:  # 本轮新翻译的也回填
        k = tkey(it)
        h = hashlib.sha1(it[k].encode()).hexdigest()[:16]
        if not has_cjk(it[k]) and h in cache:
            it["title_en"] = it[k]
            it[k] = cache[h]

# ---------- 今日要点（每 6 小时刷新一次） ----------
def highlights(channel_items):
    old = load("highlights.json", {})
    try:
        last = datetime.fromisoformat(old.get("updated", "2000-01-01T00:00:00+08:00"))
        if (datetime.now(BJ) - last).total_seconds() < 6 * 3600:
            return
    except Exception:
        pass
    cands = []
    for ch, items in channel_items.items():
        for it in items[:25]:
            k, uk = tkey(it), ukey(it)
            cands.append({"c": ch, "title": it[k], "url": it.get(uk, "") if uk else ""})
    if not cands:
        return
    lines = "\n".join(f"{n}. [{c['c']}] {c['title']}" for n, c in enumerate(cands))
    out = claude("你是预制菜研发团队的资讯编辑。从下列标题中选出 5 条对预制菜产品研发、"
                 "原料(猪肉/鸡肉/鸡蛋)行情、行业政策或宏观经济最重要的。每条写一句话中文解读，"
                 "只能基于标题，不得编造标题里没有的数据。只返回 JSON 数组："
                 "[{\"i\":编号,\"summary\":\"解读\"}]。\n" + lines, 1500)
    picks = []
    for r in parse_json(out):
        try:
            c = cands[r["i"]]
            picks.append({"title": c["title"], "url": c["url"], "channel": c["c"], "summary": r["summary"]})
        except Exception:
            pass
    if picks:
        save("highlights.json", {"updated": datetime.now(BJ).isoformat(timespec="seconds"), "items": picks[:5]})

# ---------- 主流程 ----------
def main():
    channel_items, removed = {}, 0
    for ch, path in FILES.items():
        data = load(path, None)
        if data is None:
            continue
        removed += dedupe_boards(data)
        for lst in walk(data):
            before = len(lst)
            lst[:] = clean_list(lst, ch)
            removed += before - len(lst)
        channel_items[ch] = [x for lst in walk(data) for x in lst if tkey(x)]
        if API_KEY:
            translate(channel_items[ch])
        save(path, data)
    if API_KEY:
        highlights(channel_items)
    save("meta.json", {"updated": datetime.now(BJ).strftime("%Y-%m-%d %H:%M"), "removed": removed})
    print(f"清洗完成，移除 {removed} 条")

if __name__ == "__main__":
    main()
