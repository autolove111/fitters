import cors from "cors";
import express from "express";
import { authRouter } from "./modules/auth/router.js";
import { goalsRouter } from "./modules/goals/router.js";
import { statsRouter } from "./modules/stats/router.js";
import { workoutsRouter } from "./modules/workouts/router.js";
import { sleepRouter } from "./modules/sleep/router.js";
import { dietRouter } from "./modules/diet/router.js";
import { foodRouter } from "./modules/food/router.js";
import { mealRouter } from "./modules/meal/router.js";
import { usersRouter } from "./modules/users/router.js";
import { plansRouter } from "./modules/plans/router.js";
import { workRouter } from "./modules/work/router.js";
import { errorHandler } from "./common/errors.js";

export function createApp() {
  const app = express();

  app.use(cors());
  app.use(express.json());

  app.get("/api/health", (_req, res) => {
    res.json({ code: 0, message: "ok", data: { status: "ok", service: "backend" } });
  });

  app.use("/api/auth", authRouter);
  app.use("/api/users", usersRouter);
  app.use("/api/workouts", workoutsRouter);
  app.use("/api/goals", goalsRouter);
  app.use("/api/stats", statsRouter);
  app.use("/api/sleeps", sleepRouter);
  app.use("/api/diets", dietRouter);
  app.use("/api/foods", foodRouter);
  app.use("/api/meals", mealRouter);
  app.use("/api/plans", plansRouter);
  app.use("/api/work", workRouter);
  app.use(errorHandler);

  return app;
}