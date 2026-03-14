from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.account_state import build_profile_state_path, list_login_state_files, set_active_login_state_path
from app.content.generator import SoftPostPipeline
from app.distribution.xiaohongshu import export_login_state_to_sync, get_auth_status, publish_sync
from app.models import GeneratedAssets, SoftPost
from app.storage import ensure_storage_schema, list_recent_generated_posts
from app.web_logging import get_web_logger, read_recent_logs

app = FastAPI(title="Xiaohongshu SoftPost Service")
logger = get_web_logger()

outputs_dir = Path("outputs")
outputs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")


class GenerateRequest(BaseModel):
    topic: str
    audience: str = "宝妈,大学生"
    core: str = "玩一玩就能赚钱、看短剧赚钱"


class PublishRequest(BaseModel):
    artifact_dir: str
    auto_submit: bool = False


class SwitchAccountRequest(BaseModel):
    state_path: str


class AddAccountRequest(BaseModel):
    profile: str


def _load_generated_assets(folder: Path) -> GeneratedAssets:
    markdown = folder / "post.md"
    cover = folder / "cover.png"
    if not markdown.exists() or not cover.exists():
        raise FileNotFoundError("artifact_dir 下缺少 post.md 或 cover.png")

    lines = markdown.read_text(encoding="utf-8").splitlines()
    title = lines[0].replace("#", "").strip() if lines else ""
    content_lines = [line.strip() for line in lines[3:] if line.strip()]
    hashtags = [line for line in content_lines if line.startswith("#")]
    body = "\n".join(line for line in content_lines if not line.startswith("#")).strip()

    post = SoftPost(topic="", audience="", title=title, body=body, image_prompt="", hashtags=hashtags)
    return GeneratedAssets(post=post, raw_image_path=cover, collage_path=cover, markdown_path=markdown)


def _cover_url(cover_path: str) -> str:
    cover = Path(cover_path)
    try:
        relative = cover.relative_to(outputs_dir)
        return f"/outputs/{relative.as_posix()}"
    except ValueError:
        return ""


def _render_message(message: str = "", level: str = "info") -> str:
    if not message:
        return ""
    return (
        f'<div id="server-message" class="message {html.escape(level)}">'
        f"{html.escape(message)}</div>"
    )


def _artifact_card_html(
    *,
    title: str,
    artifact_dir: str,
    topic: str,
    audience: str,
    hashtags: list[str],
    cover_url: str,
    markdown_text: str,
    created_at: str,
) -> str:
    tags_text = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
    preview = (
        f'<img src="{html.escape(cover_url)}" alt="cover">'
        if cover_url
        else '<div class="artifact-missing">No cover</div>'
    )
    return f"""
    <article class="artifact-card">
      <div class="artifact-preview">
        {preview}
      </div>
      <div class="artifact-body">
        <h3>{html.escape(title)}</h3>
        <p class="artifact-meta">{html.escape(created_at)}</p>
        <p><code>{html.escape(artifact_dir)}</code></p>
        <p><strong>选题：</strong>{html.escape(topic)}</p>
        <p><strong>受众：</strong>{html.escape(audience)}</p>
        <p><strong>标签：</strong>{html.escape(tags_text)}</p>
        <details>
          <summary>查看 Markdown</summary>
          <pre>{html.escape(markdown_text)}</pre>
        </details>
      </div>
    </article>
    """


