ALTER TABLE "workout_records"
ADD COLUMN IF NOT EXISTS "steps" INTEGER,
ADD COLUMN IF NOT EXISTS "source_type" VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS "metadata" JSONB,
ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE "sleep_records"
ADD COLUMN IF NOT EXISTS "source_type" VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE "sleep_records"
ALTER COLUMN "source_type" DROP DEFAULT;

ALTER TABLE "sleep_records"
ALTER COLUMN "source_type" TYPE VARCHAR(32) USING "source_type"::TEXT;

ALTER TABLE "sleep_records"
ALTER COLUMN "source_type" SET DEFAULT 'MANUAL';

ALTER TABLE "diet_records"
ADD COLUMN IF NOT EXISTS "record_type" VARCHAR(32) NOT NULL DEFAULT 'diet',
ADD COLUMN IF NOT EXISTS "parent_record_id" INTEGER,
ADD COLUMN IF NOT EXISTS "food_name" VARCHAR(128),
ADD COLUMN IF NOT EXISTS "meal_type" VARCHAR(32),
ADD COLUMN IF NOT EXISTS "quantity_grams" DECIMAL(8,2),
ADD COLUMN IF NOT EXISTS "protein_grams" DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS "fat_grams" DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS "carb_grams" DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS "amount_ml" INTEGER,
ADD COLUMN IF NOT EXISTS "weight_kg" DECIMAL(6,2),
ADD COLUMN IF NOT EXISTS "source_type" VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
ADD COLUMN IF NOT EXISTS "metadata" JSONB,
ADD COLUMN IF NOT EXISTS "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE "diet_records"
ALTER COLUMN "user_id" DROP NOT NULL;

CREATE TABLE IF NOT EXISTS "work_records" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "record_type" VARCHAR(32) NOT NULL,
    "type" VARCHAR(32),
    "record_date" DATE NOT NULL DEFAULT CURRENT_DATE,
    "start_time" TIMESTAMP(3),
    "end_time" TIMESTAMP(3),
    "duration_minutes" INTEGER DEFAULT 0,
    "content" VARCHAR(255),
    "completed" BOOLEAN NOT NULL DEFAULT false,
    "settings" JSONB,
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "work_records_pkey" PRIMARY KEY ("id")
);

INSERT INTO "workout_records" (
    "user_id", "type", "duration_min", "calories", "steps", "source_type",
    "record_date", "notes", "metadata", "created_at", "updated_at"
)
SELECT
    "user_id",
    'wechat_steps',
    0,
    0,
    "value"::INTEGER,
    "source_type"::TEXT,
    "record_date",
    'migrated from daily_health_metrics',
    COALESCE("metadata", '{}'::JSONB) || jsonb_build_object('oldMetricId', "id", 'unit', "unit", 'metricType', "metric_type"::TEXT),
    "created_at",
    "updated_at"
FROM "daily_health_metrics"
WHERE to_regclass('public.daily_health_metrics') IS NOT NULL
  AND "metric_type"::TEXT = 'STEPS'
  AND NOT EXISTS (
    SELECT 1
    FROM "workout_records" wr
    WHERE wr."user_id" = "daily_health_metrics"."user_id"
      AND wr."type" = 'wechat_steps'
      AND wr."source_type" = "daily_health_metrics"."source_type"::TEXT
      AND wr."record_date" = "daily_health_metrics"."record_date"
  );

INSERT INTO "diet_records" (
    "user_id", "record_type", "type", "calories", "record_date",
    "amount_ml", "source_type", "notes", "metadata", "created_at", "updated_at"
)
SELECT
    "user_id",
    'hydration',
    'hydration',
    0,
    "record_date",
    "value"::INTEGER,
    "source_type"::TEXT,
    'migrated from daily_health_metrics',
    COALESCE("metadata", '{}'::JSONB) || jsonb_build_object('oldMetricId', "id", 'unit', "unit", 'metricType', "metric_type"::TEXT),
    "created_at",
    "updated_at"
FROM "daily_health_metrics"
WHERE to_regclass('public.daily_health_metrics') IS NOT NULL
  AND "metric_type"::TEXT = 'HYDRATION';

INSERT INTO "diet_records" (
    "user_id", "record_type", "type", "calories", "record_date",
    "weight_kg", "source_type", "notes", "metadata", "created_at", "updated_at"
)
SELECT
    "user_id",
    'weight',
    'weight',
    0,
    "record_date",
    "value",
    "source_type"::TEXT,
    'migrated from daily_health_metrics',
    COALESCE("metadata", '{}'::JSONB) || jsonb_build_object('oldMetricId', "id", 'unit', "unit", 'metricType', "metric_type"::TEXT),
    "created_at",
    "updated_at"
