<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none;" :body-style="{ padding: '0' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="基金">
            <FundSelect v-model="searchForm.selectedFund" width="280px" placeholder="输入代码或名称搜索" @select="handleSearch" />
          </el-form-item>
          <el-form-item label="基金类型">
            <el-select v-model="searchForm.fund_type" placeholder="请选择类型" clearable style="width: 120px;">
              <el-option label="股票型" value="股票型" />
              <el-option label="指数型" value="指数型" />
              <el-option label="债券型" value="债券型" />
              <el-option label="混合型" value="混合型" />
              <el-option label="货币型" value="货币型" />
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
        <el-button type="primary" @click="showAddDialog">新增基金</el-button>
        <el-button @click="exportData">导出数据</el-button>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px;">
        <el-table :data="funds" style="width: 100%" v-loading="loading">
          <el-table-column prop="fund_id" label="ID" width="80" />
          <el-table-column prop="fund_code" label="基金代码" width="120" />
          <el-table-column prop="fund_name" label="基金名称" width="200" />
          <el-table-column prop="fund_type" label="基金类型" width="120">
            <template #default="{ row }">
              <el-tag>{{ row.fund_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="net_asset_value" label="净值" width="100">
            <template #default="{ row }">
              {{ row.net_asset_value.toFixed(4) }}
            </template>
          </el-table-column>
          <el-table-column prop="net_value_date" label="净值日期" width="120" />
          <el-table-column prop="fund_manager" label="基金经理" width="150" />
          <el-table-column prop="fund_size" label="规模(亿元)" width="120">
            <template #default="{ row }">
              {{ row.fund_size.toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" />
          <el-table-column label="定投计划" min-width="160">
            <template #default="{ row }">
              <el-button
                link
                :type="dipSummary(dipPlansMap[row.fund_code]) === '无' ? '' : 'primary'"
                :style="{ color: dipSummary(dipPlansMap[row.fund_code]) === '无' ? '#c0c4cc' : '#409EFF' }"
                @click="openDipDialog(row)"
                title="点击管理定投计划"
              >
                {{ dipSummary(dipPlansMap[row.fund_code]) }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="info" @click="viewHistory(row)">历史</el-button>
              <el-button size="small" type="danger" @click="deleteFund(row)">删除</el-button>
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
      :title="isEdit ? '编辑基金' : '新增基金'"
      width="680px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item label="基金代码">
          <el-input v-model="formData.fund_code" placeholder="请输入基金代码" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="基金名称">
          <el-input v-model="formData.fund_name" placeholder="请输入基金名称" />
        </el-form-item>
        <el-form-item label="基金类型">
          <el-select v-model="formData.fund_type" placeholder="请选择基金类型">
            <el-option label="股票型" value="股票型" />
            <el-option label="指数型" value="指数型" />
            <el-option label="债券型" value="债券型" />
            <el-option label="混合型" value="混合型" />
            <el-option label="货币型" value="货币型" />
          </el-select>
        </el-form-item>
        <el-form-item label="净值">
          <el-input-number v-model="formData.net_asset_value" :precision="4" :min="0" />
        </el-form-item>
        <el-form-item label="净值日期">
          <el-date-picker v-model="formData.net_value_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="基金经理">
          <el-input v-model="formData.fund_manager" placeholder="请输入基金经理" />
        </el-form-item>
        <el-form-item label="成立日期">
          <el-date-picker v-model="formData.establish_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="基金规模(亿)">
          <el-input-number v-model="formData.fund_size" :precision="2" :min="0" />
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

    <!-- 定投计划管理弹窗（独立，列表页点击定投列打开） -->
    <el-dialog
      v-model="dipDialogVisible"
      :title="`定投计划 - ${dipDialogFund.fund_code} ${dipDialogFund.fund_name}`"
      width="560px"
      @closed="onDipDialogClosed"
    >
      <el-table :data="dipPlans" v-loading="dipLoading" size="small" empty-text="暂无定投计划" style="width: 100%;">
        <el-table-column label="频率" min-width="120">
          <template #default="{ row }">{{ frequencyText(row) }}</template>
        </el-table-column>
        <el-table-column prop="dip_amount" label="金额(元)" width="100" />
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enable_dip" active-value="1" inactive-value="0" @change="toggleDipEnable(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="removeDipPlan(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增定投计划行 -->
      <div v-if="dipEditing" style="margin-top: 12px; padding: 12px; background: #fafafa; border-radius: 4px;">
        <el-form :inline="true" size="small" style="margin: 0;">
          <el-form-item label="频率">
            <el-select v-model="dipForm.dip_frequency" style="width: 90px;" @change="onDipFrequencyChange">
              <el-option v-for="o in dipFrequencyOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="dipForm.dip_frequency === 'weekly'" label="周">
            <el-select v-model="dipForm.dip_day" style="width: 90px;">
              <el-option v-for="o in weekdayOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="dipForm.dip_frequency === 'monthly'" label="日">
            <el-select v-model="dipForm.dip_day" style="width: 90px;">
              <el-option v-for="o in monthDayOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="金额(元)">
            <el-input-number v-model="dipForm.dip_amount" :min="1" :precision="2" style="width: 120px;" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" @click="addDipPlan">保存</el-button>
            <el-button size="small" @click="dipEditing = false; resetDipForm()">取消</el-button>
          </el-form-item>
        </el-form>
      </div>
      <el-button v-else size="small" type="primary" plain style="margin-top: 12px;" @click="dipEditing = true">
        + 添加定投计划
      </el-button>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundApi, dipPlanApi } from '@/api'
import FundSelect from '@/components/FundSelect.vue'

const router = useRouter()

const funds = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 搜索表单：基金代码/名称合并为下拉搜索框（selectedFund 存选中的 fund_code）
const searchForm = ref({
  selectedFund: '',   // 下拉搜索框选中的基金代码
  fund_type: ''
})

const formData = ref({
  fund_code: '',
  fund_name: '',
  fund_type: '混合型',
  net_asset_value: 0.0,
  net_value_date: '',
  fund_manager: '',
  establish_date: '',
  fund_size: 0.0,
  remark: ''
})

// ===== 定投计划（列表页独立弹窗管理，单基金多规则）=====
// 定投频率选项：daily每日 / weekly每周(选周几) / monthly每月(选几号)
const dipFrequencyOptions = [
  { label: '每日', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '每月', value: 'monthly' }
]
const weekdayOptions = [
  { label: '周一', value: '1' }, { label: '周二', value: '2' }, { label: '周三', value: '3' },
  { label: '周四', value: '4' }, { label: '周五', value: '5' }, { label: '周六', value: '6' },
  { label: '周日', value: '7' }
]
// 每月 1-28 号（限 28 以内避免某些月份无 29/30/31 号）
const monthDayOptions = Array.from({ length: 28 }, (_, i) => ({ label: `${i + 1}号`, value: String(i + 1) }))

// 单条定投计划的频率文案（表格/概要通用）
const frequencyText = (row) => {
  if (!row) return ''
  if (row.dip_frequency === 'daily') return '每日'
  if (row.dip_frequency === 'weekly') {
    const w = weekdayOptions.find(o => o.value === String(row.dip_day))
    return `每周${w ? w.label.slice(1) : row.dip_day}`
  }
  if (row.dip_frequency === 'monthly') return `每月${row.dip_day}号`
  return row.dip_frequency || ''
}

// 定投概要文案：输入某基金的计划数组，返回「N条：摘要/等M条」或「无」
// 只统计启用中的计划（停用视为无），最多展示前2条频率摘要，超出截断「等N条」
const dipSummary = (plans) => {
  const enabled = (plans || []).filter(p => p.enable_dip === '1')
  if (!enabled.length) return '无'
  const summaries = enabled.map(frequencyText)
  if (summaries.length <= 2) return `${summaries.length}条：${summaries.join('/')}`
  return `${summaries.length}条：${summaries.slice(0, 2).join('/')}/等${summaries.length - 2}条`
}

// 列表各行定投概要映射：fund_code -> 计划数组（一次取全部启用计划，前端分组，避免 N+1）
const dipPlansMap = ref({})

// 加载全部启用定投计划，按 fund_code 分组，供表格概要列展示
const fetchAllDipPlansForSummary = async () => {
  try {
    const res = await dipPlanApi.getPlans('')  // 不传 fund_code 取全部启用中
    const all = res.data || []
    const map = {}
    all.forEach(p => {
      if (!map[p.fund_code]) map[p.fund_code] = []
      map[p.fund_code].push(p)
    })
    dipPlansMap.value = map
  } catch (e) {
    dipPlansMap.value = {}
  }
}

// 定投管理弹窗状态
const dipDialogVisible = ref(false)
const dipDialogFund = ref({ fund_code: '', fund_name: '' })  // 当前弹窗管理的基金
const dipPlans = ref([])          // 弹窗内该基金的定投计划列表
const dipLoading = ref(false)
const dipEditing = ref(false)     // 新增计划行是否显示
const dipForm = ref({             // 新增计划表单
  dip_frequency: 'weekly',
  dip_day: '1',
  dip_amount: 100,
  enable_dip: '1'
})

const resetDipForm = () => {
  dipForm.value = { dip_frequency: 'weekly', dip_day: '1', dip_amount: 100, enable_dip: '1' }
}

// 频率变化时重置 dip_day 默认值
const onDipFrequencyChange = (val) => {
  if (val === 'daily') dipForm.value.dip_day = ''
  else if (val === 'weekly') dipForm.value.dip_day = '1'
  else if (val === 'monthly') dipForm.value.dip_day = '1'
}

// 打开定投管理弹窗
const openDipDialog = (row) => {
  dipDialogFund.value = { fund_code: row.fund_code, fund_name: row.fund_name }
  dipEditing.value = false
  resetDipForm()
  dipDialogVisible.value = true
  fetchDipPlans(row.fund_code)
}

// 加载指定基金的定投计划（弹窗内用，取全部含停用）
const fetchDipPlans = async (fundCode) => {
  if (!fundCode) { dipPlans.value = []; return }
  dipLoading.value = true
  try {
    const res = await dipPlanApi.getPlans(fundCode)
    dipPlans.value = res.data || []
  } catch (e) {
    ElMessage.error('获取定投计划失败')
    dipPlans.value = []
  } finally {
    dipLoading.value = false
  }
}

// 新增定投计划
const addDipPlan = async () => {
  const fundCode = dipDialogFund.value.fund_code
  if (!fundCode) {
    ElMessage.warning('基金代码缺失')
    return
  }
  if (!dipForm.value.dip_amount || dipForm.value.dip_amount <= 0) {
    ElMessage.warning('请输入定投金额')
    return
  }
  try {
    await dipPlanApi.createPlan({
      fund_code: fundCode,
      fund_name: dipDialogFund.value.fund_name,
      dip_frequency: dipForm.value.dip_frequency,
      dip_day: dipForm.value.dip_frequency === 'daily' ? '' : dipForm.value.dip_day,
      dip_amount: dipForm.value.dip_amount,
      enable_dip: dipForm.value.enable_dip,
      dip_mode: 'fixed'
    })
    ElMessage.success('定投计划已添加')
    dipEditing.value = false
    resetDipForm()
    await fetchDipPlans(fundCode)
  } catch (e) {
    ElMessage.error('添加定投计划失败')
  }
}

// 切换定投计划启停
const toggleDipEnable = async (row) => {
  try {
    await dipPlanApi.updatePlan(row.id, { enable_dip: row.enable_dip })
    ElMessage.success(row.enable_dip === '1' ? '已启用' : '已停用')
  } catch (e) {
    ElMessage.error('更新失败')
    row.enable_dip = row.enable_dip === '1' ? '0' : '1' // 回滚
  }
}

// 删除定投计划
const removeDipPlan = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除该定投计划（${frequencyText(row)} ${row.dip_amount}元）？`, '提示', { type: 'warning' })
    await dipPlanApi.deletePlan(row.id)
    ElMessage.success('删除成功')
    await fetchDipPlans(dipDialogFund.value.fund_code)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

// 定投弹窗关闭后刷新外层概要（让表格概要列同步）
const onDipDialogClosed = () => {
  fetchAllDipPlansForSummary()
}

// 获取基金列表（支持搜索和分页）
const fetchFunds = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.selectedFund,  // 下拉选中后按代码过滤
      fund_type: searchForm.value.fund_type
    }
    const result = await fundApi.getFunds(params)
    funds.value = result.data
    total.value = result.total
    // 列表加载后取定投概要
    await fetchAllDipPlansForSummary()
  } catch (error) {
    ElMessage.error('获取基金列表失败')
  } finally {
    loading.value = false
  }
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchFunds()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchFunds()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchFunds()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    selectedFund: '',
    fund_type: ''
  }
  currentPage.value = 1
  fetchFunds()
}

// 导出数据
const exportData = () => {
  ElMessage.info('导出功能开发中...')
}

// 显示新增对话框
const showAddDialog = () => {
  isEdit.value = false
  formData.value = {
    fund_code: '',
    fund_name: '',
    fund_type: '混合型',
    net_asset_value: 0.0,
    net_value_date: '',
    fund_manager: '',
    establish_date: '',
    fund_size: 0.0,
    remark: ''
  }
  dialogVisible.value = true
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.fund_id
  formData.value = {
    fund_code: row.fund_code,
    fund_name: row.fund_name,
    fund_type: row.fund_type,
    net_asset_value: row.net_asset_value,
    net_value_date: row.net_value_date,
    fund_manager: row.fund_manager,
    establish_date: row.establish_date,
    fund_size: row.fund_size,
    remark: row.remark
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  if (!formData.value.fund_code || !formData.value.fund_name) {
    ElMessage.warning('请填写必填项')
    return
  }

  try {
    if (isEdit.value) {
      await fundApi.updateFund(editId.value, formData.value)
      ElMessage.success('更新成功')
    } else {
      await fundApi.createFund(formData.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchFunds()
  } catch (error) {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  }
}

// 查看历史净值
const viewHistory = (row) => {
  router.push({ path: '/funds/history', query: { fund_code: row.fund_code } })
}

// 删除基金
const deleteFund = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该基金吗？', '提示', {
      type: 'warning'
    })
    await fundApi.deleteFund(row.fund_id)
    ElMessage.success('删除成功')
    fetchFunds()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchFunds()
})
</script>

<style scoped>
</style>