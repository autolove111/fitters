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
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "number") return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function serializeFood(food: any) {
  return {
    id: food.id,
    name: food.foodName,
    caloriesKcal: food.calories,
    proteinGrams: toNumber(food.proteinGrams),
    fatGrams: toNumber(food.fatGrams),
    carbGrams: toNumber(food.carbGrams),
    servingGrams: toNumber(food.quantityGrams),
    metadata: food.metadata,
    createdAt: food.createdAt.toISOString(),
  };
}

foodRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const body = foodSchema.parse(req.body);

    const existing = await prisma.dietRecord.findFirst({
      where: { recordType: "food_catalog", foodName: body.name },
    });
    if (existing) {
      throw new HttpError(409, "food already exists");
    }

    const food = await prisma.dietRecord.create({
      data: {
        userId: null,
        recordType: "food_catalog",
        type: "food_catalog",
        foodName: body.name,
        calories: body.caloriesKcal || 0,
        proteinGrams: body.proteinGrams,
        fatGrams: body.fatGrams,
        carbGrams: body.carbGrams,
        quantityGrams: body.servingGrams,
        recordDate: new Date(),
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

    const where: any = { recordType: "food_catalog" };
    if (name) {
      where.foodName = { contains: String(name), mode: "insensitive" };
    }

    const foods = await prisma.dietRecord.findMany({
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

    const food = await prisma.dietRecord.findUnique({ where: { id } });
    if (!food || food.recordType !== "food_catalog") {
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

    const food = await prisma.dietRecord.findUnique({ where: { id } });
    if (!food || food.recordType !== "food_catalog") {
      throw new HttpError(404, "food not found");
    }

    const body = foodSchema.partial().parse(req.body);

    const updatedFood = await prisma.dietRecord.update({
      where: { id },
      data: {
        foodName: body.name,
        calories: body.caloriesKcal,
        proteinGrams: body.proteinGrams,
        fatGrams: body.fatGrams,
        carbGrams: body.carbGrams,
        quantityGrams: body.servingGrams,
        metadata: body.metadata,
      },
    });

    ok(res, serializeFood(updatedFood), "updated");
  }),
);

foodRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid food id");
    }

    const food = await prisma.dietRecord.findUnique({ where: { id } });
    if (!food || food.recordType !== "food_catalog") {
      throw new HttpError(404, "food not found");
    }

    await prisma.dietRecord.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
