const { request } = require("../../utils/request");

Page({
  data: {
    recommendText: "点击上方按钮生成今日推荐",
    reportText: "点击上方按钮拉取每日报告",
  },

  async loadRecommendation() {
    const userId = getApp().globalData.userId;
    try {
      const resp = await request("/api/diet/recommend?userId=" + userId);
      this.setData({
        recommendText: JSON.stringify(resp.data.recommendation),
      });
    } catch (err) {
      wx.showToast({ title: "获取失败", icon: "none" });
    }
  },

  async loadDailyReport() {
    const userId = getApp().globalData.userId;
    try {
      const resp = await request("/api/report/daily?userId=" + userId);
      this.setData({
        reportText: JSON.stringify(resp.data),
      });
    } catch (err) {
      wx.showToast({ title: "获取失败", icon: "none" });
    }
  },
});
