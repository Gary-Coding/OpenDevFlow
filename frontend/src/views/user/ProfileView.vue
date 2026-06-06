<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Calendar,
  Lock,
  Message,
  OfficeBuilding,
  Postcard,
  User,
  UserFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const loading = ref(false)
const activeTab = ref('userinfo')
const profile = ref(null)
const infoFormRef = ref()
const passwordFormRef = ref()

const infoForm = reactive({
  display_name: '',
  email: ''
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const authProfile = computed(() => ({
  username: auth.user?.username || '',
  display_name: auth.user?.display_name || auth.user?.username || '',
  email: '',
  roles: auth.user?.roles || [],
  company_name: '',
  department_name: '',
  created_at: ''
}))

const displayProfile = computed(() => {
  const loaded = profile.value || {}
  return {
    username: loaded.username || authProfile.value.username,
    display_name: loaded.display_name || authProfile.value.display_name,
    email: loaded.email || authProfile.value.email,
    roles: loaded.roles?.length ? loaded.roles : authProfile.value.roles,
    company_name: loaded.company_name || authProfile.value.company_name,
    department_name: loaded.department_name || authProfile.value.department_name,
    created_at: loaded.created_at || authProfile.value.created_at
  }
})

const displayName = computed(() => displayProfile.value.display_name || displayProfile.value.username || '用户')
const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())
const roleGroup = computed(() => displayProfile.value.roles?.join('、') || '-')

const infoRules = {
  display_name: [{ required: true, message: '请输入用户昵称', trigger: 'blur' }],
  email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }]
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的新密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur'
    }
  ]
}

const loadProfile = async () => {
  loading.value = true
  infoForm.display_name = displayProfile.value.display_name || displayProfile.value.username || ''
  infoForm.email = displayProfile.value.email || ''
  try {
    const { data } = await http.get('/users/me')
    profile.value = data
    infoForm.display_name = displayProfile.value.display_name || displayProfile.value.username || ''
    infoForm.email = displayProfile.value.email || ''
  } catch (error) {
    ElMessage.error('个人资料加载失败，请刷新页面或重新登录')
  } finally {
    loading.value = false
  }
}

const submitInfo = async () => {
  await infoFormRef.value?.validate()
  ElMessage.info('当前阶段暂未开放个人资料保存接口')
}

const resetInfo = () => {
  infoForm.display_name = displayProfile.value.display_name || displayProfile.value.username || ''
  infoForm.email = displayProfile.value.email || ''
}

const submitPassword = async () => {
  await passwordFormRef.value?.validate()
  ElMessage.info('当前阶段暂未开放修改密码接口')
}

const resetPassword = () => {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
}

onMounted(loadProfile)
</script>

<template>
  <div class="page profile-page" v-loading="loading">
    <el-row :gutter="20">
      <el-col :span="6" :xs="24">
        <el-card class="profile-card">
          <template #header>
            <span>个人信息</span>
          </template>
          <div class="avatar-wrap">
            <el-avatar :size="86" class="profile-avatar">{{ avatarText }}</el-avatar>
          </div>
          <ul class="profile-list">
            <li>
              <span><el-icon><User /></el-icon>用户名称</span>
              <strong>{{ displayProfile.username || '-' }}</strong>
            </li>
            <li>
              <span><el-icon><Message /></el-icon>用户邮箱</span>
              <strong>{{ displayProfile.email || '-' }}</strong>
            </li>
            <li>
              <span><el-icon><OfficeBuilding /></el-icon>所属公司</span>
              <strong>{{ displayProfile.company_name || '-' }}</strong>
            </li>
            <li>
              <span><el-icon><Postcard /></el-icon>所属组织</span>
              <strong>{{ displayProfile.department_name || '-' }}</strong>
            </li>
            <li>
              <span><el-icon><UserFilled /></el-icon>所属角色</span>
              <strong>{{ roleGroup }}</strong>
            </li>
            <li>
              <span><el-icon><Calendar /></el-icon>创建日期</span>
              <strong>{{ formatDate(displayProfile.created_at) }}</strong>
            </li>
          </ul>
        </el-card>
      </el-col>

      <el-col :span="18" :xs="24">
        <el-card>
          <template #header>
            <span>基本资料</span>
          </template>
          <el-tabs v-model="activeTab">
            <el-tab-pane label="基本资料" name="userinfo">
              <el-form ref="infoFormRef" :model="infoForm" :rules="infoRules" label-width="90px" class="profile-form">
                <el-form-item label="用户昵称" prop="display_name">
                  <el-input v-model="infoForm.display_name" />
                </el-form-item>
                <el-form-item label="用户邮箱" prop="email">
                  <el-input v-model="infoForm.email" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="submitInfo">保存</el-button>
                  <el-button @click="resetInfo">重置</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>
            <el-tab-pane label="修改密码" name="resetPwd">
              <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="90px" class="profile-form">
                <el-form-item label="旧密码" prop="old_password">
                  <el-input v-model="passwordForm.old_password" type="password" show-password />
                </el-form-item>
                <el-form-item label="新密码" prop="new_password">
                  <el-input v-model="passwordForm.new_password" type="password" show-password />
                </el-form-item>
                <el-form-item label="确认密码" prop="confirm_password">
                  <el-input v-model="passwordForm.confirm_password" type="password" show-password />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" :icon="Lock" @click="submitPassword">保存</el-button>
                  <el-button @click="resetPassword">重置</el-button>
                </el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.profile-page {
  display: block;
}

.profile-card {
  margin-bottom: 16px;
}

.avatar-wrap {
  display: flex;
  justify-content: center;
  padding: 10px 0 18px;
}

.profile-avatar {
  background: #e0f2fe;
  color: #0369a1;
  font-size: 30px;
  font-weight: 700;
}

.profile-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.profile-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  border-top: 1px solid #eef2f7;
  color: #606266;
  font-size: 14px;
}

.profile-list span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.profile-list strong {
  min-width: 0;
  color: #303133;
  font-weight: 500;
  text-align: right;
  overflow-wrap: anywhere;
}

.profile-form {
  max-width: 520px;
  padding-top: 10px;
}
</style>
