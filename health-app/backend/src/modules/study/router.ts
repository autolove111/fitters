import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const studyRouter = Router();

const studyPlanSchema = z.object({
  content: z.string().min(1).max(200),
  start: z.string().optional(),
  end: z.string().optional(),
});

function serializeStudyPlan(plan: any) {
  return {
    id: plan.id,
    userId: plan.userId,
    content: plan.title,
    start: plan.startTime?.toISOString(),
    end: plan.endTime?.toISOString(),
    completed: plan.completed,
    createdAt: plan.createdAt.toISOString(),
    updatedAt: plan.updatedAt.toISOString(),
  };
}

studyRouter.use(requireAuth);

studyRouter.get("/plans", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;

  const plans = await prisma.studyPlan.findMany({
    where: { userId },
    orderBy: { createdAt: "desc" },
  });

  ok(res, plans.map(serializeStudyPlan));
}));

studyRouter.post("/plans", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const body = studyPlanSchema.parse(req.body);

  const plan = await prisma.studyPlan.create({
    data: {
      userId,
      title: body.content,
      startTime: body.start ? new Date(body.start) : new Date(),
      endTime: body.end ? new Date(body.end) : null,
    },
  });

  ok(res, serializeStudyPlan(plan), "created");
}));

studyRouter.put("/plans/:planId", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const planId = parseInt(req.params.planId);
  const body = studyPlanSchema.partial().parse(req.body);

  const updateData: Record<string, any> = {};
  if (body.content) updateData.title = body.content;
  if (body.start) updateData.startTime = new Date(body.start);
  if (body.end) updateData.endTime = new Date(body.end);

  const plan = await prisma.studyPlan.update({
    where: { id: planId, userId },
    data: updateData,
  });

  ok(res, serializeStudyPlan(plan));
}));

studyRouter.delete("/plans/:planId", asyncHandler(async (req, res) => {
  const userId = (req as AuthenticatedRequest).userId;
  const planId = parseInt(req.params.planId);

  await prisma.studyPlan.delete({
    where: { id: planId, userId },
  });

  ok(res, { success: true });
}));
