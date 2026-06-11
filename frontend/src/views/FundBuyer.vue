<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none;" :body-style="{ padding: '0' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="基金代码">
            <el-input v-model="searchForm.fund_code" placeholder="请输入基金代码" clearable />
          </el-form-item>
          <el-form-item label="基金名称">
            <el-input v-model="searchForm.fund_name" placeholder="请输入基金名称" clearable />
          </el-form-item>
          <el-form-item label="买入类型">
            <el-select v-model="searchForm.type" placeholder="请选择类型" clearable style="width: 120px;">
              <el-option label="手工买入" value="1" />
              <el-option label="定投买入" value="2" />
            </el-select>
          </el-form-item>
          <el-form-item label="执行状态">
            <el-select v-model="searchForm.buy_status" placeholder="请选择状态" clearable style="width: 120px;">
              <el-option label="未执行" value="PENDING" />
              <el-option label="已成功" value="SUCCESS" />
              <el-option label="执行失败" value="FAILED" />
            </el-select>
          </el-form-item>
          <el-form-item label="买入日期范围">
            <el-date-picker v-model="searchForm.start_time" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" style="width: 140px;" />
            <span style="margin: 0 10px;">-</span>
            <el-date-picker v-model="searchForm.end_time" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 140px;" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 功能区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: flex-start; gap: 10px;">
        <el-button type="primary" @click="showAddDialog">新增买入记录</el-button>
        <el-button type="success" @click="showQuickBuyDialog">快捷买入</el-button>
        <el-button @click="exportData">导出数据</el-button>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px;">
        <el-table :data="buyers" style="width: 100%" v-loading="loading" @sort-change="handleSortChange" :default-sort="defaultSort">
          <el-table-column prop="id" label="ID" width="80" sortable="custom" />
          <el-table-column prop="fund_code" label="基金代码" width="120" sortable="custom" />
          <el-table-column prop="fund_name" label="基金名称" width="200" sortable="custom" />
          <el-table-column prop="time" label="买入日期" width="120" sortable="custom" />
          <el-table-column prop="amt" label="买入金额" width="120" sortable="custom">
            <template #default="{ row }">
              {{ row.amt.toFixed(4) }}
            </template>
          </el-table-column>
          <el-table-column prop="type" label="买入类型" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="row.type === '1' ? 'success' : row.type === '2' ? 'warning' : 'info'">
                {{ typeMap[row.type] || row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="buy_status" label="执行状态" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="statusMap[row.buy_status]?.type || 'info'">
                {{ statusMap[row.buy_status]?.label || row.buy_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="policy" label="策略脚本" width="200" sortable="custom" />
          <el-table-column prop="remark" label="备注" sortable="custom" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteBuyer(row)">删除</el-button>
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
      :title="isEdit ? '编辑买入记录' : '新增买入记录'"
      width="600px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item label="选择基金" required>
          <el-select v-model="formData.fund_code" placeholder="请搜索选择基金" filterable remote :remote-method="(query) => searchFunds(query)" @change="handleFundSelectChange" style="width: 100%;">
            <el-option v-for="fund in fundOptions" :key="fund.id" :label="`${fund.fund_code} - ${fund.fund_name}`" :value="fund.fund_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="基金名称">
          <el-input v-model="formData.fund_name" placeholder="自动填充" disabled />
        </el-form-item>
        <el-form-item label="买入日期" required>
          <el-date-picker v-model="formData.time" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="买入金额" required>
          <el-input v-model="formData.amt" placeholder="请输入买入金额" />
        </el-form-item>
        <el-form-item label="买入类型">
          <el-select v-model="formData.type" placeholder="请选择买入类型">
            <el-option label="手工买入" value="1" />
            <el-option label="定投买入" value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行状态">
          <el-select v-model="formData.buy_status" placeholder="请选择状态">
            <el-option label="未执行" value="PENDING" />
            <el-option label="已成功" value="SUCCESS" />
            <el-option label="执行失败" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略脚本">
          <el-input v-model="formData.policy" placeholder="适用策略脚本，用于计算买入价格" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 快捷买入弹出框 -->
    <el-dialog
      v-model="quickBuyVisible"
      title="快捷买入"
      width="500px"
    >
      <el-form :model="quickBuyForm" label-width="100px">
        <el-form-item label="选择基金">
          <el-select v-model="quickBuyForm.fund_code" placeholder="请选择基金" style="width: 100%;">
            <el-option label="020292 - 华夏科创100ETF联结C" value="020292" />
          </el-select>
        </el-form-item>
        <el-form-item label="涨跌幅(%)" required>
          <el-input v-model="quickBuyForm.change_pct" placeholder="请输入涨跌幅，如 0.5" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickBuyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitQuickBuy">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { buyerApi, fundApi } from '@/api'

const buyers = ref([])
const funds = ref([])
const fundOptions = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

// 快捷买入相关
const quickBuyVisible = ref(false)
const quickBuyForm = ref({
  fund_code: '020292',
  change_pct: ''
})

// 获取今天的日期字符串
const getToday = () => new Date().toISOString().split('T')[0]

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 排序相关
const sortField = ref('')
const sortOrder = ref('')

// 默认排序（用于显示排序箭头）
const defaultSort = computed(() => {
  if (sortField.value && sortOrder.value) {
    return {
      prop: sortField.value,
      order: sortOrder.value === 'asc' ? 'ascending' : 'descending'
    }
  }
  return {}
})

const typeMap = {
  '1': '手工买入',
  '2': '定投买入'
}

const statusMap = {
  'PENDING': { label: '未执行', type: 'warning' },
  'SUCCESS': { label: '已成功', type: 'success' },
  'FAILED': { label: '执行失败', type: 'danger' }
}

// 搜索表单
const searchForm = ref({
  fund_code: '',
  fund_name: '',
  type: '',
  buy_status: '',
  start_time: '',
  end_time: ''
})

const formData = ref({
  fund_code: '',
  fund_name: '',
  time: '',
  amt: 0.0,
  type: '',
  policy: '',
  buy_status: 'PENDING',
  remark: ''
})

// 获取买入记录列表（支持搜索和分页）
const fetchBuyers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.fund_code,
      fund_name: searchForm.value.fund_name,
      type: searchForm.value.type,
      buy_status: searchForm.value.buy_status,
      start_time: searchForm.value.start_time,
      end_time: searchForm.value.end_time
    }
    
    // 添加排序参数
    if (sortField.value && sortOrder.value) {
      params.sort_field = sortField.value
      params.sort_order = sortOrder.value
    }
    
    const result = await buyerApi.getBuyers(params)
    buyers.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error('获取买入记录失败')
  } finally {
    loading.value = false
  }
}

// 排序改变
const handleSortChange = ({ prop, order }) => {
  if (order) {
    sortField.value = prop
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  } else {
    sortField.value = ''
    sortOrder.value = ''
  }
  
  // 保存排序状态到localStorage
  localStorage.setItem('buyer_sort_field', sortField.value)
  localStorage.setItem('buyer_sort_order', sortOrder.value)
  
  // 重新获取数据
  currentPage.value = 1
  fetchBuyers()
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchBuyers()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchBuyers()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchBuyers()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    fund_code: '',
    fund_name: '',
    type: '',
    buy_status: '',
    start_time: '',
    end_time: ''
  }
  currentPage.value = 1
  fetchBuyers()
}

// 导出数据
const exportData = () => {
  ElMessage.info('导出功能开发中...')
}

// 显示快捷买入对话框
const showQuickBuyDialog = () => {
  quickBuyForm.value = {
    fund_code: '020292',
    change_pct: ''
  }
  quickBuyVisible.value = true
}

// 提交快捷买入
const submitQuickBuy = async () => {
  if (!quickBuyForm.value.change_pct) {
    ElMessage.warning('请输入涨跌幅')
    return
  }
  
  try {
    await buyerApi.quickBuy({
      fund_code: quickBuyForm.value.fund_code,
      change_pct: quickBuyForm.value.change_pct
    })
    ElMessage.success('快捷买入成功')
    quickBuyVisible.value = false
    fetchBuyers()
  } catch (error) {
    ElMessage.error('快捷买入失败: ' + (error.response?.data?.error || error.message))
  }
}

// 显示新增对话框
const showAddDialog = () => {
  isEdit.value = false
  formData.value = {
    fund_code: '',
    fund_name: '',
    time: getToday(),
    amt: 0.0,
    type: '1',
    policy: '',
    buy_status: 'PENDING',
    remark: ''
  }
  dialogVisible.value = true
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  formData.value = {
    fund_code: row.fund_code,
    fund_name: row.fund_name,
    time: row.time,
    amt: row.amt,
    type: row.type,
    policy: row.policy,
    buy_status: row.buy_status,
    remark: row.remark
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  if (!formData.value.fund_code || !formData.value.time || formData.value.amt <= 0) {
    ElMessage.warning('请填写必填项（基金代码、买入日期、买入金额）')
    return
  }

  try {
    if (isEdit.value) {
      await buyerApi.updateBuyer(editId.value, formData.value)
      ElMessage.success('更新成功')
    } else {
      await buyerApi.createBuyer(formData.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchBuyers()
  } catch (error) {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  }
}

// 删除买入记录
const deleteBuyer = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该买入记录吗？', '提示', {
      type: 'warning'
    })
    await buyerApi.deleteBuyer(row.id)
    ElMessage.success('删除成功')
    fetchBuyers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  // 从localStorage加载排序状态
  const savedSortField = localStorage.getItem('buyer_sort_field')
  const savedSortOrder = localStorage.getItem('buyer_sort_order')
  if (savedSortField && savedSortOrder) {
    sortField.value = savedSortField
    sortOrder.value = savedSortOrder
  }
  fetchBuyers()
  fetchFunds()
})

// 获取基金列表
const fetchFunds = async () => {
  try {
    const result = await fundApi.getFunds({ page: 1, page_size: 1000 })
    funds.value = result.data || []
    fundOptions.value = funds.value.slice(0, 20)
  } catch (error) {
    console.error('获取基金列表失败:', error)
  }
}

// 选择基金时自动填入基金代码和名称
const handleFundSelectChange = (fundCode) => {
  const fund = funds.value.find(f => f.fund_code === fundCode)
  if (fund) {
    formData.value.fund_name = fund.fund_name
  } else {
    formData.value.fund_name = ''
  }
}

// 搜索基金
const searchFunds = async (query) => {
  if (!query) {
    fundOptions.value = funds.value.slice(0, 20)
    return
  }
  const filtered = funds.value.filter(f =>
    f.fund_code.toLowerCase().includes(query.toLowerCase()) ||
    f.fund_name.includes(query)
  )
  fundOptions.value = filtered.slice(0, 20)
}
</script>

<style scoped>
</style>