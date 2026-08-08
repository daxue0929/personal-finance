<template>
  <div style="height: 100%; display: flex; flex-direction: column;">
    <el-tabs v-model="activeTab" style="flex: 1; margin: 0 20px;" type="border-card">
      <el-tab-pane label="用户管理" name="users" style="height: 100%;">
    <el-card style="flex: 1; margin: 20px; box-shadow: none; border: none; overflow: hidden;" :body-style="{ padding: '0', height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }">
      <!-- 搜索区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; background-color: #fafafa;">
        <el-form :model="searchForm" inline>
          <el-form-item label="用户名">
            <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="searchForm.role" placeholder="请选择角色" clearable style="width: 140px;">
              <el-option label="管理员" value="admin" />
              <el-option label="普通用户" value="user" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.enabled" placeholder="请选择状态" clearable style="width: 120px;">
              <el-option label="启用" :value="true" />
              <el-option label="禁用" :value="false" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 功能区域 -->
      <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: flex-start; gap: 10px;">
        <el-button type="primary" @click="showAddDialog">新增用户</el-button>
        <el-button @click="fetchUsers">刷新</el-button>
      </div>

      <!-- 数据表格 -->
      <div style="padding: 20px; flex: 1; display: flex; flex-direction: column; overflow: hidden;">
        <el-table :data="users" style="width: 100%" height="100%" v-loading="loading">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="用户名" width="150" />
          <el-table-column prop="display_name" label="姓名" width="120">
            <template #default="{ row }">{{ row.display_name || '—' }}</template>
          </el-table-column>
          <el-table-column prop="role" label="角色" width="110">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'warning' : 'info'">
                {{ row.role === 'admin' ? '管理员' : '普通用户' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'danger'">
                {{ row.enabled ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="session_ttl_minutes" label="会话时长" width="130" align="right">
            <template #default="{ row }">
              <span class="num">{{ row.session_ttl_minutes }}</span> 分钟
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注">
            <template #default="{ row }">{{ row.remark || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-tooltip
                v-if="isSelf(row)"
                content="不可删除当前登录用户"
                placement="top"
              >
                <el-button size="small" type="danger" disabled>删除</el-button>
              </el-tooltip>
              <el-button v-else size="small" type="danger" @click="deleteUser(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页组件 -->
        <div style="text-align: right; margin-top: 20px;">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          />
        </div>
      </div>
    </el-card>
      </el-tab-pane>
      <el-tab-pane label="邀请码管理" name="invites" style="height: 100%;">
        <el-card style="margin: 20px 0; box-shadow: none; border: none;">
          <div style="padding: 20px; border-bottom: 1px solid #eee; display: flex; justify-content: flex-start; gap: 10px; align-items: center;">
            <span style="color: #909399; font-size: 13px;">生成新邀请码（默认 7 天有效）：</span>
            <el-input-number v-model="inviteTtlDays" :min="1" :max="365" :step="1" />
            <span style="color: #909399; font-size: 13px;">天</span>
            <el-button type="primary" :loading="creatingInvite" @click="handleCreateInvite">生成邀请码</el-button>
            <el-button @click="fetchInvites">刷新</el-button>
          </div>
          <el-table :data="invites" style="width: 100%" v-loading="loadingInvites">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="code" label="邀请码" width="160">
              <template #default="{ row }">
                <code style="font-family: 'Courier New', monospace; font-size: 14px; color: #d4af37;">{{ row.code }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="created_by" label="创建人" width="100" />
            <el-table-column prop="expires_at" label="过期时间" width="180" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.used_at" type="success" size="small">已使用</el-tag>
                <el-tag v-else-if="isExpired(row.expires_at)" type="danger" size="small">已过期</el-tag>
                <el-tag v-else type="warning" size="small">未使用</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="used_at" label="使用时间" width="180">
              <template #default="{ row }">{{ row.used_at || '—' }}</template>
            </el-table-column>
            <el-table-column prop="used_by" label="使用者 ID" width="100">
              <template #default="{ row }">{{ row.used_by || '—' }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新增用户'"
      width="500px"
    >
      <el-form :model="formData" label-width="120px">
        <el-form-item label="用户名" required>
          <el-input v-model="formData.username" placeholder="请输入用户名" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="密码" :required="!isEdit">
          <el-input
            v-model="formData.password"
            type="password"
            show-password
            :placeholder="isEdit ? '留空则不修改' : '请输入密码'"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="formData.display_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="formData.role" style="width: 100%;" :disabled="editingSelf">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
          <div v-if="editingSelf" style="color: #999; font-size: 12px; margin-top: 5px;">
            不可修改自身角色
          </div>
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="formData.enabled" :disabled="editingSelf" />
          <div v-if="editingSelf" style="color: #999; font-size: 12px; margin-top: 5px;">
            不可禁用当前登录用户
          </div>
        </el-form-item>
        <el-form-item label="会话时长">
          <el-input-number v-model="formData.session_ttl_minutes" :min="1" :max="43200" :step="5" />
          <span style="margin-left: 8px; color: #999; font-size: 12px;">分钟</span>
          <div style="color: #999; font-size: 12px; margin-top: 5px;">
            登录后保持登录态的时长，过期需重新登录
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.remark" type="textarea" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
defineOptions({ name: 'UserManage' })
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi, inviteCodeApi } from '@/api'
import { auth } from '@/stores/auth'

const activeTab = ref('users')

// 邀请码 tab 状态
const invites = ref([])
const loadingInvites = ref(false)
const creatingInvite = ref(false)
const inviteTtlDays = ref(7)

const isExpired = (expiresAt) => {
  if (!expiresAt) return false
  return new Date(expiresAt) < new Date()
}

const fetchInvites = async () => {
  loadingInvites.value = true
  try {
    const resp = await inviteCodeApi.list({ page: 1, page_size: 50 })
    invites.value = resp.data || []
  } catch (e) {
    ElMessage.error('加载邀请码失败')
  } finally {
    loadingInvites.value = false
  }
}

const handleCreateInvite = async () => {
  creatingInvite.value = true
  try {
    const resp = await inviteCodeApi.create({ ttl_days: inviteTtlDays.value })
    await navigator.clipboard.writeText(resp.code)
    ElMessage.success(`已生成：${resp.code}（已复制到剪贴板）`)
    fetchInvites()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '生成失败')
  } finally {
    creatingInvite.value = false
  }
}

const users = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

// 分页相关
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 搜索表单
const searchForm = ref({
  username: '',
  role: '',
  enabled: ''
})

// 表单数据
const formData = ref(defaultForm())

function defaultForm() {
  return {
    username: '',
    password: '',
    display_name: '',
    role: 'user',
    enabled: true,
    session_ttl_minutes: 60,
    remark: ''
  }
}

// 是否当前登录用户自己（防自锁）
const editingSelf = ref(false)
const isSelf = (row) => auth.user && row.id === auth.user.id

// 获取用户列表（支持搜索和分页）
const fetchUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      username: searchForm.value.username,
      role: searchForm.value.role,
      enabled: searchForm.value.enabled
    }
    const result = await userApi.getUsers(params)
    users.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '获取用户列表失败')
  } finally {
    loading.value = false
  }
}

