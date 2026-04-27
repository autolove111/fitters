CREATE TYPE "GoalType" AS ENUM ('DAILY_WORKOUT_MINUTES');
CREATE TYPE "GoalPeriod" AS ENUM ('DAILY');

CREATE TABLE "users" (
    "id" SERIAL NOT NULL,
    "account" VARCHAR(64) NOT NULL,
    "password_hash" VARCHAR(255) NOT NULL,
    "nickname" VARCHAR(64),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "workout_records" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "type" VARCHAR(64) NOT NULL,
    "duration_min" INTEGER NOT NULL,
    "calories" INTEGER NOT NULL DEFAULT 0,
    "record_date" DATE NOT NULL,
    "notes" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "workout_records_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "goals" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "goal_type" "GoalType" NOT NULL,
    "target_value" INTEGER NOT NULL,
    "period" "GoalPeriod" NOT NULL DEFAULT 'DAILY',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "goals_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "users_account_key" ON "users"("account");
CREATE INDEX "idx_workout_records_user_record_date" ON "workout_records"("user_id", "record_date");
CREATE UNIQUE INDEX "uq_goals_user_type_period" ON "goals"("user_id", "goal_type", "period");

ALTER TABLE "workout_records"
ADD CONSTRAINT "workout_records_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "goals"
ADD CONSTRAINT "goals_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
