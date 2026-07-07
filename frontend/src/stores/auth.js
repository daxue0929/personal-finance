import { reactive } from 'vue'

/**
 * 当前登录用户共享状态（Cookie 模式下前端不持有 token，仅缓存 /api/me 返回的用户信息）
 *
 * 跨页面共享：顶栏（显示用户名/退出）与用户管理页（防自锁）都需要当前用户，
 * 故用此轻量 reactive 模块（未引入 Pinia/Vuex，遵循项目现状）。
 */
export const auth = reactive({
  user: null,    // { id, username, display_name, role, enabled, session_ttl_minutes, ... } 或 null
  ready: false   // 首次 /api/me 探测是否完成（路由守卫据此避免登录页闪烁）
})

let _readyResolve
const _readyPromise = new Promise((resolve) => { _readyResolve = resolve })

/** 首次 /api/me 探测完成时调用（无论成功失败） */
export const finishAuthProbe = (user) => setAuthUser(user)

/** 登录成功后设置当前用户 */
export function setAuthUser(user) {
  auth.user = user || null
  auth.ready = true
  _readyResolve()
}

/** 清除当前用户（退出登录 / 401 失效） */
export function clearAuthUser() {
  auth.user = null
}

/** 等待首次鉴权探测完成（路由守卫用） */
export function whenReady() {
  return _readyPromise
}

/** 是否管理员 */
export function isAdmin() {
  return auth.user?.role === 'admin'
}
