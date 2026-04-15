# Azure DevOps Confirmation Hook for Claude Code

Native macOS dialog for reviewing Azure DevOps MCP write operations before they execute. See what's changing, approve or cancel.

| Update — word-level diff | Create — field summary | Batch update — table view |
|:---:|:---:|:---:|
| <img src="docs/demo-update.png" width="280"> | <img src="docs/demo-create.png" width="280"> | <img src="docs/demo-batch-update.png" width="280"> |

## Why

The [Azure DevOps MCP server](https://github.com/microsoft/azure-devops-mcp) lets Claude Code create, update, and link work items directly. But write operations execute immediately — no visual preview of what's about to change.

This hook intercepts MCP write calls and shows a native macOS dialog with:
- **Updates:** side-by-side diff with word-level highlighting
- **Batch updates:** table with old → new values per item
- **Creates:** field summary of the new work item
- **Links, comments, PRs:** formatted preview

## Install

```bash
npx claude-ado-confirm-hook
```

This copies the hook files to `.claude/hooks/`, compiles the native dialog, and prints the settings config to add.

### Manual install

If you prefer not to use npm:

```bash
mkdir -p .claude/hooks
curl -sL https://raw.githubusercontent.com/ZLStas/claude-code-ado-confirm-hook/main/hooks/ado-confirm.sh -o .claude/hooks/ado-confirm.sh
curl -sL https://raw.githubusercontent.com/ZLStas/claude-code-ado-confirm-hook/main/hooks/ado-confirm-dialog.py -o .claude/hooks/ado-confirm-dialog.py
curl -sL https://raw.githubusercontent.com/ZLStas/claude-code-ado-confirm-hook/main/hooks/ado-webview.swift -o .claude/hooks/ado-webview.swift
chmod +x .claude/hooks/ado-confirm.sh .claude/hooks/ado-confirm-dialog.py
swiftc -framework Cocoa -framework WebKit -O -o .claude/hooks/ado-webview .claude/hooks/ado-webview.swift
```

## Configure

Add to `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__azure-devops__wit_create_work_item|mcp__azure-devops__wit_update_work_item|mcp__azure-devops__wit_update_work_items_batch|mcp__azure-devops__wit_add_child_work_items|mcp__azure-devops__wit_add_work_item_comment|mcp__azure-devops__repo_create_pull_request|mcp__azure-devops__wit_work_items_link|mcp__azure-devops__wit_add_artifact_link|mcp__azure-devops__repo_create_branch",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/ado-confirm.sh",
            "timeout": 30000,
            "statusMessage": "Awaiting confirmation for Azure DevOps action..."
          }
        ]
      }
    ]
  }
}
```

The hook reads your org name and access token from `.mcp.json` automatically — no hardcoded config needed.

## How It Works

1. Claude Code calls an Azure DevOps MCP tool (create, update, link, etc.)
2. The hook intercepts the call before execution
3. For updates: fetches current values from Azure DevOps API to show the diff
4. Renders an HTML view in a native macOS WebView window
5. You click **Approve** (or Enter) to proceed, **Cancel** (or Escape) to block

The dialog appears on your current screen — no desktop switching.

## Requirements

- **macOS** (Cocoa WebView)
- **Xcode Command Line Tools** (for `swiftc`)
- **jq**, **curl** (for the shell script)
- [Azure DevOps MCP server](https://github.com/microsoft/azure-devops-mcp) configured in `.mcp.json`

## Files

| File | What it does |
|------|-------------|
| `ado-confirm.sh` | Hook entry point. Enriches payloads with current values for diffs. |
| `ado-confirm-dialog.py` | Builds HTML for each operation type. Handles diff, batch fetch, name normalization. |
| `ado-webview.swift` | Native macOS window with WKWebView. Renders HTML, handles Approve/Cancel. |

## License

MIT
