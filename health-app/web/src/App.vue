<script setup>
// 导入 Vue 的响应式和生命周期 API
import { computed, onMounted, reactive, ref } from "vue";

// API 基础路径，优先使用环境变量 VITE_API_BASE，否则使用相对路径 `/api`
const apiBase = import.meta.env.VITE_API_BASE || "/api";

// 存放运动记录的响应式数组
const records = ref([]);

// 今日统计数据的响应式引用，初始化为 null
const todayStats = ref(null);

// 最近一周统计数据的响应式数组
const weeklyStats = ref([]);

// 总体统计数据的响应式引用
const totalStats = ref(null);

// 通用加载状态标记，页面请求时置为 true
const loading = ref(false);

// 全局错误提示文本
const error = ref("");

// 认证 token，从 localStorage 读取或为空字符串
const token = ref(localStorage.getItem("auth_token") || "");

// 当前用户名，从 localStorage 读取或为空字符串
const username = ref(localStorage.getItem("auth_username") || "");

// 登录/注册表单数据，默认使用 demo 账户
const authForm = reactive({
  account: "demo",
  password: "demo123",
});

// 新增运动记录表单的默认值
const workoutForm = reactive({
  // 记录日期，默认今天
  recordDate: new Date().toISOString().slice(0, 10),
  // 运动类型默认 running
  type: "running",
  // 时长默认 30 分钟
  durationMin: 30,
  // 默认卡路里
  calories: 200,
  // 备注字段，默认空
  notes: "",
});

// 目标设置表单的默认值
const goalForm = reactive({
  targetValue: 45,
});

// 计算属性：是否已登录（依据 token 是否存在）
const isLoggedIn = computed(() => Boolean(token.value));

// 解析后端统一返回结构：若包含 {code, data} 则返回 data
function unwrapApi(payload) {
  if (
    payload &&
    typeof payload === "object" &&
    "code" in payload &&
    "data" in payload
  ) {
    return payload.data;
  }
  return payload;
}

// 生成认证头部（如果有 token 则返回 Authorization）
function authHeaders() {
  return token.value ? { Authorization: `Bearer ${token.value}` } : {};
}

// 保存登录信息：token 与用户名同时写入响应式变量和 localStorage
function saveLogin(authToken, user) {
  token.value = authToken;
  username.value = user.account || user.username;
  localStorage.setItem("auth_token", authToken);
  localStorage.setItem("auth_username", username.value);
}

// 登出：清空本地和内存中的认证信息与缓存的数据
function logout() {
  token.value = "";
  username.value = "";
  records.value = [];
  todayStats.value = null;
  weeklyStats.value = [];
  totalStats.value = null;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
}

// 封装 fetch，用于与后端 API 通信并处理错误/返回值
async function apiFetch(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.message || "Request failed");
  }
  return unwrapApi(payload);
}

// 注册函数：调用 /auth/register，并在成功后保存登录信息与刷新页面数据
async function register() {
  error.value = ""; // 清空错误提示
  try {
    const auth = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify(authForm),
    });
    saveLogin(auth.token, auth.user); // 保存 token 和用户信息
    await refreshDashboard(); // 注册后加载用户数据
  } catch (e) {
    error.value = e.message; // 显示错误信息
  }
}

// 登录函数：调用 /auth/login，并在成功后保存登录信息与刷新页面数据
async function login() {
  error.value = "";
  try {
    const auth = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify(authForm),
    });
    saveLogin(auth.token, auth.user);
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

// 刷新仪表盘数据：并行请求 workouts、今日统计、周统计和汇总
async function refreshDashboard() {
  if (!token.value) {
    return; // 未登录则不请求数据
  }

  loading.value = true; // 开始加载
  error.value = "";
  try {
    const [workouts, today, weekly, summary] = await Promise.all([
      apiFetch("/workouts"),
      apiFetch("/stats/today"),
      apiFetch("/stats/workouts/weekly"),
      apiFetch("/stats/summary"),
    ]);
    records.value = workouts; // 更新记录
    todayStats.value = today; // 更新今日统计
    weeklyStats.value = weekly; // 更新周统计
    totalStats.value = summary; // 更新汇总
  } catch (e) {
    error.value = e.message; // 捕获并显示错误
  } finally {
    loading.value = false; // 结束加载
  }
}

