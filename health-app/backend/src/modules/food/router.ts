import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { prisma } from "../../prisma.js";

export const foodRouter = Router();

const foodSchema = z.object({
  name: z.string().trim().min(1).max(128),
  caloriesKcal: z.number().int().min(0).optional(),
  proteinGrams: z.number().optional(),
  fatGrams: z.number().optional(),
  carbGrams: z.number().optional(),
  servingGrams: z.number().positive().optional(),
  metadata: z.record(z.any()).optional(),
});

function toNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'number') return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function serializeFood(food: any) {
  return {
    id: food.id,
    name: food.name,
    caloriesKcal: food.caloriesKcal,
    proteinGrams: toNumber(food.proteinGrams),
    fatGrams: toNumber(food.fatGrams),
    carbGrams: toNumber(food.carbGrams),
    servingGrams: toNumber(food.servingGrams),
    metadata: food.metadata,
    createdAt: food.createdAt.toISOString(),
  };
}

foodRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const body = foodSchema.parse(req.body);
    
    const food = await prisma.food.create({
      data: {
        name: body.name,
        caloriesKcal: body.caloriesKcal || 0,
        proteinGrams: body.proteinGrams,
        fatGrams: body.fatGrams,
        carbGrams: body.carbGrams,
        servingGrams: body.servingGrams,
        metadata: body.metadata,
      },
    });
    
    ok(res, serializeFood(food), "created");
  }),
);

foodRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const { name, limit = 20, offset = 0 } = req.query;
    
    const where: any = {};
    if (name) {
      where.name = { contains: String(name), mode: "insensitive" };
    }
    
    const foods = await prisma.food.findMany({
      where,
      orderBy: { createdAt: "desc" },
      take: Number(limit),
      skip: Number(offset),
    });
    
    ok(res, foods.map(serializeFood));
  }),
);

foodRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid food id");
    }
    
    const food = await prisma.food.findUnique({ where: { id } });
    if (!food) {
      throw new HttpError(404, "food not found");
    }
    
    ok(res, serializeFood(food));
  }),
);

foodRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid food id");
    }
    
    const body = foodSchema.partial().parse(req.body);
    
    const food = await prisma.food.update({
      where: { id },
      data: {
        ...body,
        caloriesKcal: body.caloriesKcal ?? undefined,
      },
    });
    
    ok(res, serializeFood(food), "updated");
  }),
);

foodRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid food id");
    }
    
    const food = await prisma.food.findUnique({ where: { id } });
    if (!food) {
      throw new HttpError(404, "food not found");
    }
    
    await prisma.food.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
