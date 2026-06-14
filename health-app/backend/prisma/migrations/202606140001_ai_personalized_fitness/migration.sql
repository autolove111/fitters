CREATE TYPE "MembershipTier" AS ENUM ('FREE', 'PRO');

CREATE TABLE "user_fitness_profiles" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "age" INTEGER,
    "height_cm" INTEGER,
    "weight_kg" DECIMAL(6,2),
    "goal" VARCHAR(64) NOT NULL DEFAULT 'general_fitness',
    "fitness_level" VARCHAR(32) NOT NULL DEFAULT 'beginner',
    "injuries" VARCHAR(255),
    "equipment" JSONB,
    "preferred_workout_time" VARCHAR(32),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_fitness_profiles_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "user_subscriptions" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "tier" "MembershipTier" NOT NULL DEFAULT 'FREE',
    "daily_ai_quota" INTEGER NOT NULL DEFAULT 3,
    "used_ai_quota" INTEGER NOT NULL DEFAULT 0,
    "quota_date" DATE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_subscriptions_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ai_plan_histories" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "membership_tier" "MembershipTier" NOT NULL DEFAULT 'FREE',
    "plan_type" VARCHAR(64) NOT NULL DEFAULT 'personalized_workout',
    "request" JSONB NOT NULL,
    "response" JSONB NOT NULL,
    "citations" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_plan_histories_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "user_fitness_profiles_user_id_key" ON "user_fitness_profiles"("user_id");
CREATE UNIQUE INDEX "user_subscriptions_user_id_key" ON "user_subscriptions"("user_id");
CREATE INDEX "idx_ai_plan_histories_user_created" ON "ai_plan_histories"("user_id", "created_at");

ALTER TABLE "user_fitness_profiles"
    ADD CONSTRAINT "user_fitness_profiles_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "user_subscriptions"
    ADD CONSTRAINT "user_subscriptions_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "ai_plan_histories"
    ADD CONSTRAINT "ai_plan_histories_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
