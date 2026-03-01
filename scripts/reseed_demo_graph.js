#!/usr/bin/env node
"use strict";

const readline = require("readline");

function parseArgs(argv) {
  const opts = {
    baseUrl: process.env.DEMO_API_URL || "http://127.0.0.1:8000",
    yes: false,
    domains: 10,
    tasksPerDomain: 100,
    includeHistory: true,
  };

  for (const raw of argv) {
    if (raw === "--yes") {
      opts.yes = true;
      continue;
    }
    if (raw.startsWith("--url=")) {
      opts.baseUrl = raw.slice("--url=".length);
      continue;
    }
    if (raw.startsWith("--domains=")) {
      opts.domains = Number(raw.slice("--domains=".length));
      continue;
    }
    if (raw.startsWith("--tasks-per-domain=")) {
      opts.tasksPerDomain = Number(raw.slice("--tasks-per-domain=".length));
      continue;
    }
    if (raw.startsWith("--include-history=")) {
      const value = raw.slice("--include-history=".length).toLowerCase();
      opts.includeHistory = value !== "false";
      continue;
    }
  }

  opts.baseUrl = opts.baseUrl.replace(/\/+$/, "");
  return opts;
}

async function fetchJson(url, init) {
  const res = await fetch(url, init);
  const text = await res.text();
  let body = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { raw: text };
  }
  if (!res.ok) {
    throw new Error(
      `Request failed (${res.status} ${res.statusText}) at ${url}: ${JSON.stringify(body)}`,
    );
  }
  return body;
}

function askConfirm(question) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(
        String(answer || "")
          .trim()
          .toLowerCase(),
      );
    });
  });
}

function printStats(header, stats) {
  console.log(`\n${header}`);
  console.log(
    JSON.stringify(
      {
        taskNodes: stats.taskNodes,
        domainNodes: stats.domainNodes,
        totalRuns: stats.totalRuns,
        zeroRunTasks: stats.zeroRunTasks,
        nonCanonicalDomains: stats.nonCanonicalDomains,
      },
      null,
      2,
    ),
  );
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const statsUrl = `${opts.baseUrl}/api/admin/graph/stats`;
  const reseedUrl = `${opts.baseUrl}/api/admin/demo/reseed`;

  const pre = await fetchJson(statsUrl);
  printStats("Pre-Reseed Stats", pre);

  if (!opts.yes) {
    const answer = await askConfirm(
      "\nThis will DELETE and rebuild task_nodes demo data. Continue? (yes/no): ",
    );
    if (answer !== "yes" && answer !== "y") {
      console.log("Cancelled.");
      process.exit(0);
    }
  }

  const reseedPayload = {
    mode: "full",
    domains: opts.domains,
    tasksPerDomain: opts.tasksPerDomain,
    includeHistory: opts.includeHistory,
  };

  const reseedResult = await fetchJson(reseedUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reseedPayload),
  });

  console.log("\nReseed Result");
  console.log(JSON.stringify(reseedResult, null, 2));

  const post = await fetchJson(statsUrl);
  printStats("Post-Reseed Stats", post);

  const warnings = [];
  if (post.zeroRunTasks > 0) {
    warnings.push(`zeroRunTasks=${post.zeroRunTasks}`);
  }
  if ((post.nonCanonicalDomains || []).length > 0) {
    warnings.push(`nonCanonicalDomains=${post.nonCanonicalDomains.join(",")}`);
  }

  if (warnings.length) {
    console.warn(`\nWarnings: ${warnings.join(" | ")}`);
    process.exitCode = 1;
  } else {
    console.log("\nDemo graph reseed complete.");
  }
}

main().catch((err) => {
  console.error(String(err));
  process.exitCode = 1;
});
