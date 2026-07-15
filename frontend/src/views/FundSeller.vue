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
          <el-form-item label="卖出类型">
            <el-select v-model="searchForm.type" placeholder="请选择类型" clearable style="width: 120px;">
              <el-option label="手工卖出" value="1" />
              <el-option label="止盈卖出" value="2" />
              <el-option label="止损卖出" value="3" />
            </el-select>
          </el-form-item>
          <el-form-item label="执行状态">
            <el-select v-model="searchForm.sell_status" placeholder="请选择状态" clearable style="width: 120px;">
              <el-option label="未执行" value="PENDING" />
              <el-option label="已成功" value="SUCCESS" />
              <el-option label="执行失败" value="FAILED" />
            </el-select>
          </el-form-item>
          <el-form-item label="卖出日期范围">
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
      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; gap: 10px;">
          <el-button type="primary" @click="showAddDialog">新增卖出记录</el-button>
          <el-button type="warning" @click="refreshAmount" :loading="refreshing">刷新金额</el-button>
        </div>
        <el-popover
          v-model:visible="popoverVisible"
          trigger="click"
          placement="bottom-end"
          :width="220"
          popper-style="padding: 4px;"
        >
          <template #reference>
            <span style="cursor: pointer; display: inline-flex; align-items: center;">
              <el-tooltip content="更多功能" placement="top">
                <el-icon :size="20" style="color: #409EFF;">
                  <MoreFilled />
                </el-icon>
              </el-tooltip>
            </span>
          </template>
          <div class="feature-panel" @mouseenter="handlePopoverMouseEnter" @mouseleave="handlePopoverMouseLeave">
            <div class="feature-panel-body">
              <div class="feature-item" @click="exportData">
                <el-icon><Download /></el-icon>
                <div class="feature-item-info">
                  <div class="feature-item-title">导出数据</div>
                  <div class="feature-item-desc">将当前数据导出为文件</div>
                </div>
              </div>
              <!-- 预留更多功能入口 -->
            </div>
          </div>
        </el-popover>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px;">
        <el-table :data="sellers" style="width: 100%" v-loading="loading" @sort-change="handleSortChange" :default-sort="defaultSort">
          <el-table-column prop="id" label="ID" width="80" sortable="custom" />
          <el-table-column prop="fund_code" label="基金代码" width="120" sortable="custom" />
          <el-table-column prop="fund_name" label="基金名称" width="200" sortable="custom" />
          <el-table-column prop="time" label="卖出日期" width="120" sortable="custom" />
          <el-table-column prop="shares" label="卖出份额" width="120" sortable="custom">
            <template #default="{ row }">
              {{ row.shares !== null && row.shares !== undefined ? Number(row.shares).toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="amt" label="卖出金额" width="120" sortable="custom">
            <template #default="{ row }">
              {{ row.amt !== null && row.amt !== undefined ? Number(row.amt).toFixed(2) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="nav" label="卖出净值" width="120" sortable="custom">
            <template #default="{ row }">
              {{ row.nav !== null && row.nav !== undefined ? Number(row.nav).toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="realized_profit" label="已实现盈亏" width="140" sortable="custom">
            <template #default="{ row }">
              <span v-if="row.realized_profit !== null && row.realized_profit !== undefined"
                    :style="{ color: profitColor(row.realized_profit) }">
                {{ signedMoney(row.realized_profit) }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="卖出类型" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="typeTagType[row.type] || 'info'">
                {{ typeMap[row.type] || row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sell_status" label="执行状态" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="statusMap[row.sell_status]?.type || 'info'">
                {{ statusMap[row.sell_status]?.label || row.sell_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" sortable="custom" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteSeller(row)">删除</el-button>
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
      :title="isEdit ? '编辑卖出记录' : '新增卖出记录'"
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
        <el-form-item label="卖出日期" required>
          <el-date-picker v-model="formData.time" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="卖出份额" required>
          <el-input v-model="formData.shares" placeholder="请输入卖出份额" />
        </el-form-item>
        <el-form-item label="卖出金额">
          <el-input v-model="formData.amt" placeholder="自动计算" disabled />
        </el-form-item>
        <el-form-item label="卖出净值">
          <el-input v-model="formData.nav" placeholder="自动计算" disabled />
        </el-form-item>
        <el-form-item label="已实现盈亏">
          <el-input v-model="formData.realized_profit" placeholder="自动计算" disabled />
        </el-form-item>
        <el-form-item label="卖出类型">
          <el-select v-model="formData.type" placeholder="请选择卖出类型">
            <el-option label="手工卖出" value="1" />
            <el-option label="止盈卖出" value="2" />
            <el-option label="止损卖出" value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行状态">
          <el-select v-model="formData.sell_status" placeholder="请选择状态">
            <el-option label="未执行" value="PENDING" />
            <el-option label="已成功" value="SUCCESS" />
            <el-option label="执行失败" value="FAILED" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略脚本">
          <el-input v-model="formData.policy" placeholder="适用策略脚本" />
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, Download } from '@element-plus/icons-vue'
import { sellerApi, fundApi, taskApi } from '@/api'

const sellers = ref([])
const funds = ref([])
const fundOptions = ref([])
const loading = ref(false)
const refreshing = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

// 功能面板相关
const popoverVisible = ref(false)
let popoverHideTimer = null

const handlePopoverMouseEnter = () => {
  if (popoverHideTimer) {
    clearTimeout(popoverHideTimer)
    popoverHideTimer = null
  }
}

const handlePopoverMouseLeave = () => {
  popoverHideTimer = setTimeout(() => {
    popoverVisible.value = false
  }, 2000)
}

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
  '1': '手工卖出',
  '2': '止盈卖出',
  '3': '止损卖出'
}

// 卖出类型 el-tag 配色：手动-info灰、止盈-success绿、止损-danger红
const typeTagType = {
  '1': 'info',
  '2': 'success',
  '3': 'danger'
}

const statusMap = {
  'PENDING': { label: '未执行', type: 'warning' },
  'SUCCESS': { label: '已成功', type: 'success' },
  'FAILED': { label: '执行失败', type: 'danger' }
}

// A股配色：涨红跌绿（与 IndexAnalysis/PositionAnalysis 一致）
const profitColor = (v) => {
  const n = Number(v)
  if (n > 0) return '#f56c6c'
  if (n < 0) return '#67c23a'
  return '#303133'
}

// 带符号金额：正数 +¥123.45，负数 -¥123.45（符号统一在 ¥ 前）
const signedMoney = (v) => {
  if (v == null) return '-'
  const n = Number(v)
  const abs = Math.abs(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n >= 0 ? '+' : '-') + '¥' + abs
}

// 搜索表单
const searchForm = ref({
  fund_code: '',
  fund_name: '',
  type: '',
  sell_status: '',
  start_time: '',
  end_time: ''
})

const formData = ref({
  fund_code: '',
  fund_name: '',
  time: '',
  shares: 0.0,
  amt: null,
  nav: null,
  realized_profit: null,
  type: '',
  policy: '',
  sell_status: 'PENDING',
  remark: ''
})

// 获取卖出记录列表（支持搜索和分页）
const fetchSellers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.fund_code,
      fund_name: searchForm.value.fund_name,
      type: searchForm.value.type,
      sell_status: searchForm.value.sell_status,
      start_time: searchForm.value.start_time,
      end_time: searchForm.value.end_time
    }

    // 添加排序参数
    if (sortField.value && sortOrder.value) {
      params.sort_field = sortField.value
      params.sort_order = sortOrder.value
    }

    const result = await sellerApi.getSellers(params)
    sellers.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error('获取卖出记录失败')
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
  localStorage.setItem('seller_sort_field', sortField.value)
  localStorage.setItem('seller_sort_order', sortOrder.value)

  // 重新获取数据
  currentPage.value = 1
  fetchSellers()
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchSellers()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchSellers()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchSellers()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    fund_code: '',
    fund_name: '',
    type: '',
    sell_status: '',
    start_time: '',
    end_time: ''
  }
  currentPage.value = 1
  fetchSellers()
}

// 导出数据
const exportData = () => {
  ElMessage.info('导出功能开发中...')
}

// 刷新金额（手动触发计算卖出金额任务）
const refreshAmount = async () => {
  refreshing.value = true
  try {
    await taskApi.runTask('calculate_seller_amount_task')
    ElMessage.success('金额刷新已触发，请稍后刷新页面查看结果')
    setTimeout(() => {
      fetchSellers()
    }, 2000)
  } catch (error) {
    ElMessage.error('刷新金额失败')
  } finally {
    refreshing.value = false
  }
}

// 显示新增对话框
const showAddDialog = () => {
  isEdit.value = false
  formData.value = {
    fund_code: '',
    fund_name: '',
    time: getToday(),
    shares: 0.0,
    amt: null,
    nav: null,
    realized_profit: null,
    type: '1',
    policy: '',
    sell_status: 'PENDING',
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
    shares: row.shares,
    amt: row.amt,
    nav: row.nav,
    realized_profit: row.realized_profit,
    type: row.type,
    policy: row.policy,
    sell_status: row.sell_status,
    remark: row.remark
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  if (!formData.value.fund_code || !formData.value.time || !(Number(formData.value.shares) > 0)) {
    ElMessage.warning('请填写必填项（基金代码、卖出日期、卖出份额>0）')
    return
  }

  try {
    if (isEdit.value) {
      await sellerApi.updateSeller(editId.value, formData.value)
      ElMessage.success('更新成功')
    } else {
      await sellerApi.createSeller(formData.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchSellers()
  } catch (error) {
    const errorInfo = error.response?.data
    const errorMsg = errorInfo?.error || errorInfo?.message || error.message
    ElMessage.error((isEdit.value ? '更新失败: ' : '创建失败: ') + errorMsg)
  }
}

// 删除卖出记录
const deleteSeller = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该卖出记录吗？（删除后不会回补持仓份额）', '提示', {
      type: 'warning'
    })
    await sellerApi.deleteSeller(row.id)
    ElMessage.success('删除成功')
    fetchSellers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  // 从localStorage加载排序状态
  const savedSortField = localStorage.getItem('seller_sort_field')
  const savedSortOrder = localStorage.getItem('seller_sort_order')
  if (savedSortField && savedSortOrder) {
    sortField.value = savedSortField
    sortOrder.value = savedSortOrder
  }
  fetchSellers()
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
.feature-panel {
  border-radius: 4px;
  overflow: hidden;
}

.feature-panel-body {
  padding: 8px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.feature-item:hover {
  background-color: #f5f7fa;
}

.feature-item .el-icon {
  font-size: 16px;
  color: #409EFF;
  flex-shrink: 0;
}

.feature-item-info {
  flex: 1;
  min-width: 0;
}

.feature-item-title {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
  line-height: 1.3;
}

.feature-item-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 1px;
  line-height: 1.3;
}
</style>
