# Fitters 数据库设计文档

> 数据库负责人：袁启泰
> 最后更新：2026-05-30
> 分支：`debug-zzj-5/28`

---

## 一、技术栈

| 项 | 选型 |
|----|------|
| 数据库 | PostgreSQL 16 (Docker: `postgres:16-alpine`) |
| ORM | Prisma 5.22 |
| 迁移工具 | Prisma Migrate |
| 后端 | Node.js 20 + TypeScript + Express |
| 数据库名 | `health_app`，schema `public` |

---

## 二、枚举类型

### GoalType（目标类型）

| 值 | 含义 |
|----|------|
| `DAILY_WORKOUT_MINUTES` | 每日运动目标（分钟） |
| `DAILY_SLEEP_HOURS` | 每日睡眠目标（小时） |
| `DAILY_DIET_CALORIES` | 每日饮食目标（热量） |

### GoalPeriod（目标周期）

| 值 | 含义 |
|----|------|
| `DAILY` | 每日目标 |

---

## 三、数据表（共 8 张）

### 3.1 users — 用户表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `account` | VARCHAR(64) | 是 | NOT NULL, UNIQUE |
| `password_hash` | VARCHAR(255) | 是 | NOT NULL |
| `nickname` | VARCHAR(64) | 否 | — |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP(3) | 是 | NOT NULL, 自动更新 |

**索引：**
- PK: `users_pkey` (`id`)
- UNIQUE: `users_account_key` (`account`)

---

### 3.2 workout_records — 运动记录表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `user_id` | INTEGER | 是 | FK → users(id) ON DELETE CASCADE |
| `type` | VARCHAR(64) | 是 | NOT NULL |
| `duration_min` | INTEGER | 是 | NOT NULL |
| `calories` | INTEGER | 是 | NOT NULL, DEFAULT 0 |
| `record_date` | DATE | 是 | NOT NULL |
| `notes` | VARCHAR(255) | 否 | — |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `workout_records_pkey` (`id`)
- COMPOSITE: `idx_workout_records_user_record_date` (`user_id`, `record_date`)

---

### 3.3 sleep_records — 睡眠记录表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `user_id` | INTEGER | 是 | FK → users(id) ON DELETE CASCADE |
| `record_date` | DATE | 是 | NOT NULL, DEFAULT CURRENT_DATE |
| `duration_hours` | DECIMAL(4,2) | 否 | CHECK: IS NULL OR > 0 |
| `sleep_time` | TIMESTAMP(3) | 是 | NOT NULL |
| `wake_time` | TIMESTAMP(3) | 是 | NOT NULL |
| `quality_score` | INTEGER | 是 | NOT NULL, DEFAULT 0, CHECK: 0 ≤ x ≤ 100 |
| `notes` | VARCHAR(255) | 否 | — |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `sleep_records_pkey` (`id`)
- COMPOSITE: `idx_sleep_records_user_record_date` (`user_id`, `record_date`)

---

### 3.4 diet_records — 饮食汇总记录表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `user_id` | INTEGER | 是 | FK → users(id) ON DELETE CASCADE |
| `type` | VARCHAR(64) | 是 | NOT NULL |
| `calories` | INTEGER | 是 | NOT NULL, DEFAULT 0, CHECK ≥ 0 |
| `record_date` | DATE | 是 | NOT NULL |
| `notes` | VARCHAR(255) | 否 | — |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `diet_records_pkey` (`id`)
- COMPOSITE: `idx_diet_records_user_record_date` (`user_id`, `record_date`)

---

