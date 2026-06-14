import bcrypt from "bcryptjs";
import { Router } from "express";
import { unlinkSync } from "fs";
import multer from "multer";
import { join } from "path";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const usersRouter = Router();

const storage = multer.diskStorage({
  destination: "uploads/",
  filename: (_req, file, cb) => {
    const ext = file.originalname.split(".").pop() || "png";
    cb(null, `avatar_${Date.now()}.${ext}`);
  },
});
const upload = multer({ storage });

const updateUserSchema = z.object({
  nickname: z.string().trim().max(64).optional(),
});

const fitnessProfileSchema = z.object({
  age: z.number().int().min(13).max(100).nullable().optional(),
  heightCm: z.number().int().min(100).max(240).nullable().optional(),
  weightKg: z.number().min(30).max(250).nullable().optional(),
  goal: z.string().trim().min(1).max(64).default("general_fitness"),
  fitnessLevel: z.enum(["beginner", "intermediate", "advanced"]).default("beginner"),
  injuries: z.string().trim().max(255).nullable().optional(),
  equipment: z.array(z.string().trim().min(1).max(64)).max(20).default([]),
  preferredWorkoutTime: z.enum(["morning", "afternoon", "evening"]).nullable().optional(),
});

const changePasswordSchema = z.object({
  oldPassword: z.string().min(6),
  newPassword: z.string().min(6).max(128),
});

usersRouter.use(requireAuth);

usersRouter.get(
  "/me",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, account: true, nickname: true, createdAt: true },
    });
    
    if (!user) {
      throw new HttpError(404, "user not found");
    }
    
    ok(res, {
      id: user.id,
      account: user.account,
      username: user.account,
      nickname: user.nickname,
      createdAt: user.createdAt.toISOString(),
    });
  }),
);

usersRouter.put(
  "/me",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = updateUserSchema.parse(req.body);
    
    const data: any = {};
    if (body.nickname !== undefined) {
      data.nickname = body.nickname;
    }
    
    const user = await prisma.user.update({
      where: { id: userId },
      data,
      select: { id: true, account: true, nickname: true, createdAt: true },
    });
    
    ok(res, {
      id: user.id,
      account: user.account,
      username: user.account,
      nickname: user.nickname,
      createdAt: user.createdAt.toISOString(),
    }, "updated");
  }),
);

usersRouter.get(
  "/avatar",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { avatar: true },
    });

    if (!user) {
      throw new HttpError(404, "user not found");
    }

    ok(res, { avatar: user.avatar || "" });
  }),
);

usersRouter.post(
  "/avatar",
  upload.single("avatar"),
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    
    if (!req.file) {
      throw new HttpError(400, "avatar file is required");
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { avatar: true },
    });

    const oldAvatar = user?.avatar;
    if (oldAvatar && oldAvatar.startsWith("/uploads/")) {
      const oldPath = join(process.cwd(), oldAvatar);
      try {
        unlinkSync(oldPath);
      } catch {}
    }

    const avatarUrl = `/uploads/${req.file.filename}`;

    await prisma.user.update({
      where: { id: userId },
      data: { avatar: avatarUrl },
    });

    ok(res, { avatar: avatarUrl }, "avatar updated");
  }),
);

usersRouter.get(
  "/profile",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { id: true, account: true, nickname: true, avatar: true, createdAt: true },
    });

    if (!user) {
      throw new HttpError(404, "user not found");
    }

    ok(res, {
      id: user.id,
      account: user.account,
      username: user.account,
      nickname: user.nickname || "",
      avatar: user.avatar || "",
      createdAt: user.createdAt.toISOString(),
    });
  }),
);

usersRouter.put(
  "/profile",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = updateUserSchema.parse(req.body);

    const data: any = {};
    if (body.nickname !== undefined) {
      data.nickname = body.nickname;
      data.account = body.nickname;
    }

    const user = await prisma.user.update({
      where: { id: userId },
      data,
      select: { id: true, account: true, nickname: true, avatar: true, createdAt: true },
    });

    ok(res, {
      id: user.id,
      account: user.account,
      username: user.account,
      nickname: user.nickname || "",
      avatar: user.avatar || "",
      createdAt: user.createdAt.toISOString(),
    }, "profile updated");
  }),
);

