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
        <template v-for="menu in menuItems" :key="menu.path">
          <el-sub-menu v-if="menu.meta?.isParent && menu.children" :index="menu.path">
            <template #title>
              <el-icon>
                <component :is="getIconComponent(menu.path)" />
              </el-icon>
              <span>{{ menu.meta.title }}</span>
            </template>
            <el-menu-item
              v-for="child in getChildrenMenu(menu)"
              :key="child.path"
              :index="child.path"
            >
              <el-icon>
                <component :is="getIconComponent(child.path)" />
              </el-icon>
              <span>{{ child.meta.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="menu.path">
            <el-icon>
              <component :is="getIconComponent(menu.path)" />
            </el-icon>
            <span>{{ menu.meta.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background-color: #fff; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between;">
        <div style="font-size: 16px; font-weight: 500;">
          {{ currentTitle }}
        </div>
        <div v-if="auth.user" style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 14px; color: #303133;">{{ auth.user.display_name || auth.user.username }}</span>
          <el-tag size="small" :type="isAdmin() ? 'warning' : 'info'">
            {{ isAdmin() ? '管理员' : '普通用户' }}
          </el-tag>
          <el-button link class="logout-btn" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <TagsView />

      <el-main style="background-color: #f5f5f5; padding: 0;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Setting, Wallet, ShoppingCart, Sell, TrendCharts, Folder, Monitor, User, DataAnalysis, Document, DataLine, PieChart, Coin, Histogram, Odometer } from '@element-plus/icons-vue'
import { authApi } from '@/api'
import TagsView from '@/components/TagsView.vue'
import { auth, isAdmin, clearAuthUser } from '@/stores/auth'

const router = useRouter()
const route = useRoute()

// 是否对当前用户可见（管理员专属项对普通用户隐藏）
const visible = (r) => !(r.meta?.adminOnly && !isAdmin())

// 获取路由列表并按sort排序
// 注意：菜单取自 Layout 父路由（根路径 '/'）的 children，而非 routes[0]——
// 登录页等独立全屏路由可能排在 Layout 之前，按下标取会取错。
const menuItems = computed(() => {
  const layoutRoute = router.options.routes.find(r => r.path === '/' && r.children)
  const routes = layoutRoute?.children || []
  return routes
    .filter(r => r.path && r.meta?.title && visible(r))
    .sort((a, b) => (a.meta?.sort || 0) - (b.meta?.sort || 0))
})

const getChildrenMenu = (menu) => {
  return (menu.children || [])
    .filter(r => r.path && r.meta?.title && visible(r))
    .sort((a, b) => (a.meta?.sort || 0) - (b.meta?.sort || 0))
}

const activeMenu = computed(() => {
  return route.path
})

const currentTitle = computed(() => {
  return route.meta?.title || '理财管理系统'
})

// 图标映射
const iconMap = {
  '/dashboard': Odometer,
  '/portfolio': Folder,
  '/buyers': ShoppingCart,
  '/sellers': Sell,
  '/funds': Wallet,
  '/funds/history': TrendCharts,
  '/position-analysis': PieChart,
  '/position-analysis/manage': Coin,
  '/position-analysis/analysis': Histogram,
  '/index': DataAnalysis,
  '/index/info': Document,
  '/index/analysis': DataLine,
  '/tasks': Setting,
  '/system': Monitor,
  '/system/logs': Monitor,
  '/system/tasks': Setting,
  '/system/users': User
}

const getIconComponent = (path) => {
  return iconMap[path] || Folder
}

// 退出登录
const handleLogout = async () => {
  try {
    await authApi.logout()
  } catch (e) {
    // 即使后端 401 也继续清除本地状态
  }
  clearAuthUser()
  ElMessage.info('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.el-header {
  padding: 0 20px;
}
/* 退出登录：基色 ink-2，悬停变 danger（DESIGN §4.3） */
.logout-btn {
  --el-button-text-color: #606262;
  --el-button-hover-text-color: #f56c6c;
}
</style>
