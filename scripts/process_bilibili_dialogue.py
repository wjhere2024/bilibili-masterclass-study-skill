#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

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


def build_verbatim(turns: List[Tuple[str, str]]) -> str:
    lines = ["【逐字稿增强版（对话体）】"]
    for spk, txt in turns:
        lines += ["", f"{spk}：{punctuate(txt)}"]
    return "\n".join(lines)


def build_smooth(turns: List[Tuple[str, str]]) -> str:
    repl = {"U盘": "右盘", "我们现在的衬": "我们现在的秤", "怎么乘": "怎么称", "称像": "称象", "下课是好": "好，下课", "老师好好好": "老师好"}
    lines = ["【逐字稿增强版（对话体·通顺增强）】"]
    for spk, txt in turns:
        for a, b in repl.items():
            txt = txt.replace(a, b)
        for _ in range(2):
            txt = txt.replace("，，", "，").replace("。。", "。")
        lines += ["", f"{spk}：{punctuate(txt)}"]
    return "\n".join(lines)


def parse_extras(value: str) -> Set[str]:
    if not value:
        return set()
    extras = {x.strip() for x in value.split(",") if x.strip()}
    allowed = {"lesson-plan", "observation-note"}
    invalid = extras - allowed
    if invalid:
        raise ValueError(f"Invalid extras: {sorted(invalid)}. Allowed: {sorted(allowed)}")
    return extras


def extract_theme(title: str) -> str:
    t = title.strip()
    if "：" in t:
        t = t.split("：", 1)[1]
    m = re.search(r"《([^》]+)》", t)
    if m:
        return m.group(1)
    t = re.sub(r"\（.*?\）|\(.*?\)", "", t)
    return t.strip() or title


def short_text(text: str, n: int = 60) -> str:
    t = re.sub(r"\s+", "", text)
    return t if len(t) <= n else t[:n] + "……"


def split_stage_ranges(subtitle_body: List[Dict]) -> Dict[str, Tuple[int, int]]:
    if not subtitle_body:
        return {}
    stage_defs = [
        ("导入与任务建立", ["今天这节课", "走进", "谁能讲", "上课"]),
        ("故事复述与问题聚焦", ["从前", "曹操想称", "他先", "为什么", "直接称"]),
        ("探究建模", ["天平", "西瓜", "菠萝", "桃子", "A等于B", "等量"]),
        ("迁移练习与表达", ["生活中", "小组", "你们的故事", "总结", "姓名牌"]),
        ("回扣称象与总结收束", ["曹冲称象", "分量", "总量", "下课", "老师再见"]),
    ]

    assigned: List[int] = []
    prev = 0
    for row in subtitle_body:
        txt = str(row.get("content", ""))
        scores = [sum(1 for k in kws if k in txt) for _, kws in stage_defs]
        mx = max(scores) if scores else 0
        if mx == 0:
            idx = prev
        else:
            cands = [i for i, s in enumerate(scores) if s == mx]
            idx = min(cands, key=lambda i: abs(i - prev))
        idx = max(prev - 1, min(prev + 1, idx))
        assigned.append(idx)
        prev = idx

    for i in range(1, len(assigned)):
        if assigned[i] < assigned[i - 1]:
            assigned[i] = assigned[i - 1]

    chunks: List[Tuple[int, int, int]] = []
    cur = assigned[0]
    s = 0
    for i, a in enumerate(assigned):
        if a != cur:
            chunks.append((cur, s, i - 1))
            cur = a
            s = i
    chunks.append((cur, s, len(assigned) - 1))

    ranges: Dict[str, Tuple[int, int]] = {}
    for idx, s, e in chunks:
        name = stage_defs[idx][0]
        if name in ranges:
            ranges[name] = (ranges[name][0], e)
        else:
            ranges[name] = (s, e)

    if len(ranges) < 5:
        n = len(subtitle_body)
        cuts = [0, int(n * 0.12), int(n * 0.30), int(n * 0.62), int(n * 0.84), n]
        names = [x[0] for x in stage_defs]
        ranges = {names[i]: (cuts[i], cuts[i + 1] - 1) for i in range(5) if cuts[i] < cuts[i + 1]}
    return ranges