def _render_home(message: str = "", level: str = "info") -> str:
    try:
        auth_status = get_auth_status()
    except Exception as exc:
        auth_status = {"level": "unknown", "message": f"登录态状态未知: {exc}"}
        logger.exception("home | failed to load auth status")

    account_files = list_login_state_files()

    try:
        artifacts = list_recent_generated_posts()
        storage_message = ""
    except Exception as exc:
        artifacts = []
        storage_message = f"MySQL 读取失败: {exc}"
        logger.exception("home | failed to load recent generated posts")

    try:
        recent_logs = read_recent_logs()
    except Exception as exc:
        recent_logs = [f"读取日志失败: {exc}"]
        logger.exception("home | failed to read logs")

    artifacts_html: list[str] = []
    for artifact in artifacts:
        markdown_path = Path(artifact.markdown_path)
        markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
        artifacts_html.append(
            _artifact_card_html(
                title=artifact.title,
                artifact_dir=artifact.artifact_dir,
                topic=artifact.topic,
                audience=artifact.audience,
                hashtags=artifact.hashtags,
                cover_url=_cover_url(artifact.cover_path),
                markdown_text=markdown,
                created_at=artifact.created_at.isoformat(sep=" ", timespec="seconds"),
            )
        )

    logs_html = (
        "<pre>" + html.escape("\n".join(recent_logs)) + "</pre>"
        if recent_logs
        else '<p class="muted">暂无日志。</p>'
    )

    message_block = _render_message(message=message, level=level)
    if not message_block and storage_message:
        message_block = _render_message(message=storage_message, level="warning")

    artifact_list_html = "".join(artifacts_html) if artifacts_html else ""
    empty_state_style = "display:none;" if artifacts_html else ""
    account_options = "".join(
        f'<option value="{html.escape(item.path)}"{" selected" if item.is_active else ""}>'
        f'{html.escape(item.name)} · {html.escape(item.updated_at)}</option>'
        for item in account_files
    )
    account_empty = ""
    if not account_files:
        account_empty = '<p class="muted" style="margin:12px 0 0;">当前 `.auth` 目录下还没有登录态文件。</p>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>小红书动态选题软文生成器</title>
  <style>
    :root {{
      --bg: #f7efe8;
      --panel: #fffaf6;
      --ink: #22181c;
      --muted: #6e5a62;
      --brand: #dd4f75;
      --line: #e8d8dc;
      --ok-bg: #edf8ef;
      --ok-line: #b8dfbf;
      --warn-bg: #fff4df;
      --warn-line: #f0c88c;
      --info-bg: #eef4ff;
      --info-line: #bdd2ff;
      --overlay: rgba(34, 24, 28, .52);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(221,79,117,.18), transparent 32%),
        linear-gradient(180deg, #fff8f3 0%, var(--bg) 100%);
      color: var(--ink);
    }}
    .page {{
      width: min(1160px, calc(100vw - 32px));
      margin: 28px auto 60px;
    }}
    .hero {{
      padding: 28px;
      border-radius: 28px;
      background: linear-gradient(135deg, #fff4ef 0%, #fffdf9 58%, #fbe8ef 100%);
      border: 1px solid var(--line);
      box-shadow: 0 16px 48px rgba(55, 27, 36, .08);
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: 34px; }}
    .hero p {{ margin: 0; color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: 1.05fr .95fr;
      gap: 20px;
      margin-top: 20px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 22px;
      box-shadow: 0 12px 36px rgba(55, 27, 36, .05);
    }}
    h2 {{ margin: 0 0 16px; font-size: 20px; }}
    label {{
      display: block;
      margin: 0 0 14px;
      font-size: 14px;
      color: var(--muted);
    }}
    input, textarea {{
      width: 100%;
      margin-top: 6px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
      color: var(--ink);
    }}
    textarea {{ min-height: 96px; resize: vertical; }}
    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    button {{
      border: none;
      border-radius: 999px;
      padding: 12px 18px;
      background: var(--brand);
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      transition: transform .16s ease, opacity .16s ease;
    }}
    button:hover {{ transform: translateY(-1px); }}
    button:disabled {{
      cursor: not-allowed;
      opacity: .58;
      transform: none;
    }}
    button.secondary {{ background: #2a1f23; }}
    .message {{
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: #fff;
      line-height: 1.5;
    }}
    .message.success {{
      background: var(--ok-bg);
      border-color: var(--ok-line);
    }}
    .message.warning {{
      background: var(--warn-bg);
      border-color: var(--warn-line);
    }}
    .message.info {{
      background: var(--info-bg);
      border-color: var(--info-line);
    }}
    .message-title {{
      display: block;
      margin-bottom: 4px;
      font-weight: 700;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .meta-card {{
      padding: 14px;
      border-radius: 16px;
      background: #fff;
      border: 1px solid var(--line);
    }}
    .meta-card strong {{ display: block; margin-bottom: 4px; }}
    .muted {{ color: var(--muted); }}
    .result-card {{
      display: none;
      margin-top: 18px;
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    .result-card.active {{ display: block; }}
    .result-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 12px;
    }}
    .result-links a {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 600;
    }}
    .artifact-list {{
      display: grid;
      gap: 16px;
      margin-top: 18px;
    }}
    .artifact-card {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 16px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: #fff;
    }}
    .artifact-preview img {{
      width: 100%;
      border-radius: 16px;
      display: block;
      object-fit: cover;
    }}
    .artifact-meta {{
      color: var(--muted);
      font-size: 13px;
      margin: 6px 0;
    }}
    .artifact-missing {{
      height: 100%;
      min-height: 180px;
      display: grid;
      place-items: center;
      border-radius: 16px;
      background: #f3eaec;
      color: var(--muted);
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      background: #fbf5f6;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      font-size: 13px;
      max-height: 420px;
      overflow: auto;
    }}
    code {{
      font-family: Consolas, Monaco, monospace;
      background: #f8f1f3;
      padding: 2px 6px;
      border-radius: 8px;
    }}
    .overlay {{
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background: var(--overlay);
      backdrop-filter: blur(4px);
      z-index: 999;
    }}
    .overlay.active {{ display: flex; }}
    .overlay-card {{
      min-width: min(420px, calc(100vw - 40px));
      padding: 24px;
      border-radius: 24px;
      background: rgba(255, 250, 246, .98);
      border: 1px solid rgba(255,255,255,.35);
      box-shadow: 0 20px 60px rgba(0, 0, 0, .18);
      text-align: center;
    }}
    .spinner {{
      width: 52px;
      height: 52px;
      margin: 0 auto 16px;
      border-radius: 50%;
      border: 4px solid rgba(221,79,117,.18);
      border-top-color: var(--brand);
      animation: spin .8s linear infinite;
    }}
    .overlay-title {{ margin: 0 0 8px; font-size: 20px; }}
    .overlay-text {{ margin: 0; color: var(--muted); }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .artifact-card {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div id="busy-overlay" class="overlay" aria-hidden="true">
    <div class="overlay-card">
      <div class="spinner"></div>
      <h3 class="overlay-title" id="busy-title">处理中</h3>
      <p class="overlay-text" id="busy-text">请求正在执行，请不要重复点击。</p>
    </div>
  </div>
  <main class="page">
    <section class="hero">
      <h1>小红书动态选题软文生成器</h1>
      <p>FastAPI Web 控制台。会记录操作成功状态和错误信息，方便快速定位问题。</p>
      <div id="page-message">{message_block}</div>
    </section>
    <section class="grid">
      <div class="panel">
        <h2>生成软文</h2>
        <form id="generate-form">
          <label>选题
            <input name="topic" placeholder="例如：看短剧赚钱" required>
          </label>
          <label>受众
            <input name="audience" value="宝妈,大学生">
          </label>
          <label>核心卖点
            <textarea name="core">玩一玩就能赚钱、看短剧赚钱</textarea>
          </label>
          <div class="actions">
            <button type="submit">生成</button>
          </div>
        </form>
        <div id="generate-result" class="result-card"></div>
      </div>
      <div class="panel">
        <h2>发布与登录态</h2>
        <div class="meta">
          <div class="meta-card">
            <strong>登录态状态</strong>
            <span id="auth-level">{html.escape(str(auth_status.get("level", "unknown")))}</span>
          </div>
          <div class="meta-card">
            <strong>提示</strong>
            <span id="auth-message">{html.escape(str(auth_status.get("message", "")))}</span>
          </div>
        </div>
        <form id="account-form" style="margin-top:16px;">
          <label>当前小红书账号
            <select id="account-select" name="state_path" style="width:100%; margin-top:6px; padding:12px 14px; border-radius:14px; border:1px solid var(--line); background:#fff; font:inherit; color:var(--ink);" {"disabled" if not account_files else ""}>
              {account_options}
            </select>
          </label>
          <div class="actions">
            <button type="submit" {"disabled" if not account_files else ""}>切换账号</button>
          </div>
          {account_empty}
        </form>
        <div class="message info">
          <span class="message-title">新增账号</span>
          <div>可以直接在下面输入账号标识并点击“新增账号”，系统会拉起浏览器等待你完成登录，然后自动保存并切换到该账号。</div>
          <div>如果你更习惯终端，也可以执行 <code>softpost-cli auth --profile main</code>。</div>
        </div>
        <form id="add-account-form" style="margin-top:16px;">
          <label>新增账号标识
            <input name="profile" placeholder="例如：main、backup、brand-a" required>
          </label>
          <div class="actions">
            <button type="submit">新增账号</button>
          </div>
        </form>
        <form id="publish-form" style="margin-top:16px;">
          <label>产物目录
            <input name="artifact_dir" placeholder="例如：outputs/20260314_xxx" required>
          </label>
          <label style="display:flex; align-items:center; gap:10px; color:var(--ink);">
            <input type="checkbox" name="auto_submit" style="width:auto; margin:0;">
            自动点击发布
          </label>
          <div class="actions">
            <button type="submit" class="secondary">从目录发布</button>
            <button type="button" onclick="window.location.href='/auth-status'">查看登录态体检</button>
          </div>
        </form>
        <div id="publish-result" class="result-card"></div>
        <p class="muted" style="margin:16px 0 0; font-size:14px;">
          登录导出仍建议在终端执行 <code>softpost-cli auth</code>，因为它需要人工在浏览器完成登录。
        </p>
      </div>
    </section>
    <section class="panel" style="margin-top:20px;">
      <h2>最近生成的产物</h2>
      <p id="artifact-empty-state" class="muted" style="{empty_state_style}">数据库里还没有生成记录。</p>
      <div id="artifact-list" class="artifact-list">
        {artifact_list_html}
      </div>
    </section>
    <section class="panel" style="margin-top:20px;">
      <h2>最近日志</h2>
      {logs_html}
    </section>
  </main>
  <script>
    let busy = false;

    function setBusy(active, title = '处理中', text = '请求正在执行，请不要重复点击。') {{
      busy = active;
      const overlay = document.getElementById('busy-overlay');
      document.getElementById('busy-title').textContent = title;
      document.getElementById('busy-text').textContent = text;
      overlay.classList.toggle('active', active);
      overlay.setAttribute('aria-hidden', String(!active));
      document.querySelectorAll('button, input, textarea').forEach((el) => {{
        if (active) {{
          el.setAttribute('data-prev-disabled', el.disabled ? 'true' : 'false');
          el.disabled = true;
        }} else if (el.getAttribute('data-prev-disabled') === 'false') {{
          el.disabled = false;
        }}
      }});
    }}

    function renderMessage(targetId, level, title, text) {{
      const container = document.getElementById(targetId);
      container.innerHTML = `
        <div class="message ${{level}}">
          <span class="message-title">${{title}}</span>
          <div>${{text}}</div>
        </div>
      `;
    }}

    function renderResult(targetId, title, lines, links = []) {{
      const node = document.getElementById(targetId);
      const items = lines.map((line) => `<div>${{line}}</div>`).join('');
      const linkHtml = links.length
        ? `<div class="result-links">${{links.map((link) => `<a href="${{link.href}}" target="_blank" rel="noreferrer">${{link.label}}</a>`).join('')}}</div>`
        : '';
      node.innerHTML = `
        <div class="message success">
          <span class="message-title">${{title}}</span>
          ${{items}}
          ${{linkHtml}}
        </div>
      `;
      node.classList.add('active');
    }}

    function upsertAccountOption(path, label) {{
      const select = document.getElementById('account-select');
      let option = Array.from(select.options).find((item) => item.value === path);
      if (!option) {{
        option = document.createElement('option');
        option.value = path;
        select.prepend(option);
      }}
      option.textContent = label;
      option.selected = true;
      select.disabled = false;
    }}

    function prependArtifactCard(cardHtml) {{
      const list = document.getElementById('artifact-list');
      const emptyState = document.getElementById('artifact-empty-state');
      if (emptyState) {{
        emptyState.style.display = 'none';
      }}
      list.insertAdjacentHTML('afterbegin', cardHtml);
    }}

    async function postJson(url, payload) {{
      const response = await fetch(url, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});

      let result = null;
      try {{
        result = await response.json();
      }} catch {{
        throw new Error('服务返回了不可解析的响应，请查看日志。');
      }}

      if (!response.ok) {{
        throw new Error(result.detail || '请求失败，请查看日志。');
      }}
      return result;
    }}

    document.getElementById('generate-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (busy) return;
      document.getElementById('generate-result').classList.remove('active');
      const form = new FormData(event.target);
      setBusy(true, '正在生成内容', '正在调用模型、生成封面并写入 MySQL，请稍候。');
      try {{
        const result = await postJson('/api/generate', Object.fromEntries(form.entries()));
        renderMessage('page-message', 'success', '生成成功', `产物目录：${{result.artifact_dir}}`);
        renderResult(
          'generate-result',
          '本次生成已完成',
          [`标题：${{result.title}}`, `目录：${{result.artifact_dir}}`],
          [
            {{ href: result.cover_url, label: '查看封面' }},
            {{ href: result.markdown_url, label: '查看 Markdown' }}
          ]
        );
        prependArtifactCard(result.artifact_html);
        document.querySelector('#publish-form input[name="artifact_dir"]').value = result.artifact_dir;
      }} catch (error) {{
        renderMessage('page-message', 'warning', '生成失败', error.message);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('account-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (busy) return;
      const form = new FormData(event.target);
      setBusy(true, '正在切换账号', '正在切换当前生效的小红书登录态，请稍候。');
      try {{
        const result = await postJson('/api/account/select', {{
          state_path: form.get('state_path')
        }});
        document.getElementById('auth-level').textContent = result.auth_status.level;
        document.getElementById('auth-message').textContent = result.auth_status.message;
        renderMessage('page-message', 'success', '账号已切换', `当前使用：${{result.state_path}}`);
      }} catch (error) {{
        renderMessage('page-message', 'warning', '切换账号失败', error.message);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('add-account-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (busy) return;
      const form = new FormData(event.target);
      setBusy(true, '正在新增账号', '浏览器即将打开小红书创作中心，请在弹出的浏览器里完成登录，系统会自动保存并切换账号。');
      try {{
        const result = await postJson('/api/account/add', {{
          profile: form.get('profile')
        }});
        upsertAccountOption(result.state_path, result.option_label);
        document.getElementById('auth-level').textContent = result.auth_status.level;
        document.getElementById('auth-message').textContent = result.auth_status.message;
        renderMessage('page-message', 'success', '账号新增成功', `当前使用：${{result.state_path}}`);
        event.target.reset();
      }} catch (error) {{
        renderMessage('page-message', 'warning', '新增账号失败', error.message);
      }} finally {{
        setBusy(false);
      }}
    }});

    document.getElementById('publish-form').addEventListener('submit', async (event) => {{
      event.preventDefault();
      if (busy) return;
      document.getElementById('publish-result').classList.remove('active');
      const form = new FormData(event.target);
      setBusy(true, '正在发布', '正在打开创作中心并执行发布流程，请不要重复提交。');
      try {{
        const result = await postJson('/api/publish', {{
          artifact_dir: form.get('artifact_dir'),
          auto_submit: form.get('auto_submit') === 'on'
        }});
        renderMessage('page-message', 'success', '发布流程已启动', result.message);
        renderResult(
          'publish-result',
          '发布请求已执行',
          [`目录：${{result.artifact_dir}}`, `模式：${{form.get('auto_submit') === 'on' ? '自动提交' : '仅填写不提交'}}`]
        );
      }} catch (error) {{
        renderMessage('page-message', 'warning', '发布失败', error.message);
      }} finally {{
        setBusy(false);
      }}
    }});
  </script>
</body>
</html>"""


@app.on_event("startup")
def startup() -> None:
    try:
        ensure_storage_schema()
        logger.info("startup | storage schema ensured")
    except Exception:
        logger.exception("startup | failed to ensure storage schema")


@app.get("/", response_class=HTMLResponse)
def home(message: str = "", level: str = "info") -> str:
    return _render_home(message=message, level=level)


@app.get("/auth-status")
def auth_status() -> dict[str, str | int | float]:
    try:
        status = get_auth_status()
        logger.info("auth_status | success | level=%s", status.get("level"))
        return status
    except Exception as exc:
        logger.exception("auth_status | failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate")
def api_generate(payload: GenerateRequest) -> dict[str, str]:
    try:
        assets = SoftPostPipeline().run(payload.topic, payload.audience, payload.core)
        artifact_dir = str(assets.markdown_path.parent)
        markdown_text = assets.markdown_path.read_text(encoding="utf-8")
        cover_url = f"/outputs/{assets.markdown_path.parent.name}/cover.png"
        markdown_url = f"/outputs/{assets.markdown_path.parent.name}/post.md"
        artifact_html = _artifact_card_html(
            title=assets.post.title,
            artifact_dir=artifact_dir,
            topic=payload.topic,
            audience=payload.audience,
            hashtags=assets.post.hashtags,
            cover_url=cover_url,
            markdown_text=markdown_text,
            created_at=datetime.now().isoformat(sep=" ", timespec="seconds"),
        )
        logger.info("generate | success | topic=%s | artifact_dir=%s", payload.topic, artifact_dir)
        return {
            "artifact_dir": artifact_dir,
            "title": assets.post.title,
            "cover_url": cover_url,
            "markdown_url": markdown_url,
            "artifact_html": artifact_html,
        }
    except Exception as exc:
        logger.exception("generate | failed | topic=%s", payload.topic)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/publish")
def api_publish(payload: PublishRequest) -> dict[str, str]:
    try:
        artifact_path = Path(payload.artifact_dir)
        assets = _load_generated_assets(artifact_path)
        publish_sync(assets, auto_submit=payload.auto_submit)
        message = (
            "已尝试自动提交发布"
            if payload.auto_submit
            else "已填写到小红书发布页，但未自动点击最终发布"
        )
        logger.info(
            "publish | success | artifact_dir=%s | auto_submit=%s",
            payload.artifact_dir,
            payload.auto_submit,
        )
        return {"message": message, "artifact_dir": str(artifact_path)}
    except Exception as exc:
        logger.exception(
            "publish | failed | artifact_dir=%s | auto_submit=%s",
            payload.artifact_dir,
            payload.auto_submit,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/account/select")
def api_account_select(payload: SwitchAccountRequest) -> dict[str, object]:
    try:
        selected = set_active_login_state_path(payload.state_path)
        auth_status = get_auth_status()
        logger.info("account_select | success | state_path=%s", selected)
        return {"state_path": str(selected), "auth_status": auth_status}
    except Exception as exc:
        logger.exception("account_select | failed | state_path=%s", payload.state_path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/account/add")
def api_account_add(payload: AddAccountRequest) -> dict[str, object]:
    try:
        target = build_profile_state_path(payload.profile)
        exported = export_login_state_to_sync(target)
        auth_status = get_auth_status()
        option_label = f"{exported.stem} · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info("account_add | success | profile=%s | state_path=%s", payload.profile, exported)
        return {
            "state_path": str(exported),
            "option_label": option_label,
            "auth_status": auth_status,
        }
    except Exception as exc:
        logger.exception("account_add | failed | profile=%s", payload.profile)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/healthz")
def healthz() -> dict[str, str]:
    logger.info("healthz | success")
    return {"status": "ok"}


def main() -> None:
    logger.info("server | starting on http://127.0.0.1:8000")
    uvicorn.run("app.web:app", host="127.0.0.1", port=8000, reload=False)
