const { request } = require("../../utils/request");

Page({
  data: {
    height: "170",
    weight: "70",
    targetWeight: "65",
    result: "",
  },

  onHeight(e) {
    this.setData({ height: e.detail.value });
  },
  onWeight(e) {
    this.setData({ weight: e.detail.value });
  },
  onTargetWeight(e) {
    this.setData({ targetWeight: e.detail.value });
  },

  async saveProfile() {
    const userId = getApp().globalData.userId;
    try {
      const resp = await request("/api/user/register", "POST", {
        userId,
        height: Number(this.data.height),
        weight: Number(this.data.weight),
        targetWeight: Number(this.data.targetWeight),
      });
      this.setData({ result: JSON.stringify(resp.data) });
      wx.showToast({ title: "保存成功", icon: "success" });
    } catch (err) {
      wx.showToast({ title: "保存失败", icon: "none" });
    }
  },
});
