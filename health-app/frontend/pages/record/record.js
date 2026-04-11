const { request } = require("../../utils/request");

Page({
  data: {
    sportType: "running",
    durationMin: "30",
    sportCalories: "260",
    sleepHours: "7.2",
    deepSleepRatio: "0.3",
    foodName: "salad",
    dietCalories: "380",
  },

  onSportType(e) {
    this.setData({ sportType: e.detail.value });
  },
  onDuration(e) {
    this.setData({ durationMin: e.detail.value });
  },
  onSportCalories(e) {
    this.setData({ sportCalories: e.detail.value });
  },
  onSleepHours(e) {
    this.setData({ sleepHours: e.detail.value });
  },
  onDeepSleepRatio(e) {
    this.setData({ deepSleepRatio: e.detail.value });
  },
  onFoodName(e) {
    this.setData({ foodName: e.detail.value });
  },
  onDietCalories(e) {
    this.setData({ dietCalories: e.detail.value });
  },

  async recordSport() {
    const userId = getApp().globalData.userId;
    try {
      await request("/api/sport/record", "POST", {
        userId,
        type: this.data.sportType,
        durationMin: Number(this.data.durationMin),
        caloriesBurned: Number(this.data.sportCalories),
      });
      wx.showToast({ title: "运动已记录", icon: "success" });
    } catch (err) {
      wx.showToast({ title: "提交失败", icon: "none" });
    }
  },

  async recordSleep() {
    const userId = getApp().globalData.userId;
    try {
      await request("/api/sleep/record", "POST", {
        userId,
        hours: Number(this.data.sleepHours),
        deepSleepRatio: Number(this.data.deepSleepRatio),
      });
      wx.showToast({ title: "睡眠已记录", icon: "success" });
    } catch (err) {
      wx.showToast({ title: "提交失败", icon: "none" });
    }
  },

  async recordDiet() {
    const userId = getApp().globalData.userId;
    try {
      await request("/api/diet/record", "POST", {
        userId,
        foodName: this.data.foodName,
        calories: Number(this.data.dietCalories),
      });
      wx.showToast({ title: "饮食已记录", icon: "success" });
    } catch (err) {
      wx.showToast({ title: "提交失败", icon: "none" });
    }
  },
});
