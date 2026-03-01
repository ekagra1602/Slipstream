import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const upsertTaskStats = mutation({
  args: {
    task: v.string(),
    domain: v.string(),
    success: v.boolean(),
    nowMs: v.number(),
  },
  handler: async (ctx, { task, domain, success, nowMs }) => {
    const existing = await ctx.db
      .query("taskStats")
      .filter((q) =>
        q.and(q.eq(q.field("task"), task), q.eq(q.field("domain"), domain))
      )
      .first();

    if (existing) {
      await ctx.db.patch(existing._id, {
        runCount: existing.runCount + 1,
        successCount: existing.successCount + (success ? 1 : 0),
        lastRunAt: nowMs,
      });
    } else {
      await ctx.db.insert("taskStats", {
        task,
        domain,
        runCount: 1,
        successCount: success ? 1 : 0,
        lastRunAt: nowMs,
      });
    }
  },
});

export const listTaskStats = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("taskStats").collect();
  },
});
