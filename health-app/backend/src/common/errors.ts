import type { ErrorRequestHandler, NextFunction, Request, Response } from "express";
import type { ZodError } from "zod";

export class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function asyncHandler(
  handler: (req: Request, res: Response, next: NextFunction) => Promise<unknown>,
) {
  return (req: Request, res: Response, next: NextFunction) => {
    void handler(req, res, next).catch(next);
  };
}

export const errorHandler: ErrorRequestHandler = (error, _req, res, _next) => {
  if (error instanceof HttpError) {
    res.status(error.status).json({ code: error.status, message: error.message, data: null });
    return;
  }

  if (error?.name === "ZodError") {
    const zodError = error as ZodError;
    const errorMessages = zodError.errors.map(err => {
      const field = err.path.join('.');
      let message = err.message;
      if (err.code === 'too_small') {
        message = `${field}至少需要${err.minimum}个字符`;
      } else if (err.code === 'too_big') {
        message = `${field}最多允许${err.maximum}个字符`;
      } else if (err.code === 'invalid_type') {
        message = `${field}类型不正确`;
      }
      return message;
    });
    res.status(400).json({ code: 400, message: errorMessages.join(', '), data: zodError.errors });
    return;
  }

  console.error(error);
  res.status(500).json({ code: 500, message: "Internal server error", data: null });
};