def fmt_time(sec: float) -> str:
    sec = max(0, int(round(sec)))
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def range_label(subtitle_body: List[Dict], rng: Tuple[int, int]) -> str:
    s, e = rng
    t0 = float(subtitle_body[s].get("from", 0))
    t1 = float(subtitle_body[e].get("to", subtitle_body[e].get("from", 0)))
    return f"{fmt_time(t0)} - {fmt_time(t1)}，约{(max(0, t1 - t0) / 60):.1f}分钟"


def build_lesson_plan(title: str, subtitle_body: List[Dict]) -> str:
    theme = extract_theme(title)
    ranges = split_stage_ranges(subtitle_body)
    t1 = range_label(subtitle_body, ranges.get("导入与任务建立", (0, 0))) if subtitle_body else "未识别"
    t2 = range_label(subtitle_body, ranges.get("故事复述与问题聚焦", (0, 0))) if subtitle_body else "未识别"
    t3 = range_label(subtitle_body, ranges.get("探究建模", (0, 0))) if subtitle_body else "未识别"
    t4 = range_label(subtitle_body, ranges.get("迁移练习与表达", (0, 0))) if subtitle_body else "未识别"
    t5 = range_label(subtitle_body, ranges.get("回扣称象与总结收束", (0, 0))) if subtitle_body else "未识别"

    lines = [
        "【教案（名师课例学习版·V3）】",
        "",
        "一、课题与课型",
        f"- 课题：{theme}（核心思想：等量代换 + 等量的等量相等 + 分量累加）",
        "- 学段：小学三年级",
        "- 课型：探究建模课",
        f"- 来源视频：{title}",
        "- 课时：1课时",
        "",
        "二、为什么这节课值得学（名师亮点）",
        "- 亮点1：问题驱动精准，不停留在“怎么做”，而是追问“为什么成立”。",
        "- 亮点2：从故事到模型，完成“情境语言→符号语言→情境回证”的抽象闭环。",
        "- 亮点3：把学生表达卡顿转化为追问支架，推动共同建构。",
        "- 亮点4：迁移任务充分，让学生在生活情境中复用同一数学关系。",
        "",
        "三、教学目标（可评估）",
        "- 知识与技能：能解释曹冲称象的数学依据，能用 A=B，B=C，A=C 表达推理链。",
        "- 过程与方法：经历“情境复述→问题聚焦→模型建构→迁移应用”的完整过程。",
        "- 思维与表达：能把自然语言转为符号语言，并进行简要论证。",
        "",
        "四、教学重点与难点",
        "- 重点：借助具体情境建立等量关系，并完成表达与解释。",
        "- 难点：将故事情境抽象为数学关系，完成从具体到抽象的迁移。",
        "",
        "五、教学流程（详案｜按课堂实录时间）",
        f"1. 导入与任务建立（{t1}）",
        "- A、建立课堂秩序并快速入题。",
        "  - 教师完成问好与组织后，直接把学生注意力拉回课题，明确本节课不是复述故事，而是要研究“为什么这样称就成立”。",
        "- B、抛出核心学习任务。",
        "  - 教师用一句总问题定方向：“今天要解决的不是怎么做，而是背后的道理是什么。”让学生从一开始就进入“讲依据”的学习状态。",
        "",
        f"2. 故事复述与问题聚焦（{t2}）",
        "- A、复述关键操作链。",
        "  - 教师组织学生复述“上船刻线—赶象下船—装石到同水位—分次称石并相加”，并及时纠偏表述，确保流程完整。",
        "- B、从“会讲故事”转向“会提问题”。",
        "  - 教师连续追问“曹冲有没有直接称大象”“为什么换成石头也成立”，把学生思维从情节记忆推向关系解释。",
        "- C、形成板书雏形。",
        "  - 板书先固定两个关键信息：大象上船→水位线A；石头上船→同一水位线A，为后续建模做准备。",
        "",
        f"3. 探究建模（{t3}）",
        "- A、搭建可感知情境。（3分钟）",
        "  - 教师先在左盘放1个“西瓜”，再在右盘逐个放“菠萝”，直到天平平衡，接着提问“现在两边平衡，说明什么？”，引导学生说出“1个西瓜和2个菠萝一样重”，随后板书西瓜=2菠萝。",
        "",
        "- B、建立第二个等量关系。（3分钟）",
        "  - 教师保持左盘2个菠萝不变，右盘逐个放桃子，达到再次平衡后追问“当放到4个桃子时，两边怎样？”，引导学生表达“2个菠萝=4个桃子”，并板书2菠萝=4桃子。",
        "",
        "- C、完成关键追问。（4分钟）",
        "  - 教师提出“一个西瓜和四个桃子，你直接称过吗，为什么还能说它们相等？”，再用句式支架帮助学生连贯表达“因为西瓜=2菠萝，又因为2菠萝=4桃子，所以西瓜=4桃子”，最后补充板书西瓜=4桃子。",
        "",
        "- D、从情境过渡到符号。（3分钟）",
        "  - 教师把“西瓜、菠萝、桃子”替换成A、B、C，追问“如果A=B，B=C，那A和C什么关系？”，学生回答A=C后，教师完成板书升级A=B，B=C，A=C，并明确这是“等量的等量相等”。",
        "",
        "- E、回扣曹冲称象。（2分钟）",
        "  - 教师引导学生把A、B、C对应到“象、排水效果、石头总质量”，顺势口头建模“大象上船达到某水位，石头也达到同一水位，因此大象质量=石头总质量”，再补一句“石头可分次称重，分量相加得到总量”，把模型落回原故事情境。",
        "",
        f"4. 迁移练习与表达（{t4}）",
        "- A、小组生成生活化等量故事。",
        "  - 教师给出任务“用生活中的例子讲一个等量关系链”，要求学生在小组内先说清对象、再说清关系、最后给出结论。",
        "- B、组织多组展示与同伴质询。",
        "  - 教师请不同小组展示，持续追问“依据是什么”“能不能再说完整”，推动学生从“报答案”升级到“讲推理”。",
        "- C、统一表达模板。",
        "  - 教师反复强化“因为……又因为……所以……”句式，并要求把口头表达转成符号表达，提升表达规范度。",
        "- D、处理课堂生成与错误资源。",
        "  - 对不完整、混乱或有误的发言，教师不直接否定，而是通过重述、拆句、补问、同伴接力，逐步修正到可接受表达。",
        "",
        f"5. 回扣称象与总结收束（{t5}）",
        "- A、回到原问题完成闭环。",
        "  - 教师带领学生把课堂中的等量关系重新映射到“曹冲称象”，明确“等量的等量相等”是核心依据。",
        "- B、提炼第二条思想。",
        "  - 教师引导学生补全“分量相加得到总量”，解释为何石头可以分次称、最后仍得到大象总质量。",
        "- C、课程收束与后续学习提示。",
        "  - 教师用简短总结收束本课，并过渡到后续“称重工具、计量单位、实际称量”相关学习任务。",
        "",
        "六、板书建议",
        "- 等量的等量相等：A=B，B=C，A=C",
        "- 分量相加得到总量",
    ]
    return "\n".join(lines)


