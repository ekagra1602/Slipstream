import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  runs: defineTable({
    traceId: v.string(),
    task: v.string(),
    domain: v.string(),
    success: v.boolean(),
    partial: v.boolean(),
    stepCount: v.number(),
    successfulSteps: v.number(),
    failedSteps: v.number(),
    timestampMs: v.number(),
  }),
  taskStats: defineTable({
    task: v.string(),
    domain: v.string(),
    runCount: v.number(),
    successCount: v.number(),
    lastRunAt: v.number(),
  }),
});
