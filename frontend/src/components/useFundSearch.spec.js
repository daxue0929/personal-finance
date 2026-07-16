// @vitest-environment node
import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

// 防止加载真实 @/api（会拉入 router/store）。composable 测试始终注入 fetcher，
// 默认 fetcher 不会被调用，但模块顶层 import 仍会执行，故 mock 掉。
vi.mock('@/api', () => ({ fundApi: { getFunds: vi.fn() } }))

const { useFundSearch } = await import('./useFundSearch')

const F1 = { fund_code: '000001', fund_name: '华夏成长' }
const F2 = { fund_code: '000002', fund_name: '华夏大盘' }
const F3 = { fund_code: '110011', fund_name: '易方达中小盘' }

describe('useFundSearch', () => {
  it('L1 loadDefault 拉 pageSize 条首页，options 映射为 "code - name"，raw 保留原对象', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1, F2], total: 2 })
    const { options, loadDefault } = useFundSearch({ fetcher })
    await loadDefault()
    expect(fetcher).toHaveBeenCalledWith({ keyword: '', page: 1, page_size: 20 })
    expect(options.value).toHaveLength(2)
    expect(options.value[0]).toMatchObject({ label: '000001 - 华夏成长', value: '000001' })
    // raw 经响应式 ref 读取会包成 Proxy，用结构相等断言
    expect(options.value[0].raw).toEqual(F1)
  })

  it('L2 search 在防抖窗口内多次调用，fetcher 只触发一次且用最后一次关键字', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn().mockResolvedValue({ data: [F3] })
    const { search, options } = useFundSearch({ fetcher, debounceMs: 300 })
    search('易方达'); search('易方达中'); search('易方达中小盘')
    expect(fetcher).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledWith({ keyword: '易方达中小盘', page: 1, page_size: 20 })
    expect(options.value[0].value).toBe('110011')
    vi.useRealTimers()
  })

  it('L3 search 空字符串等价于 loadDefault（立即触发，不走防抖）', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1] })
    const { search } = useFundSearch({ fetcher, debounceMs: 300 })
    search('')
    await flushPromises()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher).toHaveBeenCalledWith({ keyword: '', page: 1, page_size: 20 })
  })

  it('L4 竞态保护：后发请求先回，先发请求结果被丢弃', async () => {
    let resolveP1, resolveP2
    const p1 = new Promise(r => { resolveP1 = r })
    const p2 = new Promise(r => { resolveP2 = r })
    let calls = 0
    const fetcher = vi.fn(() => { calls++; return calls === 1 ? p1 : p2 })
    const { options, loadDefault } = useFundSearch({ fetcher })
    loadDefault()   // 触发 P1（reqId=1），不 await
    loadDefault()   // 触发 P2（reqId=2）
    resolveP2({ data: [F2] })
    await flushPromises()
    expect(options.value.map(o => o.value)).toEqual(['000002'])
    resolveP1({ data: [F1] })
    await flushPromises()
    expect(options.value.map(o => o.value)).toEqual(['000002']) // P1 已过期被丢弃
  })

  it('L5 resolveInitial 命中：设置 initialOption 并返回 fund', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1, F2] })
    const { resolveInitial, initialOption } = useFundSearch({ fetcher })
    const hit = await resolveInitial('000002')
    expect(hit).toBe(F2)
    expect(initialOption.value).toMatchObject({ value: '000002', label: '000002 - 华夏大盘' })
  })

  it('L6 resolveInitial 未命中：initialOption 为 null，返回 null', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1] })
    const { resolveInitial, initialOption } = useFundSearch({ fetcher })
    const hit = await resolveInitial('999999')
    expect(hit).toBeNull()
    expect(initialOption.value).toBeNull()
  })

  it('L7 fetcher 抛异常：options 置空、loading 复位、不向外抛', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('network'))
    const { options, loading, loadDefault } = useFundSearch({ fetcher })
    await expect(loadDefault()).resolves.toBeUndefined()
    expect(options.value).toEqual([])
    expect(loading.value).toBe(false)
  })

  it('L8 findInOptions 从 options 与 initialOption 命中，未命中返回 undefined', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1, F2] })
    const { loadDefault, resolveInitial, findInOptions } = useFundSearch({ fetcher })
    await loadDefault()
    await resolveInitial('000002')
    expect(findInOptions('000001')).toEqual(F1)   // options 命中
    expect(findInOptions('000002')).toEqual(F2)   // initialOption 命中
    expect(findInOptions('999999')).toBeUndefined()
  })

  it('L9 clear 清空 options 与 initialOption', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1] })
    const { loadDefault, resolveInitial, clear, options, initialOption } = useFundSearch({ fetcher })
    await loadDefault()
    await resolveInitial('000001')
    expect(options.value.length).toBeGreaterThan(0)
    expect(initialOption.value).not.toBeNull()
    clear()
    expect(options.value).toEqual([])
    expect(initialOption.value).toBeNull()
  })

  it('L10 自定义 pageSize 透传到 fetcher', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [] })
    const { loadDefault } = useFundSearch({ fetcher, pageSize: 50 })
    await loadDefault()
    expect(fetcher).toHaveBeenCalledWith({ keyword: '', page: 1, page_size: 50 })
  })

  it('L11 loading 在请求中为 true，完成后为 false', async () => {
    let resolveReq
    const fetcher = vi.fn(() => new Promise(r => { resolveReq = r }))
    const { loading, loadDefault } = useFundSearch({ fetcher })
    const p = loadDefault()
    await flushPromises()
    expect(loading.value).toBe(true)
    resolveReq({ data: [F1] })
    await p
    expect(loading.value).toBe(false)
  })

  it('L12 resolveInitial 与 loadDefault 独立计数，预填回显不被下拉预载请求丢弃', async () => {
    let resolveEcho
    const echoPromise = new Promise(r => { resolveEcho = r })
    // keyword 非空（回显）返回挂起 promise；空 keyword（预载）立即返回
    const fetcher = vi.fn(({ keyword }) => keyword ? echoPromise : Promise.resolve({ data: [F1] }))
    const { loadDefault, resolveInitial, initialOption } = useFundSearch({ fetcher })
    const p = resolveInitial('000001')   // 回显请求 in-flight
    loadDefault()                         // 预载请求（共用 reqId 会误判回显过期）
    await flushPromises()
    resolveEcho({ data: [F1] })           // 回显响应到达
    await p
    expect(initialOption.value).toMatchObject({ value: '000001' })
  })

  it('L13 pin 把 options 中已选项钉到 initialOption，不在 options 中则不改', async () => {
    const fetcher = vi.fn().mockResolvedValue({ data: [F1, F2] })
    const { loadDefault, pin, initialOption } = useFundSearch({ fetcher })
    await loadDefault()
    pin('000002')
    expect(initialOption.value).toMatchObject({ value: '000002', label: '000002 - 华夏大盘' })
    pin('999999')  // 不在 options 中，initialOption 不变
    expect(initialOption.value).toMatchObject({ value: '000002' })
  })
})
