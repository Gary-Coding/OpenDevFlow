<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../../stores/auth'
import loginIllustration from '../../assets/login-illustration.svg'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: 'admin', password: 'admin' })
const loading = ref(false)

const submit = async () => {
  if (loading.value) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.push(route.query.redirect || '/')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '登录失败，请检查账号和密码')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login">
    <section class="login-shell">
      <div class="visual-panel">
        <div class="visual-copy">
          <h1>OpenDevFlow</h1>
          <p class="subtitle">以需求为入口，串联规格、开发、验证与交付的 AI 软件工作流平台。</p>
        </div>
        <div class="illustration-wrap">
          <img :src="loginIllustration" alt="" class="illustration" />
        </div>
      </div>

      <div class="form-panel">
        <div class="form-card">
          <div class="form-header">
            <p class="eyebrow">欢迎回来</p>
            <h2>登录工作台</h2>
          </div>
          <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="账号" required>
              <el-input v-model="form.username" size="large" :prefix-icon="User" :disabled="loading" />
            </el-form-item>
            <el-form-item label="密码" required>
              <el-input
                v-model="form.password"
                size="large"
                type="password"
                show-password
                :prefix-icon="Lock"
                :disabled="loading"
              />
            </el-form-item>
            <el-button type="primary" native-type="submit" class="submit" size="large" :loading="loading">
              {{ loading ? '登录中' : '登录' }}
            </el-button>
          </el-form>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at 18% 18%, rgba(47, 111, 237, 0.12), transparent 34%),
    linear-gradient(135deg, #eef4ff 0%, #f8fafc 46%, #edf7f3 100%);
}

.login-shell {
  width: min(1120px, 100%);
  min-height: 620px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(388px, 0.74fr);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(191, 206, 229, 0.82);
  border-radius: 24px;
  box-shadow: 0 24px 70px rgba(42, 67, 101, 0.16);
}

.visual-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 44px;
  min-width: 0;
  padding: 58px 54px;
  background:
    linear-gradient(180deg, rgba(246, 249, 255, 0.96), rgba(239, 245, 255, 0.96)),
    #f6f9ff;
}

.visual-copy {
  max-width: 520px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #2f6fed;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0;
}

h1,
h2 {
  margin: 0;
  color: #15233a;
  letter-spacing: 0;
}

h1 {
  font-size: 54px;
  line-height: 1.12;
}

h2 {
  font-size: 28px;
}

.subtitle {
  max-width: 520px;
  margin: 18px 0 0;
  color: #61738d;
  font-size: 19px;
  font-weight: 650;
  line-height: 1.68;
}

.illustration-wrap {
  display: flex;
  justify-content: flex-start;
  min-height: 330px;
}

.illustration {
  width: min(86%, 540px);
  align-self: flex-start;
  filter: drop-shadow(0 18px 34px rgba(68, 91, 128, 0.12));
}

.form-panel {
  display: grid;
  place-items: center;
  padding: 40px;
  background: #ffffff;
}

.form-card {
  width: min(360px, 100%);
}

.form-header {
  margin-bottom: 30px;
}

:deep(.el-form-item) {
  margin-bottom: 22px;
}

:deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  box-shadow: 0 0 0 1px #dce5f2 inset;
}

.submit {
  width: 100%;
  min-height: 46px;
  margin-top: 4px;
  border-radius: 12px;
  font-weight: 700;
}

@media (max-width: 860px) {
  .login {
    padding: 18px;
  }

  .login-shell {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .visual-panel {
    padding: 30px 24px 22px;
    gap: 24px;
  }

  h1 {
    font-size: 36px;
  }

  .subtitle {
    font-size: 16px;
  }

  .illustration-wrap {
    min-height: 240px;
  }

  .illustration {
    width: min(82%, 340px);
    align-self: flex-start;
  }

  .form-panel {
    padding: 28px 24px 32px;
  }
}
</style>
