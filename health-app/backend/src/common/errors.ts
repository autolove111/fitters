import type { ErrorRequestHandler, NextFunction, Request, Response } from "express";

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
    res.status(400).json({ code: 400, message: "Invalid request parameters", data: error.errors });
    return;
  }

  console.error(error);
  res.status(500).json({ code: 500, message: "Internal server error", data: null });
};
