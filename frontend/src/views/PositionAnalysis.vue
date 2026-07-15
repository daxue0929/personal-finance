<template>
  <div style="padding: 20px;">
    <!-- 顶部控制栏 -->
    <el-card style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '16px 20px' }">
      <el-form :inline="true" style="margin-bottom: 0;">
        <el-form-item label="持仓">
          <el-select v-model="positionId" style="width: 260px;" @change="onParamChange">
            <el-option label="全部持仓" value="all" />
            <el-option
              v-for="item in positionOptions"
              :key="item.position_id"
              :label="`${item.fund_name} (${item.fund_code})`"
              :value="item.position_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-radio-group v-model="quickMonths" @change="onQuickChange">
            <el-radio-button v-for="q in quickRanges" :key="q.label" :label="q.months">{{ q.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker v-model="startDate" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" :disabled-date="disableStart" @change="onStartDateChange" />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker v-model="endDate" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" :disabled-date="disableEnd" @change="onEndDateChange" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchAnalysis">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-loading="loading">
      <!-- 概览卡片：7 个等宽排满一行（flex 七等分），窄屏自动折行 -->
      <div class="metric-row">
        <div class="metric-card" v-for="card in overviewCards" :key="card.label" :style="{ borderLeftColor: card.color || '#409EFF' }">
          <div class="metric-label">{{ card.label }}</div>
          <div class="metric-value" :style="{ color: card.valueColor || '#303133' }">{{ card.value }}</div>
          <div class="metric-sub" v-if="card.sub">{{ card.sub }}</div>
        </div>
      </div>
      <!-- 主图：盈亏比例折线图 -->
      <el-card style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '16px 20px' }">
        <template #header><span style="font-weight: 500;">盈亏比例走势</span></template>
        <div v-if="series.length" ref="rateChartRef" style="height: 400px;"></div>
        <el-empty v-else description="暂无快照数据" />
      </el-card>

      <!-- 双图：持仓金额折线图 + 持仓占比饼图 -->
      <el-row :gutter="16" style="margin-bottom: 16px;">
        <el-col :xs="24" :md="12">
          <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }">
            <template #header><span style="font-weight: 500;">持仓金额（市值）走势</span></template>
            <div v-if="series.length" ref="valueChartRef" style="height: 320px;"></div>
            <el-empty v-else description="暂无快照数据" />
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }">
            <template #header><span style="font-weight: 500;">持仓占比（全部持仓·最新日）</span></template>
            <div v-if="pie.length" ref="pieChartRef" style="height: 320px;"></div>
            <el-empty v-else description="暂无持仓" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 累计收益走势折线图（随持仓选择切换：全部持仓=组合每日总盈亏，单持仓=该持仓每日盈亏） -->
      <el-card style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '16px 20px' }">
        <template #header><span style="font-weight: 500;">累计收益走势{{ positionId === 'all' ? '（全部持仓·每日总盈亏）' : '' }}</span></template>
        <div v-if="profitSeries.length" ref="profitChartRef" style="height: 320px;"></div>
        <el-empty v-else description="暂无快照数据" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { positionAnalysisApi } from '@/api'
import { useEChart } from '@/composables/useEChart'

// 配色：A股涨红跌绿（与 IndexAnalysis/PortfolioBoard 一致）
const UP = '#f56c6c'
const DOWN = '#67c23a'
const C_PRIMARY = '#409EFF'
const C_VALUE = '#5470C6'

const positionOptions = ref([])
const positionId = ref(null)
const overview = ref({ count: 0 })
const series = ref([])
const pie = ref([])
const profitSeries = ref([])
const realizedProfitTotal = ref(0)
const loading = ref(false)

const quickRanges = [
  { label: '近1月', months: 1 },
  { label: '近3月', months: 3 },
  { label: '近6月', months: 6 },
  { label: '近1年', months: 12 },
  { label: '全部', months: null }
]
const quickMonths = ref(null)
const startDate = ref('')
const endDate = ref('')

