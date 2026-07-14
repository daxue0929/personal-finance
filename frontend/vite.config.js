import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd())
  
  // 开发环境使用本地代理。目标为 web 进程（5000，对外 API），
  // 不是 scheduler（5001，仅 /internal/* 内部接口）。控制类接口由 web 转发到 scheduler。
  const devApiBaseUrl = env.VITE_DEV_API_BASE_URL || 'http://localhost:5000'
  
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: devApiBaseUrl,
          changeOrigin: true
        }
      }
    }
  }
})