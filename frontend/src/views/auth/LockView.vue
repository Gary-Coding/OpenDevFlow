<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const particleCanvas = ref()
const passwordInput = ref()
const currentTime = ref('')
const currentDate = ref('')
const errorMsg = ref('')
const isShaking = ref(false)
const loading = ref(false)
const particles = []
const form = reactive({ password: '' })

let timer = null
let animationId = null
let resizeHandler = null

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '用户')
const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())

const startClock = () => {
  const update = () => {
    const now = new Date()
    const h = String(now.getHours()).padStart(2, '0')
    const m = String(now.getMinutes()).padStart(2, '0')
    const s = String(now.getSeconds()).padStart(2, '0')
    const days = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    currentTime.value = `${h}:${m}:${s}`
    currentDate.value = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${days[now.getDay()]}`
  }
  update()
  timer = window.setInterval(update, 1000)
}

const initParticles = () => {
  const canvas = particleCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const resize = () => {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resizeHandler = resize
  resize()
  window.addEventListener('resize', resize)

  particles.length = 0
  for (let i = 0; i < 80; i += 1) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 2 + 1,
      dx: (Math.random() - 0.5) * 0.6,
      dy: (Math.random() - 0.5) * 0.6,
      alpha: Math.random() * 0.5 + 0.2
    })
  }

  const draw = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    particles.forEach((p) => {
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255,255,255,${p.alpha})`
      ctx.fill()
      p.x += p.dx
      p.y += p.dy
      if (p.x < 0 || p.x > canvas.width) p.dx *= -1
      if (p.y < 0 || p.y > canvas.height) p.dy *= -1
    })

    for (let i = 0; i < particles.length; i += 1) {
      for (let j = i + 1; j < particles.length; j += 1) {
        const a = particles[i]
        const b = particles[j]
        const dist = Math.hypot(a.x - b.x, a.y - b.y)
        if (dist < 120) {
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.strokeStyle = `rgba(255,255,255,${0.15 * (1 - dist / 120)})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }
    animationId = window.requestAnimationFrame(draw)
  }
  draw()
}

const showError = (message) => {
  errorMsg.value = message
  isShaking.value = true
  window.setTimeout(() => {
    isShaking.value = false
  }, 600)
}

const unlock = async () => {
  if (!form.password) {
    showError('请输入密码')
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const redirect = localStorage.getItem('screen-lock-path') || sessionStorage.getItem('opendevflow_lock_redirect') || '/dashboard'
    localStorage.setItem('screen-lock', 'false')
    localStorage.setItem('screen-lock-path', '/dashboard')
    sessionStorage.removeItem('opendevflow_lock_redirect')
    router.replace(redirect)
  } catch (error) {
    showError(error?.message || '解锁失败')
    form.password = ''
    await nextTick()
    passwordInput.value?.focus()
  } finally {
    loading.value = false
  }
}

const goLogin = () => {
  localStorage.setItem('screen-lock', 'false')
  localStorage.setItem('screen-lock-path', '/dashboard')
  sessionStorage.removeItem('opendevflow_lock_redirect')
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  startClock()
  initParticles()
  await nextTick()
  passwordInput.value?.focus()
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
  if (animationId) window.cancelAnimationFrame(animationId)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
})
</script>

<template>
  <div class="lock-container">
    <canvas ref="particleCanvas" class="particle-bg"></canvas>

    <div class="lock-time">{{ currentTime }}</div>
    <div class="lock-date">{{ currentDate }}</div>

    <div class="lock-card">
      <div class="avatar-wrap">
        <div class="lock-avatar">{{ avatarText }}</div>
        <div class="lock-icon">🔒</div>
      </div>
      <div class="lock-username">{{ displayName }}</div>
      <div class="lock-hint">系统已锁定，请输入密码解锁</div>

      <div class="input-wrap" :class="{ shake: isShaking }">
        <input
          ref="passwordInput"
          v-model="form.password"
          type="password"
          placeholder="请输入登录密码"
          class="lock-input"
          autocomplete="off"
          @keydown.enter="unlock"
        />
        <button class="unlock-btn" :disabled="loading" @click="unlock">
          <span v-if="!loading">→</span>
          <span v-else class="loading-dot">···</span>
        </button>
      </div>

      <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>

      <div class="lock-footer">
        <a href="/login" @click.prevent="goLogin">退出重新登录</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lock-container {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  overflow: hidden;
}

.particle-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
}

.lock-time {
  position: relative;
  z-index: 1;
  font-size: clamp(48px, 7vw, 72px);
  font-weight: 200;
  color: #fff;
  letter-spacing: 4px;
  text-shadow: 0 0 40px rgba(255,255,255,0.3);
  margin-bottom: 8px;
  font-variant-numeric: tabular-nums;
}

.lock-date {
  position: relative;
  z-index: 1;
  font-size: 15px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 48px;
  letter-spacing: 2px;
}

.lock-card {
  position: relative;
  z-index: 1;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 24px;
  padding: 40px 48px;
  width: 360px;
  max-width: calc(100vw - 40px);
  display: flex;
  flex-direction: column;
  align-items: center;
  box-shadow: 0 25px 60px rgba(0,0,0,0.4);
}

.avatar-wrap {
  position: relative;
  margin-bottom: 16px;
}

.lock-avatar {
  width: 80px;
  height: 80px;
  flex: 0 0 80px;
  border-radius: 50%;
  border: 3px solid rgba(255,255,255,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 32px;
  font-weight: 600;
  background: rgba(255,255,255,0.14);
}

.lock-icon {
  position: absolute;
  bottom: -4px;
  right: -4px;
  background: rgba(255,255,255,0.15);
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffe873;
  font-size: 13px;
  line-height: 1;
  backdrop-filter: blur(8px);
}

.lock-username {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
  letter-spacing: 1px;
}

.lock-hint {
  color: rgba(255,255,255,0.5);
  font-size: 13px;
  margin-bottom: 28px;
}

.input-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 50px;
  padding: 4px 4px 4px 20px;
  transition: border-color 0.3s;
  box-sizing: border-box;
}

.input-wrap:focus-within {
  border-color: rgba(255,255,255,0.6);
  background: rgba(255,255,255,0.13);
}

.input-wrap.shake {
  animation: shake 0.5s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}

.lock-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  outline: none;
  color: #fff;
  font-size: 15px;
  padding: 10px 0;
}

.lock-input::placeholder {
  color: rgba(255,255,255,0.35);
}

.unlock-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  transition: transform 0.2s, opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.unlock-btn:hover:not(:disabled) {
  transform: scale(1.08);
}

.unlock-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-dot {
  font-size: 13px;
  letter-spacing: 1px;
}

.error-msg {
  margin-top: 14px;
  color: #ff7675;
  font-size: 13px;
  text-align: center;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.lock-footer {
  margin-top: 24px;
}

.lock-footer a {
  color: rgba(255,255,255,0.4);
  font-size: 13px;
  text-decoration: none;
  transition: color 0.2s;
}

.lock-footer a:hover {
  color: rgba(255,255,255,0.8);
}

@media (max-width: 520px) {
  .lock-date {
    margin-bottom: 32px;
    letter-spacing: 1px;
  }

  .lock-card {
    width: calc(100vw - 40px);
    padding: 34px 28px;
  }
}
</style>
