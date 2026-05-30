import bcrypt from "bcryptjs";
import { Router } from "express";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { requireAuth, type AuthenticatedRequest } from "../../middleware/auth.js";
import { prisma } from "../../prisma.js";

export const usersRouter = Router();

const updateUserSchema = z.object({
  nickname: z.string().trim().max(64).optional(),
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
  asyncHandler(async (req, res) => {
    const userId = (req as AuthenticatedRequest).userId;
    const { avatar } = req.body as { avatar: string };

    if (!avatar || typeof avatar !== "string") {
      throw new HttpError(400, "avatar data is required");
    }

    await prisma.user.update({
      where: { id: userId },
      data: { avatar },
    });

    ok(res, { avatar }, "avatar updated");
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
