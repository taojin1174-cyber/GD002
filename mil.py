
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 军事频道：抓取新闻、来源分级、多源交叉验证、生成 mil.json

import calendar
import datetime as dt
import json
import os
import re
import socket
import time
from collections import Counter
from urllib.parse import quote

import feedparser

socket.setdefaulttimeout(25)

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

DAYS = 3
PER_BOARD = 15
MAX_RETRIES = 3
RETRY_WAIT = 3

# ---------- RSS 搜索地址 ----------

def gn(query):
    query = quote(f"{query} when:{DAYS}d")
    return (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )


def gne(query):
    query = quote(f"{query} when:{DAYS}d")
    return (
        "https://news.google.com/rss/search?q="
        + query
        + "&hl=en-US&gl=US&ceid=US:en"
    )


# ---------- 来源分级 ----------

OFFICIAL = [
    "国防部", "外交部", "中国军网", "解放军报",
    "中央军委", "国务院台办", "海警局",
    "Ministry of Defence", "Ministry of Defense",
    "Department of Defense", "Department of War",
    "NATO", "Pentagon", "Kremlin",
    "GOV.UK", "defense.gov", "war.gov",
]

MAINSTREAM = [
    "新华社", "新华网", "Xinhua", "央视", "CCTV",
    "CGTN", "人民日报", "中国新闻网", "中新网",
    "澎湃", "环球时报", "环球网", "联合早报",
    "中国日报", "China Daily", "参考消息",
    "界面新闻", "财新", "第一财经", "光明网",
    "国际在线", "海外网", "央广网", "新京报",
    "中国青年报", "凤凰网", "南华早报",
    "South China Morning Post", "SCMP",
    "中央社", "韩联社", "Yonhap", "日经", "Nikkei",
    "Straits Times", "塔斯社", "TASS",
    "法新社", "AFP", "Reuters", "路透",
    "Associated Press", "AP News", "BBC",
    "Bloomberg", "Al Jazeera", "The Guardian",
    "CNN", "Financial Times", "NHK", "NPR",
    "PBS", "Axios", "Times of Israel",
    "Kyiv Independent", "Ukrinform",
]

PRO = [
    "观察者网", "Defense News", "Breaking Defense",
    "The War Zone", "twz.com", "Naval News",
    "Janes", "Jane's", "Defense One",
    "Army Technology", "Naval Technology",
    "Air Force Technology", "Military Times",
    "Stars and Stripes", "The Diplomat",
    "Air & Space Forces", "Military.com",
    "The Defense Post", "Military Watch",
    "Task & Purpose", "Aviation Week",
    "Flight Global", "Navy Times", "The Drive",
]

RANK = {"官方": 3, "媒体": 2, "专业": 1}


def level(source):
    """按来源名称进行粗略分级，不代表对报道内容的独立核实。"""
    source = (source or "").strip().lower()

    if not source:
        return None

    for name in OFFICIAL:
        if name.lower() in source:
            return "官方"

    for name in MAINSTREAM:
        if name.lower() in source:
            return "媒体"

    for name in PRO:
        if name.lower() in source:
            return "专业"

    return None


# ---------- 过滤明显无关内容 ----------

NOISE = [
    "手游", "吃鸡", "军模", "小说", "影评", "电视剧",
    "综艺", "抖音", "壁纸", "玩具", "盲盒",
    "打屁股", "校花", "高清完整", "六合彩", "彩票",
    "细思极恐", "不敢相信", "竟然是",
]


# ---------- 新闻分类 ----------
# 格式：(分类名称, 板块名称, RSS地址列表, 是否只收官方来源)

BOARDS = [
    (
        "通报",
        "官方通报",
        [
            gn("国防部 发言人"),
            gn("国防部 例行记者会"),
            gn("中国军网"),
            gn("解放军报"),
            gne("Ministry of Defence statement"),
            gne("NATO official statement defence"),
        ],
        True,
    ),
    (
        "热点",
        "台海与南海",
        [
            gn("台海 解放军 军演"),
            gn("南海 菲律宾 海警 仁爱礁 黄岩岛"),
        ],
        False,
    ),
    (
        "热点",
        "朝鲜半岛",
        [
            gn("朝鲜 导弹 试射 军演"),
            gn("韩国 美韩 联合军演"),
        ],
        False,
    ),
    (
        "热点",
        "俄乌战场",
        [
            gn("乌克兰 俄罗斯 前线 无人机 袭击"),
            gn("俄乌 停火 和谈 战场"),
        ],
        False,
    ),
    (
        "热点",
        "中东局势",
        [
            gn("以色列 伊朗 空袭 袭击"),
            gn("加沙 胡塞 中东 军事"),
        ],
        False,
    ),
    (
        "装备产业",
        "装备与技术",
        [
            gn("新型 战机 舰艇 导弹 无人机 列装"),
            gn("战机 首飞 军舰 下水 导弹 试射"),
        ],
        False,
    ),
    (
        "装备产业",
        "军工与军费",
        [
            gn("军工 订单 出口 财报"),
            gn("国防预算 军费 增长"),
        ],
        False,
    ),
    (
        "国际源",
        "国际权威源（英文）",
        [
            gne(
                "site:defensenews.com OR "
                "site:breakingdefense.com OR "
                "site:twz.com OR site:navalnews.com"
            ),
            gne("Reuters military defense warship missile"),
            gne("Associated Press military defense"),
        ],
        False,
    ),
]


