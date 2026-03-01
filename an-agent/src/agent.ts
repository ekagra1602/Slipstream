import { agent, tool } from "@an-sdk/agent";
import { ConvexHttpClient } from "convex/browser";
import { z } from "zod";

const convex = new ConvexHttpClient(process.env.CONVEX_URL!);

export default agent({
  model: "claude-sonnet-4-6",
  systemPrompt: `You are DomBot Insights, an analytics assistant for the DomBot browser agent learning system.

DomBot runs browser-use agents that learn from each other's runs. Every completed run is logged.

You help users understand their agent performance:
- "How many runs have we done?"
- "What's the success rate on walmart.com?"
- "Show me recent failures"
- "Which tasks work best?"

Always call the relevant tool first. Present data cleanly with percentages and counts.`,

  tools: {
    get_recent_runs: tool({
      description:
        "Get recent DomBot agent runs, optionally filtered by domain",
      inputSchema: z.object({
        domain: z.string().optional().describe("Filter by domain"),
        limit: z.number().optional().default(10),
      }),
      execute: async ({ domain, limit }) => {
        const runs = (await convex.query("runs:listRecentRuns" as any, {
          domain,
          limit,
        })) as any[];

        if (!runs.length)
          return { content: [{ type: "text" as const, text: "No runs found." }] };

        const lines = runs.map(
          (r: any) =>
            `[${r.success ? "OK" : r.partial ? "PARTIAL" : "FAIL"}] ${r.task} (${r.domain}) — ${r.stepCount} steps`
        );
        return { content: [{ type: "text" as const, text: lines.join("\n") }] };
      },
    }),

    get_task_stats: tool({
      description: "Get aggregate statistics for all tracked tasks",
      inputSchema: z.object({}),
      execute: async () => {
        const stats = (await convex.query(
          "taskStats:listTaskStats" as any,
          {}
        )) as any[];

        if (!stats.length)
          return {
            content: [{ type: "text" as const, text: "No task data yet." }],
          };

        const lines = stats
          .sort((a: any, b: any) => b.runCount - a.runCount)
          .map((s: any) => {
            const rate =
              s.runCount > 0
                ? Math.round((s.successCount / s.runCount) * 100)
                : 0;
            return `${s.task} (${s.domain}): ${s.runCount} runs, ${rate}% success`;
          });
        return { content: [{ type: "text" as const, text: lines.join("\n") }] };
      },
    }),

    get_domain_summary: tool({
      description: "Get a summary of all runs for a specific domain",
      inputSchema: z.object({
        domain: z.string().describe("The domain to summarize"),
      }),
      execute: async ({ domain }) => {
        const runs = (await convex.query("runs:listRecentRuns" as any, {
          domain,
          limit: 100,
        })) as any[];

        if (!runs.length)
          return {
            content: [
              {
                type: "text" as const,
                text: `No runs found for ${domain}.`,
              },
            ],
          };

        const successRate = Math.round(
          (runs.filter((r: any) => r.success).length / runs.length) * 100
        );
        const avgSteps = Math.round(
          runs.reduce((sum: number, r: any) => sum + r.stepCount, 0) /
            runs.length
        );

        return {
          content: [
            {
              type: "text" as const,
              text: `${domain}: ${runs.length} runs, ${successRate}% success rate, avg ${avgSteps} steps/run`,
            },
          ],
        };
      },
    }),
  },
});
