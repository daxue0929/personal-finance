<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background-color: #545c64">
      <div style="height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; font-weight: bold;">
        理财管理系统
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        style="border-right: none"
        background-color="#545c64"
        text-color="#fff"
        active-text-color="#ffd04b"
      >
        <template v-for="menu in menuItems" :key="menu.path">
          <el-sub-menu v-if="menu.meta?.isParent && menu.children" :index="menu.path">
            <template #title>
              <el-icon>
                <component :is="getIconComponent(menu.path)" />
              </el-icon>
              <span>{{ menu.meta.title }}</span>
            </template>
            <el-menu-item
              v-for="child in getChildrenMenu(menu)"
              :key="child.path"
              :index="child.path"
            >
              <el-icon>
                <component :is="getIconComponent(child.path)" />
              </el-icon>
              <span>{{ child.meta.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="menu.path">
            <el-icon>
              <component :is="getIconComponent(menu.path)" />
            </el-icon>
            <span>{{ menu.meta.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background-color: #fff; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between;">
        <div style="font-size: 16px; font-weight: 500;">
          {{ currentTitle }}
        </div>
        <div v-if="auth.user" style="display: flex; align-items: center; gap: 12px;">
          <el-alert
            v-if="auth.impersonate"
            type="warning"
            :closable="false"
            show-icon
            style="padding: 4px 10px; margin-right: 8px;"
          >
            <template #title>
              正在以 <b>{{ auth.user.display_name || auth.user.username }}</b> 视角操作
            </template>
          </el-alert>
          <!--
            退出入口放 alert 兄弟节点：admin 切视角后 isAdmin()=false，el-dropdown 整块隐藏，
            dropdown 里的「退出视角切换」菜单项不可见，必须在 alert 旁边给可点的退出按钮
          -->
          <el-button
            v-if="auth.impersonate"
            link
            type="warning"
            size="small"
            @click="stopImpersonate"
          >
            退出视角切换
          </el-button>
          <el-dropdown v-if="isAdmin()" trigger="click" @command="handleAdminCommand">
            <span class="user-trigger">
              <span class="user-trigger-name">{{ auth.user.display_name || auth.user.username }}</span>
              <el-tag size="small" :type="isAdmin() ? 'warning' : 'info'">
                {{ isAdmin() ? '管理员' : '普通用户' }}
              </el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人设置</el-dropdown-item>
                <el-dropdown-item v-if="auth.impersonate" command="stop-impersonate" divided>
                  退出视角切换
                </el-dropdown-item>
                <el-dropdown-item v-else command="switch-user" divided>切换用户视角</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <!--
            切换用户视角弹层（el-dialog 居中弹窗，2026-08-09 用户决定）
            - 居中 modal，width 480px
            - 顶部搜索框（el-input）+ 下方常驻候选列表（点击/回车选中）
            - 关闭：点 X / 点遮罩 / Esc / 选中后自动关
          -->
          <el-dialog
            v-if="isAdmin()"
            v-model="switcherVisible"
            title="切换用户视角"
            width="480px"
            align-center
            :close-on-click-modal="true"
            :close-on-press-escape="true"
            :show-close="true"
            @close="handleSwitcherClose"
            class="switcher-dialog"
          >
            <el-input
              v-model="autocompleteQuery"
              placeholder="搜索目标用户（username 或 display_name）"
              aria-label="搜索目标用户"
              ref="autocompleteRef"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div v-if="loadingUsers" class="switcher-loading" aria-live="polite">正在加载用户…</div>
            <div v-else-if="!recentUsers.length" class="switcher-empty">暂无其他用户可切换</div>
            <ul v-else class="switcher-list" role="listbox">
              <li
                v-for="u in filteredUsers"
                :key="u.id"
                class="switcher-item"
                role="option"
                tabindex="0"
                :aria-selected="false"
                @click="selectUser(u)"
                @keyup.enter="selectUser(u)"
              >
                <span class="user-key">{{ u.username }}</span>
                <span class="user-sep">-</span>
                <span class="user-desc">{{ u.display_name || '' }}</span>
              </li>
            </ul>
            <div v-if="!loadingUsers && recentUsers.length && !filteredUsers.length" class="switcher-empty">
              没有匹配的用户
            </div>
          </el-dialog>
          <template v-else>
            <span style="font-size: 14px; color: #303133;">{{ auth.user.display_name || auth.user.username }}</span>
            <el-tag size="small" :type="isAdmin() ? 'warning' : 'info'">
              {{ isAdmin() ? '管理员' : '普通用户' }}
            </el-tag>
            <el-button link @click="router.push('/profile')">个人设置</el-button>
            <el-button link class="logout-btn" @click="handleLogout">退出登录</el-button>
          </template>
        </div>
      </el-header>

      <TagsView />

      <el-main style="background-color: #f5f5f5; padding: 0;">
        <router-view v-slot="{ Component }">
          <keep-alive :include="cachedNames">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, h, nextTick, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElLoading, ElMessage } from 'element-plus'
import { Setting, Wallet, ShoppingCart, Sell, TrendCharts, Folder, Monitor, User, DataAnalysis, Document, DataLine, PieChart, Coin, Histogram, Odometer, Files, Search } from '@element-plus/icons-vue'
import { authApi, userApi, adminApi } from '@/api'
import TagsView from '@/components/TagsView.vue'
import { useTagsView } from '@/composables/useTagsView'
import { auth, isAdmin, clearAuthUser, setImpersonate, clearImpersonate } from '@/stores/auth'

const router = useRouter()
const route = useRoute()

// keep-alive 缓存名单：随已打开标签动态增减（关闭标签即清缓存）
const { cachedNames } = useTagsView()

// 是否对当前用户可见（管理员专属项对普通用户隐藏）
const visible = (r) => !(r.meta?.adminOnly && !isAdmin())

// 获取路由列表并按sort排序
// 注意：菜单取自 Layout 父路由（根路径 '/'）的 children，而非 routes[0]——
// 登录页等独立全屏路由可能排在 Layout 之前，按下标取会取错。
const menuItems = computed(() => {
  const layoutRoute = router.options.routes.find(r => r.path === '/' && r.children)
  const routes = layoutRoute?.children || []
  return routes
    .filter(r => r.path && r.meta?.title && visible(r))
    .sort((a, b) => (a.meta?.sort || 0) - (b.meta?.sort || 0))
})

const getChildrenMenu = (menu) => {
  return (menu.children || [])
    .filter(r => r.path && r.meta?.title && visible(r))
    .sort((a, b) => (a.meta?.sort || 0) - (b.meta?.sort || 0))
}

const activeMenu = computed(() => {
  return route.path
})

const currentTitle = computed(() => {
  return route.meta?.title || '理财管理系统'
})

// 图标映射
const iconMap = {
  '/dashboard': Odometer,
  '/portfolio': Folder,
  '/buyers': ShoppingCart,
  '/sellers': Sell,
  '/funds': Wallet,
  '/funds/history': TrendCharts,
  '/position-analysis': PieChart,
  '/position-analysis/manage': Coin,
  '/position-analysis/analysis': Histogram,
  '/index': DataAnalysis,
  '/index/info': Document,
  '/index/basic': Files,
  '/index/analysis': DataLine,
  '/tasks': Setting,
  '/system': Monitor,
  '/system/logs': Monitor,
  '/system/tasks': Setting,
  '/system/users': User
}

const getIconComponent = (path) => {
  return iconMap[path] || Folder
}

// 退出登录
const handleLogout = async () => {
  try {
    await authApi.logout()
  } catch (e) {
    // 即使后端 401 也继续清除本地状态
  }
  clearAuthUser()
  ElMessage.info('已退出登录')
  router.push('/login')
}

// admin 顶栏下拉
const handleAdminCommand = async (cmd) => {
  if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'switch-user') {
    // el-popover 在 el-dropdown 外面，用 virtual-ref 指向 adminChipRef
    // 这里手动打开 popover
    switcherVisible.value = true
  } else if (cmd === 'stop-impersonate') {
    await stopImpersonate()
  } else if (cmd === 'logout') {
    handleLogout()
  }
}

const stopImpersonate = async () => {
  // 立即弹全屏遮罩，掩盖后续 router.go(0) 整页 reload 带来的白屏和 admin 闪现
  ElLoading.service({
    lock: true,
    text: '正在退出视角切换…',
    background: 'rgba(255, 255, 255, 0.85)'
  })
  try {
    await adminApi.stopImpersonate()
  } catch (e) {
    // 即使后端失败也走 reload：reload 后 /api/me 会反映真实 session 状态
  }
  // 不调 clearImpersonate()：那是 reload 前 admin 闪现两次的根因
  // auth 状态由 reload 后的 /api/me 一次性重置为 admin
  router.go(0)
  // ElLoading 遮罩随旧页面销毁；新页面渲染后 /api/me 完成，admin 视图稳定显示
}

// === 切换用户视角：el-dialog 居中弹窗（2026-08-09 用户决定） ===
const switcherVisible = ref(false)
const autocompleteQuery = ref('')
const loadingUsers = ref(false)
const userList = ref([])
const autocompleteRef = ref(null)

// 排除 admin 自己（搜索和默认列表共用）
const nonAdminUsers = computed(() => {
  const adminId = auth.realUser?.id
  return userList.value.filter(u => u.id !== adminId)
})

// 默认列表：按 user_id DESC 取前 10
// 后端 /api/users 默认 page_size=10 + User.id.asc() 会返最旧 10 个，故前端拉全量 1000 再客户端排
const recentUsers = computed(() => {
  return [...nonAdminUsers.value]
    .sort((a, b) => b.id - a.id)
    .slice(0, 10)
})

// 搜索时过滤全量非 admin 用户（不受 10 项限制，搜索结果可能很多 → 列表 max-height 滚动）
const filteredUsers = computed(() => {
  const q = (autocompleteQuery.value || '').toLowerCase().trim()
  if (!q) return recentUsers.value
  return nonAdminUsers.value.filter(u =>
    u.username.toLowerCase().includes(q) ||
    (u.display_name || '').toLowerCase().includes(q)
  )
})

// 拉取全量用户列表（每次 dialog 打开都重新拉，不缓存）
const fetchUsers = async () => {
  loadingUsers.value = true
  try {
    const resp = await userApi.getUsers({ page: 1, page_size: 1000 })
    userList.value = resp.data || []
  } catch (e) {
    ElMessage.error('加载用户列表失败')
    switcherVisible.value = false
  } finally {
    loadingUsers.value = false
  }
}

// 选中后调 startImpersonate 切视角
const handleUserSelect = async (item) => {
  if (!item?.user) return
  if (item.user.id === auth.realUser?.id) {
    ElMessage.warning('不能切换到自身')
    return
  }
  switcherVisible.value = false
  // 立即弹全屏遮罩，掩盖后续 router.go(0) 整页 reload 带来的白屏和 target 闪现
  ElLoading.service({
    lock: true,
    text: `正在切换到 ${item.user.display_name || item.user.username} 视角…`,
    background: 'rgba(255, 255, 255, 0.85)'
  })
  try {
    const resp = await adminApi.startImpersonate(item.user.id)
    // 不调 setImpersonate()：那是 reload 前 target 闪现的根因
    // auth 状态由 reload 后的 /api/me 一次性重置（含 realUser / impersonate 标记）
    router.go(0)
    // ElLoading 遮罩随旧页面销毁；新页面 /api/me 返回后稳定显示 target 视图
  } catch (e) {
    // 401 由响应拦截器处理；其他错误吞掉（reload 后 /api/me 会反映真实 session 状态）
  }
}

// 列表项点击/回车 → 选中（包装给 handleUserSelect）
const selectUser = (u) => {
  handleUserSelect({ user: u })
}

// 弹层关闭后清理：清空 query + 数据，下次打开是干净状态
const handleSwitcherClose = () => {
  autocompleteQuery.value = ''
  loadingUsers.value = false
  userList.value = []
}

// 弹层打开 → 拉取数据 + 自动 focus 输入框
// el-dialog 有打开动画，需等动画结束再 focus；用 setTimeout(100) 兜底
watch(switcherVisible, async (val) => {
  if (val) {
    fetchUsers()
    await nextTick()
    setTimeout(() => {
      autocompleteRef.value?.focus?.()
    }, 100)
  }
})
</script>

<style scoped>
.el-header {
  padding: 0 20px;
}
/* 退出登录：基色 ink-2，悬停变 danger（DESIGN §4.3） */
.logout-btn {
  --el-button-text-color: #606262;
  --el-button-hover-text-color: #f56c6c;
}

/* admin 顶栏触发器：用户名 + 角色 tag 之间留出可视间隙，长名能自然撑开（2026-08-09） */
.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 14px;
  color: #303133;
  cursor: pointer;
  transition: background-color 0.15s;
  /* 防御：父级 flex 容器可能挤压；强制不收缩、文本不换行 */
  flex-shrink: 0;
  white-space: nowrap;
  max-width: none;
}
.user-trigger-name {
  /* 用户名撑开，不被 el-tooltip__trigger 默认样式截断 */
  white-space: nowrap;
}
.user-trigger:hover {
  background-color: #f5f7fa;
}
/* 防御：EP el-tooltip__trigger 自身不能给宽约束，否则长名会被截断 */
:deep(.el-tooltip__trigger) {
  max-width: none;
}

/* === 切换用户视角下拉（admin 顶栏 el-dialog 居中弹窗，2026-08-09） === */
/* username 是 key 字段：半粗 + 主色；display_name 是描述：常规 + 次要色 */
.user-key {
  font-weight: 500;
  color: #303133;
}
.user-sep {
  color: #c0c4cc;
  padding: 0 6px;
}
.user-desc {
  color: #909399;
}
/* 加载态：单行 muted 文字 */
.switcher-loading {
  height: 36px;
  line-height: 36px;
  padding: 0 12px;
  font-size: 13px;
  color: #909399;
}
/* 空态/无匹配：单行 muted 文字 + 居中 */
.switcher-empty {
  padding: 16px 12px;
  font-size: 13px;
  color: #909399;
  text-align: center;
}
/* 候选列表：默认 10 项刚好撑满不滚动；搜索时过滤全量，结果多则内部滚动 */
.switcher-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}
.switcher-item {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 12px;
  cursor: pointer;
  font-size: 14px;
  border-bottom: 1px solid #f5f7fa;
}
.switcher-item:last-child {
  border-bottom: none;
}
.switcher-item:hover,
.switcher-item:focus {
  background: #f5f7fa;
  outline: none;
}
.switcher-item:active {
  background: #ebeef5;
}
</style>
