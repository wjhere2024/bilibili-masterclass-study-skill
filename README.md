# B站（Bilibili）名师视频学习技能

用于将 B 站名师视频转成可教学使用的结构化文本。

## 功能
- 脚本生成 `原始字幕`（带时间戳）
- 脚本生成 `通顺增强对话稿`（规则法说话人标注）
- LLM 基于对话稿生成 `教案`
- LLM 基于对话稿生成 `听课记录（学习者视角）`
- （可选）LLM 二次优化对话稿中的发言人归属与连贯性

## 目录结构
- `SKILL.md`：技能流程与执行规范
- `agents/openai.yaml`：展示与默认提示词配置
- `scripts/process_bilibili_dialogue.py`：字幕抓取与初版对话稿生成脚本

## 环境要求
- Python 3.10+
- `requests`

安装依赖：

```bash
pip install requests
```

## 使用方式
### 1. 运行脚本生成基础文件

```bash
python scripts/process_bilibili_dialogue.py "<BV号或B站链接>" --outdir .
```

### 2. 查看脚本输出
脚本会打印：

```text
RESULT_JSON:{"bvid":...,"title":...,"cid":...,"base_name":...,"files":{"raw_subtitle":"...","dialogue_verbatim_smooth":"..."}}
```

## 输出文件
脚本会在 `bili_temp/<base_name>/` 下生成：

- `<base_name>原始字幕.txt`
- `<base_name>通顺增强对话稿.txt`

随后由 LLM 生成：

- `<base_name>教案.md`
- `<base_name>听课记录.md`

可选（用户明确要求时）：

- `<base_name>对话稿（优化版）.md`

## 说明
- 说话人标注采用规则推断，可能存在误判。
- 若需更高准确度，请执行 LLM 对话优化步骤（发言人二次判定）。
- 字幕来源接口为 B 站 `x/v2/dm/view`。
- 详细流程以 `SKILL.md` 为准。

## GitHub 发布建议

```bash
git init
git add .
git commit -m "feat: add bilibili masterclass study skill"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```
