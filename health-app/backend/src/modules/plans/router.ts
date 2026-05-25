import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { env } from "../../config/env.js";
import { requireAuth } from "../../middleware/auth.js";

export const plansRouter = Router();

const todayWorkoutPlanSchema = z.object({
  days: z.number().int().min(1).max(30).default(7).optional(),
  goal: z.string().trim().min(1).max(64).optional(),
  availableMinutes: z.number().int().positive().max(240).optional(),
  preferredTime: z.enum(["morning", "afternoon", "evening"]).optional(),
  injuries: z.string().trim().max(255).optional(),
  equipment: z.array(z.string().trim().min(1).max(64)).max(20).optional(),
});

plansRouter.use(requireAuth);

plansRouter.post(
  "/today-workout",
  asyncHandler(async (req, res) => {
    const authorization = req.header("Authorization") || "";
    if (!authorization.trim()) {
      throw new HttpError(401, "Missing authorization token");
    }

    const body = todayWorkoutPlanSchema.parse(req.body);
    const response = await fetch(`${env.aiServiceUrl}/plans/today-workout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authorization,
        "X-Internal-Secret": env.aiServiceSecret,
      },
      body: JSON.stringify(body),
    });

    const payload = (await response.json().catch(() => null)) as
      | { code?: number; message?: string; data?: unknown }
      | null;

    if (!response.ok) {
      throw new HttpError(response.status, payload?.message || "AI service request failed");
    }

    ok(res, payload?.data ?? payload);
  }),
);
