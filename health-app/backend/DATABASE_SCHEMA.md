# 数据库表结构文档

## 概述

- **数据库类型**: PostgreSQL
- **ORM**: Prisma Client JS
- **最后更新**: 2025

---

## 表关系图

```
User (1) ──────< WorkoutRecord
     │
     ├─────< Goal
     │
     ├─────< SleepRecord
     │
     ├─────< DietRecord
     │
     └─────< WorkRecord (整合了原 workSettings/workSessions/workTodos/sedentaryResponses)
```

---

## 1. users - 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 用户ID |
| account | String(64) | Unique | 账号 |
| password_hash | String(255) | | 密码哈希 |
| nickname | String(64) | Nullable | 昵称 |
| avatar | Text | Nullable | 头像URL |
| created_at | DateTime | Default: now() | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**关联关系**: 一对多 → WorkoutRecord, Goal, SleepRecord, DietRecord, WorkRecord

---

## 2. workout_records - 运动记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 记录ID |
| user_id | Int | FK → users.id | 用户ID |
| type | String(64) | | 运动类型 |
| duration_min | Int | | 时长（分钟） |
| calories | Int | Default: 0 | 消耗卡路里 |
| record_date | Date | Index | 记录日期 |
| notes | String(255) | Nullable | 备注 |
| created_at | DateTime | Default: now() | 创建时间 |

**索引**:
- `idx_workout_records_user_record_date` (user_id, record_date)

---

## 3. goals - 目标表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 目标ID |
| user_id | Int | FK → users.id | 用户ID |
| goal_type | Enum | | 目标类型 |
| target_value | Int | | 目标值 |
| period | Enum | Default: DAILY | 周期 |
| created_at | DateTime | Default: now() | 创建时间 |
| updated_at | DateTime | Auto | 更新时间 |

**目标类型 (GoalType)**:
- `DAILY_WORKOUT_MINUTES` - 每日运动分钟数
- `DAILY_SLEEP_HOURS` - 每日睡眠小时数
- `DAILY_DIET_CALORIES` - 每日饮食卡路里

**周期 (GoalPeriod)**:
- `DAILY` - 每日

**约束**: Unique (user_id, goal_type, period)

---

## 4. sleep_records - 睡眠记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 记录ID |
| user_id | Int | FK → users.id | 用户ID |
| record_date | Date | Index | 记录日期 |
| duration_hours | Decimal(4,2) | Nullable | 睡眠时长（小时） |
| deep_hours | Decimal(4,2) | Nullable | 深睡眠时长（小时） |
| bed_time | DateTime | | 入睡时间 |
| wake_time | DateTime | | 起床时间 |
| quality_score | Int | Default: 0 | 睡眠质量评分 |
| notes | String(255) | Nullable | 备注 |
| metadata | JsonB | Nullable | 元数据 |
| created_at | DateTime | Default: now() | 创建时间 |

**索引**:
- `idx_sleep_records_user_record_date` (user_id, record_date)

---

## 5. diet_records - 饮食记录表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 记录ID |
| user_id | Int | FK → users.id | 用户ID |
| record_date | Date | Index | 记录日期 |
| meal_type | String(32) | | 餐次类型 |
| food_name | String(128) | | 食物名称 |
| quantity_grams | Decimal(8,2) | Nullable | 数量（克） |
| calories | Int | Default: 0 | 卡路里 |
| protein_grams | Decimal(6,2) | Nullable | 蛋白质（克） |
| fat_grams | Decimal(6,2) | Nullable | 脂肪（克） |
| carb_grams | Decimal(6,2) | Nullable | 碳水化合物（克） |
| notes | String(255) | Nullable | 备注 |
| metadata | JsonB | Nullable | 元数据 |
| created_at | DateTime | Default: now() | 创建时间 |

**餐次类型 (mealType)**:
- `BREAKFAST` - 早餐
- `LUNCH` - 午餐
- `DINNER` - 晚餐

**索引**:
- `idx_diet_records_user_record_date` (user_id, record_date)
- `idx_diet_records_user_meal_date` (user_id, meal_type, record_date)

