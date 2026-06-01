import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";
import { dateOnly, formatDate, todayUtc } from "../../utils/dates.js";

export const dietRouter = Router();

const dietRecordSchema = z.object({
  mealType: z.string().trim().min(1).max(32).default("BREAKFAST"),
  recordDate: z.string().optional(),
  foodName: z.string().trim().min(1).max(128),
  quantityGrams: z.number().positive(),
  calories: z.number().int().min(0),
  proteinGrams: z.number().optional(),
  fatGrams: z.number().optional(),
  carbGrams: z.number().optional(),
  notes: z.string().trim().max(255).optional(),
  metadata: z.record(z.string(), z.any()).optional(),
});

function toNumber(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === 'bigint') return Number(value);
  if (typeof value === 'number') return value;
  if (value.toNumber) return value.toNumber();
  return Number(value);
}

function serializeDietRecord(record: any) {
  return {
    id: record.id,
    mealType: record.mealType,
    recordDate: formatDate(record.recordDate),
    date: formatDate(record.recordDate),
    foodName: record.foodName,
    quantityGrams: toNumber(record.quantityGrams),
    calories: record.calories,
    proteinGrams: toNumber(record.proteinGrams),
    fatGrams: toNumber(record.fatGrams),
    carbGrams: toNumber(record.carbGrams),
    notes: record.notes,
    metadata: record.metadata,
    createdAt: record.createdAt.toISOString(),
  };
}

dietRouter.use(requireAuth);

dietRouter.get(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { date, mealType } = req.query;

    const where: any = { userId };
    if (date) {
      where.recordDate = dateOnly(String(date));
    }
    if (mealType) {
      where.mealType = String(mealType);
    }

    const records = await prisma.dietRecord.findMany({
      where,
      orderBy: [{ recordDate: "desc" }, { createdAt: "desc" }],
    });

    ok(res, records.map(serializeDietRecord));
  }),
);

dietRouter.get(
  "/summary",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { date } = req.query;

    const where: any = { userId };
    if (date) {
      where.recordDate = dateOnly(String(date));
    }

    const records = await prisma.dietRecord.findMany({
      where,
      orderBy: { mealType: "asc" },
    });

    const byMealType = records.reduce((acc: any, record) => {
      const key = record.mealType;
      if (!acc[key]) {
        acc[key] = { items: [], totalCalories: 0 };
      }
      acc[key].items.push(serializeDietRecord(record));
      acc[key].totalCalories += record.calories;
      return acc;
    }, {});

    ok(res, byMealType);
  }),
);

dietRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);

    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }

    const record = await prisma.dietRecord.findUnique({
      where: { id },
    });

    if (!record) {
      throw new HttpError(404, "diet record not found");
    }

    if (record.userId !== userId) {
      throw new HttpError(403, "cannot access another user's diet record");
    }

    ok(res, serializeDietRecord(record));
  }),
);

dietRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = dietRecordSchema.parse(req.body);

    const recordDate = body.recordDate ? dateOnly(body.recordDate) : todayUtc();

    const record = await prisma.dietRecord.create({
      data: {
        userId,
        recordDate,
        mealType: body.mealType,
        foodName: body.foodName,
        quantityGrams: body.quantityGrams,
        calories: body.calories,
        proteinGrams: body.proteinGrams,
        fatGrams: body.fatGrams,
        carbGrams: body.carbGrams,
        notes: body.notes,
        metadata: body.metadata,
      },
    });

    ok(res, serializeDietRecord(record), "created");
  }),
);

dietRouter.put(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);

    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }

    const record = await prisma.dietRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "diet record not found");
    }

    if (record.userId !== userId) {
      throw new HttpError(403, "cannot modify another user's diet record");
    }

    const updateSchema = z.object({
      mealType: z.string().trim().min(1).max(32).optional(),
      recordDate: z.string().optional(),
      foodName: z.string().trim().min(1).max(128).optional(),
      quantityGrams: z.number().positive().optional(),
      calories: z.number().int().min(0).optional(),
      proteinGrams: z.number().optional(),
      fatGrams: z.number().optional(),
      carbGrams: z.number().optional(),
      notes: z.string().trim().max(255).optional(),
      metadata: z.record(z.string(), z.any()).optional(),
    });

    const body = updateSchema.parse(req.body);

    const data: any = {};
    if (body.mealType !== undefined) data.mealType = body.mealType;
    if (body.recordDate !== undefined) data.recordDate = dateOnly(body.recordDate);
    if (body.foodName !== undefined) data.foodName = body.foodName;
    if (body.quantityGrams !== undefined) data.quantityGrams = body.quantityGrams;
    if (body.calories !== undefined) data.calories = body.calories;
    if (body.proteinGrams !== undefined) data.proteinGrams = body.proteinGrams;
    if (body.fatGrams !== undefined) data.fatGrams = body.fatGrams;
    if (body.carbGrams !== undefined) data.carbGrams = body.carbGrams;
    if (body.notes !== undefined) data.notes = body.notes;
    if (body.metadata !== undefined) data.metadata = body.metadata;

    const updatedRecord = await prisma.dietRecord.update({
      where: { id },
      data,
    });

    ok(res, serializeDietRecord(updatedRecord), "updated");
  }),
);

dietRouter.delete(
  "/:id",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const id = Number(req.params.id);

    if (!Number.isInteger(id)) {
      throw new HttpError(400, "invalid diet record id");
    }

    const record = await prisma.dietRecord.findUnique({ where: { id } });
    if (!record) {
      throw new HttpError(404, "diet record not found");
    }

    if (record.userId !== userId) {
      throw new HttpError(403, "cannot delete another user's diet record");
    }

    await prisma.dietRecord.delete({ where: { id } });
    ok(res, null, "deleted");
  }),
);
