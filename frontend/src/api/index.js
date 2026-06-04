import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
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
    ElMessage.error(error.message || '请求失败')
    return Promise.reject(error)
  }
)

// 任务配置相关API
export const taskApi = {
  // 获取所有任务
  getTasks: () => api.get('/tasks'),

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
  // 获取所有基金
  getFunds: () => api.get('/funds'),

  // 获取单个基金
  getFund: (id) => api.get(`/funds/${id}`),

  // 创建基金
  createFund: (data) => api.post('/funds', data),

  // 更新基金
  updateFund: (id, data) => api.put(`/funds/${id}`, data),

  // 删除基金
  deleteFund: (id) => api.delete(`/funds/${id}`)
}

export default api