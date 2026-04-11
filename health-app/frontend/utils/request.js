const BASE_URL = "http://127.0.0.1:8080";

function request(url, method = "GET", data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + url,
      method,
      data,
      timeout: 10000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(new Error("HTTP " + res.statusCode));
      },
      fail: reject,
    });
  });
}

module.exports = {
  request,
  BASE_URL,
};
