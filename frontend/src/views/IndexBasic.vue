<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <!-- 搜索区 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="代码">
            <el-input v-model="searchForm.index_code" placeholder="模糊匹配" clearable style="width: 140px;" @keyup.enter="handleSearch" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="searchForm.index_type" clearable style="width: 140px;">
              <el-option label="宽基指数" value="宽基指数" />
              <el-option label="行业指数" value="行业指数" />
              <el-option label="策略指数" value="策略指数" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 功能区 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 12px;">
        <el-button type="primary" @click="showAddDialog">新增指数</el-button>
        <div style="flex: 1;" />
        <span style="font-size: 13px; color: #606266;">显示已停用</span>
        <el-switch v-model="includeDisabled" @change="handleSearch" />
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="list" style="width: 100%;" height="100%" v-loading="loading" stripe>
          <el-table-column prop="index_code" label="代码" width="110" />
          <el-table-column prop="index_name" label="名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="市场" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.market === 'sh' ? 'primary' : 'warning'" effect="light">
                {{ row.market === 'sh' ? '沪' : '深' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="index_type" label="类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" type="info" effect="plain">{{ row.index_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }">
              <span :class="['status-dot', row.enabled === 1 ? 'on' : 'off']" />
              <span class="status-text">{{ row.enabled === 1 ? '启用' : '停用' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="create_time" label="创建时间" width="170" />
          <el-table-column prop="update_time" label="更新时间" width="170" />
          <el-table-column label="操作" width="200" fixed="right" align="center">
            <template #default="{ row }">
              <el-switch
                v-model="row.enabled"
                :active-value="1" :inactive-value="0"
                @change="(v) => toggleEnabled(row, v)"
                style="margin-right: 8px;"
              />
              <el-button link type="primary" size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button link type="danger" size="small" @click="confirmDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

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

    <!-- 新增/编辑 dialog -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑指数' : '新增指数'" width="480px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="代码" prop="index_code">
          <el-input v-model="form.index_code" :disabled="editing" maxlength="6" show-word-limit placeholder="6 位数字" />
        </el-form-item>
        <el-form-item label="市场" prop="market">
          <el-select v-model="form.market" :disabled="editing" style="width: 100%;">
            <el-option label="沪市 (sh)" value="sh" />
            <el-option label="深市 (sz)" value="sz" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="index_name">
          <el-input v-model="form.index_name" maxlength="32" placeholder="如 沪深300" />
        </el-form-item>
        <el-form-item label="类型" prop="index_type">
          <el-select v-model="form.index_type" style="width: 100%;">
            <el-option label="宽基指数" value="宽基指数" />
            <el-option label="行业指数" value="行业指数" />
            <el-option label="策略指数" value="策略指数" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用" prop="enabled">
          <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { indexBasicApi } from '@/api'

defineOptions({ name: 'IndexBasic' })

const list = ref([])
const total = ref(0)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const includeDisabled = ref(false)

const searchForm = reactive({
  index_code: '',
  index_type: ''
})

// ==================== 列表 ====================

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      include_disabled: includeDisabled.value,
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchForm.index_code) params.index_code = searchForm.index_code
    if (searchForm.index_type) params.index_type = searchForm.index_type
    const resp = await indexBasicApi.list(params)
    // axios 响应拦截器已 unwrap：resp = body = {data: [...], total, page, page_size}
    list.value = resp.data || []
    total.value = resp.total || 0
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchList()
}

const resetSearch = () => {
  searchForm.index_code = ''
  searchForm.index_type = ''
  handleSearch()
}

const handleSizeChange = (sz) => { pageSize.value = sz; fetchList() }
const handleCurrentChange = (pg) => { currentPage.value = pg; fetchList() }

onMounted(fetchList)

// ==================== 新增/编辑 ====================

const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const form = reactive({
  index_code: '',
  market: 'sh',
  index_name: '',
  index_type: '宽基指数',
  enabled: 1
})

const rules = {
  index_code: [
    { required: true, message: '请输入指数代码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '请输入 6 位数字代码', trigger: 'blur' }
  ],
  market: [{ required: true, message: '请选择市场', trigger: 'change' }],
  index_name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { min: 2, max: 32, message: '名称长度 2-32 字', trigger: 'blur' }
  ],
  index_type: [{ required: true, message: '请选择类型', trigger: 'change' }]
}

const resetForm = () => {
  Object.assign(form, {
    index_code: '', market: 'sh', index_name: '',
    index_type: '宽基指数', enabled: 1
  })
  formRef.value?.clearValidate()
}

const showAddDialog = () => {
  editing.value = false
  resetForm()
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  editing.value = true
  Object.assign(form, {
    index_code: row.index_code,
    market: row.market,
    index_name: row.index_name,
    index_type: row.index_type,
    enabled: row.enabled
  })
  dialogVisible.value = true
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editing.value) {
      // 白名单：只送后端允许的字段
      const payload = {
        market: form.market,
        index_name: form.index_name,
        index_type: form.index_type,
        enabled: form.enabled
      }
      await indexBasicApi.update(form.index_code, payload)
      ElMessage.success('更新成功')
    } else {
      await indexBasicApi.create({ ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// ==================== 删除 ====================

const confirmDelete = (row) => {
  ElMessageBox.confirm(
    `确定删除指数「${row.index_name}」吗？相关历史行情保留，仅从列表隐藏。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
    .then(async () => {
      try {
        await indexBasicApi.remove(row.index_code)
        ElMessage.success('已删除')
        fetchList()
      } catch (e) {
        ElMessage.error(e.message || '删除失败')
      }
    })
    .catch(err => {
      if (err !== 'cancel') ElMessage.error(err.message || '删除失败')
    })
}

// ==================== 启停（行内 el-switch + 失败回滚） ====================

const toggleEnabled = async (row, v) => {
  const prev = row.enabled
  row.enabled = v  // 乐观更新
  try {
    await indexBasicApi.toggle(row.index_code, v)
    ElMessage.success(v === 1 ? '已启用' : '已停用')
  } catch (e) {
    row.enabled = prev  // 回滚
    ElMessage.error(e.message || '操作失败')
  }
}
</script>

<style scoped>
.status-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.status-dot.on { background: #67c23a; }
.status-dot.off { background: #c0c4cc; }
.status-text { font-size: 12px; color: #909399; vertical-align: middle; }
</style>
