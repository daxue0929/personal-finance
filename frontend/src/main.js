import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { authApi } from './api'
import { finishAuthProbe } from './stores/auth'

const app = createApp(App)

app.use(ElementPlus)
app.use(router)

// 挂载前探测登录态（Cookie 模式下前端无法读 HttpOnly Cookie，由后端 /api/me 返回）。
// 探测完成后路由守卫的 whenReady() 即已 resolve，初始导航不会阻塞/死锁。
;(async () => {
  try {
    const res = await authApi.me()
    finishAuthProbe(res.user)
  } catch (e) {
    finishAuthProbe(null)
  }
  app.mount('#app')
})()
