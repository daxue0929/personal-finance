<template>
  <div class="auth-wrap">
    <!-- 左：深色品牌面板（金库门） -->
    <div class="auth-brand">
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
    <div class="auth-form-wrap">
      <div class="auth-form">
        <h2 class="form-title">注册账号</h2>
        <!-- 邀请码提示：居中突出，避免被忽略（2026-08-09） -->
        <div class="invite-hint" role="note">
          <el-icon class="invite-hint-icon"><Key /></el-icon>
          <span>注册需 admin 提供的 <b>8 位邀请码</b>，请向管理员索取</span>
        </div>
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSignup"
        >
          <el-form-item prop="username">
            <template #label>
              <span>用户名</span>
              <span class="required-mark" aria-hidden="true">*</span>
            </template>
            <el-input
              v-model="form.username"
              placeholder="3-20 位字母/数字/下划线"
              :prefix-icon="User"
              @keyup.enter="handleSignup"
            />
          </el-form-item>
          <el-form-item prop="display_name">
            <template #label>
              <span>显示名</span>
              <span class="required-mark" aria-hidden="true">*</span>
            </template>
            <el-input
              v-model="form.display_name"
              placeholder="登录后顶栏显示的名字"
              :prefix-icon="UserFilled"
              @keyup.enter="handleSignup"
            />
          </el-form-item>
          <el-form-item prop="password">
            <template #label>
              <span>密码</span>
              <span class="required-mark" aria-hidden="true">*</span>
            </template>
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="6 位以上"
              :prefix-icon="Lock"
              @keyup.enter="handleSignup"
            />
          </el-form-item>
          <el-form-item prop="invite_code">
            <template #label>
              <span>邀请码</span>
              <span class="required-mark" aria-hidden="true">*</span>
            </template>
            <el-input
              v-model="form.invite_code"
              placeholder="8 位"
              :prefix-icon="Key"
              @keyup.enter="handleSignup"
            />
          </el-form-item>
          <div v-if="errorMsg" class="form-error" role="alert">{{ errorMsg }}</div>
          <el-button
            class="auth-btn"
            :loading="loading"
            :disabled="!form.username || !form.display_name || !form.password || !form.invite_code"
            @click="handleSignup"
          >注 册</el-button>
          <div class="auth-foot">
            已有账号？<el-link
              type="primary"
              :underline="false"
              aria-label="返回登录页"
              @click="$router.push('/login')"
            >去登录</el-link>
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
const formRef = ref(null)
const form = reactive({
  username: '',
  display_name: '',
  password: '',
  invite_code: '',
})
const loading = ref(false)
const errorMsg = ref('')

// 必填校验：trim 后非空（防止只输空格蒙混）
const requiredRule = (label) => ({
  required: true,
  validator: (rule, value, callback) => {
    if (!value || !String(value).trim()) {
      callback(new Error(`请输入${label}`))
    } else {
      callback()
    }
  },
  trigger: 'blur',
})
const rules = {
  username: [requiredRule('用户名')],
  display_name: [requiredRule('显示名')],
  password: [requiredRule('密码')],
  invite_code: [requiredRule('邀请码')],
}

const handleSignup = async () => {
  // 先跑 el-form 校验，失败直接红字提示，不发请求
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
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
/* 与 Login.vue 共享视觉规范（auth-wrap / auth-brand / auth-form-wrap / auth-form / auth-btn / auth-foot） */
.auth-wrap {
  display: flex;
  height: 100vh;
  width: 100%;
  background: #fff;
}

/* 左侧深色品牌面板 —— 与 Login 统一 */
.auth-brand {
  position: relative;
  flex: 0 0 55%;
  background: #2c3033;
  color: #fff;
  padding: 8vh 5vw 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.brand-mark {
  display: flex;
  align-items: center;
  gap: 12px;
}
.seal {
  color: #ffd04b;
  font-size: 16px;
  line-height: 1;
}
.brand-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 2px;
}
.brand-sub {
  margin-top: 14px;
  font-size: 13px;
  letter-spacing: 4px;
  color: rgba(255, 255, 255, 0.45);
}
/* 极淡的账本行纹理 */
.ledger {
  margin-top: auto;
  margin-bottom: 8vh;
  font-family: 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 28px;
  color: rgba(255, 255, 255, 0.04);
  user-select: none;
}
.ledger-line {
  white-space: nowrap;
}

/* 右侧表单 */
.auth-form-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
.auth-form {
  width: 100%;
  max-width: 360px;
  padding: 24px;
  animation: form-in 0.2s ease-out;
}
@keyframes form-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.form-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 16px;
}

/* 必填红色星号（label slot 内联使用） */
.required-mark {
  color: #f56c6c;
  margin-left: 4px;
  font-weight: 600;
}

/* 邀请码提示：居中突出，金色调与登录按钮呼应（2026-08-09） */
.invite-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px;
  margin: 0 0 24px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 6px;
  color: #b88230;
  font-size: 13px;
  line-height: 1.4;
}
.invite-hint b {
  color: #8a5a00;
  font-weight: 600;
}
.invite-hint-icon {
  font-size: 16px;
  color: #d4af37;
  flex-shrink: 0;
}
.form-error {
  color: #f56c6c;
  font-size: 13px;
  margin: -8px 0 16px;
}

/* 金色主按钮 —— 与 Login 一致 */
.auth-btn {
  width: 100%;
  height: 44px;
  font-weight: 700;
  letter-spacing: 4px;
  background: #ffd04b;
  border-color: #ffd04b;
  color: #2c3033;
}
.auth-btn:hover,
.auth-btn:focus {
  background: #f0c93a;
  border-color: #f0c93a;
  color: #2c3033;
}
.auth-btn.is-disabled,
.auth-btn.is-disabled:hover {
  background: rgba(255, 208, 75, 0.5);
  border-color: rgba(255, 208, 75, 0.5);
  color: #2c3033;
}

/* 金色焦点环 */
.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #ffd04b inset, 0 0 0 2px rgba(255, 208, 75, 0.25);
}

/* 底部链接：与 Login 的 signup-hint 风格统一 */
.auth-foot {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: #606266;
}
.auth-foot :deep(.el-link) {
  display: inline-block;
  min-height: 44px;
  line-height: 44px;
  padding: 0 12px;
  vertical-align: middle;
}

/* 移动端：堆叠，深色面板收为 120px 顶带 */
@media (max-width: 768px) {
  .auth-wrap { flex-direction: column; }
  .auth-brand {
    flex: 0 0 auto;
    height: 120px;
    padding: 0 24px;
    display: flex;
    align-items: center;
  }
  .brand-sub,
  .ledger { display: none; }
  .auth-form-wrap {
    flex: 1;
    padding: 24px;
    align-items: flex-start;
    padding-top: 40px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-form { animation: none; }
}
</style>
