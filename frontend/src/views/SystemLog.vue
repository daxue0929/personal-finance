<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="日志级别">
            <el-select v-model="searchForm.level" placeholder="请选择级别" clearable style="width: 120px;">
              <el-option label="DEBUG" value="DEBUG" />
              <el-option label="INFO" value="INFO" />
              <el-option label="WARNING" value="WARNING" />
              <el-option label="ERROR" value="ERROR" />
              <el-option label="CRITICAL" value="CRITICAL" />
            </el-select>
          </el-form-item>
          <el-form-item label="日志分类">
            <el-select v-model="searchForm.category" placeholder="请选择分类" clearable style="width: 120px;">
              <el-option label="任务" value="task" />
              <el-option label="爬虫" value="crawler" />
              <el-option label="API" value="api" />
              <el-option label="数据库" value="database" />
              <el-option label="系统" value="system" />
            </el-select>
          </el-form-item>
          <el-form-item label="追踪ID">
            <el-input v-model="searchForm.trace_id" placeholder="请输入TraceID" clearable />
          </el-form-item>
          <el-form-item label="请求路径">
            <el-input v-model="searchForm.request_path" placeholder="请输入请求路径" clearable />
          </el-form-item>
          <el-form-item label="任务名称">
            <el-input v-model="searchForm.task_name" placeholder="请输入任务名称" clearable />
          </el-form-item>
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD HH:mm:ss"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: flex-start; gap: 10px; align-items: center;">
        <el-button type="danger" @click="handleClean">清理日志</el-button>
        <span style="color: #666; font-size: 14px; margin-left: auto;">共 {{ total }} 条记录</span>
      </div>

      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="tableData" style="width: 100%" height="100%" v-loading="loading">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="level" label="级别" width="100">
            <template #default="{ row }">
              <el-tag :type="getLevelType(row.level)">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="分类" width="100" />
          <el-table-column prop="message" label="消息" min-width="400">
            <template #default="{ row }">
              <span class="log-message" @click="showDetail(row)">
                {{ row.message }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="trace_id" label="TraceID" width="160">
            <template #default="{ row }">
              <span
                v-if="row.trace_id"
                class="trace-id-copy"
                @click="copyToClipboard(row.trace_id)"
                title="点击复制"
              >
                {{ row.trace_id }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="request_method" label="方法" width="120" />
          <el-table-column prop="request_path" label="路径" width="200" />
          <el-table-column prop="request_ip" label="IP" width="120" />
          <el-table-column prop="task_name" label="任务" width="120" />
          <el-table-column prop="create_time" label="时间" width="180" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top: 20px; display: flex; justify-content: flex-start;">
          <el-pagination
            :current-page="pagination.page"
            :page-size="pagination.page_size"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>

      <el-dialog v-model="detailVisible" title="日志详情" width="800px">
        <el-form label-width="100px" v-if="currentLog">
          <el-form-item label="日志级别">
            <el-tag :type="getLevelType(currentLog.level)">{{ currentLog.level }}</el-tag>
          </el-form-item>
          <el-form-item label="日志分类">{{ currentLog.category }}</el-form-item>
          <el-form-item label="追踪ID">{{ currentLog.trace_id }}</el-form-item>
          <el-form-item label="请求方法">{{ currentLog.request_method }}</el-form-item>
          <el-form-item label="请求路径">{{ currentLog.request_path }}</el-form-item>
          <el-form-item label="客户端IP">{{ currentLog.request_ip }}</el-form-item>
          <el-form-item label="任务名称">{{ currentLog.task_name }}</el-form-item>
          <el-form-item label="创建时间">{{ currentLog.create_time }}</el-form-item>
          <el-form-item label="日志消息">
            <pre class="log-pre">{{ currentLog.message }}</pre>
          </el-form-item>
          <el-form-item label="错误堆栈" v-if="currentLog.error_stack">
            <pre class="log-pre error-stack">{{ currentLog.error_stack }}</pre>
          </el-form-item>
        </el-form>
      </el-dialog>

      <el-dialog v-model="cleanVisible" title="清理日志" width="400px">
        <el-form label-width="100px">
          <el-form-item label="保留天数">
            <el-input-number v-model="daysToKeep" :min="1" :max="365" />
            <span style="margin-left: 10px;">天</span>
          </el-form-item>
          <el-form-item>
            <span class="warning-text">警告：此操作将删除 {{ daysToKeep }} 天前的所有日志，不可恢复！</span>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="cleanVisible = false">取消</el-button>
          <el-button type="danger" @click="confirmClean">确认清理</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup>
defineOptions({ name: 'SystemLog' })
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { logApi } from '@/api'

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const detailVisible = ref(false)
const cleanVisible = ref(false)
const currentLog = ref(null)
const daysToKeep = ref(30)
const dateRange = ref([])

const searchForm = reactive({
  level: '',
  category: '',
  trace_id: '',
  request_path: '',
  task_name: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20
})

const getLevelType = (level) => {
  const types = {
    DEBUG: 'info',
    INFO: 'success',
    WARNING: 'warning',
    ERROR: 'danger',
    CRITICAL: 'danger'
  }
  return types[level] || 'info'
}

const copyToClipboard = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch (err) {
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    ElMessage.success('已复制到剪贴板')
  }
}

const fetchLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size,
      ...searchForm
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0]
      params.end_time = dateRange.value[1]
    }
    const res = await logApi.getLogs(params)
    tableData.value = res.data || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取日志失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchLogs()
}

const handleReset = () => {
  searchForm.level = ''
  searchForm.category = ''
  searchForm.trace_id = ''
  searchForm.request_path = ''
  searchForm.task_name = ''
  dateRange.value = []
  pagination.page = 1
  fetchLogs()
}

const handleSizeChange = (size) => {
  pagination.page_size = size
  pagination.page = 1
  fetchLogs()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  fetchLogs()
}

const showDetail = (row) => {
  currentLog.value = row
  detailVisible.value = true
}

const handleDelete = async (id) => {
  try {
    await logApi.deleteLog(id)
    fetchLogs()
  } catch (error) {
    console.error('删除日志失败:', error)
  }
}

const handleClean = () => {
  cleanVisible.value = true
}

const confirmClean = async () => {
  try {
    await logApi.cleanLogs({ days_to_keep: daysToKeep.value })
    cleanVisible.value = false
    fetchLogs()
  } catch (error) {
    console.error('清理日志失败:', error)
  }
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.log-message {
  color: #409eff;
  cursor: pointer;
  text-decoration: underline;
}

.log-message:hover {
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

.log-pre {
  white-space: pre-wrap;
  word-break: break-all;
  background-color: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
}

.error-stack {
  background-color: #fef0f0;
  color: #f56c6c;
}

.warning-text {
  color: #f56c6c;
  font-size: 14px;
}
</style>