// 新增运动记录：POST /workouts 后刷新列表
async function addRecord() {
  error.value = "";
  try {
    await apiFetch("/workouts", {
      method: "POST",
      body: JSON.stringify(workoutForm),
    });
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

// 保存目标值：POST /goals
async function saveGoal() {
  error.value = "";
  try {
    await apiFetch("/goals", {
      method: "POST",
      body: JSON.stringify({ targetValue: goalForm.targetValue }),
    });
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

// 删除记录：DELETE /workouts/:id 后刷新
async function removeRecord(id) {
  error.value = "";
  try {
    await apiFetch(`/workouts/${id}`, { method: "DELETE" });
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

// 组件挂载时尝试刷新仪表盘（若已登录）
onMounted(refreshDashboard);
</script>

<template>
  <!-- 页面主容器，居中布局 -->
  <main class="page">
    <!-- 卡片容器，包含所有功能区 -->
    <section class="card">
      <!-- 应用标题 -->
      <h1>Fitters MVP</h1>
      <!-- 简短说明文字 -->
      <p class="sub">
        PostgreSQL + Prisma + login + workout records + goals + stats
      </p>

      <!-- 未登录时显示的认证表单区域 -->
      <div v-if="!isLoggedIn" class="auth">
        <!-- 账号输入框 -->
        <input
          v-model="authForm.account"
          type="text"
          placeholder="Account"
          required
        />
        <!-- 密码输入框 -->
        <input
          v-model="authForm.password"
          type="password"
          placeholder="Password"
          required
        />
        <!-- 登录/注册按钮容器 -->
        <div class="auth-actions">
          <!-- 登录按钮，点击触发登录逻辑 -->
          <button @click="login">Login</button>
          <!-- 次要操作：注册并登录 -->
          <button class="secondary" @click="register">Register</button>
        </div>
      </div>

      <!-- 已登录时显示的顶部状态栏 -->
      <div v-else class="login-bar">
        <!-- 显示当前用户名 -->
        <span>Current user: {{ username }}</span>
        <!-- 退出登录按钮 -->
        <button class="secondary" @click="logout">Logout</button>
      </div>

      <!-- 登录后显示的仪表盘和表单 -->
      <template v-if="isLoggedIn">
        <!-- 新增运动记录表单，提交时调用 addRecord -->
        <form class="form" @submit.prevent="addRecord">
          <input v-model="workoutForm.recordDate" type="date" required />
          <input
            v-model="workoutForm.type"
            type="text"
            placeholder="Workout type"
            required
          />
          <input
            v-model.number="workoutForm.durationMin"
            type="number"
            min="1"
            placeholder="Minutes"
            required
          />
          <input
            v-model.number="workoutForm.calories"
            type="number"
            min="0"
            placeholder="Calories"
            required
          />
          <button type="submit">Add Workout</button>
        </form>

        <!-- 保存目标的表单 -->
        <form class="form goal-form" @submit.prevent="saveGoal">
          <input
            v-model.number="goalForm.targetValue"
            type="number"
            min="1"
            placeholder="Daily target minutes"
          />
          <button type="submit">Save Goal</button>
        </form>

        <!-- 汇总统计信息显示区域 -->
        <div class="summary">
          <span
            >Today: {{ todayStats?.completedMinutes || 0 }} /
            {{ todayStats?.targetMinutes || 0 }} min</span
          >
          <span>Progress: {{ todayStats?.completionPercent || 0 }}%</span>
          <span>Total workouts: {{ totalStats?.count || 0 }}</span>
          <span>Total minutes: {{ totalStats?.totalMinutes || 0 }}</span>
          <span>Total calories: {{ totalStats?.totalCalories || 0 }}</span>
        </div>

        <!-- 周统计：每一天的分钟数 -->
        <div class="summary">
          <span v-for="item in weeklyStats" :key="item.date"
            >{{ item.date }}: {{ item.minutes }} min</span
          >
        </div>
      </template>

      <!-- 全局加载提示 -->
      <p v-if="loading">Loading...</p>
      <!-- 全局错误提示 -->
      <p v-if="error" class="error">{{ error }}</p>

      <!-- 记录列表（已登录且存在记录时显示） -->
      <ul v-if="isLoggedIn && records.length" class="list">
        <li v-for="item in records" :key="item.id">
          <div>
            <!-- 记录日期 -->
            <strong>{{ item.date }}</strong>
            <!-- 类型 / 时长 / 卡路里 -->
            <span
              >{{ item.type }} / {{ item.durationMinutes }} min /
              {{ item.calories }} kcal</span
            >
          </div>
          <!-- 删除按钮，点击执行删除操作 -->
          <button class="danger" @click="removeRecord(item.id)">Delete</button>
        </li>
      </ul>
      <!-- 登录且无记录时的占位文案 -->
      <p v-else-if="isLoggedIn">No workout records yet.</p>
    </section>
  </main>
</template>
