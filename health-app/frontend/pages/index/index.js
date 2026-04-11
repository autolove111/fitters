Page({
  data: {
    userId: getApp().globalData.userId,
  },

  goProfile() {
    wx.navigateTo({ url: "/pages/profile/profile" });
  },

  goRecord() {
    wx.navigateTo({ url: "/pages/record/record" });
  },

  goReport() {
    wx.navigateTo({ url: "/pages/report/report" });
  },
});
