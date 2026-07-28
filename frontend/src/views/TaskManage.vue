<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="任务名称">
            <el-input v-model="searchForm.task_name" placeholder="请输入任务名称" clearable />
          </el-form-item>
          <el-form-item label="任务函数">
            <el-input v-model="searchForm.task_func" placeholder="请输入任务函数" clearable />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.enabled" placeholder="请选择状态" clearable style="width: 120px;">
              <el-option label="启用" :value="true" />
              <el-option label="禁用" :value="false" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 功能区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: flex-start; gap: 10px;">
        <el-button type="primary" @click="showAddDialog">新增任务</el-button>
        <el-button @click="refreshTasks">刷新状态</el-button>
        <el-button @click="exportData">导出数据</el-button>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="tasks" style="width: 100%" height="100%" v-loading="loading">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="task_name" label="任务名称" width="180" />
          <el-table-column prop="task_func" label="任务函数" width="200" />
          <el-table-column prop="cron_expression" label="Cron表达式" width="150" />
          <el-table-column prop="enabled" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'danger'">
                {{ row.enabled ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="next_run_time" label="下次执行时间" width="180" />
          <el-table-column label="执行中" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.running" type="warning" effect="dark">运行中</el-tag>
              <el-tag v-else type="info">空闲</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="执行计划" width="100">
            <template #default="{ row }">
              <span class="run-history-link" @click="showHistoryDialog(row)">执行计划</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="success" @click="runTask(row)">执行</el-button>
              <el-button size="small" type="danger" @click="deleteTask(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页组件 -->
        <div style="text-align: right; margin-top: 20px;">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑任务' : '新增任务'"
      width="500px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item label="任务名称">
          <el-input v-model="formData.task_name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务函数">
          <el-input v-model="formData.task_func" placeholder="请输入任务函数名" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="Cron表达式">
          <el-input v-model="formData.cron_expression" placeholder="例如: */5 * * * *" />
          <div style="color: #999; font-size: 12px; margin-top: 5px;">
            格式: 分 时 日 月 周 (例如: */5 * * * * 表示每5分钟执行)
          </div>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="formData.enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" placeholder="请输入任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 执行记录对话框 -->
    <el-dialog
      v-model="historyVisible"
      :title="`执行记录 - ${historyTaskName}`"
      width="900px"
    >
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: #666; font-size: 14px;">共 {{ historyTotal }} 条记录</span>
        <el-button size="small" type="danger" @click="cleanHistory">清理历史记录</el-button>
      </div>
      <el-table :data="historyData" style="width: 100%" height="400" v-loading="historyLoading" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="historyStatusMap[row.status]?.type || 'info'" size="small">
              {{ historyStatusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_type" label="触发" width="70">
          <template #default="{ row }">
            {{ row.trigger_type === 'cron' ? '定时' : '手动' }}
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90">
          <template #default="{ row }">
            {{ row.duration_ms != null ? (row.duration_ms >= 1000 ? (row.duration_ms/1000).toFixed(1)+'秒' : row.duration_ms+'ms') : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始时间" width="170" />
        <el-table-column prop="end_time" label="结束时间" width="170" />
        <el-table-column prop="trace_id" label="TraceID" width="220">
          <template #default="{ row }">
            <span v-if="row.trace_id" class="trace-id-copy" @click="copyTraceId(row.trace_id)" title="点击复制">
              {{ row.trace_id.substring(0, 24) }}...
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="triggered_by" label="触发者" width="90" />
        <el-table-column prop="error_message" label="错误" min-width="150" show-overflow-tooltip />
      </el-table>
      <div style="margin-top: 12px; display: flex; justify-content: flex-start;">
        <el-pagination
          v-model:current-page="historyPage"
          v-model:page-size="historyPageSize"
          :total="historyTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchHistory"
          @current-change="fetchHistory"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'TaskManage' })
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi } from '@/api'

const tasks = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 搜索表单
const searchForm = ref({
  task_name: '',
  task_func: '',
  enabled: ''
})

const formData = ref({
  task_name: '',
  task_func: '',
  cron_expression: '',
  enabled: true,
  description: ''
})

// 执行记录弹窗相关
const historyVisible = ref(false)
const historyTaskFunc = ref('')
const historyTaskName = ref('')
const historyData = ref([])
const historyLoading = ref(false)
const historyPage = ref(1)
const historyPageSize = ref(20)
const historyTotal = ref(0)
const historyStatusMap = {
  'RUNNING': { label: '运行中', type: 'warning' },
  'SUCCESS': { label: '已完成', type: 'success' },
  'FAILED': { label: '失败', type: 'danger' },
  'SKIPPED': { label: '已跳过', type: 'info' }
}

// 轮询定时器（全项目首例：5s 刷新任务列表含运行状态）
let pollTimer = null

// 获取任务列表（支持搜索和分页）
const fetchTasks = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      task_name: searchForm.value.task_name,
      task_func: searchForm.value.task_func,
      enabled: searchForm.value.enabled
    }
    const result = await taskApi.getTasks(params)
    tasks.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchTasks()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchTasks()
}

// 刷新状态
const refreshTasks = () => {
  fetchTasks()
  ElMessage.info('状态已刷新')
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchTasks()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    task_name: '',
    task_func: '',
    enabled: ''
  }
  currentPage.value = 1
  fetchTasks()
}