FROM "daily_health_metrics"
WHERE to_regclass('public.daily_health_metrics') IS NOT NULL
  AND "metric_type"::TEXT = 'WEIGHT';

INSERT INTO "workout_records" (
    "user_id", "type", "duration_min", "calories", "source_type",
    "record_date", "notes", "metadata", "created_at", "updated_at"
)
SELECT
    "user_id",
    'wechat_steps_sync',
    0,
    0,
    "source_type"::TEXT,
    ("started_at" AT TIME ZONE 'UTC')::DATE,
    "error_message",
    COALESCE("metadata", '{}'::JSONB) || jsonb_build_object(
      'oldSyncBatchId', "id",
      'status', "status"::TEXT,
      'startedAt', "started_at",
      'finishedAt', "finished_at",
      'importedCount', "imported_count",
      'skippedCount', "skipped_count"
    ),
    "started_at",
    COALESCE("finished_at", "started_at")
FROM "health_sync_batches"
WHERE to_regclass('public.health_sync_batches') IS NOT NULL;

INSERT INTO "diet_records" (
    "user_id", "record_type", "type", "calories", "record_date",
    "food_name", "quantity_grams", "protein_grams", "fat_grams", "carb_grams",
    "metadata", "created_at", "updated_at"
)
SELECT
    NULL,
    'food_catalog',
    'food_catalog',
    f."calories_kcal",
    CURRENT_DATE,
    f."name",
    f."serving_grams",
    f."protein_grams",
    f."fat_grams",
    f."carb_grams",
    COALESCE(f."metadata", '{}'::JSONB) || jsonb_build_object('oldFoodId', f."id"),
    f."created_at",
    CURRENT_TIMESTAMP
FROM "foods" f
WHERE NOT EXISTS (
    SELECT 1
    FROM "diet_records" d
    WHERE d."record_type" = 'food_catalog' AND d."food_name" = f."name"
);

INSERT INTO "diet_records" (
    "user_id", "record_type", "type", "calories", "record_date",
    "meal_type", "notes", "metadata", "created_at", "updated_at"
)
SELECT
    m."user_id",
    'meal',
    m."meal_type",
    0,
    m."meal_date",
    m."meal_type",
    m."notes",
    jsonb_build_object('oldMealId', m."id"),
    m."created_at",
    CURRENT_TIMESTAMP
FROM "meals" m
WHERE NOT EXISTS (
    SELECT 1
    FROM "diet_records" d
    WHERE d."record_type" = 'meal' AND (d."metadata"->>'oldMealId')::INTEGER = m."id"
);

INSERT INTO "diet_records" (
    "user_id", "record_type", "type", "calories", "record_date",
    "parent_record_id", "food_name", "quantity_grams", "protein_grams",
    "fat_grams", "carb_grams", "metadata", "created_at", "updated_at"
)
SELECT
    m."user_id",
    'meal_item',
    'meal_item',
    mi."calories",
    m."meal_date",
    parent_meal."id",
    mi."food_name",
    mi."quantity_grams",
    mi."protein_grams",
    mi."fat_grams",
    mi."carb_grams",
    COALESCE(mi."metadata", '{}'::JSONB) || jsonb_build_object(
      'oldMealItemId', mi."id",
      'oldFoodId', mi."food_id",
      'foodId', catalog_food."id"
    ),
    mi."created_at",
    CURRENT_TIMESTAMP
FROM "meal_items" mi
JOIN "meals" m ON m."id" = mi."meal_id"
JOIN "diet_records" parent_meal
  ON parent_meal."record_type" = 'meal'
 AND (parent_meal."metadata"->>'oldMealId')::INTEGER = m."id"
LEFT JOIN "foods" f ON f."id" = mi."food_id"
LEFT JOIN "diet_records" catalog_food
  ON catalog_food."record_type" = 'food_catalog'
 AND catalog_food."food_name" = COALESCE(f."name", mi."food_name");

