/**
 * ECharts 按需注册（项目首个使用 ECharts 的模块）
 * 只注册指数分析页用到的图表与组件，减小打包体积。
 */
import * as echarts from 'echarts/core'
import { LineChart, BarChart, CandlestickChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  GraphicComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  BarChart,
  CandlestickChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  GraphicComponent,
  CanvasRenderer
])

export default echarts
