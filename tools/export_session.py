# -*- coding: utf-8 -*-
"""Export a Codex rollout JSONL into a readable dialogue record.

Usage:
    python -X utf8 tools/export_session.py <rollout.jsonl> [out.md]

Default output: session/会话记录.md next to the project root. The record
keeps every user/assistant message in order plus the LAST compaction
summary (earlier summaries are superseded snapshots; the raw jsonl keeps
them if ever needed). The file is for the PRIVATE migration zip only -
debug transcripts may quote key material, so it stays out of the repo.
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CST = timezone(timedelta(hours=8))
LABEL = {"user": "用户", "assistant": "助手"}


def _text_of(content):
    parts = []
    for c in content or []:
        if isinstance(c, dict) and c.get("type") in ("text", "input_text", "output_text"):
            t = c.get("text")
            if t:
                parts.append(t)
    return "\n".join(parts)


def _msg_text(item):
    """One replacement-history entry -> '角色: 文本' (or '' )."""
    if not isinstance(item, dict):
        return ""
    role = item.get("role") or ("用户" if item.get("type") == "user_message" else "")
    body = _text_of(item.get("content")) or item.get("text") or item.get("message") or ""
    if not body:
        return ""
    return ("%s: %s" % (role, body)) if role else body


def _pick_summary(payload):
    """Compaction payloads keep an empty .message; the real distilled
    state lives in replacement_history (+ retained_context tails)."""
    lines = []
    for key in ("replacement_history", "retained_context"):
        block = payload.get(key)
        if isinstance(block, dict):
            for sub in (block.get("user_messages") or []) + (block.get("assistant_messages") or []):
                t = _msg_text(sub)
                if t:
                    lines.append(t)
        elif isinstance(block, list):
            for item in block:
                t = _msg_text(item)
                if t:
                    lines.append(t)
    if lines:
        return "\n\n".join(lines)
    for key in ("message", "summary", "compact_summary", "text"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _fmt_ts(ts):
    if not ts:
        return "?"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(CST)
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return str(ts)[:16]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "session", "会话记录.md")

    msgs = []
    compact_count = 0
    last_compact = ("", "")
    with io.open(src, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            kind = o.get("type")
            if kind == "compacted":
                compact_count += 1
                last_compact = (o.get("timestamp"), _pick_summary(o.get("payload") or {}))
            elif kind == "response_item":
                pl = o.get("payload") or {}
                if pl.get("type") == "message" and pl.get("role") in LABEL:
                    body = _text_of(pl.get("content"))
                    if body.strip():
                        msgs.append((o.get("timestamp"), pl["role"], body))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as w:
        w.write("# FareAlert 开发会话记录\n\n")
        w.write("> 由 `tools/export_session.py` 从 Codex rollout 记录导出；仅随迁移包分发，**不入公开仓库**。\n")
        w.write("> 源文件：%s\n" % os.path.basename(src))
        w.write("> 消息数：用户 %d / 助手 %d；压缩摘要 %d 次（此处收录最新一次）。\n\n" % (
            sum(1 for _, r, _ in msgs if r == "user"),
            sum(1 for _, r, _ in msgs if r == "assistant"),
            compact_count,
        ))
        if last_compact[1]:
            w.write("## 最新状态摘要（自动压缩生成，%s）\n\n%s\n\n---\n\n" % (
                _fmt_ts(last_compact[0]), last_compact[1].strip()))
        for ts, role, body in msgs:
            w.write("### [%s] %s\n\n%s\n\n" % (_fmt_ts(ts), LABEL[role], body.strip()))
    print("WROTE %s (%d messages, %.1f KB)" % (
        out, len(msgs), os.path.getsize(out) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