// 每页条数改变
const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchUsers()
}

// 当前页改变
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchUsers()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchUsers()
}

// 重置搜索
const resetSearch = () => {
  searchForm.value = { username: '', role: '', enabled: '' }
  currentPage.value = 1
  fetchUsers()
}

// 显示新增对话框
const showAddDialog = () => {
  isEdit.value = false
  editId.value = null
  editingSelf.value = false
  formData.value = defaultForm()
  dialogVisible.value = true
}

// 显示编辑对话框
const showEditDialog = (row) => {
  isEdit.value = true
  editId.value = row.id
  editingSelf.value = isSelf(row)
  formData.value = {
    username: row.username,
    password: '',
    display_name: row.display_name || '',
    role: row.role,
    enabled: !!row.enabled,
    session_ttl_minutes: row.session_ttl_minutes ?? 60,
    remark: row.remark || ''
  }
  dialogVisible.value = true
}

// 提交表单
const submitForm = async () => {
  // 手动校验（沿用项目约定，不使用 :rules）
  if (!formData.value.username) {
    ElMessage.warning('请填写用户名')
    return
  }
  if (!isEdit.value && !formData.value.password) {
    ElMessage.warning('请填写密码')
    return
  }

  try {
    if (isEdit.value) {
      const data = { ...formData.value }
      if (!data.password) delete data.password  // 留空则不修改
      await userApi.updateUser(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await userApi.createUser(formData.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || (isEdit.value ? '更新失败' : '创建失败'))
  }
}

// 删除用户
const deleteUser = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '提示', { type: 'warning' })
    await userApi.deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.error || '删除失败')
    }
  }
}

onMounted(() => {
  fetchUsers()
  fetchInvites()
})
</script>

<style scoped>
.num {
  font-variant-numeric: tabular-nums;
}
</style>
