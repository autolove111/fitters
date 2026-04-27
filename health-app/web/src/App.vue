<script setup>
import { computed, onMounted, reactive, ref } from "vue";

const apiBase = import.meta.env.VITE_API_BASE || "/api";
const records = ref([]);
const todayStats = ref(null);
const weeklyStats = ref([]);
const totalStats = ref(null);
const loading = ref(false);
const error = ref("");
const token = ref(localStorage.getItem("auth_token") || "");
const username = ref(localStorage.getItem("auth_username") || "");

const authForm = reactive({
  account: "demo",
  password: "demo123",
});

const workoutForm = reactive({
  recordDate: new Date().toISOString().slice(0, 10),
  type: "running",
  durationMin: 30,
  calories: 200,
  notes: "",
});

const goalForm = reactive({
  targetValue: 45,
});

const isLoggedIn = computed(() => Boolean(token.value));

function unwrapApi(payload) {
  if (payload && typeof payload === "object" && "code" in payload && "data" in payload) {
    return payload.data;
  }
  return payload;
}

function authHeaders() {
  return token.value ? { Authorization: `Bearer ${token.value}` } : {};
}

function saveLogin(authToken, user) {
  token.value = authToken;
  username.value = user.account || user.username;
  localStorage.setItem("auth_token", authToken);
  localStorage.setItem("auth_username", username.value);
}

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

async function register() {
  error.value = "";
  try {
    const auth = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify(authForm),
    });
    saveLogin(auth.token, auth.user);
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

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

async function refreshDashboard() {
  if (!token.value) {
    return;
  }

  loading.value = true;
  error.value = "";
  try {
    const [workouts, today, weekly, summary] = await Promise.all([
      apiFetch("/workouts"),
      apiFetch("/stats/today"),
      apiFetch("/stats/workouts/weekly"),
      apiFetch("/stats/summary"),
    ]);
    records.value = workouts;
    todayStats.value = today;
    weeklyStats.value = weekly;
    totalStats.value = summary;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

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

async function removeRecord(id) {
  error.value = "";
  try {
    await apiFetch(`/workouts/${id}`, { method: "DELETE" });
    await refreshDashboard();
  } catch (e) {
    error.value = e.message;
  }
}

onMounted(refreshDashboard);
</script>

<template>
  <main class="page">
    <section class="card">
      <h1>Fitters MVP</h1>
      <p class="sub">PostgreSQL + Prisma + login + workout records + goals + stats</p>

      <div v-if="!isLoggedIn" class="auth">
        <input v-model="authForm.account" type="text" placeholder="Account" required />
        <input v-model="authForm.password" type="password" placeholder="Password" required />
        <div class="auth-actions">
          <button @click="login">Login</button>
          <button class="secondary" @click="register">Register</button>
        </div>
      </div>

      <div v-else class="login-bar">
        <span>Current user: {{ username }}</span>
        <button class="secondary" @click="logout">Logout</button>
      </div>

      <template v-if="isLoggedIn">
        <form class="form" @submit.prevent="addRecord">
          <input v-model="workoutForm.recordDate" type="date" required />
          <input v-model="workoutForm.type" type="text" placeholder="Workout type" required />
          <input v-model.number="workoutForm.durationMin" type="number" min="1" placeholder="Minutes" required />
          <input v-model.number="workoutForm.calories" type="number" min="0" placeholder="Calories" required />
          <button type="submit">Add Workout</button>
        </form>

        <form class="form goal-form" @submit.prevent="saveGoal">
          <input v-model.number="goalForm.targetValue" type="number" min="1" placeholder="Daily target minutes" />
          <button type="submit">Save Goal</button>
        </form>

        <div class="summary">
          <span>Today: {{ todayStats?.completedMinutes || 0 }} / {{ todayStats?.targetMinutes || 0 }} min</span>
          <span>Progress: {{ todayStats?.completionPercent || 0 }}%</span>
          <span>Total workouts: {{ totalStats?.count || 0 }}</span>
          <span>Total minutes: {{ totalStats?.totalMinutes || 0 }}</span>
          <span>Total calories: {{ totalStats?.totalCalories || 0 }}</span>
        </div>

        <div class="summary">
          <span v-for="item in weeklyStats" :key="item.date">{{ item.date }}: {{ item.minutes }} min</span>
        </div>
      </template>

      <p v-if="loading">Loading...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <ul v-if="isLoggedIn && records.length" class="list">
        <li v-for="item in records" :key="item.id">
          <div>
            <strong>{{ item.date }}</strong>
            <span>{{ item.type }} / {{ item.durationMinutes }} min / {{ item.calories }} kcal</span>
          </div>
          <button class="danger" @click="removeRecord(item.id)">Delete</button>
        </li>
      </ul>
      <p v-else-if="isLoggedIn">No workout records yet.</p>
    </section>
  </main>
</template>
