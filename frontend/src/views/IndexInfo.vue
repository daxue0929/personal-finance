<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="指数">
            <el-select
              v-model="searchForm.index_code"
              placeholder="全部指数"
              style="width: 220px;"
              clearable
              @change="handleSearch"
            >
              <el-option
                v-for="item in indexOptions"
                :key="item.index_code"
                :label="`${item.index_name} (${item.index_code})`"
                :value="item.index_code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="指数类型">
            <el-select v-model="searchForm.index_type" placeholder="全部类型" clearable style="width: 140px;" @change="handleSearch">
              <el-option label="宽基指数" value="宽基指数" />
              <el-option label="行业指数" value="行业指数" />
              <el-option label="策略指数" value="策略指数" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker
              v-model="startDate"
              type="date"
              placeholder="开始日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disableStart"
              clearable
              @change="handleSearch"
            />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="endDate"
              type="date"
              placeholder="结束日期"
              value-format="YYYY-MM-DD"
              :disabled-date="disableEnd"
              clearable
              @change="handleSearch"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="list" style="width: 100%" height="100%" v-loading="loading">
          <el-table-column prop="trade_date" label="交易日期" width="120" />
          <el-table-column prop="index_code" label="指数代码" width="100" />
          <el-table-column prop="index_name" label="指数名称" width="120" />
          <el-table-column prop="index_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.index_type || '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="open_price" label="开盘价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.open_price) }}</template>
          </el-table-column>
          <el-table-column prop="close_price" label="收盘价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.close_price) }}</template>
          </el-table-column>
          <el-table-column prop="high_price" label="最高价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.high_price) }}</template>
          </el-table-column>
          <el-table-column prop="low_price" label="最低价" width="100" align="right">
            <template #default="{ row }">{{ fmt(row.low_price) }}</template>
          </el-table-column>
          <el-table-column prop="change_percent" label="涨跌幅" width="110" align="right">
            <template #default="{ row }">
              <span :style="{ color: row.change_percent >= 0 ? '#f56c6c' : '#67c23a' }">
                {{ row.change_percent >= 0 ? '+' : '' }}{{ row.change_percent.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="volume" label="成交量(万手)" width="120" align="right">
            <template #default="{ row }">{{ row.volume ? row.volume.toLocaleString() : '-' }}</template>
          </el-table-column>
          <el-table-column prop="amount" label="成交额(亿)" width="110" align="right">
            <template #default="{ row }">{{ row.amount ? row.amount.toFixed(2) : '-' }}</template>
          </el-table-column>
          <el-table-column prop="source" label="数据来源" width="110" />
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
  </div>
</template>

<script setup>
defineOptions({ name: 'IndexInfo' })
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { indexApi } from '@/api'

const indexOptions = ref([])
const list = ref([])
const loading = ref(false)

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const searchForm = ref({
  index_code: '',
  index_type: ''
})
const startDate = ref('')
const endDate = ref('')
// 联动约束：开始不得晚于结束，结束不得早于开始（两侧互相限制可选范围）
const disableStart = (date) => endDate.value ? date.getTime() > new Date(endDate.value).getTime() : false
const disableEnd = (date) => startDate.value ? date.getTime() < new Date(startDate.value).getTime() : false

const fmt = (v) => (v != null ? Number(v).toFixed(2) : '-')

const fetchOptions = async () => {
  try {
    const res = await indexApi.getOptions()
    indexOptions.value = res.data || []
  } catch (e) {
    ElMessage.error('获取指数列表失败')
  }
}

const fetchList = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      index_code: searchForm.value.index_code,
      index_type: searchForm.value.index_type,
      start_date: startDate.value,
      end_date: endDate.value
    }
    const res = await indexApi.getIndexes(params)
    list.value = res.data
    total.value = res.total
  } catch (e) {
    ElMessage.error('获取指数信息失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchList()
}

const resetSearch = () => {
  searchForm.value = { index_code: '', index_type: '' }
  startDate.value = ''
  endDate.value = ''
  currentPage.value = 1
  fetchList()
}

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchList()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchList()
}

onMounted(() => {
  fetchOptions()
  fetchList()
})
</script>

<style scoped>
</style>
