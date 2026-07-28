<template>
  <div style="padding: 20px;">
    <!-- 顶部控制栏 -->
    <el-card style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '16px 20px' }">
      <el-form :inline="true" style="margin-bottom: 0;">
        <el-form-item label="指数">
          <el-select v-model="indexCode" style="width: 220px;" @change="onParamChange">
            <el-option
              v-for="item in indexOptions"
              :key="item.index_code"
              :label="`${item.index_name} (${item.index_code})`"
              :value="item.index_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-radio-group v-model="quickMonths" @change="onQuickChange">
            <el-radio-button v-for="q in quickRanges" :key="q.label" :label="q.months">{{ q.label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker
            v-model="startDate"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            :disabled-date="disableStart"
            @change="onStartDateChange"
          />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker
            v-model="endDate"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            :disabled-date="disableEnd"
            @change="onEndDateChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchAnalysis">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 概览卡片 -->
    <div v-loading="analysisLoading">
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :xs="12" :sm="8" :md="6" v-for="card in overviewCards" :key="card.label">
        <div class="metric-card" :style="{ borderLeftColor: card.color || '#409EFF' }">
          <div class="metric-label">{{ card.label }}</div>
          <div class="metric-value" :style="{ color: card.valueColor || '#303133' }">{{ card.value }}</div>
          <div class="metric-sub" v-if="card.sub">{{ card.sub }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 智能信号（横向可扩展，从左到右排列）-->
    <el-card v-if="overview.count > 0" style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '12px 20px' }">
      <div class="signal-row">
        <div
          v-for="sig in signalCards"
          :key="sig.title"
          class="signal-card"
          :class="'signal-' + sig.type"
        >
          <div class="signal-title">
            <el-icon class="signal-icon"><component :is="sig.icon" /></el-icon>
            {{ sig.title }}
          </div>
          <div class="signal-content">{{ sig.content }}</div>
        </div>
      </div>
    </el-card>

    <!-- 主图：价格走势 + 均线 + 成交额 -->
    <el-card style="margin-bottom: 16px; box-shadow: none;" :body-style="{ padding: '16px 20px' }">
      <template #header><span style="font-weight: 500;">价格走势与均线</span></template>
      <div ref="mainChartRef" style="height: 400px;"></div>
    </el-card>

    <!-- 双图：涨跌幅分布 + 月度收益 -->
    <el-row :gutter="16" style="margin-bottom: 16px;">
      <el-col :xs="24" :md="12">
        <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }">
          <template #header><span style="font-weight: 500;">日涨跌幅分布</span></template>
          <div ref="distChartRef" style="height: 320px;"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }">
          <template #header><span style="font-weight: 500;">月度收益率</span></template>
          <div ref="monthlyChartRef" style="height: 320px;"></div>
        </el-card>
      </el-col>
    </el-row>
    </div>

    <!-- 定投模拟 -->
    <el-card style="box-shadow: none;" :body-style="{ padding: '16px 20px' }" v-loading="dcaLoading">
      <template #header><span style="font-weight: 500;">定投模拟</span></template>
      <el-row :gutter="24">
        <!-- 参数 -->
        <el-col :xs="24" :md="8">
          <el-form label-width="90px" style="max-width: 320px;">
            <el-form-item label="定投频率">
              <el-select v-model="dcaForm.frequency" @change="fetchDca">
                <el-option label="每周" value="weekly" />
                <el-option label="每两周" value="biweekly" />
                <el-option label="每月" value="monthly" />
              </el-select>
            </el-form-item>
            <el-form-item label="每次金额">
              <el-input-number v-model="dcaForm.amount" :min="100" :step="100" @change="fetchDca" />
            </el-form-item>
            <el-form-item label="区间">
              <span style="color: #909399; font-size: 13px;">{{ dateRangeText }}</span>
            </el-form-item>
          </el-form>
        </el-col>
        <!-- 结果 -->
        <el-col :xs="24" :md="16">
          <el-row :gutter="12">
            <el-col :span="8" v-for="c in dcaCards" :key="c.label">
              <div class="metric-card" :style="{ borderLeftColor: c.color || '#409EFF' }">
                <div class="metric-label">{{ c.label }}</div>
                <div class="metric-value" :style="{ color: c.valueColor || '#303133', fontSize: '20px' }">{{ c.value }}</div>
              </div>
            </el-col>
          </el-row>
          <div ref="dcaChartRef" style="height: 300px; margin-top: 16px;"></div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
