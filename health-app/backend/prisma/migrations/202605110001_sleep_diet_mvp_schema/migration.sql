ALTER TYPE "GoalType" ADD VALUE IF NOT EXISTS 'DAILY_SLEEP_HOURS';
ALTER TYPE "GoalType" ADD VALUE IF NOT EXISTS 'DAILY_DIET_CALORIES';

CREATE TABLE "sleep_records" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "record_date" DATE NOT NULL DEFAULT CURRENT_DATE,
    "duration_hours" DECIMAL(4,2),
    "deep_hours" DECIMAL(4,2),
    "bed_time" TIMESTAMP(3) NOT NULL,
    "wake_time" TIMESTAMP(3) NOT NULL,
    "quality_score" INTEGER NOT NULL DEFAULT 0,
    "notes" VARCHAR(255),
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sleep_records_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "sleep_records_duration_hours_check" CHECK ("duration_hours" IS NULL OR "duration_hours" > 0),
    CONSTRAINT "sleep_records_deep_hours_check" CHECK ("deep_hours" IS NULL OR "deep_hours" >= 0),
    CONSTRAINT "sleep_records_deep_lte_duration_check" CHECK ("duration_hours" IS NULL OR "deep_hours" IS NULL OR "deep_hours" <= "duration_hours"),
    CONSTRAINT "sleep_records_quality_score_check" CHECK ("quality_score" >= 0 AND "quality_score" <= 100)
);

CREATE TABLE "diet_records" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "type" VARCHAR(64) NOT NULL,
    "calories" INTEGER NOT NULL DEFAULT 0,
    "record_date" DATE NOT NULL,
    "notes" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "diet_records_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "diet_records_calories_check" CHECK ("calories" >= 0)
);

CREATE TABLE "foods" (
    "id" SERIAL NOT NULL,
    "name" VARCHAR(128) NOT NULL,
    "calories_kcal" INTEGER NOT NULL DEFAULT 0,
    "protein_grams" DECIMAL(6,2),
    "fat_grams" DECIMAL(6,2),
    "carb_grams" DECIMAL(6,2),
    "serving_grams" DECIMAL(6,2),
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "foods_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "foods_calories_kcal_check" CHECK ("calories_kcal" >= 0),
    CONSTRAINT "foods_protein_grams_check" CHECK ("protein_grams" IS NULL OR "protein_grams" >= 0),
    CONSTRAINT "foods_fat_grams_check" CHECK ("fat_grams" IS NULL OR "fat_grams" >= 0),
    CONSTRAINT "foods_carb_grams_check" CHECK ("carb_grams" IS NULL OR "carb_grams" >= 0),
    CONSTRAINT "foods_serving_grams_check" CHECK ("serving_grams" IS NULL OR "serving_grams" > 0)
);

CREATE TABLE "meals" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "meal_date" DATE NOT NULL,
    "meal_type" VARCHAR(32) NOT NULL,
    "notes" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "meals_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "meal_items" (
    "id" SERIAL NOT NULL,
    "meal_id" INTEGER NOT NULL,
    "food_id" INTEGER,
    "food_name" VARCHAR(128) NOT NULL,
    "quantity_grams" DECIMAL(8,2),
    "calories" INTEGER NOT NULL DEFAULT 0,
    "protein_grams" DECIMAL(6,2),
    "fat_grams" DECIMAL(6,2),
    "carb_grams" DECIMAL(6,2),
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "meal_items_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "meal_items_quantity_grams_check" CHECK ("quantity_grams" IS NULL OR "quantity_grams" > 0),
    CONSTRAINT "meal_items_calories_check" CHECK ("calories" >= 0),
    CONSTRAINT "meal_items_protein_grams_check" CHECK ("protein_grams" IS NULL OR "protein_grams" >= 0),
    CONSTRAINT "meal_items_fat_grams_check" CHECK ("fat_grams" IS NULL OR "fat_grams" >= 0),
    CONSTRAINT "meal_items_carb_grams_check" CHECK ("carb_grams" IS NULL OR "carb_grams" >= 0)
);

CREATE INDEX "idx_sleep_records_user_record_date" ON "sleep_records"("user_id", "record_date");
CREATE INDEX "idx_diet_records_user_record_date" ON "diet_records"("user_id", "record_date");
CREATE UNIQUE INDEX "foods_name_key" ON "foods"("name");
CREATE INDEX "idx_meals_user_meal_date" ON "meals"("user_id", "meal_date");
CREATE INDEX "idx_meal_items_meal_id" ON "meal_items"("meal_id");
CREATE INDEX "idx_meal_items_food_id" ON "meal_items"("food_id");

ALTER TABLE "sleep_records"
ADD CONSTRAINT "sleep_records_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "diet_records"
ADD CONSTRAINT "diet_records_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "meals"
ADD CONSTRAINT "meals_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "meal_items"
ADD CONSTRAINT "meal_items_meal_id_fkey"
FOREIGN KEY ("meal_id") REFERENCES "meals"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "meal_items"
ADD CONSTRAINT "meal_items_food_id_fkey"
FOREIGN KEY ("food_id") REFERENCES "foods"("id") ON DELETE SET NULL ON UPDATE CASCADE;
