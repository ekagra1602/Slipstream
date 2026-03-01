#!/usr/bin/env node
"use strict";

/**
 * Validate frontend graph payload topology:
 * - canonical domains (no www.*)
 * - expected real node volume and domain count
 * - balanced per-domain task distribution
 * - dominant connected component share
 *
 * Usage:
 *   node scripts/check_graph_topology.js
 *   GRAPH_API_URL=http://127.0.0.1:8000/api/graph node scripts/check_graph_topology.js
 */

const GRAPH_API_URL =
  process.env.GRAPH_API_URL || "http://127.0.0.1:8000/api/graph";

const EXPECTED = {
  taskMin: 950,
  taskMax: 1050,
  domains: 10,
  maxDomainSkew: 0, // exact 100/domain for this seed
  dominantComponentMinShare: 0.95,
};

function getNodeId(ref) {
  return typeof ref === "object" && ref !== null ? ref.id : ref;
}

function connectedComponents(graph) {
  const nodeIds = graph.nodes.map((n) => n.id);
  const nodesById = new Map(graph.nodes.map((n) => [n.id, n]));
  const adj = new Map(nodeIds.map((id) => [id, new Set()]));

  for (const link of graph.links) {
    const src = getNodeId(link.source);
    const tgt = getNodeId(link.target);
    if (!adj.has(src) || !adj.has(tgt)) continue;
    adj.get(src).add(tgt);
    adj.get(tgt).add(src);
  }

  const seen = new Set();
  const components = [];

  for (const id of nodeIds) {
    if (seen.has(id)) continue;
    const stack = [id];
    seen.add(id);
    const ids = [];

    while (stack.length) {
      const cur = stack.pop();
      ids.push(cur);
      for (const nb of adj.get(cur)) {
        if (!seen.has(nb)) {
          seen.add(nb);
          stack.push(nb);
        }
      }
    }

    const domains = new Set(
      ids
        .map((nodeId) => nodesById.get(nodeId))
        .filter((n) => n?.type === "domain")
        .map((n) => n.domain),
    );

    components.push({
      size: ids.length,
      tasks: ids.filter((nodeId) => nodesById.get(nodeId)?.type === "task")
        .length,
      domainNodes: ids.filter(
        (nodeId) => nodesById.get(nodeId)?.type === "domain",
      ).length,
      domains: [...domains].sort(),
    });
  }

  components.sort((a, b) => b.size - a.size);
  return components;
}

async function main() {
  const res = await fetch(GRAPH_API_URL);
  if (!res.ok) {
    throw new Error(
      `Graph API request failed: ${res.status} ${res.statusText}`,
    );
  }

  const graph = await res.json();
  const tasks = graph.nodes.filter((n) => n.type === "task");
  const domains = graph.nodes.filter((n) => n.type === "domain");
  const byDomain = new Map();

  for (const task of tasks) {
    byDomain.set(task.domain, (byDomain.get(task.domain) || 0) + 1);
  }

  const domainCounts = [...byDomain.entries()].sort((a, b) => b[1] - a[1]);
  const countsOnly = domainCounts.map(([, count]) => count);
  const minCount = countsOnly.length ? Math.min(...countsOnly) : 0;
  const maxCount = countsOnly.length ? Math.max(...countsOnly) : 0;
  const skew = maxCount - minCount;

  const hasWwwDomain = domainCounts.some(([domain]) =>
    domain.startsWith("www."),
  );
  const components = connectedComponents(graph);
  const dominantShare = components.length
    ? components[0].size / graph.nodes.length
    : 0;

  const failures = [];

  if (tasks.length < EXPECTED.taskMin || tasks.length > EXPECTED.taskMax) {
    failures.push(
      `Task count ${tasks.length} outside expected range ${EXPECTED.taskMin}-${EXPECTED.taskMax}.`,
    );
  }

  if (domains.length !== EXPECTED.domains) {
    failures.push(
      `Domain node count ${domains.length} does not match expected ${EXPECTED.domains}.`,
    );
  }

  if (hasWwwDomain) {
    failures.push("Found non-canonical domains starting with 'www.'.");
  }

  if (skew > EXPECTED.maxDomainSkew) {
    failures.push(
      `Per-domain task skew ${skew} exceeds allowed ${EXPECTED.maxDomainSkew}.`,
    );
  }

  if (dominantShare < EXPECTED.dominantComponentMinShare) {
    failures.push(
      `Dominant connected component share ${(dominantShare * 100).toFixed(2)}% is below expected ${(EXPECTED.dominantComponentMinShare * 100).toFixed(0)}%.`,
    );
  }

  console.log(
    JSON.stringify(
      {
        api: GRAPH_API_URL,
        totals: {
          nodes: graph.nodes.length,
          links: graph.links.length,
          tasks: tasks.length,
          domains: domains.length,
        },
        domainDistribution: domainCounts,
        distributionSkew: skew,
        components,
        dominantComponentShare: Number(dominantShare.toFixed(4)),
        ok: failures.length === 0,
        failures,
      },
      null,
      2,
    ),
  );

  if (failures.length) {
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(String(err));
  process.exitCode = 1;
});
