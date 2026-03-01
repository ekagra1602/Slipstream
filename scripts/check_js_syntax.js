"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const ROOTS = ["frontend", "scripts"];
const SKIP_DIRS = new Set(["node_modules", ".git", "__pycache__"]);

function collectJsFiles(dir) {
  const out = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    if (SKIP_DIRS.has(entry.name)) continue;

    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectJsFiles(full));
      continue;
    }

    if (!entry.isFile()) continue;
    if (full.endsWith(".js")) out.push(full);
  }
  return out;
}

function checkFile(file) {
  const proc = spawnSync(process.execPath, ["--check", file], {
    encoding: "utf8",
  });
  return proc;
}

function main() {
  const files = [];
  for (const root of ROOTS) {
    if (!fs.existsSync(root)) continue;
    files.push(...collectJsFiles(root));
  }

  if (!files.length) {
    console.log("No JS files found for syntax checks.");
    return 0;
  }

  let failures = 0;
  for (const file of files.sort()) {
    const result = checkFile(file);
    if (result.status !== 0) {
      failures += 1;
      process.stderr.write(`\n[FAIL] ${file}\n`);
      if (result.stderr) process.stderr.write(result.stderr);
      if (result.stdout) process.stderr.write(result.stdout);
    } else {
      process.stdout.write(`[PASS] ${file}\n`);
    }
  }

  if (failures > 0) {
    process.stderr.write(
      `\nJavaScript syntax check failed in ${failures} file(s).\n`,
    );
    return 1;
  }

  console.log("\nJavaScript syntax checks passed.");
  return 0;
}

process.exitCode = main();
