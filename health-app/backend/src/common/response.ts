import type { Response } from "express";

export function ok<T>(res: Response, data: T, message = "ok") {
  return res.json({ code: 0, message, data });
}
