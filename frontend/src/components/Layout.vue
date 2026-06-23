<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background-color: #545c64">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold;">
        理财管理系统
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        style="border-right: none"
        background-color="#545c64"
        text-color="#fff"
        active-text-color="#ffd04b"
      >
        <el-menu-item
          v-for="menu in menuItems"
          :key="menu.path"
          :index="menu.path"
        >
          <el-icon>
            <component :is="getIconComponent(menu.path)" />
          </el-icon>
          <span>{{ menu.meta.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background-color: #fff; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between;">
        <div style="font-size: 16px; font-weight: 500;">
          {{ currentTitle }}
        </div>
      </el-header>

      <el-main style="background-color: #f5f5f5; padding: 0;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Setting, Wallet, ShoppingCart, TrendCharts, Folder } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

// 获取路由列表并按sort排序
const menuItems = computed(() => {
  const routes = router.options.routes[0]?.children || []
  return routes
    .filter(r => r.path && r.meta?.title)
    .sort((a, b) => (a.meta?.sort || 0) - (b.meta?.sort || 0))
})

const activeMenu = computed(() => {
  return route.path
})

const currentTitle = computed(() => {
  return route.meta?.title || '理财管理系统'
})

// 图标映射
const iconMap = {
  '/portfolio': Folder,
  '/buyers': ShoppingCart,
  '/funds': Wallet,
  '/funds/history': TrendCharts,
  '/tasks': Setting
}

const getIconComponent = (path) => {
  return iconMap[path] || Folder
}
</script>

<style scoped>
.el-header {
  padding: 0 20px;
}
</style>