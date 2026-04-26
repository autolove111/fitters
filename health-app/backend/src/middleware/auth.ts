import type { NextFunction, Request, Response } from "express";
import jwt from "jsonwebtoken";
import { env } from "../config/env.js";
import { HttpError } from "../common/errors.js";

export interface AuthenticatedRequest extends Request {
  userId: number;
}

interface JwtPayload {
  sub: string;
}

export function requireAuth(req: Request, _res: Response, next: NextFunction) {
  const authorization = req.header("Authorization") || "";
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : authorization.trim();

  if (!token) {
    next(new HttpError(401, "Missing authorization token"));
    return;
  }

  try {
    const payload = jwt.verify(token, env.jwtSecret) as JwtPayload;
    const userId = Number(payload.sub);
    if (!Number.isInteger(userId)) {
      throw new Error("invalid subject");
    }
    (req as AuthenticatedRequest).userId = userId;
    next();
  } catch {
    next(new HttpError(401, "Invalid or expired token"));
  }
}