const disableStart = (date) => endDate.value ? date.getTime() > new Date(endDate.value).getTime() : false
const disableEnd = (date) => startDate.value ? date.getTime() < new Date(startDate.value).getTime() : false

const { chartRef: rateChartRef, setOption: setRate } = useEChart()
const { chartRef: valueChartRef, setOption: setValue } = useEChart()
const { chartRef: pieChartRef, setOption: setPie } = useEChart()
const { chartRef: profitChartRef, setOption: setProfit } = useEChart()

const fmtDate = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const pct = (v, digits = 2) => (v == null ? '-' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(digits)}%`)
const num = (v, digits = 2) => (v == null ? '-' : Number(v).toFixed(digits))
const money = (v) => (v == null ? '-' : `¥${Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`)
// 带符号金额：正数 +¥123.45，负数 -¥123.45（符号统一在 ¥ 前）
const signedMoney = (v) => {
  if (v == null) return '-'
  const n = Number(v)
  const abs = Math.abs(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n >= 0 ? '+' : '-') + '¥' + abs
}

const overviewCards = computed(() => {
  const o = overview.value
  if (!o || !o.count) return []
  const plColor = (o.latest_profit_loss || 0) >= 0 ? UP : DOWN
  const ddColor = (o.max_drawdown || 0) > 0 ? DOWN : '#909399'
  const rpt = realizedProfitTotal.value
  const rptColor = (rpt || 0) >= 0 ? UP : DOWN
  return [
    { label: '最新市值', value: money(o.latest_value), sub: o.end_date, color: C_PRIMARY },
    { label: '最新盈亏', value: signedMoney(o.latest_profit_loss), valueColor: plColor, color: plColor, sub: pct(o.latest_profit_loss_rate) },
    { label: '区间最高市值', value: money(o.max_value), color: UP },
    { label: '区间最低市值', value: money(o.min_value), color: DOWN },
    { label: '最大回撤率', value: o.max_drawdown == null ? '-' : (o.max_drawdown > 0 ? `-${num(o.max_drawdown)}%` : '0.00%'), valueColor: ddColor, color: ddColor, sub: '峰值到谷值' },
    { label: '区间盈亏变化', value: signedMoney(o.profit_loss_change), valueColor: (o.profit_loss_change || 0) >= 0 ? UP : DOWN, color: (o.profit_loss_change || 0) >= 0 ? UP : DOWN },
    { label: '累计已实现盈亏', value: signedMoney(rpt), valueColor: rptColor, color: rptColor, sub: '历史卖出已实现' }
  ]
})

const fetchOptions = async () => {
  try {
    const res = await positionAnalysisApi.getOptions()
    positionOptions.value = res.data || []
    // 默认选「全部持仓」组合视角
    if (!positionId.value) {
      positionId.value = 'all'
    }
  } catch (e) {
    ElMessage.error('获取持仓列表失败')
  }
}

const onQuickChange = (months) => {
  if (months === null) {
    startDate.value = ''
    endDate.value = ''
  } else {
    const end = new Date()
    const start = new Date()
    start.setMonth(start.getMonth() - months)
    startDate.value = fmtDate(start)
    endDate.value = fmtDate(end)
  }
  fetchAnalysis()
}

const onStartDateChange = () => {
  quickMonths.value = null
  if (startDate.value && endDate.value && startDate.value > endDate.value) endDate.value = startDate.value
  fetchAnalysis()
}
const onEndDateChange = () => {
  quickMonths.value = null
  if (startDate.value && endDate.value && endDate.value < startDate.value) startDate.value = endDate.value
  fetchAnalysis()
}
const onParamChange = () => fetchAnalysis()

const fetchAnalysis = async () => {
  if (!positionId.value) return
  const params = { position_id: positionId.value }
  if (startDate.value) params.start_date = startDate.value
  if (endDate.value) params.end_date = endDate.value
  loading.value = true
  try {
    const res = await positionAnalysisApi.getAnalysis(params)
    overview.value = res.overview || { count: 0 }
    series.value = res.series || []
    pie.value = res.pie || []
    // 累计收益序列：随持仓选择切换。选「全部持仓」时用组合级 portfolio_series；
    // 选单持仓时用该持仓 series（含 profit_loss 字段）。
    profitSeries.value = positionId.value === 'all'
      ? (res.portfolio_series || [])
      : (res.series || [])
    realizedProfitTotal.value = res.realized_profit_total || 0
    await nextTick()
    renderRate()
    renderValue()
    renderPie()
    renderProfit()
  } catch (e) {
    console.error('[PositionAnalysis] fetchAnalysis 失败:', e)
    ElMessage.error('获取分析数据失败')
  } finally {
    loading.value = false
  }
}

// 盈亏比例走势图：按盈亏率「变化方向」着色（上升段红、下降段绿），与 K 线涨跌语义一致
const renderRate = () => {
  const s = series.value
  if (!s.length) { setRate({}); return }
  const dates = s.map(p => p.snapshot_date)
  const rates = s.map(p => Number(p.profit_loss_rate))

  // 每个数据点 symbol 颜色：首点按自身正负，后续按相对前点变化方向（上升红/下降绿）
  const pointColors = rates.map((r, i) => {
    if (i === 0) return r >= 0 ? UP : DOWN
    return r >= rates[i - 1] ? UP : DOWN
  })

  // 每段（相邻两点）一条稀疏 line series：只有该段两端点有值，其余 null。
  // category 轴下稀疏数组按 index 对应日期，两端点连线即为该段，颜色按方向。
  const segSeries = []
  for (let i = 1; i < rates.length; i++) {
    const data = rates.map((_, idx) => (idx === i - 1 || idx === i) ? rates[idx] : null)
    segSeries.push({
      type: 'line',
      data,
      lineStyle: { color: rates[i] >= rates[i - 1] ? UP : DOWN, width: 2 },
      symbol: 'none',
      smooth: false,
      connectNulls: false,
      silent: true,
      z: 1
    })
  }

  // 主 series：承载全部点（symbol + tooltip + 0 轴 markLine），连线透明（颜色由分段 series 提供）
  const mainSeries = {
    type: 'line',
    data: rates.map((r, i) => ({ value: r, itemStyle: { color: pointColors[i] } })),
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { opacity: 0 },
    z: 2,
    markLine: {
      silent: true, symbol: 'none',
      lineStyle: { color: '#909399', type: 'dashed' },
      label: { show: true, formatter: '0%', position: 'insideEndTop', color: '#909399', fontSize: 11 },
      // 0% 水面线：单对象 { yAxis: 0 } 写法，ECharts 5.5 会归一化为横跨整个 x 轴的水平线
      data: [{ yAxis: 0 }]
    }
  }

  // 单点时无分段 series，主 series 用自身颜色画连线
  if (rates.length === 1) {
    mainSeries.lineStyle = { color: pointColors[0], width: 2, opacity: 1 }
  }

  const segCount = segSeries.length
  setRate({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        // 主 series 排在分段 series 之后，取它的点
        const p = params.find(x => x.seriesIndex === segCount)
        if (!p) return ''
        return `${p.axisValue}<br/>盈亏率：${p.value >= 0 ? '+' : ''}${Number(p.value).toFixed(2)}%`
      }
    },
    grid: { left: 60, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '盈亏率%', axisLabel: { formatter: '{value}%' } },
    series: [...segSeries, mainSeries]
  })
}

// 持仓金额（市值）折线图
const renderValue = () => {
  const s = series.value
  if (!s.length) { setValue({}); return }
  const dates = s.map(p => p.snapshot_date)
  const values = s.map(p => Number(p.current_value))
  setValue({
    tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '-' : '¥' + Number(v).toFixed(2)) },
    grid: { left: 70, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '市值(元)', axisLabel: { formatter: '{value}' } },
    series: [{
      type: 'line', data: values, smooth: true, symbol: 'none',
      itemStyle: { color: C_VALUE }, lineStyle: { color: C_VALUE },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(84,112,198,0.3)' }, { offset: 1, color: 'rgba(84,112,198,0.02)' }] } }
    }]
  })
}

// 累计收益走势折线图：按盈亏「变化方向」着色（上升段红、下降段绿），带 0 轴水面线。
// 口径随持仓选择切换：全部持仓=组合每日总盈亏，单持仓=该持仓每日盈亏。
const renderProfit = () => {
  const s = profitSeries.value
  if (!s.length) { setProfit({}); return }
  const dates = s.map(p => p.snapshot_date)
  const profits = s.map(p => Number(p.profit_loss))

  // 每个数据点 symbol 颜色：首点按自身正负，后续按相对前点变化方向（上升红/下降绿）
  const pointColors = profits.map((p, i) => {
    if (i === 0) return p >= 0 ? UP : DOWN
    return p >= profits[i - 1] ? UP : DOWN
  })

  // 每段相邻两点一条稀疏 line series，颜色按盈亏变化方向
  const segSeries = []
  for (let i = 1; i < profits.length; i++) {
    const data = profits.map((_, idx) => (idx === i - 1 || idx === i) ? profits[idx] : null)
    segSeries.push({
      type: 'line',
      data,
      lineStyle: { color: profits[i] >= profits[i - 1] ? UP : DOWN, width: 2 },
      symbol: 'none',
      smooth: false,
      connectNulls: false,
      silent: true,
      z: 1
    })
  }

  // 主 series：承载全部点（symbol + tooltip + 0 轴 markLine），连线透明
  const mainSeries = {
    type: 'line',
    data: profits.map((p, i) => ({ value: p, itemStyle: { color: pointColors[i] } })),
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { opacity: 0 },
    z: 2,
    markLine: {
      silent: true, symbol: 'none',
      lineStyle: { color: '#909399', type: 'dashed' },
      label: { show: true, formatter: '0', position: 'insideEndTop', color: '#909399', fontSize: 11 },
      data: [{ yAxis: 0 }]
    }
  }

  // 单点时无分段 series，主 series 用自身颜色画连线
  if (profits.length === 1) {
    mainSeries.lineStyle = { color: pointColors[0], width: 2, opacity: 1 }
  }

  const segCount = segSeries.length
  setProfit({
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params.find(x => x.seriesIndex === segCount)
        if (!p) return ''
        return `${p.axisValue}<br/>累计盈亏：${signedMoney(p.value)}`
      }
    },
    grid: { left: 70, right: 30, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '盈亏(元)', axisLabel: { formatter: '{value}' } },
    series: [...segSeries, mainSeries]
  })
}

// 持仓占比饼图
const renderPie = () => {
  const p = pie.value
  if (!p.length) { setPie({}); return }
  setPie({
    tooltip: { trigger: 'item', formatter: (i) => `${i.name}<br/>市值：¥${Number(i.value).toFixed(2)}<br/>占比：${i.percent}%` },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%' },
      data: p.map(x => ({ name: `${x.fund_name}`, value: Number(x.value) }))
    }]
  })
}

onMounted(async () => {
  await fetchOptions()
  onQuickChange(null) // 默认全部
})
</script>

<style scoped>
.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  flex: 1 1 0;
  min-width: 120px;
  background: #fff;
  border-radius: 4px;
  border-left: 3px solid #409EFF;
  padding: 10px 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.metric-label { font-size: 12px; color: #909399; margin-bottom: 4px; }
.metric-value { font-size: 16px; font-weight: 600; color: #303133; line-height: 1.2; word-break: break-all; }
.metric-sub { font-size: 11px; color: #c0c4cc; margin-top: 3px; }
</style>
