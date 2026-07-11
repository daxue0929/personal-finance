/**
 * ECharts 组合式函数：封装 init / resize / dispose 生命周期。
 * 用法：
 *   const { chartRef, setOption } = useEChart()
 *   watch(data, () => setOption(buildOption(data)))
 *   <div ref="chartRef" style="height:320px"></div>
 */
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import echarts from '@/utils/echarts'

export function useEChart() {
  const chartRef = ref(null)
  let chart = null

  const resize = () => {
    if (chart) chart.resize()
  }

  const setOption = (option) => {
    if (!chart && chartRef.value) {
      chart = echarts.init(chartRef.value)
    }
    if (chart) {
      chart.setOption(option, true)
    }
  }

  onMounted(() => {
    nextTick(() => {
      if (chartRef.value && !chart) {
        chart = echarts.init(chartRef.value)
      }
    })
    window.addEventListener('resize', resize)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', resize)
    if (chart) {
      chart.dispose()
      chart = null
    }
  })

  return { chartRef, setOption, resize }
}
