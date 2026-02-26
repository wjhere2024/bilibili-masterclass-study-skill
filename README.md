# B站（Bilibili）名师视频学习技能

用于将 B 站名师视频自动转成可教学使用的结构化文本。

## 功能
- 提取视频字幕（原始文本）
- 生成说话人标注稿（老师/学生/全班）
- 生成逐字稿增强版、通顺增强版对话稿
- 可选生成：
  - 教案（V3，含课堂实录时段）
  - 听课记录（学习者视角，含教学智慧与可迁移做法）

## 目录结构
- `SKILL.md`：技能说明
- `agents/openai.yaml`：展示与默认提示词配置
- `scripts/process_bilibili_dialogue.py`：主脚本

## 环境要求
- Python 3.10+
- `requests`

安装依赖：

```bash
pip install requests
```

## 使用方式
### 1) 基础输出（字幕 + 对话稿）

```bash
python scripts/process_bilibili_dialogue.py "<BV号或B站链接>" --outdir .
```

### 2) 额外生成教案与听课记录

```bash
python scripts/process_bilibili_dialogue.py "<BV号或B站链接>" --outdir . --extras lesson-plan,observation-note
```

## 输出文件
脚本会在 `bili_temp/<BV_ID>/` 下生成：

- `<BV_ID>_transcript_dmview.txt`
- `<BV_ID>_transcript_speaker_labeled.txt`
- `<BV_ID>_dialogue_verbatim_enhanced.txt`
- `<BV_ID>_dialogue_verbatim_smooth.txt`
- `<BV_ID>_lesson_plan.txt`（可选）
- `<BV_ID>_observation_note.txt`（可选）

## 说明
- 说话人标注采用规则推断，可能存在少量误判。
- 教案与听课记录为自动生成草稿，建议结合教学场景二次编辑。
- 字幕来源接口为 B 站 `x/v2/dm/view`。

## GitHub 发布建议
1. 初始化仓库并提交
2. 配置远程仓库地址
3. 推送到 `main`

示例：

```bash
git init
git add .
git commit -m "feat: add bilibili masterclass study skill"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
