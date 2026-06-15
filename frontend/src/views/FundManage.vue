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
      width="600px"
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundApi } from '@/api'

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

// 搜索表单
const searchForm = ref({
  fund_code: '',
  fund_name: '',
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

// 获取基金列表（支持搜索和分页）
const fetchFunds = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.fund_code,
      fund_name: searchForm.value.fund_name,
      fund_type: searchForm.value.fund_type
    }
    const result = await fundApi.getFunds(params)
    funds.value = result.data
    total.value = result.total
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
    fund_code: '',
    fund_name: '',
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