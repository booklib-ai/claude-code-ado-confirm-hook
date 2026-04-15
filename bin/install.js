#!/usr/bin/env node

const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const HOOKS_DIR = ".claude/hooks";
const FILES = ["ado-confirm.sh", "ado-confirm-dialog.py", "ado-webview.swift"];
const BINARY = "ado-webview";

function log(msg) {
  console.log(`\x1b[36m[ado-confirm]\x1b[0m ${msg}`);
}

function error(msg) {
  console.error(`\x1b[31m[ado-confirm]\x1b[0m ${msg}`);
}

function findProjectRoot() {
  let dir = process.cwd();
  while (dir !== path.dirname(dir)) {
    if (fs.existsSync(path.join(dir, ".claude")) || fs.existsSync(path.join(dir, ".mcp.json"))) {
      return dir;
    }
    dir = path.dirname(dir);
  }
  return process.cwd();
}

function main() {
  if (process.platform !== "darwin") {
    error("This hook only works on macOS (requires Cocoa WebView).");
    process.exit(1);
  }

  const root = findProjectRoot();
  const targetDir = path.join(root, HOOKS_DIR);
  const sourceDir = path.join(__dirname, "..", "hooks");

  log(`Installing to ${targetDir}`);

  // Create hooks directory
  fs.mkdirSync(targetDir, { recursive: true });

  // Copy hook files
  for (const file of FILES) {
    const src = path.join(sourceDir, file);
    const dst = path.join(targetDir, file);
    fs.copyFileSync(src, dst);
    fs.chmodSync(dst, 0o755);
    log(`Copied ${file}`);
  }

  // Compile Swift binary
  const swiftSrc = path.join(targetDir, "ado-webview.swift");
  const binaryPath = path.join(targetDir, BINARY);

  log("Compiling native dialog (swiftc)...");
  const result = spawnSync("swiftc", [
    "-framework", "Cocoa",
    "-framework", "WebKit",
    "-O",
    "-o", binaryPath,
    swiftSrc,
  ], { stdio: "inherit", timeout: 120000 });

  if (result.status !== 0) {
    error("Failed to compile. Make sure Xcode Command Line Tools are installed:");
    error("  xcode-select --install");
    process.exit(1);
  }

  log("Compiled native dialog");

  // Add binary to .gitignore
  const gitignorePath = path.join(root, ".gitignore");
  const ignoreEntry = `${HOOKS_DIR}/${BINARY}`;
  if (fs.existsSync(gitignorePath)) {
    const content = fs.readFileSync(gitignorePath, "utf8");
    if (!content.includes(ignoreEntry)) {
      fs.appendFileSync(gitignorePath, `\n${ignoreEntry}\n`);
      log("Added binary to .gitignore");
    }
  }

  // Show config instructions
  console.log("");
  log("Installed successfully!");
  console.log("");
  console.log("Add this to your .claude/settings.local.json:");
  console.log("");
  console.log(JSON.stringify({
    hooks: {
      PreToolUse: [{
        matcher: [
          "mcp__azure-devops__wit_create_work_item",
          "mcp__azure-devops__wit_update_work_item",
          "mcp__azure-devops__wit_update_work_items_batch",
          "mcp__azure-devops__wit_add_child_work_items",
          "mcp__azure-devops__wit_add_work_item_comment",
          "mcp__azure-devops__repo_create_pull_request",
          "mcp__azure-devops__wit_work_items_link",
          "mcp__azure-devops__wit_add_artifact_link",
          "mcp__azure-devops__repo_create_branch",
        ].join("|"),
        hooks: [{
          type: "command",
          command: ".claude/hooks/ado-confirm.sh",
          timeout: 30000,
          statusMessage: "Awaiting confirmation for Azure DevOps action...",
        }],
      }],
    },
  }, null, 2));
  console.log("");
}

main();
