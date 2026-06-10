import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // 根据环境加载不同的环境变量
  const env = {
    development: 'http://localhost:5001',
    production: 'http://localhost:5000'
  }
  
  const apiBaseUrl = env[mode] || env.development
  
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
          target: apiBaseUrl,
          changeOrigin: true
        }
      }
    }
  }
})