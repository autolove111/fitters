# Fitters — 智能健康管理平台

Fitters 是一个集健康管理与智能学习于一体的全栈应用，由五个 Docker 服务组成。其中 **AidLearning** 是本项目的核心亮点——一个基于多 Agent 协作与 RAG 的智能学习伴侣。

---

## 项目总览

| 服务 | 技术栈 | 端口 | 简述 |
|------|--------|------|------|
| **backend** | Node.js 20 / TypeScript / Express / Prisma / PostgreSQL | 18080 | 健康数据 API（运动、目标、统计） |
| **miniapp** | Vue 3.5 / UniApp / uview-plus | 5174 | 跨端前端（微信小程序、H5 等） |
| **ai-service** | Python 3.11 / Flask | 5000 | AI 每日运动计划生成 |
| **postgres** | PostgreSQL 16 Alpine | 5432 | 数据库 |
| **aidlearning** | Python 3.11+ / FastAPI / LlamaIndex | **8001** | **智能学习平台（详见下文）** |

一键启动所有服务：

```bash
docker compose up -d
```

---

## 🎓 AidLearning — 智能学习伴侣

> An agent-native intelligent learning companion with multi-agent collaboration and RAG.

AidLearning（v1.4.0）是本项目的重点模块。它不是一个简单的聊天机器人，而是一个 **Agent 原生** 的学习平台——LLM 遵循标签协议（`FINISH` / `TOOL` / `THINK` / `PAUSE`）自主决定何时回答、何时调用工具、何时深度推理。

### 核心能力

#### 1. 💬 智能对话（Chat）

多轮对话，支持 Agentic 循环。模型可自主调用知识库检索、网页搜索、代码执行、论文搜索等工具，而非被动应答。

```bash
aidlearning chat                                          # 交互式 REPL
aidlearning run chat "解释傅里叶变换"                       # 单次执行
aidlearning chat --capability chat --kb my-kb --tool rag  # 指定知识库与工具
```

#### 2. 🔬 深度研究（Deep Research）

完整的学术研究流水线，分四个阶段自动完成：

| 阶段 | 名称 | 说明 |
|------|------|------|
| Phase 1 | Rephrase | 与用户对话，精炼研究主题 |
| Phase 2 | Decompose | 将主题拆解为多个子课题 |
| Phase 3 | Research | 对子课题逐个进行工具增强研究（动态队列） |
| Phase 4 | Report | 生成带引用和参考文献的结构化报告 |

### 知识库管理（RAG）

支持 PDF、DOCX、XLSX、PPTX 等格式的文档导入，采用 **BM25 + 向量检索** 的混合搜索策略（基于 LlamaIndex），支持增量添加文档。

```bash
aidlearning kb create my-kb --doc textbook.pdf --doc notes.docx   # 创建知识库
aidlearning kb add my-kb --doc lecture05.pptx                     # 增量添加
aidlearning kb search my-kb "矩阵的特征值分解"                     # 搜索
aidlearning kb list                                                # 列出所有知识库
```

### 三层记忆系统

AidLearning 拥有独立的三层记忆架构，使学习过程具有连续性：

| 层级 | 说明 |
|------|------|
| **短期记忆** | 当前会话上下文，实时构建 |
| **中期记忆** | 跨会话摘要，自动迁移 |
| **长期记忆** | 用户画像与学习偏好，持久化存储 |

记忆支持快照、合并与主动整理。

```bash
aidlearning memory show        # 查看记忆
aidlearning memory clear       # 清除记忆
```

### API 服务器

基于 FastAPI，提供完整的 REST + WebSocket 接口：

- JWT 鉴权与多用户支持
- WebSocket 实时流式对话
- 附件上传与知识库管理端点
- 会话管理与记忆查询


### 支持的 LLM 提供商

| 提供商 | 说明 |
|--------|------|
| OpenAI | GPT-4o, GPT-4 等 |
| Anthropic | Claude 系列 |
| DashScope | 阿里通义千问（默认：qwen3-14b） |
| Perplexity | 在线搜索增强模型 |

任何 OpenAI 兼容 API 均可通过 `OPENAI_BASE_URL` 接入。

---

## 快速开始

### 环境要求

- Docker Desktop（推荐最新稳定版）
- Python 3.11+（本地开发 AidLearning 时需要）
- Node.js 20 LTS（本地开发后端/前端时需要）

### 1. 克隆项目

```bash
git clone <repo-url>
cd fitters/health-app
```

### 2. 配置环境变量

