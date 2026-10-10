# AI 频道：采集 -> 分类 -> 去重 -> ai.json（和食品站的 data.json 完全分开）。依赖: feedparser
import json, re, time, socket, os, sys, calendar, datetime as dt
from urllib.parse import quote, urlparse
import feedparser
socket.setdefaulttimeout(20)
UA = "Mozilla/5.0 (ai-news bot)"
g = lambda q, hl, gl, ce: f"https://news.google.com/rss/search?q={quote(q + ' when:7d')}&hl={hl}&gl={gl}&ceid={ce}"
zh = lambda q: g(q, "zh-CN", "CN", "CN:zh-Hans")
en = lambda q: g(q, "en-US", "US", "US:en")
FEEDS = [  # 想加来源就加一行 RSS 地址
    zh("新模型 发布 OR 推出 OR 上线 大模型"), zh("DeepSeek OR 通义千问 OR 豆包 OR Kimi OR 智谱 OR 文心 OR 混元 大模型"),
    zh("OpenAI OR Anthropic OR Gemini OR xAI 模型 OR 发布 OR 融资"), zh("人工智能 医疗 OR 药物研发 OR 科学发现 OR 教育 OR 农业 突破"),
    zh("智能体 OR AI编程 OR Agent 发布 OR 应用"), zh("人工智能 监管 OR 立法 OR 安全 OR 版权"), zh("AI 食品研发 OR 餐饮 OR 预制菜 OR 食品行业"),
    en("OpenAI OR Anthropic OR Gemini OR DeepSeek new model release"), en("AI agent OR coding agent launch"),
    en("AI drug discovery OR medical AI breakthrough"), en("AI regulation OR AI safety law"), en("AI food industry OR food technology artificial intelligence"),
    "https://openai.com/news/rss.xml", "https://huggingface.co/blog/feed.xml", "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "https://venturebeat.com/category/ai/feed/"]
AIRE = re.compile(r"\bAI\b|人工智能|大模型|模型|OpenAI|Anthropic|Claude|Gemini|DeepSeek|GPT|LLM|智能体|千问|Kimi|豆包|智谱|文心|混元|agent|machine learning|generative|机器人|robot", re.I)
MODEL = r"模型|model|GPT|Claude|Gemini|Llama|Qwen|DeepSeek|Kimi|千问|豆包"
LAUNCH = r"发布|推出|上线|升级|release|launch|unveil|introduc|debut|rolls? out"
COLS = [  # 按顺序匹配，先中先得；都不中归「全球AI公司动态」
    ("AI与食品产业", r"食品|餐饮|预制菜|\bfood\b|restaurant|agri"),
    ("全球新模型发布", rf"({LAUNCH}).*({MODEL})|({MODEL}).*({LAUNCH})"),
    ("AI造福人类", r"医疗|诊断|药物|疾病|癌|教育|农业|科学发现|health|medical|drug|disease|cancer|climate|diagnos|education|scien"),
    ("AI工具与智能体", r"智能体|编程|自动化|办公|Copilot|Cursor|Codex|agent|coding|workflow|automation"),
    ("AI科学与技术突破", r"机器人|多模态|算力|芯片|开源|论文|研究|robot|multimodal|GPU|chip|open-source|paper|research"),
    ("AI政策与安全", r"监管|立法|版权|安全|法案|regulat|\blaw\b|copyright|safety|\bban\b|policy")]
ORDER = ["全球新模型发布", "全球AI公司动态", "AI造福人类", "AI工具与智能体", "AI与食品产业", "AI科学与技术突破", "AI政策与安全"]
CN = re.compile(r"DeepSeek|通义|千问|Qwen|豆包|字节|Kimi|月之暗面|智谱|文心|百度|混元|腾讯|阿里|华为|讯飞|商汤|MiniMax", re.I)
OS = re.compile(r"OpenAI|Anthropic|Claude|Gemini|Google|DeepMind|Meta|Llama|xAI|Grok|Microsoft|Mistral|Nvidia|英伟达|GPT", re.I)
OFF_HOST = ("openai.com", "huggingface.co", "blog.google", "anthropic.com", "deepmind.google", "ai.meta.com", "deepseek.com")
OFF_NAME = re.compile(r"^(OpenAI|Anthropic|Google (AI|DeepMind)|DeepMind|Hugging Face|Meta AI|DeepSeek)", re.I)
RUMOR = re.compile(r"传闻|据称|爆料|疑似|rumou?r|reportedly|leak|allegedly", re.I)
RANK = {"官方发布": 2, "媒体报道": 1, "待核实": 0}

def evid(it):  # 规则标记（按来源判断），不等于独立核实
    if any(urlparse(it["u"]).netloc.endswith(x) for x in OFF_HOST) or OFF_NAME.search(it["s"]): return "官方发布"
    return "待核实" if RUMOR.search(it["t"]) else "媒体报道"
def bg(s):
    s = re.sub(r"[\W_]+", "", s.lower()); return {s[i:i + 2] for i in range(len(s) - 1)}

now = time.time(); items = []
for url in FEEDS:
    try: d = feedparser.parse(url, agent=UA)
    except Exception as ex: print("失败", url[:50], ex); continue
    print(urlparse(url).netloc, len(d.entries))
    for e in d.entries:
        t = re.sub(r"\s+", " ", e.get("title", "")).strip(); s = ""
        if " - " in t and "news.google.com" in url: t, s = t.rsplit(" - ", 1)
        s = s or (e.get("source") or {}).get("title") or urlparse(url).netloc.replace("www.", "")
        ts = calendar.timegm(e.published_parsed) if e.get("published_parsed") else 0
        if t and ts and ts > now - 10 * 86400 and (AIRE.search(t) or "news.google.com" not in url): items.append({"t": t, "u": e.get("link", ""), "s": s, "ts": ts})

items.sort(key=lambda x: -x["ts"]); ev = []
for it in items:   # 事件去重：不同媒体改写的同一件事合并
    gs = bg(it["t"])
    for e in ev:
        if len(gs & e["g"]) / (len(gs | e["g"]) or 1) >= .5: e["it"].append(it); break
    else: ev.append({"g": gs, "it": [it]})
reps = []
for e in ev:
    for it in e["it"]: it["ev"] = evid(it)
    r = max(e["it"], key=lambda i: (RANK[i["ev"]], i["ts"])); r["n"] = len({i["s"] for i in e["it"]}); reps.append(r)
reps = sorted(reps, key=lambda x: -x["ts"])[:200]
if len(reps) < 5 and os.path.exists("ai.json"): print("本次数据过少，保留上次的 ai.json"); sys.exit(0)

try: cache = json.load(open("links3.json", encoding="utf-8"))   # Google 跳转链接 -> 原文直链
except Exception: cache = {}
todo = [r["u"] for r in reps if "news.google.com" in r["u"] and r["u"] not in cache][:60]
try:
    from googlenewsdecoder import gnewsdecoder
    for k in range(0, len(todo), 10):
        c = todo[k:k + 10]
        try:
            for u, x in zip(c, gnewsdecoder(c, interval=1)):
                if (x.get("success") or x.get("status")) and x.get("decoded_url"): cache[u] = x["decoded_url"]
        except Exception as ex: print("解码失败:", ex)
except Exception as ex: print("解码库不可用:", ex)
cur = {r["u"] for r in reps}; cache = {u: v for u, v in cache.items() if u in cur}
json.dump(cache, open("links3.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

boards = {c: [] for c in ORDER}
for r in reps:
    col = next((c for c, p in COLS if re.search(p, r["t"], re.I)), "全球AI公司动态")
    cn, o = bool(CN.search(r["t"])), bool(OS.search(r["t"]))
    reg = "国内+海外" if cn and o else "国内" if cn else "海外" if o else "地区未标注"
    tag = f"{r['s']} · {reg} · {r['ev']}" + (f" · {r['n']}家报道" if r["n"] > 1 else "")
    boards[col].append({"t": r["t"], "u": cache.get(r["u"], r["u"]), "s": tag, "ts": r["ts"]})
out = {"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "title": "AI 动态 · 全球观察",
       "boards": [{"cat": c, "name": c, "items": boards[c][:30]} for c in ORDER]}
json.dump(out, open("ai.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("完成：", {c: len(boards[c]) for c in ORDER})
