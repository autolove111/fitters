export const isDevAuthBypass = () => import.meta.env.DEV

export const getDevAuthUser = () => ({
  enabled: false,
  authenticated: true,
  user_id: 'dev-user',
  username: '开发模式',
  role: 'admin',
  is_admin: true,
})
