<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="基金代码">
            <FundSelect v-model="searchForm.fund_code" width="200px" placeholder="请选择基金" @select="handleSearch" />
          </el-form-item>
          <el-form-item label="基金名称">
            <el-input v-model="searchForm.fund_name" placeholder="基金名称" clearable style="width: 180px;" @keyup.enter="handleSearch" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
            <el-button type="success" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              新增持仓
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="list" style="width: 100%" height="100%" v-loading="loading">
          <el-table-column prop="fund_code" label="基金代码" width="100" />
          <el-table-column prop="fund_name" label="基金名称" min-width="180" />
          <el-table-column prop="shares" label="份额" width="120" align="right">
            <template #default="{ row }">{{ fmt(row.shares, 4) }}</template>
          </el-table-column>
          <el-table-column prop="cost_price" label="成本价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.cost_price, 4) }}</template>
          </el-table-column>
          <el-table-column prop="current_price" label="现价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.current_price, 4) }}</template>
          </el-table-column>
          <el-table-column prop="current_value" label="市值" width="120" align="right">
            <template #default="{ row }">¥{{ fmt(row.current_value) }}</template>
          </el-table-column>
          <el-table-column prop="profit_loss" label="盈亏" width="120" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.profit_loss >= 0 ? '#f56c6c' : '#67c23a' }">
                {{ row.profit_loss >= 0 ? '+' : '' }}¥{{ fmt(row.profit_loss) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="profit_loss_rate" label="盈亏率" width="100" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.profit_loss_rate >= 0 ? '#f56c6c' : '#67c23a' }">
                {{ row.profit_loss_rate >= 0 ? '+' : '' }}{{ fmt(row.profit_loss_rate) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="buy_date" label="买入日期" width="120" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
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

    <!-- 新增/编辑持仓对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑持仓' : '新增持仓'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="基金代码" required>
          <FundSelect v-model="form.fund_code" :disabled="isEdit" placeholder="请选择基金" @select="onFundSelect" />
        </el-form-item>
        <el-form-item label="基金名称">
          <el-input v-model="form.fund_name" disabled />
        </el-form-item>
        <el-form-item label="持仓份额" required>
          <el-input-number v-model="form.shares" :min="0" :precision="4" :step="100" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="成本价" required>
          <el-input-number v-model="form.cost_price" :min="0" :precision="4" :step="0.01" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="当前净值">
          <el-input-number v-model="form.current_price" :min="0" :precision="4" :step="0.01" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="买入日期" required>
          <el-date-picker v-model="form.buy_date" type="date" value-format="YYYY-MM-DD" style="width: 100%;" />
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
import { Plus } from '@element-plus/icons-vue'
import { portfolioApi } from '@/api'
import FundSelect from '@/components/FundSelect.vue'

const list = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchForm = ref({ fund_code: '', fund_name: '' })

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = ref({ fund_code: '', fund_name: '', shares: 0, cost_price: 0, current_price: 0, buy_date: '' })

const fmt = (v, digits = 2) => (v != null ? Number(v).toFixed(digits) : '-')
// 本地日期（避免 toISOString 在北京时间凌晨取到昨天）
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await portfolioApi.getPositions({
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.fund_code,
      fund_name: searchForm.value.fund_name
    })
    list.value = res.data
    total.value = res.total
  } catch (e) {
    ElMessage.error('获取持仓列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { currentPage.value = 1; fetchList() }
const resetSearch = () => {
  searchForm.value = { fund_code: '', fund_name: '' }
  currentPage.value = 1
  fetchList()
}
const handleSizeChange = () => { currentPage.value = 1; fetchList() }
const handleCurrentChange = () => { fetchList() }

const showAddDialog = () => {
  isEdit.value = false
  editId.value = null
  form.value = { fund_code: '', fund_name: '', shares: 0, cost_price: 0, current_price: 0, buy_date: todayStr() }
  dialogVisible.value = true
}

const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  form.value = {
    fund_code: row.fund_code,
    fund_name: row.fund_name,
    shares: row.shares,
    cost_price: row.cost_price,
    current_price: row.current_price,
    buy_date: row.buy_date
  }
  dialogVisible.value = true
}

const submitForm = async () => {
  if (!form.value.fund_code || !form.value.shares || !form.value.cost_price) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    if (isEdit.value) {
      await portfolioApi.updatePosition(editId.value, form.value)
      ElMessage.success('持仓更新成功')
    } else {
      await portfolioApi.createPosition(form.value)
      ElMessage.success('持仓新增成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(isEdit.value ? '更新失败' : '新增失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除持仓 ${row.fund_code} ${row.fund_name} 吗？`, '提示', { type: 'warning' })
    await portfolioApi.deletePosition(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 选择基金时自动带出名称和最新净值（FundSelect 抛出完整 fund 对象）
const onFundSelect = (fund) => {
  if (isEdit.value) return
  if (!fund) {
    form.value.fund_name = ''
    form.value.current_price = 0
    return
  }
  form.value.fund_name = fund.fund_name
  form.value.current_price = fund.net_asset_value || 0
}

onMounted(() => {
  fetchList()
})
</script>

<style scoped>
</style>
