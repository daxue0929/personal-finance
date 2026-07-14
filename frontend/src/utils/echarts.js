/**
 * ECharts 按需注册
 * 注册指数分析、持仓分析页用到的图表与组件，减小打包体积。
 */
import * as echarts from 'echarts/core'
import { LineChart, BarChart, CandlestickChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  GraphicComponent,
  VisualMapComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  BarChart,
  CandlestickChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  GraphicComponent,
  VisualMapComponent,
  CanvasRenderer
])

export default echarts
