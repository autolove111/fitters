# Fitters MVP Database Contract

This document is the shared database reference for the first demo.

## Technology Baseline

- Runtime: Node.js 20 LTS
- API: TypeScript + Express
- Database: PostgreSQL 14+
- ORM and migrations: Prisma + Prisma Migrate
- Core response shape: `{ code, message, data }`

## Tables

### users

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| id | serial integer | yes | Primary key |
| account | varchar(64) | yes | Unique login account |
| password_hash | varchar(255) | yes | bcrypt hash only; never store raw password |
| nickname | varchar(64) | no | Display name |
| created_at | timestamp | yes | Created by database |
| updated_at | timestamp | yes | Updated by Prisma |

### workout_records

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| id | serial integer | yes | Primary key |
| user_id | integer | yes | Foreign key to `users.id`; cascade delete |
| type | varchar(64) | yes | Workout type |
| duration_min | integer | yes | Positive minutes |
| calories | integer | yes | Non-negative kcal |
| record_date | date | yes | Workout date |
| notes | varchar(255) | no | Optional note |
| created_at | timestamp | yes | Created by database |

Index: `idx_workout_records_user_record_date` on `(user_id, record_date)`.

### goals

| Field | Type | Required | Rule |
| --- | --- | --- | --- |
| id | serial integer | yes | Primary key |
| user_id | integer | yes | Foreign key to `users.id`; cascade delete |
| goal_type | enum | yes | First demo uses `DAILY_WORKOUT_MINUTES` |
| target_value | integer | yes | Positive target value |
| period | enum | yes | First demo uses `DAILY` |
| created_at | timestamp | yes | Created by database |
| updated_at | timestamp | yes | Updated by Prisma |

Unique key: `(user_id, goal_type, period)`.

## API Coverage

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/workouts`
- `GET /api/workouts`
- `DELETE /api/workouts/:id`
- `POST /api/goals`
- `GET /api/stats/today`
- `GET /api/stats/workouts/weekly`
- `GET /api/stats/summary`

All protected APIs derive `user_id` from JWT and never accept user ownership from request bodies.
