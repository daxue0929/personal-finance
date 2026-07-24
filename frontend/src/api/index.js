import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '@/router'
import { clearAuthUser } from '@/stores/auth'

// 根据环境选择不同的 baseURL
const baseURL = import.meta.env.PROD ? '/prod-api' : '/api'

const api = axios.create({
  baseURL: baseURL,
  timeout: 10000
})

// 请求重试机制
const retry = async (fn, retries = 2, delay = 1000) => {
  try {
    return await fn()
  } catch (error) {
    if (retries > 0 && (error.code === 'ECONNABORTED' ||
        (error.response && error.response.status >= 500))) {
      await new Promise(resolve => setTimeout(resolve, delay))
      return retry(fn, retries - 1, delay * 2)
    }
    throw error
  }
}

// 请求拦截器
// Cookie 鉴权模式：HttpOnly Cookie 由浏览器自动随请求携带，无需手动注入 Authorization 头。
// 同源（dev Vite 代理 / prod Nginx 反代）下 withCredentials 默认即可。
api.interceptors.request.use(
  config => config,
  error => Promise.reject(error)
)

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    // 401：登录态失效。清状态 + 跳登录页 + 提示。
    // _skipAuthHandler：部分请求（如 /api/me 探测、/api/logout）自行处理 401，不在此兜底
    const skip = error.config && error.config._skipAuthHandler
    if (error.response && error.response.status === 401 && !skip) {
      clearAuthUser()
      ElMessage.error('登录已过期，请重新登录')
      const current = router.currentRoute.value
      if (current.path !== '/login') {
        router.push({ path: '/login', query: { redirect: current.fullPath } })
      }
    }
    return Promise.reject(error)
  }
)

// 鉴权相关API
export const authApi = {
  // 登录（跳过 401 兜底：登录失败由 Login.vue 自行展示错误，避免「登录已过期」误导）
  login: (data) => api.post('/login', data, { _skipAuthHandler: true }),
  // 退出登录（跳过 401 兜底，自行处理）
  logout: () => api.post('/logout', {}, { _skipAuthHandler: true }),
  // 获取当前登录用户（首次探测；跳过 401 兜底，由路由守卫/App.vue 处理）
  me: () => api.get('/me', { _skipAuthHandler: true })
}

// 用户管理相关API（仅管理员）
export const userApi = {
  // 获取用户列表（支持搜索和分页）
  getUsers: (params) => api.get('/users', { params }),

  // 创建用户
  createUser: (data) => api.post('/users', data),

  // 更新用户
  updateUser: (id, data) => api.put(`/users/${id}`, data),

  // 删除用户
  deleteUser: (id) => api.delete(`/users/${id}`)
}

// 任务配置相关API
export const taskApi = {
  // 获取任务列表（支持搜索和分页）
  getTasks: (params) => api.get('/tasks', { params }),

  // 获取单个任务
  getTask: (id) => api.get(`/tasks/${id}`),

  // 创建任务
  createTask: (data) => api.post('/tasks', data),

  // 更新任务
  updateTask: (id, data) => api.put(`/tasks/${id}`, data),

  // 删除任务
  deleteTask: (id) => api.delete(`/tasks/${id}`),

  // 立即执行任务（异步：立即返回 triggered，不再同步等任务跑完）
  runTask: (taskFunc, forceRun = false) =>
    api.post(`/task/run/${taskFunc}`, { force_run: forceRun }),

  // 查询当前运行中的 task_func 集合（轻量轮询接口，不拉全量列表）
  getRunningTasks: () => api.get('/tasks/running'),

  // 查询任务执行记录列表（执行计划弹窗，分页+task_func/status 过滤）
  getRunHistory: (params) => api.get('/task-records', { params }),

  // 查询单条执行记录（轮询执行状态用）
  getRunStatus: (recordId) => api.get(`/task-records/${recordId}`),

  // 清理 N 天前的执行记录
  cleanRunHistory: (days) => api.delete('/task-records', { params: { days } }),

  // 获取调度器状态
  getStatus: () => api.get('/status')
}

// 基金管理相关API
export const fundApi = {
  // 获取基金列表（支持搜索和分页）
  getFunds: (params) => api.get('/funds', { params }),

  // 获取单个基金
  getFund: (id) => api.get(`/funds/${id}`),

  // 创建基金
  createFund: (data) => api.post('/funds', data),

  // 更新基金
  updateFund: (id, data) => api.put(`/funds/${id}`, data),

  // 删除基金
  deleteFund: (id) => api.delete(`/funds/${id}`)
}

// 基金定投计划相关API（一个基金可配多条定投规则）
export const dipPlanApi = {
  // 获取定投计划列表（传 fund_code 查指定基金的，不传查全部启用中）
  getPlans: (fundCode) => api.get('/dip-plans', { params: { fund_code: fundCode || '' } }),

  // 创建定投计划
  createPlan: (data) => api.post('/dip-plans', data),

  // 更新定投计划
  updatePlan: (id, data) => api.put(`/dip-plans/${id}`, data),

  // 删除定投计划
  deletePlan: (id) => api.delete(`/dip-plans/${id}`)
}

