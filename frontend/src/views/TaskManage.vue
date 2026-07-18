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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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

// 立即执行任务
const runTask = async (row) => {
  try {
    await ElMessageBox.confirm('确定要立即执行该任务吗？', '提示', {
      type: 'info'
    })
    await taskApi.runTask(row.task_func, true)
    ElMessage.success('任务已触发执行')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('执行失败')
    }
  }
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
</style>