<template>
  <div style="padding: 20px;">
    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }">
          <template #header><span style="font-weight: 500;">持仓占比（实时）</span></template>
          <div v-if="allocation.length" ref="pieChartRef" style="height: 560px;"></div>
          <el-empty v-else description="暂无持仓" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { portfolioApi } from '@/api'
import { useEChart } from '@/composables/useEChart'

const allocation = ref([])
const { chartRef: pieChartRef, setOption: setPie } = useEChart()

// 持仓占比饼图（复用 PositionAnalysis renderPie 结构）
const renderPie = () => {
  const p = allocation.value
  if (!p.length) { setPie({}); return }
  setPie({
    tooltip: { trigger: 'item', formatter: (i) => `${i.name}<br/>市值：¥${Number(i.value).toFixed(2)}<br/>占比：${i.percent}%` },
    legend: {
      bottom: 10,
      left: 'center',
      // 自动换行多行展示，宽度不足即折行
      type: 'plain',
      itemGap: 12,
      itemWidth: 14,
      textStyle: { fontSize: 12 }
    },
    series: [{
      type: 'pie', radius: ['38%', '58%'], center: ['50%', '42%'],
      avoidLabelOverlap: true,
      minShowLabelAngle: 3,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      // 显示名称+占比；小扇区（<3°）自动隐藏标签避免挤压，其占比仍可 hover 查看
      label: { show: true, formatter: '{b}\n{d}%', fontSize: 12, lineHeight: 15 },
      labelLine: { show: true, length: 10, length2: 10 },
      data: p.map(x => ({ name: x.fund_name, value: Number(x.value) }))
    }]
  })
}

const fetchAllocation = async () => {
  try {
    const res = await portfolioApi.getAllocation()
    allocation.value = res.data || []
    await nextTick()
    renderPie()
  } catch (e) {
    allocation.value = []
    ElMessage.error('获取持仓占比失败')
  }
}

onMounted(fetchAllocation)
</script>

<style scoped>
</style>
