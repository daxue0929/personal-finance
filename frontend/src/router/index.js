import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/components/Layout.vue'
import TaskManage from '@/views/TaskManage.vue'
import FundManage from '@/views/FundManage.vue'
import FundBuyer from '@/views/FundBuyer.vue'
import FundNavHistory from '@/views/FundNavHistory.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/tasks',
    children: [
      {
        path: '/tasks',
        name: 'TaskManage',
        component: TaskManage,
        meta: { title: '任务配置管理' }
      },
      {
        path: '/funds',
        name: 'FundManage',
        component: FundManage,
        meta: { title: '基金信息管理' }
      },
      {
        path: '/buyers',
        name: 'FundBuyer',
        component: FundBuyer,
        meta: { title: '基金买入流水' }
      },
      {
        path: '/funds/history',
        name: 'FundNavHistory',
        component: FundNavHistory,
        meta: { title: '基金历史净值' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router