# ---------- 获取 RSS ----------

def pull(url):
    """抓取 RSS，返回统一格式的新闻列表。"""
    parsed = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            parsed = feedparser.parse(
                url,
                agent=UA,
                request_headers={"User-Agent": UA},
            )

            entries = parsed.entries
            status = parsed.get("status", "?")

            print(
                f"[RSS] HTTP状态={status} "
                f"条数={len(entries)} "
                f"尝试={attempt} "
                f"地址={url[:110]}"
            )

            if entries:
                break

        except Exception as exc:
            print(f"[RSS错误] 第{attempt}次：{exc}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT)

    if parsed is None:
        return []

    results = []

    for entry in parsed.entries:
        title = re.sub(
            r"\s+", " ", entry.get("title", "")
        ).strip()

        if not title:
            continue

        source = (
            (entry.get("source") or {}).get("title") or ""
        ).strip()

        # Google 新闻标题常见格式：新闻标题 - 媒体名称
        if " - " in title:
            possible_title, possible_source = title.rsplit(
                " - ", 1
            )

            if possible_title.strip():
                title = possible_title.strip()

            if not source:
                source = possible_source.strip()

        published = entry.get("published_parsed")

        if published:
            timestamp = int(calendar.timegm(published))
        else:
            updated = entry.get("updated_parsed")
            timestamp = (
                int(calendar.timegm(updated))
                if updated
                else 0
            )

        results.append({
            "t": title,
            "u": entry.get("link", ""),
            "s": source,
            "ts": timestamp,
        })

    return results


# ---------- 标题相似度 ----------

def normalize_title(title):
    title = (title or "").lower()
    return re.sub(r"[\W_]+", "", title)


def bigrams(title):
    text = normalize_title(title)

    if len(text) <= 1:
        return {text} if text else set()

    return {
        text[i:i + 2]
        for i in range(len(text) - 1)
    }


def similarity(a, b):
    if not a or not b:
        return 0.0

    return len(a & b) / max(1, len(a | b))


def same_story(title_a, title_b):
    """判断两条标题是否可能描述同一事件。"""
    a = normalize_title(title_a)
    b = normalize_title(title_b)

    if not a or not b:
        return False

    # 短标题必须更谨慎，避免错误合并不同事件
    if min(len(a), len(b)) < 8:
        return a == b

    if a in b or b in a:
        return True

    return similarity(bigrams(a), bigrams(b)) >= 0.30


# ---------- 主程序 ----------

def main():
    now = int(time.time())
    cutoff = now - DAYS * 86400

    dropped = Counter()
    pool = []
    pending_pool = []

    # 关键修复：
    # 不在抓取阶段跨媒体全局去重。
    # 不同来源的相似标题必须保留，后面才能交叉聚类。

    for category, board_name, urls, official_only in BOARDS:
        stats = Counter()
        board_seen = set()

        for url in urls:
            try:
                articles = pull(url)
            except Exception as exc:
                print(f"[抓取失败] {board_name}: {exc}")
                continue

            for article in articles:
                stats["抓取"] += 1

                title = article["t"]
                timestamp = article["ts"]
                source = article["s"]

                if not title or not article["u"]:
                    stats["缺少标题或链接"] += 1
                    continue

                if not timestamp:
                    stats["缺少发布时间"] += 1
                    continue

                if timestamp < cutoff or timestamp > now + 3600:
                    stats["时间范围外"] += 1
                    continue

                title_key = normalize_title(title)

                # 只在当前板块内去掉完全相同的重复项；
                # 不阻止不同媒体的同一事件进入聚类。
                local_key = (title_key, source, article["u"])

                if local_key in board_seen:
                    continue

                board_seen.add(local_key)

                if any(word.lower() in title.lower() for word in NOISE):
                    stats["过滤无关内容"] += 1
                    continue

                article["board"] = board_name
                article["cat"] = category
                article["level"] = level(source)

                if not article["level"]:
                    stats["来源待识别"] += 1
                    dropped[source or "未知来源"] += 1

                    if not official_only:
                        pending_pool.append(article)

                    continue

                if official_only and article["level"] != "官方":
                    stats["非官方来源"] += 1
                    continue

                pool.append(article)
                stats["进入候选"] += 1

            time.sleep(0.8)

        print(f"[统计] {board_name}: {dict(stats)}")

    # ---------- 按标题合并同一事件 ----------

    groups = []

    for article in sorted(
        pool, key=lambda item: item["ts"], reverse=True
    ):
        matched_group = None

        for group in groups:
            if same_story(article["t"], group["t"]):
                matched_group = group
                break

        if matched_group is None:
            groups.append({
                "items": [article],
                "board": article["board"],
                "cat": article["cat"],
                "t": article["t"],
                "u": article["u"],
                "s": article["s"],
                "ts": article["ts"],
                "level": article["level"],
            })
            continue

        matched_group["items"].append(article)

        # 优先采用来源等级较高的报道作为展示标题和链接
        if RANK.get(article["level"], 0) > RANK.get(
            matched_group["level"], 0
        ):
            matched_group["t"] = article["t"]
            matched_group["u"] = article["u"]
            matched_group["s"] = article["s"]
            matched_group["ts"] = article["ts"]
            matched_group["level"] = article["level"]

    # ---------- 生成多源确认要闻 ----------

    headlines = []

    for group in groups:
        sources = {
            item["s"].strip()
            for item in group["items"]
            if item.get("s", "").strip()
        }

        if len(sources) >= 2:
            headlines.append({
                "t": group["t"],
                "u": group["u"],
                "s": (
                    f'{group["level"]}来源 · '
                    f'多源报道（{len(sources)}家）'
                ),
                "ts": group["ts"],
            })

    headlines.sort(
        key=lambda item: item["ts"], reverse=True
    )

    boards = [{
        "cat": "要闻",
        "name": "多源确认要闻",
        "items": headlines[:PER_BOARD],
    }]

    # ---------- 生成各分类板块 ----------

    for category, board_name, urls, official_only in BOARDS:
        items = []

        for group in groups:
            if group["board"] != board_name:
                continue

            sources = {
                item["s"].strip()
                for item in group["items"]
                if item.get("s", "").strip()
            }

            if len(sources) >= 2:
                label = (
                    f'{group["level"]}来源 · '
                    f'多源报道（{len(sources)}家）'
                )
            elif group["level"] == "官方":
                label = "官方来源"
            elif group["level"] == "媒体":
                label = "主流媒体"
            else:
                label = "专业来源"

            items.append({
                "t": group["t"],
                "u": group["u"],
                "s": f'{label} · {group["s"]}',
                "ts": group["ts"],
            })

        items.sort(
            key=lambda item: item["ts"], reverse=True
        )

        boards.append({
            "cat": category,
            "name": board_name,
            "items": items[:PER_BOARD],
        })

    # ---------- 来源待核实线索 ----------

    if pending_pool:
        pending = []
        seen_pending = set()

        for article in sorted(
            pending_pool,
            key=lambda item: item["ts"],
            reverse=True,
        ):
            key = normalize_title(article["t"])

            if key in seen_pending:
                continue

            seen_pending.add(key)

            pending.append({
                "t": article["t"],
                "u": article["u"],
                "s": (
                    "来源待核实 · "
                    + (article["s"] or "未知来源")
                ),
                "ts": article["ts"],
            })

        boards.append({
            "cat": "待核实",
            "name": "待核实线索",
            "items": pending[:PER_BOARD],
        })

    # ---------- 输出 JSON ----------

    data = {
        "updated": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(),
        "boards": boards,
    }

    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "mil.json",
    )
    temp_path = output_path + ".tmp"

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # 原子替换，避免读取到半截 JSON
    os.replace(temp_path, output_path)

    total = sum(
        len(board["items"]) for board in boards
    )

    print("=" * 50)
    print(f"[完成] 军事频道生成 {total} 条")
    print(f"[完成] 多源报道 {len(headlines)} 条")
    print(f"[完成] JSON 路径：{output_path}")

    for board in boards:
        print(
            f'  {board["name"]}: '
            f'{len(board["items"])} 条'
        )

    if not pool:
        print(
            "[警告] 没有获得可用的已分级新闻。"
            "请检查上方 RSS 状态、网络和来源分级统计。"
        )

    if dropped:
        print("[来源待识别统计]")
        for source, count in dropped.most_common(15):
            print(f"  {source}: {count}")


if __name__ == "__main__":
    main()