defineOptions({ name: 'IndexAnalysis' })
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { TrendCharts, DataLine, Warning, Opportunity, InfoFilled } from '@element-plus/icons-vue'
import { indexApi } from '@/api'
import { useEChart } from '@/composables/useEChart'

const route = useRoute()

// 颜色常量（见 tasks/design-index-analysis.md）
const UP = '#f56c6c'
const DOWN = '#67c23a'
const C_CLOSE = '#409EFF'
const C_MA5 = '#E6A23C'
const C_MA20 = '#909399'
const C_MA60 = '#9C27B0'
const C_MA250 = '#009688'
const C_AMOUNT = '#5470C6'
// 布林带配色：上中下同属亮绿色系，明度由浅到深区分
const C_BOLL_UP = '#69d97a'
const C_BOLL_MID = '#2faf45'
const C_BOLL_LOW = '#0a6b22'

const indexOptions = ref([])
const indexCode = ref('000688')
const overview = ref({ count: 0 })
const series = ref([])
const changeDist = ref([])
const monthlyReturns = ref([])
const maSignal = ref({ suggestion: '', ma60_diff_pct: null, ma250_diff_pct: null })
const bollSignal = ref({ suggestion: '', type: 'info' })
const dcaResult = ref({})
const dcaLoading = ref(false)
const analysisLoading = ref(false)

const quickRanges = [
  { label: '近1月', months: 1 },
  { label: '近3月', months: 3 },
  { label: '近6月', months: 6 },
  { label: '近1年', months: 12 },
  { label: '近3年', months: 36 },
  { label: '全部', months: null }
]
const quickMonths = ref(12)
const startDate = ref('')
const endDate = ref('')

// 联动约束：开始不得晚于结束，结束不得早于开始（两侧互相限制可选范围）
const disableStart = (date) => endDate.value ? date.getTime() > new Date(endDate.value).getTime() : false
const disableEnd = (date) => startDate.value ? date.getTime() < new Date(startDate.value).getTime() : false

const dcaForm = reactive({ frequency: 'monthly', amount: 1000 })

// 图表
const { chartRef: mainChartRef, setOption: setMain } = useEChart()
const { chartRef: distChartRef, setOption: setDist } = useEChart()
const { chartRef: monthlyChartRef, setOption: setMonthly } = useEChart()
const { chartRef: dcaChartRef, setOption: setDca } = useEChart()

const fmtDate = (d) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const dateRangeText = computed(() => {
  if (startDate.value && endDate.value) return `${startDate.value} 至 ${endDate.value}`
  if (startDate.value) return `${startDate.value} 至今`
  if (endDate.value) return `至 ${endDate.value}`
  return '全部区间'
})

// 智能信号卡片：横向排列，未来新增信号只需往数组 push 一项
const ICON_MAP = { warning: Warning, success: Opportunity, info: InfoFilled }
const signalCards = computed(() => {
  const cards = []
  const m = maSignal.value
  if (m.suggestion) {
    const d = m.ma250_diff_pct
    const type = d === null ? 'info' : (d < 0 ? 'success' : (m.ma60_diff_pct > 0 ? 'warning' : 'info'))
    let detail = ''
    if (m.ma250_diff_pct !== null) detail += `距年线 ${m.ma250_diff_pct.toFixed(2)}%；`
    if (m.ma60_diff_pct !== null) detail += `距半年线 ${m.ma60_diff_pct.toFixed(2)}%`
    cards.push({ title: '均线位置', content: m.suggestion + (detail ? `（${detail}）` : ''), type, icon: TrendCharts })
  }
  const b = bollSignal.value
  if (b.suggestion) {
    cards.push({ title: '布林带', content: b.suggestion, type: b.type || 'info', icon: DataLine })
  }
  return cards
})