**说明**: 本表整合了原有的 foods（食物库）、meals（餐次表）、meal_items（餐次明细表）三张表的功能。

---

## 6. work_records - 工作记录表（整合后）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Int | PK, Auto | 记录ID |
| user_id | Int | FK → users.id | 用户ID |
| record_type | String(32) | Index | 记录类型 |
| record_date | Date | Index | 记录日期 |
| occupation | String(64) | Nullable | 职业 |
| pomodoro_duration | Int | Nullable | 番茄钟时长（分钟） |
| sedentary_reminder_on | Boolean | Nullable | 久坐提醒开关 |
| sedentary_interval | Int | Nullable | 久坐提醒间隔（分钟） |
| wrist_health_score | Int | Nullable | 手腕健康评分 |
| eye_rest_count | Int | Nullable | 眼睛休息次数 |
| water_intake | Int | Nullable | 饮水量 |
| back_relax_count | Int | Nullable | 背部放松次数 |
| vocal_rest_count | Int | Nullable | 嗓音休息次数 |
| stop_move_count | Int | Nullable | 停止活动次数 |
| eye_exercise_count | Int | Nullable | 眼保健操次数 |
| class_break_count | Int | Nullable | 课间休息次数 |
| deep_breath_count | Int | Nullable | 深呼吸次数 |
| leg_move_count | Int | Nullable | 腿部活动次数 |
| neck_relax_count | Int | Nullable | 颈部放松次数 |
| step_count | Int | Nullable | 步数 |
| energy_snack_count | Int | Nullable | 能量零食次数 |
| stand_count | Int | Nullable | 站立次数 |
| session_type | String(32) | Nullable | 会话类型 |
| session_start | DateTime | Nullable | 会话开始时间 |
| session_end | DateTime | Nullable | 会话结束时间 |
| session_duration | Int | Nullable | 会话时长（秒） |
| todo_content | String(255) | Nullable | 待办内容 |
| todo_completed | Boolean | Nullable | 待办是否完成 |
| sedentary_responded_at | DateTime | Nullable | 久坐响应时间 |
| notes | String(255) | Nullable | 备注 |
| metadata | JsonB | Nullable | 元数据 |
| created_at | DateTime | Default: now() | 创建时间 |

**记录类型 (recordType)**:
- `SETTINGS` - 工作设置
- `SESSION` - 番茄钟会话
- `TODO` - 待办事项
- `RESPONSE` - 久坐响应

**索引**:
- `idx_work_records_user_record_date` (user_id, record_date)
- `idx_work_records_user_type_date` (user_id, record_type, record_date)

**说明**: 本表整合了原有的 work_settings、work_sessions、work_todos、sedentary_responses 四张表的功能。

---

## 表数量统计

| 序号 | 表名 | 行数估算 | 说明 |
|------|------|----------|------|
| 1 | users | - | 用户表 |
| 2 | workout_records | 多 | 运动记录表 |
| 3 | goals | 少量 | 目标表 |
| 4 | sleep_records | 多 | 睡眠记录表 |
| 5 | diet_records | 多 | 饮食记录表（已整合） |
| 6 | work_records | 多 | 工作记录表（已整合） |

**总计**: 6 张表（原 10 张，已精简为 6 张）

---

## 整合历史

### 本次更新（2025）
将 work_settings、work_sessions、work_todos、sedentary_responses 四张表整合为 work_records 表：
- SETTINGS 类型：存储工作设置和健康指标
- SESSION 类型：存储番茄钟会话
- TODO 类型：存储待办事项
- RESPONSE 类型：存储久坐响应（使用 sedentary_responded_at 字段）

### 之前的更新
将 foods、meals、meal_items 三张表整合为 diet_records 表：
- 每条记录包含：日期、餐次类型、食物名称、数量和营养数据

---

## 迁移注意事项

1. 数据库已有数据需要先备份再执行迁移
2. 部署后执行 `npx prisma migrate deploy` 进行数据库迁移
3. 执行 `npm run seed` 重新生成测试数据
4. 由于表结构变更，前端可能需要同步更新 API 调用
