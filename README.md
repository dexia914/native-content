# 小红书动态选题软文生成器（Python + AI）

这个项目实现了你要的完整链路：

1. 输入**动态选题**（不是写死）。
2. AI 自动生成：标题 + 正文 + 标签 + 封面提示词。
3. 图片生成（支持 DALL-E 3 / Flux.1 的 OpenAI 兼容接口）。
4. 使用 Pillow/OpenCV 做二次视觉拼贴封面。
5. 使用 Playwright 自动打开小红书创作中心并填充内容。

> 你后续可手动配置 DeepSeek / 通义千问等 API Key 与 Base URL，不需要改业务代码。

---

## 1) 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
cp .env.example .env
```

填写 `.env`：
- `LLM_*`：文本大模型（DeepSeek/Qwen）
- `IMAGE_*`：图片模型（DALL-E 3 / Flux.1）

### 生成一篇动态选题软文

```bash
softpost generate --topic "看短剧赚钱" --audience "宝妈,大学生" --core "玩一玩就能赚钱、看短剧赚钱"
```

输出在 `outputs/<时间戳_选题>/` 下：
- `raw.png`：AI 原图
- `cover.png`：拼贴后封面
- `post.md`：可直接发布的文案

### 自动分发到小红书（Playwright）

先准备登录态（一次性，手动导出 storage state 到 `.auth/xiaohongshu.json`），然后：

```bash
softpost publish --artifact-dir "outputs/20260101_120000_看短剧赚钱"
```

> 注意：小红书页面结构经常变化，`app/distribution/xiaohongshu.py` 里的选择器可按页面更新。

---

## 2) 给你的示例文案（可直接用）

**标题示例：**

`我在带娃空档刷短剧，顺手把奶粉钱刷出来了`  

**正文示例：**

以前我以为“网赚”都很复杂，要剪辑、要拉人，
直到最近试了一个偏轻量的平台：碎片时间看短剧+做基础互动任务。

我主要是孩子睡着后、做饭前后那几十分钟做，
大学生朋友则是在课间和晚上回宿舍后做。

核心感受就三点：
第一是门槛低，不需要设备和复杂技能；
第二是时间很自由，十几分钟也能做；
第三是收益反馈比较快，做完当日就能看到记录。

如果你是想找“不会占用主业/学业”的补贴方式，
这种玩法比盲目刷信息流更容易坚持。

**风险提示：任何平台收益都会受任务量、活跃度和规则变化影响，
请理性看待，不要把它当作稳定工资。**

我把自己踩过的坑和更省时的操作整理好了，
想看完整版流程可以留言“短剧”。

#宝妈副业 #大学生副业 #看短剧赚钱 #碎片时间赚钱 #新手副业 #线上兼职 #副业思路 #轻创业

---

## 3) 架构说明

- `app/ai/llm.py`: OpenAI 兼容聊天接口，动态生成 JSON 文案。
- `app/ai/image.py`: OpenAI 兼容图片接口，生成封面图。
- `app/content/collage.py`: Pillow/OpenCV 做视觉拼贴。
- `app/content/generator.py`: 一键串联生成流程。
- `app/distribution/xiaohongshu.py`: Playwright 自动填充发布页面。
- `app/cli.py`: 命令行入口（generate / publish）。

---

## 4) 你后续可扩展

1. 新增多个文案风格模板（宝妈纪实 / 学生测评 / 清单体）。
2. 增加 A/B 标题一次生成 5 组并自动评分。
3. 接入定时发布队列（cron + sqlite）。
4. 保存发布结果到日志（成功率、发布时间、转化回写）。
