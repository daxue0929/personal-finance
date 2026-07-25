import { describe, it, expect } from 'vitest'
import { useTagsView } from './useTagsView'

// 叶子路由 mock（matched 末位有 components.default）
const leaf = (path, title) => ({
  path, meta: { title }, matched: [{ components: { default: {} } }]
})
// 父路由 mock（matched 末位无 components，即无组件的菜单组）
const parent = (path, title) => ({
  path, meta: { title }, matched: [{}]
})

describe('useTagsView', () => {
  it('初始含首页 affix tab', () => {
    const { tabs } = useTagsView()
    expect(tabs.value).toHaveLength(1)
    expect(tabs.value[0].path).toBe('/dashboard')
    expect(tabs.value[0].affix).toBe(true)
  })

  it('addTab 新路由 -> tabs +1', () => {
    const { tabs, addTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    expect(tabs.value).toHaveLength(2)
    expect(tabs.value[1]).toEqual({ path: '/funds', title: '基金信息管理', affix: false })
  })

  it('addTab 重复路由 -> 不增（仅置 active）', () => {
    const { tabs, addTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    addTab(leaf('/funds', '基金信息管理'))
    expect(tabs.value).toHaveLength(2)
  })

  it('addTab 跳过无组件父路由', () => {
    const { tabs, addTab } = useTagsView()
    addTab(parent('/index', '指数分析'))
    expect(tabs.value).toHaveLength(1) // 仅首页
  })

  it('closeTab 非活跃 tab -> -1 且返回 null（不跳转）', () => {
    const { tabs, addTab, closeTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理')) // active
    addTab(leaf('/buyers', '基金买入流水')) // active
    const jump = closeTab('/funds') // 非活跃
    expect(jump).toBeNull()
    expect(tabs.value).toHaveLength(2) // 首页 + /buyers
    expect(tabs.value.some(t => t.path === '/funds')).toBe(false)
  })

  it('closeTab 活跃 tab -> 返回相邻 path（右优先->左->首页）', () => {
    const { addTab, closeTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    addTab(leaf('/buyers', '基金买入流水'))
    addTab(leaf('/sellers', '基金卖出流水'))
    addTab(leaf('/buyers', '基金买入流水')) // 重新激活中间 tab（去重，仅置 active）
    const jump = closeTab('/buyers') // 关活跃中间 tab -> 右邻 /sellers
    expect(jump).toBe('/sellers')
  })

  it('closeOthers -> 仅留当前 + affix', () => {
    const { tabs, addTab, closeOthers } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    addTab(leaf('/buyers', '基金买入流水'))
    closeOthers('/funds')
    expect(tabs.value).toHaveLength(2) // 首页 affix + /funds
    expect(tabs.value.some(t => t.path === '/buyers')).toBe(false)
  })

  it('closeAll -> 仅留 affix，返回首页 path', () => {
    const { tabs, addTab, closeAll } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    addTab(leaf('/buyers', '基金买入流水'))
    const jump = closeAll()
    expect(tabs.value).toHaveLength(1) // 仅首页 affix
    expect(tabs.value[0].path).toBe('/dashboard')
    expect(jump).toBe('/dashboard')
  })

  it('closeTab 对 affix 无效', () => {
    const { tabs, closeTab } = useTagsView()
    const jump = closeTab('/dashboard') // 首页 affix
    expect(jump).toBeNull()
    expect(tabs.value).toHaveLength(1) // 仍在
  })

  it('moveTab 把 tab 移到目标位置', () => {
    const { tabs, addTab, moveTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    addTab(leaf('/buyers', '基金买入流水'))
    addTab(leaf('/sellers', '基金卖出流水'))
    // tabs: [portfolio, funds, buyers, sellers]
    moveTab('/sellers', '/funds') // 把 sellers 移到 funds 位置
    expect(tabs.value.map(t => t.path)).toEqual(['/dashboard', '/sellers', '/funds', '/buyers'])
  })

  it('moveTab 相同 path -> 不变', () => {
    const { tabs, addTab, moveTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    moveTab('/funds', '/funds')
    expect(tabs.value.map(t => t.path)).toEqual(['/dashboard', '/funds'])
  })

  it('moveTab 不存在的 path -> 不变', () => {
    const { tabs, addTab, moveTab } = useTagsView()
    addTab(leaf('/funds', '基金信息管理'))
    moveTab('/nope', '/funds')
    expect(tabs.value.map(t => t.path)).toEqual(['/dashboard', '/funds'])
  })
})
