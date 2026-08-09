<template>
  <div class="auth-wrap">
    <!-- 左：深色品牌面板（金库门） -->
    <div class="auth-brand">
      <div class="brand-mark">
        <span class="seal">◆</span>
        <span class="brand-title">理财管理系统</span>
      </div>
      <div class="brand-sub">定 投 · 持 仓 · 组 合</div>
      <div class="ledger" aria-hidden="true">
        <div class="ledger-line">0001  沪深300   …………………</div>
        <div class="ledger-line">0002  科创50    …………………</div>
        <div class="ledger-line">0003  中证500   …………………</div>
        <div class="ledger-line">0004  创业板指  …………………</div>
        <div class="ledger-line">0005  上证50    …………………</div>
      </div>
    </div>

    <!-- 右：登录表单 -->
    <div class="auth-form-wrap">
      <div class="auth-form">
        <h2 class="form-title">欢迎回来</h2>
        <p class="form-sub">登录以继续</p>
        <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
          <el-form-item>
            <el-input
              ref="usernameRef"
              v-model="form.username"
              placeholder="用户名"
              aria-label="用户名"
              :prefix-icon="User"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              ref="passwordRef"
              v-model="form.password"
              type="password"
              show-password
              placeholder="密码"
              aria-label="密码"
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <div v-if="errorMsg" class="form-error" role="alert">{{ errorMsg }}</div>
          <el-button
            class="auth-btn"
            :loading="loading"
            :disabled="!form.username || !form.password"
            @click="handleLogin"
          >登 录</el-button>
          <div class="auth-foot">
            还没有账号？<el-link
              type="primary"
              :underline="false"
              aria-label="使用邀请码注册新账号"
              @click="$router.push('/signup')"
            >立即注册</el-link>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { authApi } from '@/api'
import { setAuthUser } from '@/stores/auth'

const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')
const usernameRef = ref(null)
const passwordRef = ref(null)

const handleLogin = async () => {
  if (!form.username || !form.password) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await authApi.login({ username: form.username, password: form.password })
    setAuthUser(res.user)
    ElMessage.success('登录成功')
    // 仅允许站内相对路径跳转，防止开放重定向
    const raw = route.query.redirect
    const redirect = typeof raw === 'string' && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = err.response?.data?.error || '用户名或密码错误'
    form.password = ''
    // 聚焦密码框以便用户重新输入
    passwordRef.value?.focus?.()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-wrap {
  display: flex;
  height: 100vh;
  width: 100%;
  background: #fff;
}

/* 左侧深色品牌面板 —— 比侧边栏 #545c64 更深一档，强调「门」 */
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
/* 极淡的账本行纹理：仅作材质暗示，不承载真实信息 */
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
  margin: 0 0 4px;
}
.form-sub {
  font-size: 13px;
  color: #909399;
  margin: 0 0 28px;
}
.form-error {
  color: #f56c6c;
  font-size: 13px;
  margin: -8px 0 16px;
}

/* 金色主按钮 —— 登录页唯一的金色时刻，进入工作区后主按钮回到 EP 蓝 */
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

/* 金色焦点环：与深面板封印呼应 */
.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #ffd04b inset, 0 0 0 2px rgba(255, 208, 75, 0.25);
}

/* 移动端：堆叠，深色面板收为 120px 顶带（仅留品牌标 + 金菱形），账本纹理与副标隐藏 */
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

/* 底部链接：登录 ↔ 注册 互相跳转的入口 */
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
</style>
