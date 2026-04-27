import bcrypt from "bcryptjs";
import { Router } from "express";
import jwt from "jsonwebtoken";
import { z } from "zod";
import { HttpError, asyncHandler } from "../../common/errors.js";
import { ok } from "../../common/response.js";
import { env } from "../../config/env.js";
import { prisma } from "../../prisma.js";

export const authRouter = Router();

const authSchema = z.object({
  account: z.string().trim().min(3).max(64).optional(),
  username: z.string().trim().min(3).max(64).optional(),
  password: z.string().min(6).max(128),
  nickname: z.string().trim().max(64).optional(),
});

function publicUser(user: { id: number; account: string; nickname: string | null }) {
  return { id: user.id, account: user.account, username: user.account, nickname: user.nickname };
}

function signToken(userId: number) {
  const options: jwt.SignOptions = { subject: String(userId), expiresIn: env.jwtExpiresIn as jwt.SignOptions["expiresIn"] };
  return jwt.sign({}, env.jwtSecret, options);
}

authRouter.post(
  "/register",
  asyncHandler(async (req, res) => {
    const body = authSchema.parse(req.body);
    const account = body.account || body.username;
    if (!account) {
      throw new HttpError(400, "account is required");
    }

    const passwordHash = await bcrypt.hash(body.password, 10);
    try {
      const user = await prisma.user.create({
        data: { account, passwordHash, nickname: body.nickname || account },
        select: { id: true, account: true, nickname: true },
      });
      const token = signToken(user.id);
      ok(res, { token, user: publicUser(user) }, "registered");
    } catch (error: any) {
      if (error?.code === "P2002") {
        throw new HttpError(409, "account already exists");
      }
      throw error;
    }
  }),
);

authRouter.post(
  "/login",
  asyncHandler(async (req, res) => {
    const body = authSchema.parse(req.body);
    const account = body.account || body.username;
    if (!account) {
      throw new HttpError(400, "account is required");
    }

    const user = await prisma.user.findUnique({ where: { account } });
    if (!user || !(await bcrypt.compare(body.password, user.passwordHash))) {
      throw new HttpError(401, "invalid account or password");
    }

    const token = signToken(user.id);
    ok(res, { token, user: publicUser(user) }, "logged in");
  }),
);
