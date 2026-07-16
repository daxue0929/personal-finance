import { ref } from 'vue'
import { fundApi } from '@/api'

// 把后端 fund 对象映射为 el-option 项：label 统一 "code - name"，value 为 code，raw 保留原对象供 @select 抛出
function toOption(f) {
  return {
    fund_code: f.fund_code,
    fund_name: f.fund_name,
    label: `${f.fund_code} - ${f.fund_name}`,
    value: f.fund_code,
    raw: f
  }
}

/**
 * 基金下拉搜索的逻辑层（composable），与组件分离以便独立单测。
 *
 * @param {Object} opts
 * @param {number} [opts.pageSize=20]    每次拉取条数
 * @param {number} [opts.debounceMs=300] 搜索防抖毫秒
 * @param {Function} [opts.fetcher]      请求函数，默认 fundApi.getFunds。测试时注入 mock。
 * @returns {{options, loading, initialOption, search, loadDefault, resolveInitial, clear, findInOptions}}
 */
export function useFundSearch(opts = {}) {
  const pageSize = opts.pageSize ?? 20
  const debounceMs = opts.debounceMs ?? 300
  // fetcher 依赖注入点：生产用 fundApi.getFunds，测试注入 mock，逻辑层不绑定具体 IO
  const fetcher = opts.fetcher || ((params) => fundApi.getFunds(params))

  const options = ref([])          // 搜索/默认加载的选项
  const loading = ref(false)
  const initialOption = ref(null)  // 初始值回显用的单项，单独维护避免被搜索结果冲掉

  let timer = null
  let reqId = 0                    // 搜索/预载竞态保护：递增，慢请求返回时若已过期则丢弃
  let initialReqId = 0             // 初始值回显独立计数器，避免被搜索/预载请求误判过期

  // 发请求并写 options（带竞态保护与异常吞掉）
  async function fetchAndSet(keyword) {
    loading.value = true
    const myId = ++reqId
    try {
      const res = await fetcher({ keyword, page: 1, page_size: pageSize })
      if (myId !== reqId) return                   // 已有更新请求发出，丢弃本次
      options.value = (res?.data || []).map(toOption)
    } catch (e) {
      if (myId === reqId) options.value = []       // 搜索失败不应中断 UI
    } finally {
      if (myId === reqId) loading.value = false
    }
  }

  // 带防抖的远程搜索（el-select remote-method 的直接回调）
  function search(query) {
    if (timer) clearTimeout(timer)
    const q = (query || '').trim()
    if (!q) {                                     // 空关键字走默认列表，不走防抖
      loadDefault()
      return
    }
    timer = setTimeout(() => fetchAndSet(q), debounceMs)
  }

  // 拉 pageSize 条首页（空 keyword -> 后端返回前 N 条）。聚焦预载用。
  async function loadDefault() {
    if (timer) { clearTimeout(timer); timer = null }
    await fetchAndSet('')
  }

  // 初始值回显：给定 fund_code 解析出 name。命中则设置 initialOption 并返回 fund。
  async function resolveInitial(code) {
    if (!code) { initialOption.value = null; return null }
    const myId = ++initialReqId
    try {
      const res = await fetcher({ keyword: code, page: 1, page_size: pageSize })
      if (myId !== initialReqId) return null
      const hit = (res?.data || []).find(f => f.fund_code === code)
      if (hit) {
        initialOption.value = toOption(hit)
        return hit
      }
      initialOption.value = null
      return null
    } catch (e) {
      return null
    }
  }

  function clear() {
    options.value = []
    initialOption.value = null
  }

  // 把当前 options 中已选项钉到 initialOption，防止后续搜索替换 options 时选中项 label 丢失
  function pin(code) {
    const opt = options.value.find(o => o.value === code)
    if (opt) initialOption.value = opt
  }

  // 在 options 与 initialOption 中按 code 查 fund 原始对象（@select 抛出时用）
  function findInOptions(code) {
    const all = []
    if (initialOption.value) all.push(initialOption.value.raw)
    all.push(...options.value.map(o => o.raw))
    return all.find(f => f.fund_code === code)
  }

  return { options, loading, initialOption, search, loadDefault, resolveInitial, clear, pin, findInOptions }
}
