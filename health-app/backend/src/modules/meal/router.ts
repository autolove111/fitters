import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { dateOnly, formatDate, todayUtc } from "../../utils/dates.js";

export const mealRouter = Router();

const mealItemSchema = z.object({
  foodId: z.number().int().positive().optional(),
  foodName: z.string().trim().min(1).max(128),
  quantityGrams: z.number().positive(),
  calories: z.number().int().min(0),
  proteinGrams: z.number().optional(),
  fatGrams: z.number().optional(),
  carbGrams: z.number().optional(),
});

const mealSchema = z.object({
  mealType: z.string().trim().min(1).max(32).default("BREAKFAST"),
  mealDate: z.string().optional(),
  items: z.array(mealItemSchema).min(1),
});

function toNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'number') return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function serializeMealItem(item: any) {
  return {
    id: item.id,
    foodId: item.foodId,
    foodName: item.foodName,
    quantityGrams: toNumber(item.quantityGrams),
    calories: item.calories,
    proteinGrams: toNumber(item.proteinGrams),
    fatGrams: toNumber(item.fatGrams),
    carbGrams: toNumber(item.carbGrams),
  };
}

function serializeMeal(meal: any) {
  const date = formatDate(meal.mealDate);
  const totalCalories = meal.items?.reduce((sum: number, item: any) => sum + item.calories, 0) || 0;
  return {
    id: meal.id,
    mealType: meal.mealType,
    mealDate: date,
    date,
    totalCalories,
    items: meal.items?.map(serializeMealItem) || [],
    createdAt: meal.createdAt.toISOString(),
  };
}

mealRouter.use(requireAuth);

mealRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { date } = req.query;
    
    const where: any = { userId };
    if (date) {
      where.mealDate = dateOnly(String(date));
    }
    
    const meals = await prisma.meal.findMany({
      where,
      include: { items: true },
      orderBy: [{ mealDate: "desc" }, { createdAt: "desc" }],
    });
    
    ok(res, meals.map(serializeMeal));
  }),
);

mealRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid meal id");
    }
    
    const meal = await prisma.meal.findUnique({
      where: { id },
      include: { items: true },
    });
    
    if (!meal) {
      throw new HttpError(404, "meal not found");
    }
    
    if (meal.userId !== userId) {
      throw new HttpError(403, "cannot access another user's meal");
    }
    
    ok(res, serializeMeal(meal));
  }),
);

mealRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = mealSchema.parse(req.body);
    
    const mealDate = body.mealDate ? dateOnly(body.mealDate) : todayUtc();
    
    const meal = await prisma.meal.create({
      data: {
        userId,
        mealType: body.mealType,
        mealDate,
        items: {
          create: body.items.map((item: any) => ({
            foodId: item.foodId,
            foodName: item.foodName,
            quantityGrams: item.quantityGrams,
            calories: item.calories,
            proteinGrams: item.proteinGrams,
            fatGrams: item.fatGrams,
            carbGrams: item.carbGrams,
          })),
        },
      },
      include: { items: true },
    });
    
    ok(res, serializeMeal(meal), "created");
  }),
);

mealRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid meal id");
    }
    
    const meal = await prisma.meal.findUnique({ where: { id } });
    if (!meal) {
      throw new HttpError(404, "meal not found");
    }
    
    if (meal.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's meal");
    }
    
    const updateSchema = z.object({
      mealType: z.string().trim().min(1).max(32).optional(),
      mealDate: z.string().optional(),
    });
    
    const body = updateSchema.parse(req.body);
    
    const data: any = {};
    if (body.mealType) {
      data.mealType = body.mealType;
    }
    if (body.mealDate) {
      data.mealDate = dateOnly(body.mealDate);
    }
    
    const updatedMeal = await prisma.meal.update({
      where: { id },
      data,
      include: { items: true },
    });
    
    ok(res, serializeMeal(updatedMeal), "updated");
  }),
);

mealRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid meal id");
    }
    
    const meal = await prisma.meal.findUnique({ where: { id } });
    if (!meal) {
      throw new HttpError(404, "meal not found");
    }
    
    if (meal.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's meal");
    }
    
    await prisma.meal.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);

mealRouter.post(
  "/:id/items",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    
    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid meal id");
    }
    
    const meal = await prisma.meal.findUnique({ where: { id } });
    if (!meal) {
      throw new HttpError(404, "meal not found");
    }
    
    if (meal.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's meal");
    }
    
    const body = mealItemSchema.parse(req.body);
    
    const item = await prisma.mealItem.create({
      data: {
        mealId: id,
        foodId: body.foodId,
        foodName: body.foodName,
        quantityGrams: body.quantityGrams,
        calories: body.calories,
        proteinGrams: body.proteinGrams,
        fatGrams: body.fatGrams,
        carbGrams: body.carbGrams,
      },
    });
    
    ok(res, serializeMealItem(item), "created");
  }),
);

mealRouter.delete(
  "/:id/items/:itemId",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);
    const itemId = Number(req.params.itemId);
    
    if (!Number.isInteger(id) || !Number.isInteger(itemId)) {
      throw new HttpError(400, "invalid meal or item id");
    }
    
    const meal = await prisma.meal.findUnique({ where: { id } });
    if (!meal) {
      throw new HttpError(404, "meal not found");
    }
    
    if (meal.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's meal");
    }
    
    const item = await prisma.mealItem.findUnique({ where: { id: itemId } });
    if (!item || item.mealId !== id) {
      throw new HttpError(404, "meal item not found");
    }
    
    await prisma.mealItem.delete({ where: { id: itemId } });
    ok(res, null, "deleted");
  }),
);
