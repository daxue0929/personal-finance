import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 独立的 vitest 配置，不并入 vite.config.js，避免改动构建链路。
// alias 与 plugin 与 vite.config.js 保持一致，确保 @ -> src 解析正常。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  test: {
    environment: 'jsdom',
    globals: false,             // 显式 import { describe, it, expect }，不污染全局
    include: ['src/**/*.{spec,test}.js']
  }
})