usersRouter.get(
  "/fitness-profile",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const profile = await prisma.userFitnessProfile.findUnique({ where: { userId } });

    ok(res, {
      age: profile?.age ?? null,
      heightCm: profile?.heightCm ?? null,
      weightKg: profile?.weightKg ? Number(profile.weightKg) : null,
      goal: profile?.goal ?? "general_fitness",
      fitnessLevel: profile?.fitnessLevel ?? "beginner",
      injuries: profile?.injuries ?? "",
      equipment: Array.isArray(profile?.equipment) ? profile?.equipment : [],
      preferredWorkoutTime: profile?.preferredWorkoutTime ?? "evening",
    });
  }),
);

usersRouter.put(
  "/fitness-profile",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = fitnessProfileSchema.parse(req.body);
    const profile = await prisma.userFitnessProfile.upsert({
      where: { userId },
      update: {
        age: body.age,
        heightCm: body.heightCm,
        weightKg: body.weightKg,
        goal: body.goal,
        fitnessLevel: body.fitnessLevel,
        injuries: body.injuries,
        equipment: body.equipment,
        preferredWorkoutTime: body.preferredWorkoutTime,
      },
      create: {
        userId,
        age: body.age,
        heightCm: body.heightCm,
        weightKg: body.weightKg,
        goal: body.goal,
        fitnessLevel: body.fitnessLevel,
        injuries: body.injuries,
        equipment: body.equipment,
        preferredWorkoutTime: body.preferredWorkoutTime,
      },
    });

    ok(res, {
      age: profile.age,
      heightCm: profile.heightCm,
      weightKg: profile.weightKg ? Number(profile.weightKg) : null,
      goal: profile.goal,
      fitnessLevel: profile.fitnessLevel,
      injuries: profile.injuries ?? "",
      equipment: Array.isArray(profile.equipment) ? profile.equipment : [],
      preferredWorkoutTime: profile.preferredWorkoutTime,
    }, "updated");
  }),
);

usersRouter.put(
  "/me/password",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = changePasswordSchema.parse(req.body);

    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      throw new HttpError(404, "user not found");
    }

    const isPasswordValid = await bcrypt.compare(body.oldPassword, user.passwordHash);
    if (!isPasswordValid) {
      throw new HttpError(400, "old password is incorrect");
    }

    const newPasswordHash = await bcrypt.hash(body.newPassword, 10);

    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash: newPasswordHash },
    });

    ok(res, null, "password updated");
  }),
);

usersRouter.put(
  "/password",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const body = changePasswordSchema.parse(req.body);

    const user = await prisma.user.findUnique({ where: { id: userId } });
    if (!user) {
      throw new HttpError(404, "user not found");
    }

    const isPasswordValid = await bcrypt.compare(body.oldPassword, user.passwordHash);
    if (!isPasswordValid) {
      throw new HttpError(400, "old password is incorrect");
    }

    const newPasswordHash = await bcrypt.hash(body.newPassword, 10);

    await prisma.user.update({
      where: { id: userId },
      data: { passwordHash: newPasswordHash },
    });

    ok(res, null, "password updated");
  }),
);

usersRouter.delete(
  "/account",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;

    await prisma.user.delete({
      where: { id: userId },
    });

    ok(res, null, "account deleted");
  }),
);

usersRouter.get(
  "/theme",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { theme: true },
    });

    if (!user) {
      throw new HttpError(404, "user not found");
    }

    ok(res, { theme: user.theme || "light" });
  }),
);

usersRouter.put(
  "/theme",
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { mode } = req.body as { mode: string };

    if (!["light", "dark", "auto"].includes(mode)) {
      throw new HttpError(400, "invalid theme mode");
    }

    await prisma.user.update({
      where: { id: userId },
      data: { theme: mode },
    });

    ok(res, { theme: mode }, "theme updated");
  }),
);
