<script setup>
import { ref } from "vue";

const baseUrl = ref("http://127.0.0.1:18080");
const userId = ref("demo-user");

const height = ref(170);
const weight = ref(70);
const targetWeight = ref(65);

const sportType = ref("running");
const durationMin = ref(30);
const sportCalories = ref(260);

const sleepHours = ref(7.2);
const deepSleepRatio = ref(0.3);

const foodName = ref("salad");
const dietCalories = ref(380);

const output = ref("等待操作...");

function setOutput(data) {
  output.value = JSON.stringify(data, null, 2);
}

async function req(path, method, body) {
  const resp = await fetch(baseUrl.value.trim() + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  const json = await resp.json();
  if (!resp.ok) {
    throw new Error(JSON.stringify(json));
  }
  return json;
}

function uid() {
  return userId.value.trim() || "demo-user";
}

async function saveProfile() {
  try {
    const data = await req("/api/user/register", "POST", {
      userId: uid(),
      height: Number(height.value),
      weight: Number(weight.value),
      targetWeight: Number(targetWeight.value),
    });
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}

async function recordSport() {
  try {
    const data = await req("/api/sport/record", "POST", {
      userId: uid(),
      type: sportType.value,
      durationMin: Number(durationMin.value),
      caloriesBurned: Number(sportCalories.value),
    });
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}

async function recordSleep() {
  try {
    const data = await req("/api/sleep/record", "POST", {
      userId: uid(),
      hours: Number(sleepHours.value),
      deepSleepRatio: Number(deepSleepRatio.value),
    });
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}

async function recordDiet() {
  try {
    const data = await req("/api/diet/record", "POST", {
      userId: uid(),
      foodName: foodName.value,
      calories: Number(dietCalories.value),
    });
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}

async function getRecommend() {
  try {
    const data = await req(
      "/api/diet/recommend?userId=" + encodeURIComponent(uid()),
      "GET",
    );
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}

async function getReport() {
  try {
    const data = await req(
      "/api/report/daily?userId=" + encodeURIComponent(uid()),
      "GET",
    );
    setOutput(data);
  } catch (e) {
    setOutput({ error: String(e) });
  }
}
</script>

<template>
  <main class="wrap">
    <section class="card hero">
      <h1>减脂助手 Vue 版</h1>
      <p>浏览器直连后端，完成用户、记录、推荐、日报的最小闭环。</p>
      <div class="row">
        <label>后端地址</label>
        <input v-model="baseUrl" />
      </div>
      <div class="row">
        <label>用户ID</label>
        <input v-model="userId" />
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h2>用户信息</h2>
        <input v-model="height" type="number" placeholder="身高 cm" />
        <input v-model="weight" type="number" placeholder="体重 kg" />
        <input v-model="targetWeight" type="number" placeholder="目标体重 kg" />
        <button @click="saveProfile">保存用户</button>
      </article>

      <article class="card">
        <h2>运动记录</h2>
        <input v-model="sportType" placeholder="类型，例如 running" />
        <input v-model="durationMin" type="number" placeholder="时长 分钟" />
        <input v-model="sportCalories" type="number" placeholder="消耗 kcal" />
        <button @click="recordSport">提交运动</button>
      </article>

      <article class="card">
        <h2>睡眠记录</h2>
        <input
          v-model="sleepHours"
          type="number"
          step="0.1"
          placeholder="睡眠小时"
        />
        <input
          v-model="deepSleepRatio"
          type="number"
          step="0.1"
          placeholder="深睡比例 0~1"
        />
        <button @click="recordSleep">提交睡眠</button>
      </article>

      <article class="card">
        <h2>饮食记录</h2>
        <input v-model="foodName" placeholder="食物名" />
        <input v-model="dietCalories" type="number" placeholder="热量 kcal" />
        <button @click="recordDiet">提交饮食</button>
      </article>

      <article class="card">
        <h2>推荐与日报</h2>
        <button @click="getRecommend">获取推荐</button>
        <button @click="getReport">获取日报</button>
      </article>
    </section>

    <section class="card">
      <h2>响应结果</h2>
      <pre>{{ output }}</pre>
    </section>
  </main>
</template>
