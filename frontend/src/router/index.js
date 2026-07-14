import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/components/Layout.vue'
import TaskManage from '@/views/TaskManage.vue'
import FundManage from '@/views/FundManage.vue'
import FundBuyer from '@/views/FundBuyer.vue'
import FundNavHistory from '@/views/FundNavHistory.vue'
import PortfolioBoard from '@/views/PortfolioBoard.vue'
import SystemLog from '@/views/SystemLog.vue'
import UserManage from '@/views/UserManage.vue'
import IndexInfo from '@/views/IndexInfo.vue'
import IndexAnalysis from '@/views/IndexAnalysis.vue'
import PositionManage from '@/views/PositionManage.vue'
import PositionAnalysis from '@/views/PositionAnalysis.vue'

import { auth, whenReady } from '@/stores/auth'

const routes = [
  {
    // 登录页：独立全屏路由，不套 Layout
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/portfolio',
    meta: { requiresAuth: true },
    children: [
      {
        path: '/portfolio',
        name: 'PortfolioBoard',
        component: PortfolioBoard,
        meta: { title: '持仓看板', sort: 10 }
      },
      {
        path: '/buyers',
        name: 'FundBuyer',
        component: FundBuyer,
        meta: { title: '基金买入流水', sort: 20 }
      },
      {
        path: '/funds',
        name: 'FundManage',
        component: FundManage,
        meta: { title: '基金信息管理', sort: 30 }
      },
      {
        path: '/funds/history',
        name: 'FundNavHistory',
        component: FundNavHistory,
        meta: { title: '基金历史净值', sort: 40 }
      },
      {
        path: '/position-analysis',
        name: 'PositionAnalysisRoot',
        meta: { title: '持仓分析', sort: 15, isParent: true },
        children: [
          {
            path: '/position-analysis/manage',
            name: 'PositionManage',
            component: PositionManage,
            meta: { title: '持仓信息管理', sort: 16, parentTitle: '持仓分析' }
          },
          {
            path: '/position-analysis/analysis',
            name: 'PositionAnalysis',
            component: PositionAnalysis,
            meta: { title: '持仓分析', sort: 17, parentTitle: '持仓分析' }
          }
        ]
      },
      {
        path: '/index',
        name: 'Index',
        meta: { title: '指数分析', sort: 45, isParent: true },
        children: [
          {
            path: '/index/info',
            name: 'IndexInfo',
            component: IndexInfo,
            meta: { title: '指数信息', sort: 46, parentTitle: '指数分析' }
          },
          {
            path: '/index/analysis',
            name: 'IndexAnalysis',
            component: IndexAnalysis,
            meta: { title: '指数分析', sort: 47, parentTitle: '指数分析' }
          }
        ]
      },
      {
        path: '/system',
        name: 'System',
        meta: { title: '系统管理', sort: 50, isParent: true },
        children: [
          {
            path: '/system/logs',
            name: 'SystemLog',
            component: SystemLog,
            meta: { title: '系统日志', sort: 51, parentTitle: '系统管理' }
          },
          {
            path: '/system/tasks',
            name: 'TaskManage',
            component: TaskManage,
            meta: { title: '任务配置管理', sort: 52, parentTitle: '系统管理' }
          },
          {
            path: '/system/users',
            name: 'UserManage',
            component: UserManage,
            meta: { title: '用户管理', sort: 53, parentTitle: '系统管理', adminOnly: true }
          }
        ]
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：未登录重定向到登录页。
// Cookie 鉴权模式下前端不持有 token，故等待 App.vue 的 /api/me 探测完成后再判断，
// 避免已登录用户刷新时被闪到登录页。
router.beforeEach(async (to) => {
  if (to.meta.public) {
    // 已登录用户访问登录页 → 跳首页
    await whenReady()
    if (to.name === 'Login' && auth.user) {
      return { path: '/' }
    }
    return true
  }

  await whenReady()

  // 需鉴权但未登录 → 登录页（带 redirect）
  if (to.matched.some(r => r.meta.requiresAuth) && !auth.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 非管理员访问管理员专属页 → 回首页
  if (to.meta.adminOnly && auth.user?.role !== 'admin') {
    return { path: '/' }
  }

  return true
})

export default router
