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
        <el-menu-item index="/tasks">
        <el-icon><Setting /></el-icon>
        <span>任务配置管理</span>
      </el-menu-item>
      <el-menu-item index="/funds">
        <el-icon><Wallet /></el-icon>
        <span>基金信息管理</span>
      </el-menu-item>
      <el-menu-item index="/buyers">
        <el-icon><ShoppingCart /></el-icon>
        <span>基金买入流水</span>
      </el-menu-item>
      <el-menu-item index="/funds/history">
        <el-icon><TrendCharts /></el-icon>
        <span>基金历史净值</span>
      </el-menu-item>
        <!--
        <el-menu-item index="/funds">
          <el-icon><Wallet /></el-icon>
          <span>基金管理</span>
        </el-menu-item>
        -->

        <!--
        <el-sub-menu index="2">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>数据分析</span>
          </template>
          <el-menu-item index="/analysis/index">
            <el-icon><DataLine /></el-icon>
            <span>指数分析</span>
          </el-menu-item>
        </el-sub-menu>
        -->
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
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Setting, Wallet, ShoppingCart, TrendCharts } from '@element-plus/icons-vue'

const router = useRouter()

const activeMenu = computed(() => {
  const path = router.currentRoute.value.path
  return path
})

const currentTitle = computed(() => {
  const route = router.currentRoute.value
  return route.meta?.title || '理财管理系统'
})
</script>

<style scoped>
.el-header {
  padding: 0 20px;
}
</style>