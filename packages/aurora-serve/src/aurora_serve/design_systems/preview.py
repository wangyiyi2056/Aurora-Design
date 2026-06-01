from __future__ import annotations

import html
import re


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")


def render_design_system_preview(system_id: str, raw: str) -> str:
    title = _title(raw) or system_id
    summary = _summary(raw)
    colors = _colors(raw)
    bg = _pick(colors, ["#ffffff", "#fff"]) or "#ffffff"
    fg = _pick(colors, ["#171717", "#111111", "#000000"]) or "#111111"
    accent = next((color for color in colors if color.lower() not in {bg.lower(), fg.lower(), "#000000", "#fff"}), "#2f6feb")
    swatches = "\n".join(
        f'<div class="swatch"><div class="chip" style="background:{html.escape(color)}"></div><span>{html.escape(color)}</span></div>'
        for color in colors[:12]
    )
    prose = _markdown_lite(raw)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)} - Design system preview</title>
  <style>
    :root {{ --bg: {bg}; --fg: {fg}; --accent: {accent}; --border: rgba(127,127,127,.25); }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.55 Inter, ui-sans-serif, system-ui, sans-serif; }}
    main {{ max-width: 1040px; margin: 0 auto; padding: 56px 28px 88px; }}
    .badge {{ display: inline-flex; border: 1px solid var(--border); border-radius: 999px; padding: 4px 10px; color: var(--accent); font-size: 12px; }}
    h1 {{ margin: 18px 0 10px; font-size: clamp(38px, 6vw, 72px); line-height: 1.02; letter-spacing: -0.02em; }}
    .lede {{ max-width: 68ch; color: color-mix(in srgb, var(--fg), transparent 34%); font-size: 18px; }}
    .palette {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 14px; margin: 34px 0 46px; }}
    .swatch {{ border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: color-mix(in srgb, var(--bg), var(--fg) 3%); }}
    .chip {{ height: 86px; }}
    .swatch span {{ display: block; padding: 8px 10px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .components {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 46px; }}
    .card {{ border: 1px solid var(--border); border-radius: 8px; padding: 22px; background: color-mix(in srgb, var(--bg), var(--fg) 4%); }}
    button {{ border: 1px solid var(--accent); background: var(--accent); color: #fff; border-radius: 6px; padding: 10px 16px; font: inherit; }}
    .secondary {{ background: transparent; color: var(--fg); border-color: var(--border); }}
    .prose {{ border-top: 1px solid var(--border); padding-top: 28px; }}
    .prose h1 {{ font-size: 28px; }}
    .prose h2 {{ margin-top: 28px; font-size: 20px; }}
    .prose code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    pre {{ overflow: auto; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
    blockquote {{ border-left: 3px solid var(--accent); margin-left: 0; padding-left: 14px; opacity: .78; }}
    @media (max-width: 700px) {{ .components {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <span class="badge">Design system preview - {html.escape(system_id)}</span>
    <h1>{html.escape(title)}</h1>
    <p class="lede">{html.escape(summary)}</p>
    <section class="palette">{swatches}</section>
    <section class="components">
      <div class="card"><h2>Interface Card</h2><p>Sample surface using the extracted color and spacing language.</p></div>
      <div class="card"><h2>Actions</h2><p><button>Primary</button> <button class="secondary">Secondary</button></p></div>
    </section>
    <section class="prose">{prose}</section>
  </main>
</body>
</html>"""


def render_design_system_showcase(system_id: str, raw: str) -> str:
    title = _title(raw) or system_id
    summary = _summary(raw)
    colors = _colors(raw)
    accent = colors[2] if len(colors) > 2 else "#2f6feb"
    preview = render_design_system_preview(system_id, raw)
    return preview.replace(
        "<section class=\"palette\">",
        f"<section><h2>{html.escape(title)} Showcase</h2><p>{html.escape(summary)}</p><button style=\"background:{html.escape(accent)};border-color:{html.escape(accent)}\">Generate with this system</button></section><section class=\"palette\">",
        1,
    )


def _title(raw: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", raw, re.MULTILINE)
    if not match:
        return ""
    return re.sub(r"^Design System Inspired by\s+", "", match.group(1).strip(), flags=re.I)


def _summary(raw: str) -> str:
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") and "Category:" not in stripped:
            return stripped.lstrip(">").strip()
    for block in re.split(r"\n\s*\n", raw):
        text = block.strip()
        if text and not text.startswith("#") and not text.startswith(">"):
            return re.sub(r"\s+", " ", text)[:220]
    return ""


def _colors(raw: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in HEX_RE.finditer(raw):
        color = match.group(0)
        key = color.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(color)
    return out


def _pick(colors: list[str], candidates: list[str]) -> str | None:
    lower = {color.lower(): color for color in colors}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return None


def _markdown_lite(raw: str) -> str:
    escaped = html.escape(raw)
    escaped = re.sub(r"^### (.+)$", r"<h3>\1</h3>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^## (.+)$", r"<h2>\1</h2>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^# (.+)$", r"<h1>\1</h1>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^&gt; (.+)$", r"<blockquote>\1</blockquote>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    parts = [part.strip() for part in escaped.split("\n\n") if part.strip()]
    return "\n".join(part if part.startswith("<h") or part.startswith("<blockquote") else f"<p>{part}</p>" for part in parts)
