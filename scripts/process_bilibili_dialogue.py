#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
COOKIE_FILE = os.path.expanduser("~/.openclaw/workspace/bilibili_cookie.txt")


def parse_bvid(value: str) -> str:
    m = re.search(r"BV[0-9A-Za-z]{10}", value.strip())
    if m:
        return m.group(0)
    raise ValueError("Cannot find BV id from input. Provide BV id or bilibili video URL.")


def load_cookie() -> str:
    if os.path.exists(COOKIE_FILE):
        return Path(COOKIE_FILE).read_text(encoding="utf-8").strip()
    return ""


def http_json(url: str, *, params: Dict = None, cookie: str = "") -> Dict:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com/"}
    if cookie:
        headers["Cookie"] = cookie
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_video_info(bvid: str, cookie: str) -> Dict:
    data = http_json("https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid}, cookie=cookie)
    if data.get("code") != 0:
        raise RuntimeError(f"view api failed: code={data.get('code')} msg={data.get('message')}")
    return data["data"]


def get_subtitle_url(cid: int, cookie: str) -> str:
    data = http_json("https://api.bilibili.com/x/v2/dm/view", params={"oid": cid, "type": 1}, cookie=cookie)
    if data.get("code") != 0:
        raise RuntimeError(f"dm/view api failed: code={data.get('code')} msg={data.get('message')}")
    subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
    if not subtitles:
        raise RuntimeError("No subtitle found for this video.")
    target = next((s for s in subtitles if "zh" in str(s.get("lan", ""))), subtitles[0])
    subtitle_url = target.get("subtitle_url", "")
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url
    if not subtitle_url:
        raise RuntimeError("Subtitle URL is empty.")
    return subtitle_url


def fetch_subtitle_body(subtitle_url: str) -> List[Dict]:
    data = requests.get(subtitle_url, timeout=20).json()
    return [x for x in data.get("body", []) if str(x.get("content", "")).strip()]


def label_speakers(lines: List[str]) -> List[str]:
    teacher_cues = ["同学们", "今天这节课", "我们一起", "我请", "开始吧", "大点声音", "谁能", "谁来", "为什么", "对不对", "下课"]
    class_cues = ["老师好", "老师再见", "同意吗", "大家一起说"]
    question_cues = ["吗", "呢", "谁", "为什么", "怎么", "有没有"]

    out: List[str] = []
    mode = "老师"
    expect_student = False

    for line in lines:
        if any(k in line for k in class_cues):
            spk = "全班"
            expect_student = False
        elif any(k in line for k in teacher_cues):
            spk = "老师"
        elif expect_student:
            spk = "学生"
        else:
            spk = mode

        if spk == "老师" and (line.endswith("吗") or line.endswith("呢") or any(k in line for k in question_cues)):
            expect_student = True
        elif spk in ("学生", "全班"):
            expect_student = False

        if spk in ("老师", "学生"):
            # 只有明确判断为老师或学生时才更新 mode；
            # 当 spk == "全班" 时有意保留 mode 不变，
            # 以便全班发言后续若无明显线索仍延续上一个明确说话人。
            mode = spk

        out.append(f"{spk}：{line}")
    return out


def merge_turns(labeled: List[str]) -> List[Tuple[str, str]]:
    turns: List[Tuple[str, str]] = []
    for line in labeled:
        if "：" not in line:
            continue
        spk, txt = line.split("：", 1)
        spk = spk.strip()
        txt = txt.strip()
        if not txt:
            continue
        if turns and turns[-1][0] == spk:
            turns[-1] = (spk, turns[-1][1] + "，" + txt)
        else:
            turns.append((spk, txt))
    return turns


def punctuate(text: str) -> str:
    text = re.sub(r"[，]{2,}", "，", text).strip("，。？！；、 ")
    if not text:
        return ""
    q_cues = ["吗", "呢", "为什么", "怎么", "谁", "有没有", "对不对", "是不是"]
    if any(c in text for c in q_cues) or text.endswith(("吗", "呢")):
        return text + "？"
    return text + "。"


def build_smooth(turns: List[Tuple[str, str]]) -> str:
    lines = ["【逐字稿增强版（对话体·通顺增强）】"]
    for spk, txt in turns:
        for _ in range(2):
            txt = txt.replace("，，", "，").replace("。。", "。")
        lines += ["", f"{spk}：{punctuate(txt)}"]
    return "\n".join(lines)


def extract_theme(title: str) -> str:
    t = title.strip()
    if "：" in t:
        t = t.split("：", 1)[1]
    m = re.search(r"《([^》]+)》", t)
    if m:
        return m.group(1)
    t = re.sub(r"\（.*?\）|\(.*?\)", "", t)
    return t.strip() or title


def build_product_base_name(title: str) -> str:
    author = ""
    theme = extract_theme(title).replace("的故事", "").strip()
    if "：" in title:
        author = title.split("：", 1)[0]
    author = re.sub(r"^\d+[.\s]*", "", author).strip()
    base = (author + theme).strip() or "名师课堂"
    base = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", base)
    return base or "名师课堂"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Bilibili subtitle and generate smooth dialogue transcript.")
    parser.add_argument("input", help="BV id or bilibili video URL")
    parser.add_argument("--outdir", default=".", help="output root dir (default: current dir)")
    args = parser.parse_args()

    bvid = parse_bvid(args.input)
    cookie = load_cookie()

    info = get_video_info(bvid, cookie)
    title = info.get("title", bvid)
    pages = info.get("pages", [])
    if not pages:
        raise RuntimeError("No pages found.")

    cid = pages[0]["cid"]
    subtitle_url = get_subtitle_url(cid, cookie)
    subtitle_body = fetch_subtitle_body(subtitle_url)
    raw_lines = [str(x.get("content", "")).strip() for x in subtitle_body if str(x.get("content", "")).strip()]
    if not raw_lines:
        raise RuntimeError("Subtitle body is empty.")

    base_name_for_dir = build_product_base_name(title)
    out_dir = Path(args.outdir) / "bili_temp" / base_name_for_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # 输出原始字幕（带时间戳、无说话人标注），供 Claude 优化对话稿时参照
    raw_subtitle_file = out_dir / f"{base_name_for_dir}原始字幕.txt"
    raw_subtitle_lines = []
    for item in subtitle_body:
        f = item.get("from", 0)
        t = item.get("to", 0)
        content = str(item.get("content", "")).strip()
        if content:
            fm, fs = int(f) // 60, int(f) % 60
            tm, ts = int(t) // 60, int(t) % 60
            raw_subtitle_lines.append(f"[{fm:02d}:{fs:02d}-{tm:02d}:{ts:02d}] {content}")
    raw_subtitle_file.write_text("\n".join(raw_subtitle_lines), encoding="utf-8")

    labeled = label_speakers(raw_lines)
    turns = merge_turns(labeled)
    base_name = base_name_for_dir

    smooth_file = out_dir / f"{base_name}通顺增强对话稿.txt"
    smooth_file.write_text(build_smooth(turns), encoding="utf-8")

    print("RESULT_JSON:" + json.dumps({
        "bvid": bvid,
        "title": title,
        "cid": cid,
        "base_name": base_name,
        "files": {
            "raw_subtitle": str(raw_subtitle_file),
            "dialogue_verbatim_smooth": str(smooth_file),
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
