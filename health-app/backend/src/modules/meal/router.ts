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
  if (typeof value === "bigint") return Number(value);
  if (typeof value === "number") return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function metadataObject(value: any): Record<string, any> {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function serializeMealItem(item: any) {
  const metadata = metadataObject(item.metadata);
  return {
    id: item.id,
    foodId: metadata.foodId ?? null,
    foodName: item.foodName,
    quantityGrams: toNumber(item.quantityGrams),
    calories: item.calories,
    proteinGrams: toNumber(item.proteinGrams),
    fatGrams: toNumber(item.fatGrams),
    carbGrams: toNumber(item.carbGrams),
  };
}

function serializeMeal(meal: any) {
  const date = formatDate(meal.recordDate);
  const items = meal.children || [];
  const totalCalories = items.reduce((sum: number, item: any) => sum + item.calories, 0);
  return {
    id: meal.id,
    mealType: meal.mealType || meal.type,
    mealDate: date,
    date,
    totalCalories,
    items: items.map(serializeMealItem),
    createdAt: meal.createdAt.toISOString(),
  };
}

async function findUserMeal(id: number, userId: number) {
  const meal = await prisma.dietRecord.findUnique({
    where: { id },
    include: { children: { where: { recordType: "meal_item" }, orderBy: { createdAt: "asc" } } },
  });
  if (!meal || meal.recordType !== "meal") {
    throw new HttpError(404, "meal not found");
  }
  if (meal.userId !== userId) {
    throw new HttpError(403, "cannot access another user's meal");
  }
  return meal;
}

function mealItemData(item: z.infer<typeof mealItemSchema>, userId: number, recordDate: Date, parentRecordId: number) {
  return {
    userId,
    parentRecordId,
    recordType: "meal_item",
    type: "meal_item",
    recordDate,
    foodName: item.foodName,
    quantityGrams: item.quantityGrams,
    calories: item.calories,
    proteinGrams: item.proteinGrams,
    fatGrams: item.fatGrams,
    carbGrams: item.carbGrams,
    metadata: item.foodId ? { foodId: item.foodId } : undefined,
  };
}

mealRouter.use(requireAuth);

mealRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { date } = req.query;

    const where: any = { userId, recordType: "meal" };
    if (date) {
      where.recordDate = dateOnly(String(date));
    }

    const meals = await prisma.dietRecord.findMany({
      where,
      include: { children: { where: { recordType: "meal_item" }, orderBy: { createdAt: "asc" } } },
      orderBy: [{ recordDate: "desc" }, { createdAt: "desc" }],
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

    const meal = await findUserMeal(id, userId);
    ok(res, serializeMeal(meal));
  }),
);

mealRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = mealSchema.parse(req.body);
    const mealDate = body.mealDate ? dateOnly(body.mealDate) : todayUtc();

    const meal = await prisma.$transaction(async (tx) => {
      const createdMeal = await tx.dietRecord.create({
        data: {
          userId,
          recordType: "meal",
          type: body.mealType,
          mealType: body.mealType,
          calories: 0,
          recordDate: mealDate,
        },
      });

      await tx.dietRecord.createMany({
        data: body.items.map((item) => mealItemData(item, userId, mealDate, createdMeal.id)),
      });

      return tx.dietRecord.findUnique({
        where: { id: createdMeal.id },
        include: { children: { where: { recordType: "meal_item" }, orderBy: { createdAt: "asc" } } },
      });
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

    await findUserMeal(id, userId);

    const updateSchema = z.object({
      mealType: z.string().trim().min(1).max(32).optional(),
      mealDate: z.string().optional(),
    });
    const body = updateSchema.parse(req.body);

    const data: any = {};
    if (body.mealType) {
      data.type = body.mealType;
      data.mealType = body.mealType;
    }
    if (body.mealDate) {
      data.recordDate = dateOnly(body.mealDate);
    }

    const updatedMeal = await prisma.dietRecord.update({
      where: { id },
      data,
      include: { children: { where: { recordType: "meal_item" }, orderBy: { createdAt: "asc" } } },
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

    await findUserMeal(id, userId);
    await prisma.dietRecord.delete({ where: { id } });
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

    const meal = await findUserMeal(id, userId);
    const body = mealItemSchema.parse(req.body);

    const item = await prisma.dietRecord.create({
      data: mealItemData(body, userId, meal.recordDate, id),
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

    await findUserMeal(id, userId);

    const item = await prisma.dietRecord.findUnique({ where: { id: itemId } });
    if (!item || item.recordType !== "meal_item" || item.parentRecordId !== id) {
      throw new HttpError(404, "meal item not found");
    }

    await prisma.dietRecord.delete({ where: { id: itemId } });
    ok(res, null, "deleted");
  }),
);