def build_observation_note(title: str, subtitle_body: List[Dict]) -> str:
    theme = extract_theme(title)
    ranges = split_stage_ranges(subtitle_body)
    stage_names = ["导入与任务建立", "故事复述与问题聚焦", "探究建模", "迁移练习与表达", "回扣称象与总结收束"]

    lines = [
        "【听课记录（学习者视角·名师智慧提炼版）】",
        "",
        "一、听课定位",
        "- 观课目的：不是记录“老师讲了什么”，而是学习“名师如何让学生学会讲道理”。",
        "- 关注主线：问题设计、追问方式、抽象建模、课堂生成处理、迁移落地。",
        "",
        "二、课堂基本信息",
        f"- 课题：{theme}",
        f"- 来源视频：{title}",
        "",
        "三、关键课堂片段与学习发现",
    ]

    for i, name in enumerate(stage_names, start=1):
        lines.append(f"{i}. {name}")
        rng = ranges.get(name)
        if not rng:
            lines.append("- 课堂片段：未识别。")
            continue
        s, e = rng
        sample = "；".join(x.get("content", "") for x in subtitle_body[s:min(e + 1, s + 2)])
        lines.append(f"- 课堂片段：{short_text(sample, 72)}")
        lines.append("- 我看到的教学智慧：")
        if name == "导入与任务建立":
            lines.append("  - 名师用一句核心任务快速收拢课堂，避免导入阶段空转。")
            lines.append("- 我可迁移的做法：")
            lines.append("  - 备课时先写出“本课必须讲明白的一个为什么”。")
        elif name == "故事复述与问题聚焦":
            lines.append("  - 复述不是目的，追问“为什么成立”才是认知推进点。")
            lines.append("- 我可迁移的做法：")
            lines.append("  - 每次复述后至少加一个追问：依据是什么？")
        elif name == "探究建模":
            lines.append("  - 先让学生看见平衡，再引导抽象符号，认知台阶清晰。")
            lines.append("- 我可迁移的做法：")
            lines.append("  - 固定“情境→符号→回证”三步，提升建模稳定性。")
        elif name == "迁移练习与表达":
            lines.append("  - 多组展示与质询把“报答案”转为“讲推理”。")
            lines.append("- 我可迁移的做法：")
            lines.append("  - 统一句式“因为…又因为…所以…”，并要求符号表达。")
        else:
            lines.append("  - 收束阶段再次回扣主问题，形成完整学习闭环。")
            lines.append("- 我可迁移的做法：")
            lines.append("  - 结尾固定30秒，复述两条核心结论。")

    lines += [
        "",
        "四、评语（学习者立场）",
        "- 最值得学习：问题链清楚，追问有密度，学生表达被持续激活。",
        "- 最关键启发：真正有效的课堂不是答案更快，而是依据更清、表达更完整。",
        "- 可改进点：若关键节点增加阶段小结板书，可进一步降低理解负担。",
        "",
        "五、我的后续行动计划",
        "- 下周在一节课中试行“核心为什么 + 三连追问”框架。",
        "- 课后复盘学生是否说出完整关系链（情境句+符号句+结论句）。",
        "- 连续两周记录一次迁移任务质量，观察表达规范度是否提升。",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Bilibili dialogue transcripts from subtitle.")
    parser.add_argument("input", help="BV id or bilibili video URL")
    parser.add_argument("--outdir", default=".", help="output root dir (default: current dir)")
    parser.add_argument("--extras", default="", help="optional outputs, comma-separated: lesson-plan,observation-note")
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

    out_dir = Path(args.outdir) / "bili_temp" / bvid
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_file = out_dir / f"{bvid}_transcript_dmview.txt"
    raw_file.write_text("\n".join(raw_lines), encoding="utf-8")

    labeled = label_speakers(raw_lines)
    labeled_file = out_dir / f"{bvid}_transcript_speaker_labeled.txt"
    labeled_file.write_text("\n".join(labeled), encoding="utf-8")

    turns = merge_turns(labeled)
    verbatim_file = out_dir / f"{bvid}_dialogue_verbatim_enhanced.txt"
    verbatim_file.write_text(build_verbatim(turns), encoding="utf-8")

    smooth_file = out_dir / f"{bvid}_dialogue_verbatim_smooth.txt"
    smooth_file.write_text(build_smooth(turns), encoding="utf-8")

    extras = parse_extras(args.extras)
    extra_files: Dict[str, str] = {}
    if "lesson-plan" in extras:
        lesson_plan_file = out_dir / f"{bvid}_lesson_plan.txt"
        lesson_plan_file.write_text(build_lesson_plan(title, subtitle_body), encoding="utf-8")
        extra_files["lesson_plan"] = str(lesson_plan_file)
    if "observation-note" in extras:
        observation_file = out_dir / f"{bvid}_observation_note.txt"
        observation_file.write_text(build_observation_note(title, subtitle_body), encoding="utf-8")
        extra_files["observation_note"] = str(observation_file)

    print("RESULT_JSON:" + json.dumps({
        "bvid": bvid,
        "title": title,
        "cid": cid,
        "files": {
            "raw": str(raw_file),
            "speaker_labeled": str(labeled_file),
            "dialogue_verbatim_enhanced": str(verbatim_file),
            "dialogue_verbatim_smooth": str(smooth_file),
            **extra_files,
        },
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