// 导出数据
const exportData = () => {
  ElMessage.info('导出功能开发中...')
}

// 显示新增对话框
const showAddDialog = () => {
  isEdit.value = false
  formData.value = {
    task_name: '',
    task_func: '',
    cron_expression: '',
    enabled: true,
    description: ''
  }
  dialogVisible.value = true
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  formData.value = {
    task_name: row.task_name,
    task_func: row.task_func,
    cron_expression: row.cron_expression,
    enabled: row.enabled,
    description: row.description
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  if (!formData.value.task_name || !formData.value.task_func || !formData.value.cron_expression) {
    ElMessage.warning('请填写必填项')
    return
  }

  try {
    if (isEdit.value) {
      await taskApi.updateTask(editId.value, formData.value)
      ElMessage.success('更新成功')
    } else {
      await taskApi.createTask(formData.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTasks()
  } catch (error) {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  }
}

// 删除任务
const deleteTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
      type: 'warning'
    })
    await taskApi.deleteTask(row.id)
    ElMessage.success('删除成功')
    fetchTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 立即执行任务（异步：立即返回已触发，前端轮询看状态）
const runTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要立即执行该任务吗？', '提示', {
      type: 'info'
    })
  } catch (e) {
    return  // 用户取消
  }
  try {
    const res = await taskApi.runTask(row.task_func, true)
    // 异步触发：成功返回 {status:'TRIGGERED', record_id, trace_id}；rejected 返回 {rejected:true, message}
    if (res.rejected) {
      ElMessage.warning(res.message || '任务正在运行，请等待完成')
    } else {
      ElMessage.success('任务已触发')
      // 乐观更新：立即把该任务标记为运行中（局部更新，不触发全量刷新避免闪烁）
      const t = tasks.value.find(x => x.task_func === row.task_func)
      if (t) t.running = true
    }
  } catch (error) {
    ElMessage.error('执行失败')
  }
}

// 显示执行记录弹窗
const showHistoryDialog = (row) => {
  historyTaskFunc.value = row.task_func
  historyTaskName.value = row.task_name
  historyPage.value = 1
  historyPageSize.value = 20  // 每次打开默认一页 20 条
  historyVisible.value = true
  fetchHistory()
}

// 获取执行记录
const fetchHistory = async () => {
  historyLoading.value = true
  try {
    const res = await taskApi.getRunHistory({
      task_func: historyTaskFunc.value,
      page: historyPage.value,
      page_size: historyPageSize.value
    })
    historyData.value = res.data || []
    historyTotal.value = res.total || 0
  } catch (error) {
    ElMessage.error('获取执行记录失败')
  } finally {
    historyLoading.value = false
  }
}

// 复制 trace_id（含非 HTTPS 环境降级，参照 SystemLog copyToClipboard）
const copyTraceId = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制 TraceID')
  } catch (e) {
    // 降级方案：非 HTTPS 环境 navigator.clipboard 不可用
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制 TraceID')
  }
}

// 清理历史记录
const cleanHistory = async () => {
  try {
    const { value } = await ElMessageBox.prompt('保留最近多少天的记录？', '清理历史记录', {
      confirmButtonText: '确定清理',
      cancelButtonText: '取消',
      inputType: 'number',
      inputValue: 30,
      inputValidator: (v) => parseInt(v) >= 1 || '请输入大于 0 的整数'
    })
    const days = parseInt(value)
    const res = await taskApi.cleanRunHistory(days)
    ElMessage.success(`已清理 ${res.deleted} 条记录`)
    fetchHistory()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清理失败')
    }
  }
}

// 轻量轮询：只查运行中 task_func 集合，局部更新对应任务的 running 字段（不替换 tasks 数组，避免表格闪烁）
const pollRunning = async () => {
  try {
    const res = await taskApi.getRunningTasks()
    const runningSet = new Set(res.running || [])
    // 仅更新 running 状态发生变化的任务，避免无变化时触发重渲染
    let changed = false
    for (const t of tasks.value) {
      const isRunning = runningSet.has(t.task_func)
      if (t.running !== isRunning) {
        t.running = isRunning
        changed = true
      }
    }
    // 若本地有运行中任务但已不在新集合里（完成），也刷新一次执行记录弹窗（若开着）
    if (changed && historyVisible.value) {
      fetchHistory()
    }
  } catch (e) {
    // 轮询失败静默（不影响主流程）
  }
}

onMounted(() => {
  fetchTasks()
  // 5s 轻量轮询运行状态（仅查运行中集合 + 局部更新，不拉全量列表）
  pollTimer = setInterval(pollRunning, 5000)
})

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.run-history-link {
  color: #409eff;
  cursor: pointer;
  text-decoration: underline;
}

.run-history-link:hover {
  color: #66b1ff;
}

.trace-id-copy {
  color: #409eff;
  cursor: pointer;
  font-family: monospace;
  font-size: 12px;
}

.trace-id-copy:hover {
  color: #66b1ff;
  text-decoration: underline;
}
</style>