DO $$
BEGIN
  IF to_regclass('public.work_settings') IS NOT NULL THEN
    EXECUTE $SQL$
      INSERT INTO "work_records" (
        "user_id", "record_type", "record_date", "settings", "created_at", "updated_at"
      )
      SELECT
        "user_id",
        'settings',
        CURRENT_DATE,
        to_jsonb(ws) - 'id' - 'user_id' - 'created_at' - 'updated_at',
        "created_at",
        "updated_at"
      FROM "work_settings" ws
    $SQL$;
  END IF;

  IF to_regclass('public.work_sessions') IS NOT NULL THEN
    EXECUTE $SQL$
      INSERT INTO "work_records" (
        "user_id", "record_type", "type", "record_date", "start_time", "end_time",
        "duration_minutes", "created_at", "updated_at"
      )
      SELECT
        "user_id",
        'session',
        "type",
        ("start_time" AT TIME ZONE 'UTC')::DATE,
        "start_time",
        "end_time",
        "duration",
        "created_at",
        CURRENT_TIMESTAMP
      FROM "work_sessions"
    $SQL$;
  END IF;

  IF to_regclass('public.work_todos') IS NOT NULL THEN
    EXECUTE $SQL$
      INSERT INTO "work_records" (
        "user_id", "record_type", "record_date", "content", "completed", "created_at", "updated_at"
      )
      SELECT
        "user_id",
        'todo',
        "todo_date",
        "content",
        "completed",
        "created_at",
        CURRENT_TIMESTAMP
      FROM "work_todos"
    $SQL$;
  END IF;

  IF to_regclass('public.sedentary_responses') IS NOT NULL THEN
    EXECUTE $SQL$
      INSERT INTO "work_records" (
        "user_id", "record_type", "record_date", "start_time", "created_at", "updated_at"
      )
      SELECT
        "user_id",
        'sedentary_response',
        ("responded_at" AT TIME ZONE 'UTC')::DATE,
        "responded_at",
        "responded_at",
        "responded_at"
      FROM "sedentary_responses"
    $SQL$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS "idx_diet_records_record_type" ON "diet_records"("record_type");
CREATE INDEX IF NOT EXISTS "idx_diet_records_parent_record_id" ON "diet_records"("parent_record_id");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_diet_records_food_catalog_name"
ON "diet_records"("food_name")
WHERE "record_type" = 'food_catalog' AND "food_name" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "idx_work_records_user_type_date" ON "work_records"("user_id", "record_type", "record_date");
CREATE INDEX IF NOT EXISTS "idx_work_records_user_start" ON "work_records"("user_id", "start_time");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_work_records_user_settings"
ON "work_records"("user_id")
WHERE "record_type" = 'settings';

CREATE UNIQUE INDEX IF NOT EXISTS "uq_workout_records_user_wechat_steps_date"
ON "workout_records"("user_id", "record_date")
WHERE "type" = 'wechat_steps' AND "source_type" = 'WECHAT_WERUN';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'diet_records_parent_record_id_fkey'
  ) THEN
    ALTER TABLE "diet_records"
    ADD CONSTRAINT "diet_records_parent_record_id_fkey"
    FOREIGN KEY ("parent_record_id") REFERENCES "diet_records"("id") ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'work_records_user_id_fkey'
  ) THEN
    ALTER TABLE "work_records"
    ADD CONSTRAINT "work_records_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'workout_records_steps_check'
  ) THEN
    ALTER TABLE "workout_records"
    ADD CONSTRAINT "workout_records_steps_check" CHECK ("steps" IS NULL OR "steps" >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'work_records_duration_minutes_check'
  ) THEN
    ALTER TABLE "work_records"
    ADD CONSTRAINT "work_records_duration_minutes_check" CHECK ("duration_minutes" IS NULL OR "duration_minutes" >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'diet_records_amount_ml_check'
  ) THEN
    ALTER TABLE "diet_records"
    ADD CONSTRAINT "diet_records_amount_ml_check" CHECK ("amount_ml" IS NULL OR "amount_ml" >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'diet_records_weight_kg_check'
  ) THEN
    ALTER TABLE "diet_records"
    ADD CONSTRAINT "diet_records_weight_kg_check" CHECK ("weight_kg" IS NULL OR "weight_kg" >= 0);
  END IF;
END $$;

DROP TABLE IF EXISTS "health_sync_batches";
DROP TABLE IF EXISTS "daily_health_metrics";
DROP TABLE IF EXISTS "meal_items";
DROP TABLE IF EXISTS "meals";
DROP TABLE IF EXISTS "foods";
DROP TABLE IF EXISTS "sedentary_responses";
DROP TABLE IF EXISTS "work_todos";
DROP TABLE IF EXISTS "work_sessions";
DROP TABLE IF EXISTS "work_settings";

DROP TYPE IF EXISTS "SyncStatus";
DROP TYPE IF EXISTS "MetricType";
DROP TYPE IF EXISTS "DataSourceType";
