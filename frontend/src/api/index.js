import axios from 'axios'
import { ElMessage } from 'element-plus'

// 根据环境选择不同的 baseURL
const baseURL = import.meta.env.PROD ? '/prod-api' : '/api'

const api = axios.create({
  baseURL: baseURL,
  timeout: 10000
})

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
    // 显示更详细的错误信息
    let errorMsg = '请求失败'
    if (error.response) {
      // 后端返回的错误信息
      errorMsg = error.response.data?.error || error.response.data?.message || error.message
    } else if (error.request) {
      // 请求已发送但没有响应
      errorMsg = '服务器无响应，请检查网络连接'
    } else {
      // 请求配置错误
      errorMsg = error.message
    }
    ElMessage.error(errorMsg)
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