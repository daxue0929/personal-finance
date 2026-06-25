import axios from 'axios'

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
api.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    // 不在这里显示错误消息，由调用方自行处理
    return Promise.reject(error)
  }
)

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

  // 立即执行任务
  runTask: (taskFunc, forceRun = false) =>
    api.post(`/task/run/${taskFunc}`, { force_run: forceRun }),

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