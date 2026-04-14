<script setup>
import { computed, onMounted, reactive, ref } from "vue";

const apiBase = import.meta.env.VITE_API_BASE || "/api";
const records = ref([]);
const loading = ref(false);
const error = ref("");
const token = ref(localStorage.getItem("auth_token") || "");
const username = ref(localStorage.getItem("auth_username") || "");

const authForm = reactive({
  username: "demo",
  password: "demo123",
});

const form = reactive({
  date: new Date().toISOString().slice(0, 10),
  type: "跑步",
  durationMinutes: 30,
  calories: 200,
});

const summary = computed(() => {
  return records.value.reduce(
    (acc, item) => {
      acc.count += 1;
      acc.totalMinutes += Number(item.durationMinutes || 0);
      acc.totalCalories += Number(item.calories || 0);
      return acc;
    },
    { count: 0, totalMinutes: 0, totalCalories: 0 },
  );
});

const isLoggedIn = computed(() => !!token.value);

function authHeaders() {
  if (!token.value) {
    return {};
  }
  return { Authorization: `Bearer ${token.value}` };
}

function saveLogin(authToken, user) {
  token.value = authToken;
  username.value = user;
  localStorage.setItem("auth_token", authToken);
  localStorage.setItem("auth_username", user);
}

function logout() {
  token.value = "";
  username.value = "";
  records.value = [];
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_username");
}

async function register() {
  error.value = "";
  try {
    const response = await fetch(`${apiBase}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(authForm),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || "注册失败");
    }
    await login();
  } catch (e) {
    error.value = e.message;
  }
}

async function login() {
  error.value = "";
  try {
    const response = await fetch(`${apiBase}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(authForm),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.message || "登录失败");
    }
    saveLogin(data.token, data.username);
    await fetchRecords();
  } catch (e) {
    error.value = e.message;
  }
}

async function fetchRecords() {
  if (!token.value) {
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const response = await fetch(`${apiBase}/workouts`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error("获取记录失败");
    }
    records.value = await response.json();
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function addRecord() {
  error.value = "";
  try {
    const response = await fetch(`${apiBase}/workouts`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(form),
    });
    if (!response.ok) {
      throw new Error("新增失败，请检查输入");
    }
    await fetchRecords();
  } catch (e) {
    error.value = e.message;
  }
}

async function removeRecord(id) {
  error.value = "";
  try {
    const response = await fetch(`${apiBase}/workouts/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error("删除失败");
    }
    await fetchRecords();
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(fetchRecords);
</script>

<template>
  <main class="page">
    <section class="card">
      <h1>运动记录软件</h1>
      <p class="sub">最小可运行版本：PostgreSQL + 登录 + 运动记录</p>

      <div v-if="!isLoggedIn" class="auth">
        <input
          v-model="authForm.username"
          type="text"
          placeholder="用户名（至少3位）"
          required
        />
        <input
          v-model="authForm.password"
          type="password"
          placeholder="密码（至少6位）"
          required
        />
        <div class="auth-actions">
          <button @click="login">登录</button>
          <button class="secondary" @click="register">注册并登录</button>
        </div>
      </div>

      <div v-else class="login-bar">
        <span>当前用户：{{ username }}</span>
        <button class="secondary" @click="logout">退出登录</button>
      </div>

      <template v-if="isLoggedIn">
        <form class="form" @submit.prevent="addRecord">
          <input v-model="form.date" type="date" required />
          <input
            v-model="form.type"
            type="text"
            placeholder="运动类型"
            required
          />
          <input
            v-model.number="form.durationMinutes"
            type="number"
            min="1"
            placeholder="时长(分钟)"
            required
          />
          <input
            v-model.number="form.calories"
            type="number"
            min="0"
            placeholder="消耗(kcal)"
            required
          />
          <button type="submit">新增记录</button>
        </form>

        <div class="summary">
          <span>次数：{{ summary.count }}</span>
          <span>总时长：{{ summary.totalMinutes }} 分钟</span>
          <span>总消耗：{{ summary.totalCalories }} kcal</span>
        </div>
      </template>

      <p v-if="loading">加载中...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <ul class="list" v-if="isLoggedIn && records.length">
        <li v-for="item in records" :key="item.id">
          <div>
            <strong>{{ item.date }}</strong>
            <span
              >{{ item.type }} / {{ item.durationMinutes }} 分钟 /
              {{ item.calories }} kcal</span
            >
          </div>
          <button class="danger" @click="removeRecord(item.id)">删除</button>
        </li>
      </ul>
      <p v-else-if="isLoggedIn">暂无记录，先添加一条吧。</p>
    </section>
  </main>
</template>
