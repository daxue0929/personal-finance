import { ref } from 'vue'

const HOME = { path: '/dashboard', title: '首页', affix: true }

// 叶子路由：matched 末位记录有 components.default（父菜单 isParent 无组件，不成 tab）
const isLeafRoute = (route) => {
  const matched = route?.matched
  const last = matched && matched[matched.length - 1]
  return !!(last && last.components && last.components.default)
}

export function useTagsView() {
  const tabs = ref([{ ...HOME }])
  const activePath = ref(HOME.path)

  // 路由变化时调用：去重新增 tab，并置 active
  const addTab = (route) => {
    if (!route || !route.meta?.title || !isLeafRoute(route)) return
    activePath.value = route.path
    if (tabs.value.some(t => t.path === route.path)) return // 去重
    tabs.value.push({ path: route.path, title: route.meta.title, affix: false })
  }

  // 关闭 tab：返回需跳转的 path（关非活跃/affix 返回 null，不跳转）
  const closeTab = (path) => {
    const idx = tabs.value.findIndex(t => t.path === path)
    if (idx === -1) return null
    if (tabs.value[idx].affix) return null
    const wasActive = path === activePath.value
    tabs.value.splice(idx, 1)
    if (!wasActive) return null
    // 关了活跃 tab：右邻 -> 左邻 -> 首页
    const next = tabs.value[idx] || tabs.value[idx - 1] || tabs.value[0]
    if (next) {
      activePath.value = next.path
      return next.path
    }
    return null
  }

  // 关闭其他：仅留 keepPath + affix
  const closeOthers = (keepPath) => {
    tabs.value = tabs.value.filter(t => t.affix || t.path === keepPath)
    if (tabs.value.some(t => t.path === keepPath)) activePath.value = keepPath
    return keepPath
  }

  // 关闭全部：仅留 affix，返回首页 path
  const closeAll = () => {
    tabs.value = tabs.value.filter(t => t.affix)
    const home = tabs.value[0]
    if (home) {
      activePath.value = home.path
      return home.path
    }
    return null
  }

  // 拖拽排序：把 fromPath 的 tab 移到 toPath 的位置
  const moveTab = (fromPath, toPath) => {
    if (!fromPath || fromPath === toPath) return
    const fromIdx = tabs.value.findIndex(t => t.path === fromPath)
    const toIdx = tabs.value.findIndex(t => t.path === toPath)
    if (fromIdx === -1 || toIdx === -1) return
    const [moved] = tabs.value.splice(fromIdx, 1)
    tabs.value.splice(toIdx, 0, moved)
  }

  return { tabs, activePath, addTab, closeTab, closeOthers, closeAll, moveTab }
}