复制并编辑 `.env` 文件，至少配置以下变量：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen3-14b
```

### 3. 启动服务

```bash
docker compose up -d
```

服务访问地址：

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:5174 |
| 后端 API | http://localhost:18080 |
| AI 服务 | http://localhost:5000 |
| AidLearning | http://localhost:8001 |

### 4. AidLearning 本地开发（可选）

```bash
cd study/aid_learning_agent
pip install -e ".[dev]"
aidlearning init        # 首次配置
aidlearning chat        # 开始对话
```

---

## 项目结构

```
health-app/
├── backend/                    # 后端 API（Express / Prisma / PostgreSQL）
├── miniapp-vue3/               # 前端（Vue 3 / UniApp）
├── ai-service/                 # AI 运动计划服务（Flask）
├── study/
│   └── aid_learning_agent/     # ⭐ AidLearning 智能学习平台
│       ├── aid_learning_agent/ # Python 包
│       │   ├── agents/         #   Agent 实现
│       │   ├── api/            #   FastAPI 服务器
│       │   ├── capabilities/   #   能力注册中心
│       │   ├── core/           #   Agentic 循环引擎
│       │   ├── knowledge/      #   知识库与 RAG
│       │   ├── memory/         #   三层记忆系统
│       │   ├── services/       #   LLM / Embedding / 搜索等服务
│       │   └── tools/          #   工具注册与内置工具
│       ├── requirements/       #   分场景依赖文件
└── docker-compose.yml          # 编排所有服务
```

---

# Fitters 启动教程

这份文档对应当前源码结构：后端是 Node.js + TypeScript + Express + Prisma，数据库是 PostgreSQL，整体通过 Docker Compose 启动。

## 一、新电脑首次启动

### 1. 安装环境

Windows 下建议安装：

1. Docker Desktop（必须）
2. Git（建议）
3. Node.js 20 LTS（可选；只用 Docker 启动时不是必须）

不再需要 Java、Maven，也不需要手动打包 jar。

安装 Docker Desktop 后，用 PowerShell 验证：

```powershell
docker --version
docker compose version
docker run hello-world
```

看到 `Hello from Docker!` 说明 Docker 可用。

### 2. 拉代码并进入项目目录

```powershell
git clone 你们仓库地址
cd fitters/health-app
```

如果已经有代码，直接进入 `health-app` 目录即可：

```powershell
cd "D:\软件工程\小组开发\正式开工\远程仓库克隆\fitters\health-app"
```

### 3. 启动所有容器

```powershell
docker compose up -d --build
```

第一次启动会拉取镜像并构建服务，时间会比较久。

当前会启动：

1. `health-postgres`：PostgreSQL 数据库
2. `health-backend`：Node/TypeScript 后端
3. `health-web`：Vue 前端
4. `health-ai-service`：Python AI 服务

后端容器启动时会自动执行：

```powershell
npx prisma migrate deploy
```

也就是说，数据库表结构会根据 `backend/prisma/migrations` 自动迁移，不需要手动建表。

### 4. 查看状态

```powershell
docker compose ps
```

正常情况下应看到：

- `health-postgres` 为 `healthy`
- `health-backend` 为 `Up`
- `health-web` 为 `Up`
- `health-ai-service` 为 `Up`

### 5. 初始化演示数据

第一次启动后可以写入 demo 用户和 7 天运动记录：

```powershell
docker compose exec backend npm run prisma:seed
```

演示账号：

```text
账号：demo
密码：demo123
```

### 6. 验证是否成功

后端健康检查：

```powershell
curl http://localhost:18080/api/health
```

看到类似内容即可：

```json
{"code":0,"message":"ok","data":{"status":"ok","service":"backend"}}
```

前端页面：

```text
http://localhost:5173
```

登录后能看到运动记录、今日进度、近 7 天统计，说明前端、后端和数据库已经联通。

## 二、常见问题

### 1. Docker 拉镜像失败

先登录 Docker：

```powershell
docker login
```

再重试：

```powershell
docker compose up -d --build
```

如果仍失败，通常是网络到 Docker Hub 不稳定。可以换网络、开代理，或在 Docker Desktop 的 `Settings -> Resources -> Proxies` 配置代理。

### 2. 端口被占用

修改 `health-app/.env`：

```env
BACKEND_PORT=18080
WEB_PORT=5173
POSTGRES_PORT=5432
AI_SERVICE_PORT=5000
```

改完后重新启动：

```powershell
docker compose up -d --build
```

### 3. 数据库结构异常或想清空重来

注意：下面命令会删除本地 PostgreSQL 数据。

```powershell
docker compose down -v
docker compose up -d --build
docker compose exec backend npm run prisma:seed
```

### 4. 在错误目录执行命令

`docker compose` 必须在 `health-app` 根目录执行，也就是能看到 `docker-compose.yml` 的目录。

## 三、不同端改代码后的重启命令

### 1. 只改前端

```powershell
docker compose up -d --build web
```

### 2. 只改后端 Node/TypeScript 代码

```powershell
docker compose up -d --build backend
```

### 3. 只改 Prisma schema 或 migration

如果只是新增 migration：

```powershell
docker compose up -d --build backend
```

后端启动时会自动执行迁移。

如果需要清空旧数据重新验证：

```powershell
docker compose down -v
docker compose up -d --build
docker compose exec backend npm run prisma:seed
```

### 4. 只改 AI 服务

```powershell
docker compose up -d --build ai-service
```

## 四、提交前检查清单

提交前建议确认：

1. `docker compose ps` 里核心服务都是 `Up`
2. `health-postgres` 是 `healthy`
3. `curl http://localhost:18080/api/health` 返回 `code: 0`
4. 前端 `http://localhost:5173` 能登录 demo 用户
5. 运动记录、目标进度、统计数据能正常显示
6. 没有提交本地 `.env`、`node_modules`、`dist` 等临时文件



## 五.数据库密码

现在你可以回到 pgAdmin，用下面这些信息连接：

| 字段 | 值 |
|------|----|
| Host | `localhost` |
| Port | `5432` |
| Username | `health_user` |
| Password | `health_pass` |

点击保存或测试连接，应该就能成功连上数据库了。
