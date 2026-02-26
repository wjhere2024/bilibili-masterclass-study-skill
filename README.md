# B站（Bilibili）名师视频学习技能

用于将 B 站名师视频自动转成可教学使用的结构化文本。

## 功能
- 生成通顺增强版对话稿
- 生成教案（含课堂实录时段）
- 生成听课记录（学习者视角，含教学智慧与可迁移做法）

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
### 生成三个成品（固定输出）

```bash
python scripts/process_bilibili_dialogue.py "<BV号或B站链接>" --outdir .
```

## 输出文件
脚本会在 `bili_temp/<BV_ID>/` 下生成（中文文件名）：

- `<视频标题提炼名>通顺增强对话稿.txt`
- `<视频标题提炼名>教案.md`
- `<视频标题提炼名>听课记录.md`

示例：
- `吴正宪曹冲称象通顺增强对话稿.txt`
- `吴正宪曹冲称象教案.md`
- `吴正宪曹冲称象听课记录.md`

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
