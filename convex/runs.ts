import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const insertRun = mutation({
  args: {
    traceId: v.string(),
    task: v.string(),
    domain: v.string(),
    success: v.boolean(),
    partial: v.boolean(),
    stepCount: v.number(),
    successfulSteps: v.number(),
    failedSteps: v.number(),
    timestampMs: v.number(),
  },
  handler: async (ctx, args) => {
    await ctx.db.insert("runs", args);
  },
});

export const listRecentRuns = query({
  args: { limit: v.optional(v.number()), domain: v.optional(v.string()) },
  handler: async (ctx, { limit, domain }) => {
    const runs = await ctx.db.query("runs").order("desc").take(limit ?? 20);
    return domain ? runs.filter((r) => r.domain === domain) : runs;
  },
});
