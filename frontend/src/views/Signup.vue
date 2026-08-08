<template>
  <div class="signup-wrap">
    <!-- 左：深色品牌面板 -->
    <div class="login-brand">
      <div class="brand-mark">
        <span class="seal">◆</span>
        <span class="brand-title">理财管理系统</span>
      </div>
      <div class="brand-sub">注 册 新 账 号</div>
      <div class="ledger" aria-hidden="true">
        <div class="ledger-line">需 admin 提供的邀请码</div>
        <div class="ledger-line">用户名 / 密码 自由设置</div>
        <div class="ledger-line">注册成功即可登录</div>
      </div>
    </div>

    <!-- 右：注册表单 -->
    <div class="login-form-wrap">
      <div class="login-form">
        <h2 class="form-title">注册账号</h2>
        <p class="form-sub">需有效邀请码</p>
        <el-form :model="form" label-position="top" @submit.prevent="handleSignup">
          <el-form-item>
            <el-input
              v-model="form.username"
              placeholder="用户名"
              aria-label="用户名"
              :prefix-icon="User"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.display_name"
              placeholder="显示名（可选）"
              aria-label="显示名"
              :prefix-icon="UserFilled"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="密码"
              aria-label="密码"
              :prefix-icon="Lock"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="form.invite_code"
              placeholder="邀请码"
              aria-label="邀请码"
              :prefix-icon="Key"
            />
          </el-form-item>
          <div v-if="errorMsg" class="form-error" role="alert">{{ errorMsg }}</div>
          <el-button
            class="login-btn"
            :loading="loading"
            :disabled="!form.username || !form.password || !form.invite_code"
            @click="handleSignup"
          >注 册</el-button>
          <div class="form-link">
            已有账号？<el-button link type="primary" @click="$router.push('/login')">去登录</el-button>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, UserFilled, Lock, Key } from '@element-plus/icons-vue'
import { signupApi } from '@/api'

const router = useRouter()
const form = reactive({
  username: '',
  display_name: '',
  password: '',
  invite_code: '',
})
const loading = ref(false)
const errorMsg = ref('')

const handleSignup = async () => {
  errorMsg.value = ''
  loading.value = true
  try {
    const resp = await signupApi.signup({
      username: form.username.trim(),
      display_name: form.display_name.trim(),
      password: form.password,
      invite_code: form.invite_code.trim(),
    })
    ElMessage.success(`注册成功：${resp.user.username}，请登录`)
    router.push('/login')
  } catch (e) {
    const detail = e.response?.data?.error || e.message || '注册失败'
    errorMsg.value = detail
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.signup-wrap {
  display: flex;
  height: 100vh;
  width: 100%;
}
.login-brand {
  flex: 1;
  background: linear-gradient(135deg, #1f2733 0%, #2c3543 100%);
  color: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.brand-mark {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.seal {
  font-size: 36px;
  color: #d4af37;
}
.brand-title {
  font-size: 28px;
  font-weight: bold;
  letter-spacing: 2px;
}
.brand-sub {
  font-size: 14px;
  color: #aab2bd;
  letter-spacing: 6px;
  margin-bottom: 36px;
}
.ledger {
  font-family: 'Courier New', monospace;
  color: #6b7280;
  font-size: 13px;
  line-height: 24px;
}
.ledger-line {
  border-bottom: 1px dashed #3a4250;
  padding: 2px 0;
}
.login-form-wrap {
  width: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
.login-form {
  width: 320px;
}
.form-title {
  font-size: 24px;
  font-weight: 600;
  color: #1f2733;
  margin: 0 0 4px 0;
}
.form-sub {
  font-size: 14px;
  color: #909399;
  margin: 0 0 24px 0;
}
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
  letter-spacing: 4px;
  margin-top: 8px;
  background: linear-gradient(135deg, #d4af37 0%, #b8941f 100%);
  border: none;
  color: #fff;
}
.login-btn:hover {
  background: linear-gradient(135deg, #e0bd44 0%, #c4a02a 100%);
}
.form-error {
  color: #f56c6c;
  font-size: 13px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #fef0f0;
  border-radius: 4px;
}
.form-link {
  text-align: center;
  margin-top: 12px;
  font-size: 13px;
  color: #606266;
}
</style>
