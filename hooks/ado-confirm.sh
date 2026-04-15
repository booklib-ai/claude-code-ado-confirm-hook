#!/bin/bash
# Azure DevOps MCP write-operation confirmation dialog (macOS)
# Routes all operations through the Swift WebView dialog via Python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input')

# For update operations, enrich with current field values for diff view
if [ "$TOOL_NAME" = "mcp__azure-devops__wit_update_work_item" ]; then
  ID=$(echo "$TOOL_INPUT" | jq -r '.id // "N/A"')
  MCP_JSON="$(git rev-parse --show-toplevel 2>/dev/null)/.mcp.json"
  ADO_PAT=$(jq -r '.mcpServers["azure-devops"].env.AZURE_DEVOPS_EXT_PAT // empty' "$MCP_JSON" 2>/dev/null)
  ADO_ORG=$(jq -r '.mcpServers["azure-devops"].args[0] // empty' "$MCP_JSON" 2>/dev/null)

  CURRENT_FIELDS="{}"
  CURRENT_TITLE=""
  if [ -n "$ADO_PAT" ] && [ -n "$ADO_ORG" ] && [ "$ID" != "N/A" ]; then
    CURRENT_WI=$(curl -s -u ":$ADO_PAT" \
      "https://dev.azure.com/${ADO_ORG}/_apis/wit/workitems/${ID}?api-version=7.0" 2>/dev/null || echo "{}")
    CURRENT_TITLE=$(echo "$CURRENT_WI" | jq -r '.fields["System.Title"] // empty' 2>/dev/null)
    CURRENT_FIELDS=$(echo "$CURRENT_WI" | jq '.fields // {}' 2>/dev/null)
  fi

  INPUT=$(echo "$INPUT" | jq \
    --argjson fields "$CURRENT_FIELDS" \
    --arg title "$CURRENT_TITLE" \
    '.tool_input._current_fields = $fields | .tool_input._current_title = $title')
fi

# Show the dialog (handles all operation types)
EXIT_CODE=0
echo "$INPUT" | /usr/bin/python3 "$SCRIPT_DIR/ado-confirm-dialog.py" || EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo '{"continue": true}' | jq '.'
  exit 0
else
  echo "User declined the Azure DevOps action: $TOOL_NAME" >&2
  exit 2
fi