### 3.5 foods — 食物库表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `name` | VARCHAR(128) | 是 | NOT NULL, UNIQUE |
| `calories_kcal` | INTEGER | 是 | NOT NULL, DEFAULT 0, CHECK ≥ 0 |
| `protein_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `fat_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `carb_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `serving_grams` | DECIMAL(6,2) | 否 | CHECK > 0 |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `foods_pkey` (`id`)
- UNIQUE: `foods_name_key` (`name`)

---

### 3.6 meals — 餐次表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `user_id` | INTEGER | 是 | FK → users(id) ON DELETE CASCADE |
| `meal_date` | DATE | 是 | NOT NULL |
| `meal_type` | VARCHAR(32) | 是 | NOT NULL |
| `notes` | VARCHAR(255) | 否 | — |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `meals_pkey` (`id`)
- COMPOSITE: `idx_meals_user_meal_date` (`user_id`, `meal_date`)

---

### 3.7 meal_items — 餐次明细表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `meal_id` | INTEGER | 是 | FK → meals(id) ON DELETE CASCADE |
| `food_id` | INTEGER | 否 | FK → foods(id) ON DELETE SET NULL |
| `food_name` | VARCHAR(128) | 是 | NOT NULL |
| `quantity_grams` | DECIMAL(8,2) | 否 | CHECK > 0 |
| `calories` | INTEGER | 是 | NOT NULL, DEFAULT 0, CHECK ≥ 0 |
| `protein_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `fat_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `carb_grams` | DECIMAL(6,2) | 否 | CHECK ≥ 0 |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |

**索引：**
- PK: `meal_items_pkey` (`id`)
- `idx_meal_items_meal_id` (`meal_id`)
- `idx_meal_items_food_id` (`food_id`)

---

### 3.8 goals — 健康目标表

| 字段 | 数据库类型 | 必填 | 约束 |
|------|-----------|------|------|
| `id` | SERIAL INTEGER | 是 | PRIMARY KEY |
| `user_id` | INTEGER | 是 | FK → users(id) ON DELETE CASCADE |
| `goal_type` | ENUM (GoalType) | 是 | NOT NULL |
| `target_value` | INTEGER | 是 | NOT NULL |
| `period` | ENUM (GoalPeriod) | 是 | NOT NULL, DEFAULT DAILY |
| `created_at` | TIMESTAMP(3) | 是 | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP(3) | 是 | NOT NULL, 自动更新 |

**索引：**
- PK: `goals_pkey` (`id`)
- UNIQUE COMPOSITE: `uq_goals_user_type_period` (`user_id`, `goal_type`, `period`)

---

## 四、ER 关系图

```
┌──────────┐
│  users   │
└────┬─────┘
     │ 1
     │
     ├──< workout_records    (user_id → users.id, CASCADE)
     ├──< sleep_records      (user_id → users.id, CASCADE)
     ├──< diet_records       (user_id → users.id, CASCADE)
     ├──< meals              (user_id → users.id, CASCADE)
     ├──< goals              (user_id → users.id, CASCADE)

┌──────────┐     ┌────────────┐
│  meals   │────<│ meal_items │
└──────────┘  1  └─────┬──────┘
                      * │
                        │  0..1
                 ┌──────┴──────┐
                 │    foods    │
                 └─────────────┘

meal_items.meal_id  → meals.id  (CASCADE)
meal_items.food_id  → foods.id  (SET NULL)
```

---

## 五、待办事项

- [ ] 执行数据库迁移：`npx prisma migrate dev`
- [ ] 后续阶段：健康报告、智能建议、提醒、审计日志表

---

*最后更新：2026-05-30 - 精简数据库表，移除未使用字段*

---

## 修改记录

### 2026-05-30 修改内容

**精简内容：**

| 表名 | 精简项 | 原字段 | 原因 |
|------|--------|--------|------|
| sleep_records | 移除 `deep_hours` | DECIMAL(4,2) | 无代码引用 |
| sleep_records | 移除 `metadata` | JSONB | 无代码引用 |
| foods | 移除 `metadata` | JSONB | 无代码引用 |
| meal_items | 移除 `metadata` | JSONB | 无代码引用 |

**数据表数量变更：**
- 13张 → 8张（移除文档中未实现的表，保留实际代码中存在的表）
- 字段精简：移除4个未使用的字段
