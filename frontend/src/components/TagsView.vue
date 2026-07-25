<template>
  <div class="tags-view">
    <div class="tags-scroll">
      <div
        v-for="tab in tabs"
        :key="tab.path"
        class="tag-item"
        :class="{ active: tab.path === activePath, dragging: tab.path === dragPath }"
        draggable="true"
        @click="onClick(tab)"
        @contextmenu.prevent="onContextmenu($event, tab)"
        @dragstart="onDragStart(tab.path)"
        @dragover.prevent
        @drop="onDrop(tab.path)"
        @dragend="onDragEnd"
      >
        <span class="tag-title">{{ tab.title }}</span>
        <el-icon v-if="!tab.affix" class="tag-close" @click.stop="onClose(tab)">
          <Close />
        </el-icon>
      </div>
    </div>

    <!-- 右键上下文菜单 -->
    <ul v-if="menu.visible" class="ctx-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }">
      <li @click="onMenuClose('current')">关闭当前</li>
      <li @click="onMenuClose('others')">关闭其他</li>
      <li @click="onMenuClose('all')">关闭全部</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Close } from '@element-plus/icons-vue'
import { useTagsView } from '@/composables/useTagsView'

const route = useRoute()
const router = useRouter()
const { tabs, activePath, addTab, closeTab, closeOthers, closeAll, moveTab } = useTagsView()

const menu = reactive({ visible: false, x: 0, y: 0, path: '' })
const dragPath = ref(null)

const onDragStart = (path) => { dragPath.value = path }
const onDrop = (path) => {
  const from = dragPath.value
  dragPath.value = null
  if (from) moveTab(from, path)
}
const onDragEnd = () => { dragPath.value = null }

const onClick = (tab) => {
  if (tab.path !== route.path) router.push(tab.path)
}

const onClose = (tab) => {
  const jump = closeTab(tab.path)
  if (jump) router.push(jump)
}

const onContextmenu = (e, tab) => {
  menu.visible = true
  menu.x = e.clientX
  menu.y = e.clientY
  menu.path = tab.path
}

const closeMenu = () => { menu.visible = false }

const onMenuClose = (type) => {
  const path = menu.path
  menu.visible = false
  if (type === 'current') {
    const jump = closeTab(path)
    if (jump) router.push(jump)
  } else if (type === 'others') {
    closeOthers(path)
    if (path !== route.path) router.push(path)
  } else if (type === 'all') {
    const jump = closeAll()
    if (jump && jump !== route.path) router.push(jump)
  }
}

// 路由变化 -> addTab（immediate: 初始路由也入 tab）
watch(() => route.path, () => addTab(route), { immediate: true })

// 点击他处 / 滚动 -> 关闭右键菜单
onMounted(() => {
  document.addEventListener('click', closeMenu)
  document.addEventListener('scroll', closeMenu, true)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenu)
  document.removeEventListener('scroll', closeMenu, true)
})
</script>

<style scoped>
.tags-view {
  position: relative;
  height: 40px;
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 0 16px;
  display: flex;
  align-items: center;
}
.tags-scroll {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  height: 100%;
  width: 100%;
}
.tags-scroll::-webkit-scrollbar { height: 4px; }
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  font-size: 13px;
  color: #303133;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.tag-item:hover { color: #409EFF; border-color: #c6e2ff; }
.tag-item.active { color: #409EFF; border-color: #409EFF; background: rgba(64, 158, 255, 0.08); }
.tag-item.dragging { opacity: 0.5; }
.tag-close { font-size: 12px; color: #909399; opacity: 0; transition: opacity 0.2s; }
.tag-item:hover .tag-close,
.tag-item.active .tag-close { opacity: 1; }
.tag-close:hover { color: #f56c6c; }
.ctx-menu {
  position: fixed;
  z-index: 3000;
  list-style: none;
  margin: 0;
  padding: 4px 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.12);
  font-size: 13px;
  user-select: none;
}
.ctx-menu li { padding: 6px 16px; cursor: pointer; color: #303133; }
.ctx-menu li:hover { background: #f5f7fa; color: #409EFF; }
</style>
