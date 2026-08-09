import { reactive } from 'vue'

/**
 * 当前登录用户共享状态（Cookie 模式下前端不持有 token，仅缓存 /api/me 返回的用户信息）
 *
 * 跨页面共享：顶栏（显示用户名/退出）与用户管理页（防自锁）都需要当前用户，
 * 故用此轻量 reactive 模块（未引入 Pinia/Vuex，遵循项目现状）。
 *
 * multi-user 扩展（AC-5）：
 * - `realUser` 保存 admin 真实身份（用于顶栏显示）
 * - `impersonate` 标记当前是否在切换视角状态
 * - `auth.user` 反映的是「当前生效身份」：admin 切到 target user 时是 target user
 */
export const auth = reactive({
  user: null,        // 当前生效身份（admin 切换时是 target user）
  realUser: null,    // 真实登录用户（始终是登录时的 admin）
  impersonate: false,
  ready: false       // 首次 /api/me 探测是否完成
})

let _readyResolve
const _readyPromise = new Promise((resolve) => { _readyResolve = resolve })

/** 首次 /api/me 探测完成时调用（无论成功失败）
 *  payload 格式：{ user, realUser?, impersonate? }
 *  - 普通登录：payload = { user } 或 null
 *  - admin 切换视角：payload = { user: target, realUser: admin, impersonate: true }
 */
export const finishAuthProbe = (payload) => {
  const user = payload?.user || null
  if (payload && payload.impersonate && payload.realUser) {
    setImpersonate(user, payload.realUser)
  } else {
    setAuthUser(user)
  }
  // setImpersonate 不会标 ready，补一下以免 router guard 的 whenReady() 永久 hang
  if (!auth.ready) {
    auth.ready = true
    _readyResolve()
  }
}

/** 登录成功后设置当前用户 */
export function setAuthUser(user) {
  auth.user = user || null
  auth.realUser = user || null
  auth.impersonate = false
  auth.ready = true
  _readyResolve()
}

/** admin 切换 user 视角：user = target, realUser = admin */
export function setImpersonate(target, admin) {
  auth.user = target
  auth.realUser = admin || auth.realUser
  auth.impersonate = true
}

/** 退出切换视角 */
export function clearImpersonate() {
  if (auth.realUser) {
    auth.user = auth.realUser
  }
  auth.impersonate = false
}

/** 清除当前用户（退出登录 / 401 失效） */
export function clearAuthUser() {
  auth.user = null
  auth.realUser = null
  auth.impersonate = false
}

/** 等待首次鉴权探测完成（路由守卫用） */
export function whenReady() {
  return _readyPromise
}

/** 是否管理员（按真实身份判断） */
export function isAdmin() {
  return auth.realUser?.role === 'admin' || auth.user?.role === 'admin'
}
