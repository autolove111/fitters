<script>
export default {
  onLaunch: function () {
    console.log('App Launch')
  },
  onShow: function () {
    console.log('App Show')
  },
  onHide: function () {
    console.log('App Hide')
  },
}
</script>

<style lang="scss">
/*每个页面公共css */
  @import 'uview-plus/index.scss';

  /* 浅色模式 CSS 变量（默认） */
  page {
    --bg-primary: #f3f9ff;
    --bg-secondary: #eef5ff;
    --card-bg: rgba(255, 255, 255, 0.96);
    --card-border: rgba(255, 255, 255, 0.7);
    --card-shadow: rgba(14, 165, 233, 0.1);
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --text-tertiary: #94a3b8;
    --divider: rgba(148, 163, 184, 0.1);
    --modal-bg: #ffffff;
    --input-bg: #f8fafc;
    --input-border: rgba(148, 163, 184, 0.2);
    --btn-cancel-bg: #f1f5f9;
    --btn-cancel-text: #334155;
    --toggle-bg: #e2e8f0;
    --toggle-active-bg: linear-gradient(90deg, #38bdf8, #22c55e);
    --danger-color: #e53935;
    --danger-bg: rgba(239, 68, 68, 0.05);
    --overlay-bg: rgba(0, 0, 0, 0.4);
  }

  /* 深色模式 CSS 变量 — 作用在带 .dark 类的元素上 */
  .dark {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --card-bg: rgba(30, 41, 59, 0.96);
    --card-border: rgba(51, 65, 85, 0.7);
    --card-shadow: rgba(0, 0, 0, 0.3);
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-tertiary: #64748b;
    --divider: rgba(71, 85, 105, 0.3);
    --modal-bg: #1e293b;
    --input-bg: #1e293b;
    --input-border: rgba(71, 85, 105, 0.4);
    --btn-cancel-bg: #334155;
    --btn-cancel-text: #e2e8f0;
    --toggle-bg: #334155;
    --toggle-active-bg: linear-gradient(90deg, #38bdf8, #22c55e);
    --danger-color: #ef4444;
    --danger-bg: rgba(239, 68, 68, 0.1);
    --overlay-bg: rgba(0, 0, 0, 0.6);
  }
</style>
