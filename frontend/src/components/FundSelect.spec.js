import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElSelect, ElOption } from 'element-plus'

import { fundApi } from '@/api'
const { default: FundSelect } = await import('./FundSelect.vue')

const F1 = { fund_code: '000001', fund_name: '华夏成长' }
const F2 = { fund_code: '000002', fund_name: '华夏大盘' }

// 组件用真实 composable + mock 掉 fundApi.getFunds，覆盖"composable 与组件的接线"
vi.mock('@/api', () => ({ fundApi: { getFunds: vi.fn() } }))

const mountSelect = (props = {}) => mount(FundSelect, {
  props: { modelValue: '', ...props },
  global: { plugins: [ElementPlus] }
})

describe('FundSelect', () => {
  beforeEach(() => {
    fundApi.getFunds.mockReset()
  })

  it('C1 初始值回显：mount 时 modelValue 预设触发 resolveInitial 按 code 查询', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1] })
    mountSelect({ modelValue: '000001' })
    await flushPromises()
    expect(fundApi.getFunds).toHaveBeenCalledWith({ keyword: '000001', page: 1, page_size: 20 })
  })

  it('C2 选中：emit update:modelValue 带 code、emit select 带完整 fund 对象', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1, F2] })
    const wrapper = mountSelect({ modelValue: '' })
    wrapper.findComponent(ElSelect).vm.$emit('visible-change', true)
    await flushPromises()
    wrapper.findComponent(ElSelect).vm.$emit('change', '000002')
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['000002'])
    expect(wrapper.emitted('select')[0]).toEqual([F2])
  })

  it('C3 清空：change 空值时 emit update:modelValue 空串、emit select null', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1] })
    const wrapper = mountSelect({ modelValue: '' })
    wrapper.findComponent(ElSelect).vm.$emit('visible-change', true)
    await flushPromises()
    wrapper.findComponent(ElSelect).vm.$emit('change', '')
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([''])
    expect(wrapper.emitted('select')[0]).toEqual([null])
  })

  it('C4 聚焦预载去重：首次 visible-change(true) 拉默认列表，二次不重复拉', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1] })
    const wrapper = mountSelect({ modelValue: '' })
    const select = wrapper.findComponent(ElSelect)
    select.vm.$emit('visible-change', true)
    await flushPromises()
    expect(fundApi.getFunds).toHaveBeenCalledTimes(1)
    select.vm.$emit('visible-change', true)
    await flushPromises()
    expect(fundApi.getFunds).toHaveBeenCalledTimes(1)
  })

  it('C5 disabled 透传到 el-select', () => {
    const wrapper = mountSelect({ disabled: true })
    expect(wrapper.findComponent(ElSelect).props('disabled')).toBe(true)
  })

  it('C6 mergedOptions 去重：initialOption 与 options 同 value 时只出现一次', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1, F2] })
    const wrapper = mountSelect({ modelValue: '000001' })
    await flushPromises()                                  // resolveInitial -> initialOption=F1
    wrapper.findComponent(ElSelect).vm.$emit('visible-change', true)
    await flushPromises()                                  // loadDefault -> options=[F1,F2]
    const opts = wrapper.findAllComponents(ElOption)
    const labels = opts.map(o => o.props('label'))
    expect(labels).toHaveLength(2)
    expect(labels).toEqual(['000001 - 华夏成长', '000002 - 华夏大盘'])
  })

  it('C7 modelValue 被外部清空时清除残留 initialOption，避免下次会话脏选项', async () => {
    fundApi.getFunds.mockResolvedValue({ data: [F1] })
    const wrapper = mountSelect({ modelValue: '000001' })  // 回显 -> initialOption=F1
    await flushPromises()
    expect(wrapper.findAllComponents(ElOption)).toHaveLength(1)
    await wrapper.setProps({ modelValue: '' })             // 模拟弹窗重置
    await flushPromises()
    expect(wrapper.findAllComponents(ElOption)).toHaveLength(0)  // 残留已清除
  })
})
