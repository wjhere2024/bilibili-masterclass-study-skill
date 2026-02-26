---
name: bilibili-dialogue-transcript
description: B站（Bilibili）名师视频学习技能。Extract Bilibili subtitles from a BV id or URL, generate dialogue-form transcripts, and optionally produce a V3 lesson plan and learner-perspective observation notes. This skill should be used when users need classroom-style transcript processing and teaching-document outputs.
---

# B站（Bilibili）名师视频学习技能

## Overview
Convert a Bilibili video to structured text outputs for teaching scenarios. Generate base transcript files first, then optionally generate `教案（V3）` and `听课记录（学习者视角）`.

## When To Use
Use this skill when the request includes one of these goals:
- Convert Bilibili BV/URL into text.
- Convert subtitle lines into dialogue format (`老师/学生/全班`).
- Produce `逐字稿增强` or `通顺增强` dialogue text.
- Optionally produce teaching documents (`教案`, `听课记录`).

## Workflow

### 1. Run the script
Run:

```bash
python scripts/process_bilibili_dialogue.py <BV_ID_OR_URL> --outdir <workspace_root>
```

### 2. Optional document outputs
To generate extra documents, add `--extras`:

```bash
python scripts/process_bilibili_dialogue.py <BV_ID_OR_URL> --outdir <workspace_root> --extras lesson-plan,observation-note
```

Supported extras:
- `lesson-plan`: output V3 style lesson plan, with stage timing directly from subtitle timeline.
- `observation-note`: output learner-perspective notes with teaching insights and actionable takeaways (without timeline lines).

### 3. Return generated file paths
Read `RESULT_JSON` and return output paths.

Base output files:
- `bili_temp/<BV_ID>/<BV_ID>_transcript_dmview.txt`
- `bili_temp/<BV_ID>/<BV_ID>_transcript_speaker_labeled.txt`
- `bili_temp/<BV_ID>/<BV_ID>_dialogue_verbatim_enhanced.txt`
- `bili_temp/<BV_ID>/<BV_ID>_dialogue_verbatim_smooth.txt`

Optional output files:
- `bili_temp/<BV_ID>/<BV_ID>_lesson_plan.txt`
- `bili_temp/<BV_ID>/<BV_ID>_observation_note.txt`

## Output Semantics
- Speaker labeling is heuristic and may have minor misclassification.
- `verbatim_enhanced` preserves source wording as much as possible.
- `verbatim_smooth` improves readability with light corrections.
- `lesson_plan` uses process-first structure and stage time labels from subtitle timeline.
- `observation_note` uses learner viewpoint, extracts teaching wisdom, and gives practical migration actions (time ranges omitted for cleaner reading).

## Notes
- Subtitle source uses `x/v2/dm/view` for better consistency.
- If subtitle is missing, return a clear error and ask for another video.
- Keep original files; write new derived files instead of overwriting user-edited files.
