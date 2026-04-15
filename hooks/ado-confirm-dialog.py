#!/usr/bin/python3
"""Confirmation dialog for Azure DevOps MCP operations.

Supports all operation types: create, update, link, comment, PR, etc.
Renders HTML in a native macOS WebView via the pre-compiled ado-webview binary.
Reads JSON payload from stdin. Exits 0 for approve, 2 for decline.
"""

import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from html import escape
from html.parser import HTMLParser

__all__ = ["strip_html", "friendly_name", "word_diff_html", "build_html", "show_swift_dialog"]


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("li",):
            self._parts.append("\u2022 ")
        elif tag in ("br", "p"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("li", "p", "div"):
            self._parts.append("\n")

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        text = "".join(self._parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def strip_html(html_str):
    if not html_str:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(html_str)
    return stripper.get_text()


FRIENDLY_NAMES = {
    "System.Title": "Title",
    "System.Tags": "Tags",
    "System.Description": "Description",
    "System.State": "State",
    "System.AssignedTo": "Assigned To",
    "System.IterationPath": "Iteration",
    "System.AreaPath": "Area Path",
    "Microsoft.VSTS.Common.AcceptanceCriteria": "Acceptance Criteria",
    "Microsoft.VSTS.Scheduling.Size": "Story Points",
    "Philips.STI.Requirement.Description": "Description",
    "Philips.Common.Product": "Product",
}


def friendly_name(field):
    return FRIENDLY_NAMES.get(field, field.rsplit(".", 1)[-1])


def friendly_action(tool_name):
    raw = tool_name.split("__")[-1].replace("_", " ").strip()
    for prefix in ("wit ", "repo ", "work "):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
    return raw.title()


def word_diff_html(old, new):
    old_words = re.findall(r'\S+|\s+', old)
    new_words = re.findall(r'\S+|\s+', new)
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    old_parts, new_parts = [], []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            old_parts.append(escape("".join(old_words[i1:i2])))
            new_parts.append(escape("".join(new_words[j1:j2])))
        elif op == "delete":
            old_parts.append('<span class="del">{}</span>'.format(escape("".join(old_words[i1:i2]))))
        elif op == "insert":
            new_parts.append('<span class="ins">{}</span>'.format(escape("".join(new_words[j1:j2]))))
        elif op == "replace":
            old_parts.append('<span class="del">{}</span>'.format(escape("".join(old_words[i1:i2]))))
            new_parts.append('<span class="ins">{}</span>'.format(escape("".join(new_words[j1:j2]))))
    return "".join(old_parts), "".join(new_parts)


# ── HTML builders ──────────────────────────────────────────────────

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, 'SF Pro Display', sans-serif;
    background: #1e1e1e; color: #d4d4d4;
    padding: 20px; overflow-y: auto;
  }
  .action { font-size: 15px; font-weight: 700; color: #dcdcaa; }
  .item { font-size: 13px; color: #fff; margin-top: 4px; }
  hr { border: none; border-top: 1px solid #3c3c3c; margin: 14px 0; }
  .field-label {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 12px; font-weight: 600; color: #569cd6;
    margin: 14px 0 6px 0;
  }
  .field-value {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 11px; color: #c8c8c8;
    background: #252526; border-radius: 4px; padding: 8px;
    white-space: pre-wrap; word-wrap: break-word; line-height: 1.5;
    max-height: 200px; overflow-y: auto;
  }
  .diff-row { display: flex; gap: 8px; }
  .diff-col { flex: 1; border-radius: 4px; overflow: hidden; }
  .old-col { background: #2d1517; }
  .new-col { background: #1d2d1f; }
  .col-header {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 10px; color: #888; padding: 4px 8px;
  }
  .col-body {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 11px; color: #c8c8c8; padding: 6px 8px;
    white-space: pre-wrap; word-wrap: break-word; line-height: 1.5;
  }
  .del { color: #fff; background: #6e2020; border-radius: 2px; padding: 1px 2px; }
  .ins { color: #fff; background: #2a6e2a; border-radius: 2px; padding: 1px 2px; }
  .items-list { margin: 8px 0; }
  .items-list li {
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 11px; color: #c8c8c8; padding: 4px 0;
    list-style: none;
  }
  .items-list li:before { content: '• '; color: #569cd6; }
  table { border: 1px solid #3c3c3c; border-radius: 4px; overflow: hidden; }
  th { background: #252526; }
  tr:hover { background: #2a2d2e; }
"""


def wrap_html(action, header, body_html):
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>
  <div class="action">\u26a0\ufe0f  {action}</div>
  <div class="item">{header}</div>
  <hr>
  {body}
</body></html>""".format(css=CSS, action=escape(action), header=escape(header), body=body_html)


def field_block(label, value):
    return '<div class="field-label">{}</div><div class="field-value">{}</div>'.format(
        escape(label), escape(value).replace("\n", "<br>"))


def diff_block(label, old, new):
    old_html, new_html = word_diff_html(old, new)
    return """
    <div class="field-label">{label}</div>
    <div class="diff-row">
      <div class="diff-col old-col">
        <div class="col-header">Current</div>
        <div class="col-body">{old}</div>
      </div>
      <div class="diff-col new-col">
        <div class="col-header">New</div>
        <div class="col-body">{new}</div>
      </div>
    </div>""".format(label=escape(label), old=old_html.replace("\n", "<br>"), new=new_html.replace("\n", "<br>"))


# ── Operation handlers ─────────────────────────────────────────────

def handle_update(tool_input, current_fields, current_title):
    item_id = tool_input.get("id", "?")
    header = "#{}".format(item_id)
    if current_title:
        header = "#{} \u2014 {}".format(item_id, current_title)

    body = ""
    for update in tool_input.get("updates", []):
        field_path = update.get("path", "")
        field_name = field_path.rsplit("/", 1)[-1]
        label = friendly_name(field_name)
        new_val = strip_html(str(update.get("value", "")))
        old_val = strip_html(str(current_fields.get(field_name, ""))) or "(empty)"
        body += diff_block(label, old_val, new_val)

    return "Update Work Item", header, body


def handle_create(tool_input):
    wi_type = tool_input.get("workItemType", "Work Item")
    fields = tool_input.get("fields", [])
    title = ""
    body = ""

    for f in fields:
        name = f.get("name", "")
        value = strip_html(str(f.get("value", "")))
        label = friendly_name(name)
        if name == "System.Title":
            title = value
        elif value and len(value) < 500:
            body += field_block(label, value[:300])

    header = "New {} \u2014 {}".format(wi_type, title) if title else "New {}".format(wi_type)
    return "Create Work Item", header, body


def handle_add_children(tool_input):
    parent_id = tool_input.get("parentId", "?")
    items = tool_input.get("items", [])
    wi_type = tool_input.get("workItemType", "Work Item")

    body = field_block("Type", wi_type)
    body += '<div class="field-label">Items ({})</div><ul class="items-list">'.format(len(items))
    for item in items[:20]:
        t = escape(item.get("title", "(no title)"))
        body += "<li>{}</li>".format(t)
    body += "</ul>"

    return "Add Child Work Items", "Parent #{}".format(parent_id), body


def handle_link(tool_input):
    updates = tool_input.get("updates", [])
    body = '<ul class="items-list">'
    for u in updates[:20]:
        wi_id = u.get("id", "?")
        link_to = u.get("linkToId", "?")
        link_type = u.get("type", "related")
        body += "<li>#{} \u2192 #{} ({})</li>".format(wi_id, link_to, escape(link_type))
    body += "</ul>"

    return "Link Work Items", "{} link(s)".format(len(updates)), body


def handle_comment(tool_input):
    wi_id = tool_input.get("workItemId", tool_input.get("id", "?"))
    text = strip_html(str(tool_input.get("text", tool_input.get("comment", ""))))
    body = field_block("Comment", text[:500])
    return "Add Comment", "#{}".format(wi_id), body


def handle_create_pr(tool_input):
    title = tool_input.get("title", "")
    source = tool_input.get("sourceBranch", "")
    target = tool_input.get("targetBranch", "")
    body = field_block("Title", title)
    body += field_block("Source", source)
    body += field_block("Target", target)
    return "Create Pull Request", title, body


def _normalize_person(val):
    """Normalize person display to 'FirstName LastName' from various formats:
    - 'Last, First (Suffix)' → 'First Last'
    - 'user.First.Last@domain.com' → 'First Last'
    - 'First Last' → 'First Last' (no change)
    """
    if not val:
        return ""
    # Email format: anything@domain → extract name from local part
    if "@" in val:
        local = val.split("@")[0]
        parts = local.split(".")
        # Skip common prefixes that aren't names
        name_parts = [p for p in parts if p.lower() not in ("partner", "ext", "contractor", "admin")]
        return " ".join(p.capitalize() for p in name_parts) if name_parts else val
    # "Last, First (Suffix)" format — strip parenthetical, flip comma
    clean = re.sub(r'\s*\([^)]*\)\s*', '', val).strip()
    if "," in clean:
        parts = [p.strip() for p in clean.split(",", 1)]
        if len(parts) == 2:
            return "{} {}".format(parts[1], parts[0])
    return clean


def _fetch_batch_current(wi_ids):
    """Fetch current field values for multiple work items in one API call."""
    import urllib.request
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))
    mcp_path = os.path.join(repo_root, ".mcp.json")
    try:
        with open(mcp_path) as f:
            mcp_config = json.load(f)["mcpServers"]["azure-devops"]
            pat = mcp_config["env"]["AZURE_DEVOPS_EXT_PAT"]
            org = mcp_config.get("args", [""])[0]
        if not org:
            return {}
        ids_str = ",".join(str(i) for i in wi_ids)
        url = "https://dev.azure.com/{}/_apis/wit/workitems?ids={}&api-version=7.0".format(org, ids_str)
        req = urllib.request.Request(url)
        import base64
        auth = base64.b64encode(":{}".format(pat).encode()).decode()
        req.add_header("Authorization", "Basic {}".format(auth))
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = {}
        for wi in data.get("value", []):
            wi_id = wi.get("id")
            fields = wi.get("fields", {})
            title = fields.get("System.Title", "")
            result[wi_id] = {"title": title, "fields": fields}
        return result
    except Exception:
        return {}


def handle_batch_update(tool_input):
    updates = tool_input.get("updates", [])
    # Group updates by work item ID
    grouped = {}
    for u in updates:
        wi_id = u.get("id", "?")
        if wi_id not in grouped:
            grouped[wi_id] = []
        field_name = u.get("path", "").rsplit("/", 1)[-1]
        value = strip_html(str(u.get("value", "")))
        grouped[wi_id].append((field_name, friendly_name(field_name), value))

    # Fetch current values in one batch call
    current = _fetch_batch_current(list(grouped.keys()))

    # Get unique field labels from first item for consistent columns
    if grouped:
        field_entries = list(grouped.values())[0]
        field_names = [(raw, label) for raw, label, _ in field_entries]
    else:
        field_names = []

    # Build table header
    body = '<table style="width:100%;border-collapse:collapse;margin-top:8px;">'
    body += '<tr style="border-bottom:1px solid #3c3c3c;">'
    body += '<th style="text-align:left;padding:6px 8px;color:#569cd6;font-family:SF Mono,Menlo,monospace;font-size:11px;">ID / Title</th>'
    for _, label in field_names:
        body += '<th style="text-align:left;padding:6px 8px;color:#569cd6;font-family:SF Mono,Menlo,monospace;font-size:11px;">{}</th>'.format(escape(label))
    body += '</tr>'

    # Build rows
    for wi_id, fields in grouped.items():
        field_map = {raw: val for raw, _, val in fields}
        wi_info = current.get(wi_id, {})
        wi_title = wi_info.get("title", "")
        wi_fields = wi_info.get("fields", {})

        # ID + title cell
        body += '<tr style="border-bottom:1px solid #2a2a2a;">'
        id_cell = "#{}<br><span style='color:#888;font-size:10px;'>{}</span>".format(
            wi_id, escape(wi_title[:40]))
        body += '<td style="padding:6px 8px;color:#dcdcaa;font-family:SF Mono,Menlo,monospace;font-size:11px;white-space:nowrap;">{}</td>'.format(id_cell)

        for raw_name, _ in field_names:
            new_val = field_map.get(raw_name, "")
            old_val = str(wi_fields.get(raw_name, "")) if wi_fields else ""

            # Clean up AssignedTo display — normalize both old and new to comparable format
            if isinstance(wi_fields.get(raw_name), dict):
                old_val = wi_fields[raw_name].get("displayName", str(wi_fields[raw_name]))
            if raw_name == "System.AssignedTo":
                old_val = _normalize_person(old_val)
                new_val = _normalize_person(new_val)

            old_display = strip_html(old_val)[:50] if old_val else "(empty)"
            new_display = new_val[:50]

            cell = '<span style="color:#888;font-size:10px;">{}</span><br><span style="color:#89d185;">\u2192 {}</span>'.format(
                escape(old_display), escape(new_display))

            body += '<td style="padding:6px 8px;font-family:SF Mono,Menlo,monospace;font-size:11px;">{}</td>'.format(cell)
        body += '</tr>'

    body += '</table>'

    return "Batch Update Work Items", "{} items".format(len(grouped)), body


def handle_generic(tool_name, tool_input):
    action = friendly_action(tool_name)
    payload_str = json.dumps(tool_input, indent=2, ensure_ascii=False)[:800]
    body = field_block("Payload", payload_str)
    return action, tool_name.split("__")[-1], body


# ── Main ───────────────────────────────────────────────────────────

def show_swift_dialog(html_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    binary = os.path.join(script_dir, "ado-webview")
    if not os.path.isfile(binary):
        sys.stderr.write("ado-webview binary not found\n")
        return False
    result = subprocess.run(
        [binary, html_path],
        capture_output=True, text=True, timeout=60)
    return result.stdout.strip() == "approve"


if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, str):
        tool_input = json.loads(tool_input)

    current_fields = tool_input.pop("_current_fields", {})
    current_title = tool_input.pop("_current_title", "")

    if "update_work_items_batch" in tool_name:
        action, header, body = handle_batch_update(tool_input)
    elif "update_work_item" in tool_name:
        action, header, body = handle_update(tool_input, current_fields, current_title)
    elif "create_work_item" in tool_name:
        action, header, body = handle_create(tool_input)
    elif "add_child_work_items" in tool_name:
        action, header, body = handle_add_children(tool_input)
    elif "work_items_link" in tool_name:
        action, header, body = handle_link(tool_input)
    elif "add_work_item_comment" in tool_name:
        action, header, body = handle_comment(tool_input)
    elif "create_pull_request" in tool_name:
        action, header, body = handle_create_pr(tool_input)
    else:
        action, header, body = handle_generic(tool_name, tool_input)

    html = wrap_html(action, header, body)

    fd, html_path = tempfile.mkstemp(suffix=".html")
    with os.fdopen(fd, "w") as f:
        f.write(html)

    try:
        if show_swift_dialog(html_path):
            sys.exit(0)
        else:
            sys.exit(2)
    finally:
        try:
            os.unlink(html_path)
        except OSError:
            pass
