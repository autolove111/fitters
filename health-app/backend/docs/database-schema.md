# Fitters 数据库设计文档

最后更新：2026-06-02  
当前目标：只保留 6 张业务表，所有旧功能数据合并存储。

## 技术栈

| 项目 | 选型 |
| --- | --- |
| 数据库 | PostgreSQL 16 |
| ORM | Prisma 5.22 |
| 迁移工具 | Prisma Migrate |
| 后端 | Node.js + TypeScript + Express |

## 业务表总览

| 序号 | 表名 | 说明 |
| --- | --- | --- |
| 1 | `users` | 用户表 |
| 2 | `workout_records` | 运动记录表，包含手动运动和微信步数 |
| 3 | `goals` | 目标表 |
| 4 | `sleep_records` | 睡眠记录表 |
| 5 | `diet_records` | 饮食整合表，包含原饮食、食物库、餐次、餐次明细、饮水、体重 |
| 6 | `work_records` | 工作整合表，包含原工作设置、工作会话、待办、久坐响应 |

`_prisma_migrations` 是 Prisma 迁移历史表，不计入业务表。

## 合并规则

### workout_records

- 手动运动记录保持原结构。
- 微信步数记录写入本表：
  - `type = 'wechat_steps'`
  - `source_type = 'WECHAT_WERUN'`
  - `steps` 保存步数
  - `duration_min = 0`
  - `calories = 0`
- 微信步数同一用户同一天只允许一条记录，由部分唯一索引 `uq_workout_records_user_wechat_steps_date` 约束。
- 普通运动统计必须排除 `type in ('wechat_steps', 'wechat_steps_sync')`。

### diet_records

通过 `record_type` 区分整合数据：

| record_type | 含义 |
| --- | --- |
| `diet` | 原 `/api/diets` 饮食记录 |
| `food_catalog` | 原 `foods` 食物库 |
| `meal` | 原 `meals` 餐次 |
| `meal_item` | 原 `meal_items` 餐次明细 |
| `hydration` | 手动饮水 |
| `weight` | 手动体重 |

餐次明细通过 `parent_record_id` 关联 `record_type = 'meal'` 的父记录。食物库允许 `user_id` 为空，表示全局食物。

### work_records

通过 `record_type` 区分整合数据：

| record_type | 含义 |
| --- | --- |
| `settings` | 原 `work_settings` |
| `session` | 原 `work_sessions` |
| `todo` | 原 `work_todos` |
| `sedentary_response` | 原 `sedentary_responses` |

每个用户只允许一条 `settings` 记录，由部分唯一索引 `uq_work_records_user_settings` 约束。

### sleep_records

睡眠记录保持独立表，新增 `source_type`、`metadata`、`updated_at`。当前只支持 `source_type = 'MANUAL'`。

## 旧表迁移映射

| 旧表 | 新表 |
| --- | --- |
| `foods` | `diet_records(record_type = 'food_catalog')` |
| `meals` | `diet_records(record_type = 'meal')` |
| `meal_items` | `diet_records(record_type = 'meal_item')` |
| `work_settings` | `work_records(record_type = 'settings')` |
| `work_sessions` | `work_records(record_type = 'session')` |
| `work_todos` | `work_records(record_type = 'todo')` |
| `sedentary_responses` | `work_records(record_type = 'sedentary_response')` |
| `daily_health_metrics(STEPS)` | `workout_records(type = 'wechat_steps')` |
| `daily_health_metrics(HYDRATION)` | `diet_records(record_type = 'hydration')` |
| `daily_health_metrics(WEIGHT)` | `diet_records(record_type = 'weight')` |
| `health_sync_batches` | `workout_records(type = 'wechat_steps_sync')` |

## 接口兼容

- `/api/foods` 保留，底层使用 `diet_records(record_type = 'food_catalog')`。
- `/api/meals` 保留，底层使用 `diet_records(record_type in ('meal', 'meal_item'))`。
- `/api/work/*` 保留，底层使用 `work_records`。
- `/api/stats/*` 只从六张业务表聚合。
- `/api/workouts/wechat-steps` 用于同步微信步数。

## 验证要求

- `npx prisma validate` 通过。
- `prisma migrate deploy` 后业务表只剩 6 张。
- TypeScript 构建通过。
- 旧 Prisma 模型不再出现在后端代码中。
- 微信步数重复写入触发唯一约束或由接口覆盖更新。
- 用户删除后，六表内关联数据级联删除。
