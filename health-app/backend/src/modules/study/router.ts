import { Router } from "express";
import { z } from "zod";
import { asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const studyRouter = Router();

const addPlanSchema = z.object({
  content: z.string().trim().min(1, "计划内容不能为空").max(500),
  start: z.string().trim().min(1, "开始时间不能为空"),
  end: z.string().trim().min(1, "结束时间不能为空"),
});

function serializePlan(plan: any) {
  return {
    id: plan.id,
    content: plan.content,
    startTime: plan.startTime.toISOString(),
    endTime: plan.endTime.toISOString(),
    status: plan.status,
    createdAt: plan.createdAt.toISOString(),
  };
}

studyRouter.use(requireAuth);

// GET /api/study/plans - 获取学习计划列表
studyRouter.get(
  "/plans",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const plans = await prisma.studyPlan.findMany({
      where: { userId },
      orderBy: { createdAt: "desc" },
    });
    ok(res, plans.map(serializePlan));
  }),
);

// POST /api/study/plans - 添加学习计划
studyRouter.post(
  "/plans",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = addPlanSchema.parse(req.body);

    const plan = await prisma.studyPlan.create({
      data: {
        userId,
        content: body.content,
        startTime: new Date(body.start),
        endTime: new Date(body.end),
      },
    });
    ok(res, serializePlan(plan), "created");
  }),
);
