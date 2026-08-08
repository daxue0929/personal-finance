<template>
  <div class="profile-page">
    <el-card class="profile-card">
      <template #header>
        <span>个人设置</span>
      </template>
      <el-form :model="form" label-width="100px" @submit.prevent="handleSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>
        <el-form-item label="角色">
          <el-tag :type="form.role === 'admin' ? 'warning' : 'info'" size="small">
            {{ form.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="显示名（可选）" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input
            v-model="newPassword"
            type="password"
            show-password
            placeholder="留空则不修改密码"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
          <el-button @click="loadData">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi, meApi } from '@/api'
import { setAuthUser } from '@/stores/auth'

const form = reactive({
  username: '',
  display_name: '',
  role: '',
  remark: '',
})
const newPassword = ref('')
const saving = ref(false)

const loadData = async () => {
  try {
    const resp = await authApi.me()
    Object.assign(form, resp.user)
    newPassword.value = ''
  } catch (e) {
    ElMessage.error('加载个人信息失败')
  }
}

const handleSubmit = async () => {
  saving.value = true
  try {
    const data = { display_name: form.display_name, remark: form.remark }
    if (newPassword.value) {
      data.password = newPassword.value
    }
    await meApi.updateMe(data)
    ElMessage.success('已保存')
    const me = await authApi.me()
    setAuthUser(me.user)
    newPassword.value = ''
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.profile-page {
  padding: 16px;
}
.profile-card {
  max-width: 720px;
}
</style>
