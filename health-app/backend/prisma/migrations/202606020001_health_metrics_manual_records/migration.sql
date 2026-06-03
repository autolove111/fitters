CREATE TYPE "DataSourceType" AS ENUM ('MANUAL', 'WECHAT_WERUN');

CREATE TYPE "MetricType" AS ENUM ('STEPS', 'HYDRATION', 'WEIGHT');

CREATE TYPE "SyncStatus" AS ENUM ('SUCCESS', 'FAILED');

ALTER TABLE "sleep_records"
ADD COLUMN "source_type" "DataSourceType" NOT NULL DEFAULT 'MANUAL',
ADD COLUMN "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE "daily_health_metrics" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "metric_type" "MetricType" NOT NULL,
    "record_date" DATE NOT NULL,
    "value" DECIMAL(12,2) NOT NULL,
    "unit" VARCHAR(16) NOT NULL,
    "source_type" "DataSourceType" NOT NULL,
    "measured_at" TIMESTAMP(3),
    "metadata" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "daily_health_metrics_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "daily_health_metrics_value_check" CHECK ("value" >= 0)
);

CREATE TABLE "health_sync_batches" (
    "id" SERIAL NOT NULL,
    "user_id" INTEGER NOT NULL,
    "source_type" "DataSourceType" NOT NULL,
    "status" "SyncStatus" NOT NULL,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(3),
    "imported_count" INTEGER NOT NULL DEFAULT 0,
    "skipped_count" INTEGER NOT NULL DEFAULT 0,
    "error_message" VARCHAR(500),
    "metadata" JSONB,

    CONSTRAINT "health_sync_batches_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "health_sync_batches_imported_count_check" CHECK ("imported_count" >= 0),
    CONSTRAINT "health_sync_batches_skipped_count_check" CHECK ("skipped_count" >= 0)
);

CREATE UNIQUE INDEX "uq_daily_health_metrics_user_metric_source_date"
ON "daily_health_metrics"("user_id", "metric_type", "source_type", "record_date");

CREATE INDEX "idx_daily_health_metrics_user_metric_date"
ON "daily_health_metrics"("user_id", "metric_type", "record_date");

CREATE INDEX "idx_health_sync_batches_user_source_started"
ON "health_sync_batches"("user_id", "source_type", "started_at");

ALTER TABLE "daily_health_metrics"
ADD CONSTRAINT "daily_health_metrics_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "health_sync_batches"
ADD CONSTRAINT "health_sync_batches_user_id_fkey"
FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
