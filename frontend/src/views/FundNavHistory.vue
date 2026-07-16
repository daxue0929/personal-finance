<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none;" :body-style="{ padding: '0' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="基金代码">
            <FundSelect v-model="searchForm.fund_code" width="250px" placeholder="请选择基金" @select="handleSearch" />
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker
              v-model="searchForm.start_date"
              type="date"
              placeholder="选择开始日期"
              value-format="YYYY-MM-DD"
              clearable
            />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker
              v-model="searchForm.end_date"
              type="date"
              placeholder="选择结束日期"
              value-format="YYYY-MM-DD"
              clearable
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px;">
        <el-table :data="navHistory" style="width: 100%" v-loading="loading">
          <el-table-column prop="fund_code" label="基金代码" width="120" />
          <el-table-column prop="fund_name" label="基金名称" width="200" />
          <el-table-column prop="nav_date" label="净值日期" width="150" />
          <el-table-column prop="unit_nav" label="单位净值" width="150">
            <template #default="{ row }">
              {{ row.unit_nav !== null ? row.unit_nav.toFixed(4) : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="daily_growth_rate" label="日涨跌幅" width="150">
            <template #default="{ row }">
              <span v-if="row.daily_growth_rate !== null" :style="{ color: row.daily_growth_rate >= 0 ? '#f56c6c' : '#67c23a' }">
                {{ row.daily_growth_rate >= 0 ? '+' : '' }}{{ row.daily_growth_rate.toFixed(4) }}%
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="数据来源" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.source === 'system'" type="info" size="small">系统</el-tag>
              <el-tag v-else-if="row.source === 'crawler'" type="success" size="small">爬虫</el-tag>
              <el-tag v-else type="warning" size="small">手动</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="create_time" label="创建时间" />
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
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fundNavApi } from '@/api'
import FundSelect from '@/components/FundSelect.vue'

const route = useRoute()

const navHistory = ref([])
const loading = ref(false)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 搜索表单
const searchForm = ref({
  fund_code: '',
  start_date: '',
  end_date: ''
})

// 获取基金历史净值列表
const fetchNavHistory = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      fund_code: searchForm.value.fund_code,
      start_date: searchForm.value.start_date,
      end_date: searchForm.value.end_date
    }
    const result = await fundNavApi.getNavHistory(searchForm.value.fund_code, params)
    navHistory.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error('获取基金历史净值失败')
  } finally {
    loading.value = false
  }
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchNavHistory()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchNavHistory()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchNavHistory()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = {
    fund_code: '',
    start_date: '',
    end_date: ''
  }
  currentPage.value = 1
  fetchNavHistory()
}

// 监听路由查询参数变化
watch(() => route.query.fund_code, (newCode) => {
  if (newCode) {
    searchForm.value.fund_code = newCode
    currentPage.value = 1
    fetchNavHistory()
  }
})

onMounted(() => {
  // 如果路由中有基金代码参数，自动填充（FundSelect 会自动回显 label）
  if (route.query.fund_code) {
    searchForm.value.fund_code = route.query.fund_code
  }

  // 初始加载（默认查询所有基金的历史净值）
  fetchNavHistory()
})
</script>

<style scoped>
</style>
