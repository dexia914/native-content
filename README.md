# 小红书动态选题软文生成器（Python + AI）

这个项目实现了你要的完整链路：

1. 输入**动态选题**（不是写死）。
2. AI 自动生成：标题 + 正文 + 标签 + 封面提示词。
3. 图片生成（支持通义万相；也可切回 DALL-E 3 / Flux.1）。
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
cp .env .env
```

填写 `.env`：
- `LLM_*`：文本大模型（DeepSeek/Qwen）
- `IMAGE_*`：图片模型（默认已切到通义万相）
- `NO_TEXT_IN_IMAGE`：是否强制图片底图不生成任何文字，默认 `true`
- `FONT_PATH`：可选。若系统缺少中文字体，可手动指定字体文件路径

Linux/Ubuntu 说明：
- Ubuntu 24 不等于一定是纯 headless，但云服务器场景通常是 headless 环境
- `softpost generate` 在 Ubuntu 上通常可运行，但建议安装中文字体；若未安装，封面中文可能显示异常
- 当前代码已自动适配 Windows 和 Ubuntu 常见中文字体路径
- 若仍找不到合适字体，请在 `.env` 中显式设置 `FONT_PATH`
- `softpost publish` 在 Ubuntu 上也可以运行，但若服务器没有桌面环境，`softpost auth` 这类需要人工登录的步骤通常要借助图形界面、远程桌面或虚拟显示

Ubuntu 24 一键初始化：

```bash
chmod +x scripts/bootstrap_ubuntu.sh
./scripts/bootstrap_ubuntu.sh
```

这个脚本会：
- 安装 Python 虚拟环境工具
- 安装 Playwright/Chromium 常见系统依赖
- 安装中文字体 `fonts-noto-cjk` 和 `fonts-wqy-zenhei`
- 创建 `.venv`
- 安装项目 Python 依赖
- 安装 Playwright Chromium 浏览器

如果你在纯 headless Ubuntu 上只跑内容生成，通常重点验证：
- `softpost generate`
- 中文字体是否正常渲染

如果你在 Ubuntu 上还要跑小红书自动发布，建议额外确认：
- Chromium 能正常启动
- 登录步骤可完成
- 目标环境具备图形界面、远程桌面或虚拟显示能力

### 生成一篇动态选题软文

```bash
softpost generate --topic "看短剧赚钱" --audience "宝妈,大学生" --core "玩一玩就能赚钱、看短剧赚钱"
```

参数说明：

- `--topic`：这篇内容的核心选题，也就是你想让 AI 围绕什么话题生成软文。
  例如：`看短剧赚钱`、`居家副业`、`学生党零成本赚钱`
  它会直接影响标题、正文角度、封面主题和标签方向。

- `--audience`：目标受众，告诉 AI 这篇内容主要写给谁看。
  支持填写一个或多个群体，多个对象建议用英文逗号分隔。
  例如：`宝妈`、`大学生`、`宝妈,大学生`
  它会影响文案语气、场景描述、利益点和封面人群形象。

- `--core`：核心卖点，也就是你最想强调的价值点、吸引点或转化点。
  例如：`玩一玩就能赚钱、看短剧赚钱`、`不耽误带娃、碎片时间可做`
  它会影响正文重点、标题措辞和 CTA 方向。

推荐理解方式：

- `topic` 决定“写什么”
- `audience` 决定“写给谁”
- `core` 决定“重点突出什么”

示例：

```bash
softpost generate --topic "居家手工副业" --audience "宝妈" --core "不出门也能做、带娃空档可操作"
```

```bash
softpost generate --topic "宿舍副业" --audience "大学生" --core "低门槛、零碎时间可做、赚生活费"
```

输出在 `outputs/<时间戳_选题>/` 下：
- `raw.png`：AI 原图
- `cover.png`：拼贴后封面
- `post.md`：可直接发布的文案

### 自动分发到小红书（Playwright）

先准备登录态（一次性）：

```bash
softpost auth
```

浏览器会打开小红书创作中心。完成登录后，回到终端按回车，会自动导出 `.auth/xiaohongshu.json`。

检查登录态剩余有效期：

```bash
softpost auth-status
```

这个命令会读取 `.auth/xiaohongshu.json` 里的关键登录 cookie，提示：
- 当前登录态文件路径
- 关键 cookie 数量
- 最早到期的 cookie 名称
- 最早到期时间（UTC）
- 剩余天数
- 当前状态：`ok` / `expiring_soon` / `expired`

建议：
- `ok`：可继续使用
- `expiring_soon`：建议重新执行 `softpost auth`
- `expired`：需要重新登录并导出登录态

然后：

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
- `app/distribution/xiaohongshu.py`: Playwright 登录态导出、登录态体检与自动填充发布页面。
- `app/cli.py`: 命令行入口（generate / auth / auth-status / publish）。

---

## 4) 你后续可扩展

1. 新增多个文案风格模板（宝妈纪实 / 学生测评 / 清单体）。
2. 增加 A/B 标题一次生成 5 组并自动评分。
3. 接入定时发布队列（cron + sqlite）。
4. 保存发布结果到日志（成功率、发布时间、转化回写）。