const pct = (v, digits = 2) => (v == null ? '-' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(digits)}%`)
const num = (v, digits = 2) => (v == null ? '-' : Number(v).toFixed(digits))

// 概览卡片
const overviewCards = computed(() => {
  const o = overview.value
  if (!o || !o.count) return []
  const chg = o.interval_change_pct
  return [
    { label: '最新收盘价', value: num(o.latest_close), sub: o.latest_date, color: C_CLOSE },
    { label: '区间涨跌幅', value: pct(chg), valueColor: chg >= 0 ? UP : DOWN, color: chg >= 0 ? UP : DOWN },
    { label: '区间最高价', value: num(o.high_price), color: UP },
    { label: '区间最低价', value: num(o.low_price), color: DOWN },
    { label: '振幅', value: pct(o.amplitude), color: '#909399' },
    { label: '年化波动率', value: pct(o.annualized_volatility), color: '#E6A23C' },
    { label: '年化收益率', value: pct(o.annualized_return), valueColor: (o.annualized_return || 0) >= 0 ? UP : DOWN, color: (o.annualized_return || 0) >= 0 ? UP : DOWN },
    { label: '日均成交额(亿)', value: num(o.avg_amount), color: C_AMOUNT }
  ]
})

// 定投结果卡片
const dcaCards = computed(() => {
  const r = dcaResult.value
  if (!r || !r.total_invest) return []
  const profit = r.profit
  const profitColor = profit >= 0 ? UP : DOWN
  return [
    { label: '累计投入(元)', value: num(r.total_invest, 0), color: '#91CC75' },
    { label: '累计份额', value: num(r.total_shares, 2), color: C_CLOSE },
    { label: '持有成本', value: num(r.cost_price), color: '#909399' },
    { label: '当前市值(元)', value: num(r.market_value, 0), color: C_CLOSE },
    { label: '累计收益(元)', value: num(profit, 0), valueColor: profitColor, color: profitColor },
    { label: '定投收益率', value: pct(r.return_rate), valueColor: profitColor, color: profitColor },
    { label: '一次性买入收益率', value: pct(r.lump_sum?.return_rate), valueColor: (r.lump_sum?.return_rate || 0) >= 0 ? UP : DOWN, color: '#FAC858' },
    { label: '定投期数', value: (r.schedule?.length || 0) + ' 期', color: '#909399' }
  ]
})

const fetchOptions = async () => {
  try {
    const res = await indexApi.getOptions()
    indexOptions.value = res.data || []
    if (indexOptions.value.length && !indexOptions.value.find(i => i.index_code === indexCode.value)) {
      indexCode.value = indexOptions.value[0].index_code
    }
  } catch (e) {
    ElMessage.error('获取指数列表失败')
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

// 自定义日期联动：改一边时清掉快捷选择，并夹紧越界的另一边，保证 start ≤ end
const onStartDateChange = () => {
  quickMonths.value = null
  if (startDate.value && endDate.value && startDate.value > endDate.value) {
    endDate.value = startDate.value
  }
  fetchAnalysis()
}
const onEndDateChange = () => {
  quickMonths.value = null
  if (startDate.value && endDate.value && endDate.value < startDate.value) {
    startDate.value = endDate.value
  }
  fetchAnalysis()
}

const onParamChange = () => {
  fetchAnalysis()
}

const fetchAnalysis = async () => {
  const params = { index_code: indexCode.value }
  if (startDate.value) params.start_date = startDate.value
  if (endDate.value) params.end_date = endDate.value
  analysisLoading.value = true
  try {
    const res = await indexApi.getAnalysis(params)
    overview.value = res.overview || { count: 0 }
    series.value = res.series || []
    changeDist.value = res.change_distribution || []
    monthlyReturns.value = res.monthly_returns || []
    maSignal.value = res.ma_signal || { suggestion: '' }
    bollSignal.value = res.boll_signal || { suggestion: '', type: 'info' }
    await nextTick()
    renderMain()
    renderDist()
    renderMonthly()
    fetchDca()
  } catch (e) {
    ElMessage.error('获取分析数据失败')
  } finally {
    analysisLoading.value = false
  }
}

const fetchDca = async () => {
  if (!series.value.length) return
  dcaLoading.value = true
  const params = { index_code: indexCode.value, frequency: dcaForm.frequency, amount: dcaForm.amount }
  if (startDate.value) params.start_date = startDate.value
  if (endDate.value) params.end_date = endDate.value
  try {
    const res = await indexApi.getDca(params)
    dcaResult.value = res
    await nextTick()
    renderDca()
  } catch (e) {
    ElMessage.error('定投模拟失败')
  } finally {
    dcaLoading.value = false
  }
}

// ===== 图表渲染 =====
const renderMain = () => {
  const s = series.value
  if (!s.length) { setMain({}); return }
  const dates = s.map(p => p.date)
  const line = (name, data, color, width = 1) => ({
    name, type: 'line', data, xAxisIndex: 0, yAxisIndex: 0, smooth: true,
    symbol: 'none', lineStyle: { width, color }, itemStyle: { color }
  })
  // 数值格式化：均线/布林带/成交额保留 2 位小数；K线数组单独解析
  const f2 = (v) => (v == null ? '-' : Number(v).toFixed(2))
  setMain({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const date = params[0]?.axisValue
        const lines = params.map(p => {
          let val
          if (p.seriesType === 'candlestick') {
            // value 可能是 [open,close,low,high] 或带前缀 index 的 5 元素
            const v = p.value
            const arr = Array.isArray(v) && v.length > 4 && typeof v[0] !== 'number' ? v : v
            // ECharts candlestick: [open, close, low, high]（axis tooltip 下首项为 dataIndex 时取后4位）
            const ohlc = arr.length === 4 ? arr : arr.slice(-4)
            val = `开${f2(ohlc[0])} 收${f2(ohlc[1])} 低${f2(ohlc[2])} 高${f2(ohlc[3])}`
          } else {
            val = f2(p.value)
          }
          return `${p.marker}${p.seriesName}：${val}`
        })
        return `${date}<br/>${lines.join('<br/>')}`
      }
    },
    legend: { data: ['日K', 'MA5', 'MA20', 'MA60', 'MA250', 'BOLL上轨', 'BOLL中轨', 'BOLL下轨', '成交额'], top: 0 },
    grid: [
      { left: 60, right: 60, top: 40, height: '58%' },
      { left: 60, right: 60, top: '75%', height: '18%' }
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, boundaryGap: true, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: true }
    ],
    yAxis: [
      { gridIndex: 0, scale: true, name: '价格' },
      { gridIndex: 1, name: '亿', splitNumber: 2 }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 5, height: 16 }
    ],
    series: [
      {
        name: '日K',
        type: 'candlestick',
        data: s.map(p => [p.open, p.close, p.low, p.high]),
        xAxisIndex: 0, yAxisIndex: 0,
        // A 股惯例：涨红跌绿（阳线红、阴线绿）
        itemStyle: {
          color: UP,
          color0: DOWN,
          borderColor: UP,
          borderColor0: DOWN
        }
      },
      line('MA5', s.map(p => p.ma5), C_MA5, 1),
      line('MA20', s.map(p => p.ma20), C_MA20, 1),
      line('MA60', s.map(p => p.ma60), C_MA60, 1),
      line('MA250', s.map(p => p.ma250), C_MA250, 1),
      line('BOLL上轨', s.map(p => p.boll_upper), C_BOLL_UP, 1.5),
      line('BOLL中轨', s.map(p => p.boll_middle), C_BOLL_MID, 1.5),
      line('BOLL下轨', s.map(p => p.boll_lower), C_BOLL_LOW, 1.5),
      { name: '成交额', type: 'bar', data: s.map(p => p.amount), xAxisIndex: 1, yAxisIndex: 1, itemStyle: { color: C_AMOUNT } }
    ]
  })
}

const renderDist = () => {
  const d = changeDist.value
  if (!d.length) { setDist({}); return }
  setDist({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: d.map(b => b.label), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '天数' },
    series: [{ type: 'bar', data: d.map(b => b.count), itemStyle: { color: C_AMOUNT } }]
  })
}

const renderMonthly = () => {
  const m = monthlyReturns.value
  if (!m.length) { setMonthly({}); return }
  setMonthly({
    tooltip: {
      trigger: 'axis',
      formatter: (p) => `${p[0].name}<br/>收益率：${p[0].value >= 0 ? '+' : ''}${p[0].value}%`
    },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: m.map(x => x.label), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value', name: '收益率%', axisLabel: { formatter: '{value}%' } },
    series: [{
      type: 'bar',
      data: m.map(x => ({
        value: Number((x.return_rate * 100).toFixed(2)),
        itemStyle: { color: x.return_rate >= 0 ? UP : DOWN }
      }))
    }]
  })
}

const renderDca = () => {
  const r = dcaResult.value
  const sched = r.schedule || []
  if (!sched.length) { setDca({}); return }
  const dates = sched.map(p => p.date)
  const lumpShares = r.lump_sum?.shares || 0
  setDca({
    tooltip: { trigger: 'axis', valueFormatter: (v) => (v == null ? '-' : Number(v).toFixed(2) + ' 元') },
    legend: { data: ['累计投入', '定投市值', '一次性买入'], top: 0 },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '元' },
    series: [
      { name: '累计投入', type: 'line', data: sched.map(p => Number(p.cum_invest.toFixed(2))), itemStyle: { color: '#91CC75' }, symbol: 'none' },
      { name: '定投市值', type: 'line', data: sched.map(p => Number((p.cum_shares * p.close).toFixed(2))), itemStyle: { color: '#EE6666' }, symbol: 'none' },
      { name: '一次性买入', type: 'line', data: sched.map(p => Number((lumpShares * p.close).toFixed(2))), itemStyle: { color: '#FAC858' }, symbol: 'none' }
    ]
  })
}

onMounted(async () => {
  // 从持仓分析跳转带入的指数代码（在 fetchOptions 前设置，若在选项中则保留）
  if (route.query.index_code) {
    indexCode.value = String(route.query.index_code)
  }
  await fetchOptions()
  onQuickChange(12) // 默认近1年
})
</script>

<style scoped>
.metric-card {
  background: #fff;
  border-radius: 4px;
  border-left: 3px solid #409EFF;
  padding: 14px 16px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}
.metric-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  line-height: 1.2;
}
.metric-sub {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}
/* 智能信号：横向排列，可扩展 */
.signal-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.signal-card {
  flex: 1 1 280px;
  min-width: 260px;
  border-radius: 6px;
  padding: 10px 14px;
  border-left: 3px solid #909399;
  background: #fafafa;
}
.signal-card.signal-warning { border-left-color: #e6a23c; background: #fdf6ec; }
.signal-card.signal-success { border-left-color: #67c23a; background: #f0f9eb; }
.signal-card.signal-info    { border-left-color: #909399; background: #f4f4f5; }
.signal-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.signal-card.signal-warning .signal-title { color: #e6a23c; }
.signal-card.signal-success .signal-title { color: #67c23a; }
.signal-icon { vertical-align: middle; }
.signal-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}
</style>