// 基金买入流水相关API
export const buyerApi = {
  // 获取买入记录列表（支持搜索和分页）
  getBuyers: (params) => api.get('/buyers', { params }),

  // 获取单个买入记录
  getBuyer: (id) => api.get(`/buyers/${id}`),

  // 创建买入记录
  createBuyer: (data) => api.post('/buyers', data),

  // 更新买入记录
  updateBuyer: (id, data) => api.put(`/buyers/${id}`, data),

  // 删除买入记录
  deleteBuyer: (id) => api.delete(`/buyers/${id}`),

  // 快捷买入
  quickBuy: (data) => api.post('/buyers/quick-buy', data)
}

// 基金卖出流水相关API
export const sellerApi = {
  // 获取卖出记录列表（支持搜索和分页）
  getSellers: (params) => api.get('/sellers', { params }),

  // 获取单个卖出记录
  getSeller: (id) => api.get(`/sellers/${id}`),

  // 创建卖出记录
  createSeller: (data) => api.post('/sellers', data),

  // 更新卖出记录
  updateSeller: (id, data) => api.put(`/sellers/${id}`, data),

  // 删除卖出记录
  deleteSeller: (id) => api.delete(`/sellers/${id}`)
}

// 基金历史净值相关API
export const fundNavApi = {
  // 获取基金历史净值列表（支持日期范围筛选和分页）
  getNavHistory: (fundCode, params) => api.get('/funds/history', { params: { fund_code: fundCode, ...params } })
}

// 系统日志相关API
export const logApi = {
  // 获取日志列表（支持搜索和分页）
  getLogs: (params) => api.get('/logs', { params }),

  // 获取单个日志详情
  getLog: (id) => api.get(`/logs/${id}`),

  // 删除日志
  deleteLog: (id) => api.delete(`/logs/${id}`),

  // 清理日志
  cleanLogs: (data) => api.post('/logs/clean', data)
}

// 持仓组合相关API
export const portfolioApi = {
  // 获取组合列表（支持搜索和分页，不包含持仓）
  getPortfolios: async (params) => retry(() => api.get('/portfolios', { params })),

  // 获取单个组合（包含持仓列表）
  getPortfolio: (id) => api.get(`/portfolios/${id}`),

  // 获取组合的持仓列表
  getPortfolioPositions: (portfolioId) => api.get(`/portfolios/${portfolioId}/positions`),

  // 创建组合
  createPortfolio: (data) => api.post('/portfolios', data),

  // 更新组合
  updatePortfolio: (id, data) => api.put(`/portfolios/${id}`, data),

  // 删除组合
  deletePortfolio: (id) => api.delete(`/portfolios/${id}`),

  // 获取持仓列表（支持搜索和分页）
  getPositions: (params) => api.get('/positions', { params }),

  // 获取单个持仓
  getPosition: (id) => api.get(`/positions/${id}`),

  // 按基金代码查询已有持仓（添加持仓时带出）
  getPositionByFund: (fundCode) => api.get('/positions/by-fund', { params: { fund_code: fundCode } }),

  // 创建持仓
  createPosition: (data) => api.post('/positions', data),

  // 更新持仓
  updatePosition: (id, data) => api.put(`/positions/${id}`, data),

  // 删除持仓
  deletePosition: (id) => api.delete(`/positions/${id}`),

  // 创建组合持仓关联
  createPortfolioPosition: (data) => api.post('/portfolio-positions', data),

  // 删除组合持仓关联
  deletePortfolioPosition: (id) => api.delete(`/portfolio-positions/${id}`)
}

// 指数分析相关API
export const indexApi = {
  // 获取指数信息列表（支持搜索、日期范围、分页）
  getIndexes: (params) => api.get('/indexes', { params }),

  // 获取指数下拉选项
  getOptions: () => api.get('/indexes/options'),

  // 获取指数分析数据（概览+价格序列+均线+成交额+涨跌幅分布+月度收益+均线信号）
  getAnalysis: (params) => api.get('/indexes/analysis', { params }),

  // 定投模拟
  getDca: (params) => api.get('/indexes/dca', { params })
}

// 持仓分析相关API
export const positionAnalysisApi = {
  // 获取有快照数据的可选持仓列表（分析页下拉）
  getOptions: () => api.get('/positions/snapshot/options'),

  // 获取持仓分析数据（概览+盈亏/市值序列+最大回撤+全部持仓占比饼图）
  getAnalysis: (params) => api.get('/positions/snapshot/analysis', { params }),

  // 获取成本价↔指数对应走势（单持仓，规则 A 固定比例·最新日）
  getCostIndex: (params) => api.get('/positions/snapshot/cost-index', { params })
}
