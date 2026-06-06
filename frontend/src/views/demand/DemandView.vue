<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Delete, Edit, Plus, Refresh, Search, UserFilled, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const deletingId = ref('')
const memberSaving = ref(false)
const demands = ref([])
const users = ref([])
const departments = ref([])
const userSearchLoading = ref(false)
const dialogVisible = ref(false)
const memberDialogVisible = ref(false)
const editingDemand = ref(null)
const memberDemand = ref(null)
const memberRows = ref([])
const memberEditing = ref(false)

const filters = reactive({
  title: '',
  type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10
})

const form = reactive({
  title: '',
  type: 'new_business',
  description: '',
  expected_live_at: '',
  department_id: ''
})

const dialogTitle = computed(() => (editingDemand.value ? '编辑需求' : '新增需求'))
const canCreateDemand = computed(() => auth.hasPermission('demand:create'))
const canUpdateDemand = computed(() => auth.hasPermission('demand:update'))
const canDeleteDemand = computed(() => auth.hasPermission('demand:delete'))
const pagedDemands = computed(() => {
  const start = (pagination.page - 1) * pagination.pageSize
  return demands.value.slice(start, start + pagination.pageSize)
})

const departmentOptions = computed(() => departments.value.filter((item) => item.status === 'active' && item.org_type === 'dev_group'))

const typeLabel = (type) => ({
  new_business: '新业务需求',
  new_project: '新项目需求',
  optimization: '优化需求',
  bugfix: '缺陷修复',
  refactor: '重构需求'
}[type] || type)

const roleLabel = (role) => ({
  owner: '负责人',
  product_owner: '产品负责人',
  dev_owner: '开发负责人',
  developer: '开发',
  qa_owner: '测试负责人',
  tester: '测试',
  viewer: '观察者'
}[role] || role)

const demandStatusLabel = (status) => ({
  active: '进行中',
  blocked: '阻塞',
  delivered: '已交付',
  archived: '已归档'
}[status] || status)

const demandStatusType = (status) => ({
  active: 'primary',
  blocked: 'danger',
  delivered: 'success',
  archived: 'info'
}[status] || 'info')

const orgTypeLabel = (type) => ({ department: '部门', project_group: '项目组', dev_group: '开发组' }[type] || type || '组织架构')

const departmentOptionLabel = (department) => `${department.name}（${orgTypeLabel(department.org_type)}）`

const loadDemands = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/demands/', {
      params: {
        title: filters.title.trim() || undefined,
        type: filters.type || undefined,
        status: filters.status || undefined
      }
    })
    demands.value = data
    const maxPage = Math.max(Math.ceil(demands.value.length / pagination.pageSize), 1)
    if (pagination.page > maxPage) {
      pagination.page = maxPage
    }
  } finally {
    loading.value = false
  }
}

const mergeUsers = (items) => {
  const byId = new Map(users.value.map((user) => [user.id, user]))
  items.forEach((user) => {
    if (user.id) byId.set(user.id, user)
  })
  users.value = Array.from(byId.values())
}

const loadUsers = async (keyword = '') => {
  userSearchLoading.value = true
  try {
    const { data } = await http.get('/admin/users', {
      params: {
        company_id: memberDemand.value?.company_id || auth.user?.company_id || undefined,
        q: keyword || undefined,
        page: 1,
        page_size: 100
      }
    })
    if (keyword) {
      mergeUsers(data.items || [])
    } else {
      users.value = data.items || []
    }
  } finally {
    userSearchLoading.value = false
  }
}

const loadDepartments = async () => {
  const { data } = await http.get('/departments', {
    params: { company_id: auth.user?.company_id || undefined }
  })
  departments.value = data.items || []
}

const loadDemandDepartmentMembers = async () => {
  if (!memberDemand.value?.id) return
  try {
    const { data } = await http.get(`/demands/${memberDemand.value.id}/department-members`)
    mergeUsers(
      (data.items || []).map((item) => ({
        id: item.user_id,
        username: item.username,
        display_name: item.display_name,
        email: item.email
      }))
    )
  } catch (err) {
    ElMessage.warning(err?.response?.data?.detail || '归属开发组成员加载失败')
  }
}

const resetFilters = () => {
  filters.title = ''
  filters.type = ''
  filters.status = ''
  pagination.page = 1
  loadDemands()
}

const searchDemands = () => {
  pagination.page = 1
  loadDemands()
}

const changePageSize = () => {
  pagination.page = 1
}

const resetForm = () => {
  editingDemand.value = null
  Object.assign(form, {
    title: '',
    type: 'new_business',
    description: '',
    expected_live_at: '',
    department_id: ''
  })
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (demand) => {
  editingDemand.value = demand
  Object.assign(form, {
    title: demand.title,
    type: demand.type,
    description: demand.description,
    expected_live_at: demand.expected_live_at || '',
    department_id: demand.department_id || ''
  })
  dialogVisible.value = true
}

const saveDemand = async () => {
  if (saving.value) return
  if (!form.title.trim() || !form.description.trim() || !form.department_id) {
    ElMessage.warning('请填写需求标题、描述和归属开发组')
    return
  }
  const payload = {
    title: form.title.trim(),
    type: form.type,
    description: form.description.trim(),
    expected_live_at: form.expected_live_at || null,
    department_id: form.department_id || null
  }
  saving.value = true
  try {
    if (editingDemand.value) {
      await http.patch(`/demands/${editingDemand.value.id}`, payload)
    } else {
      await http.post('/demands/', payload)
    }
    ElMessage.success('需求已保存')
    dialogVisible.value = false
    await loadDemands()
  } finally {
    saving.value = false
  }
}

const removeDemand = async (demand) => {
  if (deletingId.value) return
  await ElMessageBox.confirm(
    `删除需求「${demand.title}」后，将同步删除该需求下的工作流、阶段记录、AI 会话、产物版本、测试/审查记录、代码上下文、本地项目绑定和服务端工作空间文件。此操作不可恢复，确认继续删除吗？`,
    '危险操作：删除需求',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning',
      dangerouslyUseHTMLString: false,
      confirmButtonClass: 'el-button--danger'
    }
  )
  deletingId.value = demand.id
  try {
    await http.delete(`/demands/${demand.id}`)
    ElMessage.success('需求已删除')
    await loadDemands()
  } finally {
    deletingId.value = ''
  }
}

const openMembers = async (demand) => {
  memberDemand.value = demand
  memberEditing.value = false
  memberDialogVisible.value = true
  await loadMembers(demand.id)
}

const openDetail = (demand) => {
  router.push(`/demands/${demand.id}`)
}

const loadMembers = async (demandId) => {
  const { data } = await http.get(`/demands/${demandId}/members`)
  memberRows.value = (data.items || []).map((item) => ({
    id: item.id,
    user_id: item.user_id,
    username: item.username,
    display_name: item.display_name,
    email: item.email,
    member_role: item.member_role
  }))
  mergeUsers(
    memberRows.value.map((item) => ({
      id: item.user_id,
      username: item.username,
      display_name: item.display_name,
      email: item.email
    }))
  )
}

const editMembers = async () => {
  memberEditing.value = true
  await Promise.all([loadUsers(), loadDemandDepartmentMembers()])
}

const cancelEditMembers = async () => {
  memberEditing.value = false
  if (memberDemand.value) {
    await loadMembers(memberDemand.value.id)
  }
}

const addMemberRow = async () => {
  if (!memberEditing.value) return
  if (!users.value.length) {
    await Promise.all([loadUsers(), loadDemandDepartmentMembers()])
  }
  memberRows.value.push({ user_id: '', member_role: 'viewer' })
}

const searchUsers = (keyword) => {
  loadUsers(keyword.trim())
}

const removeMemberRow = (index) => {
  if (!memberEditing.value) return
  memberRows.value.splice(index, 1)
}

const saveMembers = async () => {
  if (memberSaving.value) return
  const payload = memberRows.value
    .filter((item) => item.user_id)
    .map((item) => ({ user_id: item.user_id, member_role: item.member_role || 'viewer' }))
  if (new Set(payload.map((item) => item.user_id)).size !== payload.length) {
    ElMessage.warning('成员不能重复')
    return
  }
  memberSaving.value = true
  try {
    await http.put(`/demands/${memberDemand.value.id}/members`, payload)
    ElMessage.success('成员已保存')
    memberEditing.value = false
    await loadMembers(memberDemand.value.id)
    await loadDemands()
  } finally {
    memberSaving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadDemands(), loadDepartments()])
})
</script>

<template>
  <section class="page demand-page">
    <div class="list-header">
      <div class="filter-bar">
        <div class="filter-item">
          <label>需求标题</label>
          <el-input v-model="filters.title" clearable placeholder="请输入需求标题" class="filter-input" @keyup.enter="searchDemands" />
        </div>
        <div class="filter-item">
          <label>类型</label>
          <el-select v-model="filters.type" clearable placeholder="需求类型" class="filter-input">
            <el-option label="新业务需求" value="new_business" />
            <el-option label="新项目需求" value="new_project" />
            <el-option label="优化需求" value="optimization" />
            <el-option label="缺陷修复" value="bugfix" />
            <el-option label="重构需求" value="refactor" />
          </el-select>
        </div>
        <div class="filter-item">
          <label>状态</label>
          <el-select v-model="filters.status" clearable placeholder="需求状态" class="filter-input">
            <el-option label="进行中" value="active" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已交付" value="delivered" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </div>
        <div class="filter-actions">
          <el-button type="primary" :icon="Search" @click="searchDemands">搜索</el-button>
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
    </div>

    <div class="list-actions-row">
      <div class="toolbar">
        <el-button :icon="Refresh" @click="loadDemands">刷新</el-button>
        <el-button v-if="canCreateDemand" type="primary" :icon="Plus" @click="openCreate">新增需求</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card" v-loading="loading">
      <el-table :data="pagedDemands" row-key="id">
        <el-table-column prop="title" label="需求标题" min-width="300" show-overflow-tooltip />
        <el-table-column label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="demandStatusType(row.status)" effect="light">{{ demandStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department_name" label="归属开发组" min-width="180" align="center" show-overflow-tooltip />
        <el-table-column label="期望上线" width="120" align="center">
          <template #default="{ row }">{{ row.expected_live_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="120" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ row.creator_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right" align="center">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" :icon="View" @click="openDetail(row)">进入需求</el-button>
              <el-button v-if="canUpdateDemand" link type="primary" :icon="UserFilled" @click="openMembers(row)">成员</el-button>
              <el-button v-if="canUpdateDemand" link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
              <el-button
                v-if="canDeleteDemand"
                link
                type="danger"
                :icon="Delete"
                :loading="deletingId === row.id"
                :disabled="Boolean(deletingId)"
                @click="removeDemand(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="demands.length" class="pagination-row">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="demands.length"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="changePageSize"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="需求标题" required>
          <el-input v-model="form.title" placeholder="请输入需求标题" />
        </el-form-item>
        <el-form-item label="需求类型" required>
          <el-select v-model="form.type" class="full-field">
            <el-option label="新业务需求" value="new_business" />
            <el-option label="新项目需求" value="new_project" />
            <el-option label="优化需求" value="optimization" />
            <el-option label="缺陷修复" value="bugfix" />
            <el-option label="重构需求" value="refactor" />
          </el-select>
        </el-form-item>
        <el-form-item label="归属开发组" required>
          <el-select v-model="form.department_id" filterable placeholder="选择开发组" class="full-field">
            <el-option
              v-for="department in departmentOptions"
              :key="department.id"
              :label="departmentOptionLabel(department)"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="期望上线时间">
          <el-date-picker v-model="form.expected_live_at" type="date" value-format="YYYY-MM-DD" class="full-field" />
        </el-form-item>
        <el-form-item label="需求描述" required>
          <el-input v-model="form.description" type="textarea" :rows="5" placeholder="请输入需求背景和目标" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDemand">{{ saving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="memberDialogVisible" :title="`需求成员 - ${memberDemand?.title || ''}`" width="760px" @closed="memberEditing = false">
      <div class="member-toolbar">
        <el-button v-if="!memberEditing && canUpdateDemand" type="primary" plain :icon="Edit" :loading="memberSaving" @click="editMembers">修改</el-button>
        <template v-else-if="memberEditing">
          <el-button :disabled="memberSaving" @click="cancelEditMembers">取消修改</el-button>
          <el-button type="primary" plain :icon="Plus" :disabled="memberSaving" @click="addMemberRow">新增成员</el-button>
        </template>
      </div>
      <el-table :data="memberRows" border>
        <el-table-column label="成员" min-width="280">
          <template #default="{ row }">
            <el-select
              v-if="memberEditing"
              v-model="row.user_id"
              filterable
              remote
              reserve-keyword
              :remote-method="searchUsers"
              :loading="userSearchLoading"
              placeholder="输入姓名、用户名或邮箱搜索"
              class="full-field"
            >
              <el-option
                v-for="user in users"
                :key="user.id"
                :label="`${user.display_name || user.username}（${user.username}）`"
                :value="user.id"
              />
            </el-select>
            <span v-else>{{ row.display_name || row.username || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="需求角色" width="180">
          <template #default="{ row }">
            <el-select v-if="memberEditing" v-model="row.member_role" class="full-field">
              <el-option label="负责人" value="owner" />
              <el-option label="产品负责人" value="product_owner" />
              <el-option label="开发负责人" value="dev_owner" />
              <el-option label="开发" value="developer" />
              <el-option label="测试负责人" value="qa_owner" />
              <el-option label="测试" value="tester" />
              <el-option label="观察者" value="viewer" />
            </el-select>
            <el-tag v-else size="small" effect="plain">{{ roleLabel(row.member_role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="memberEditing" label="操作" width="90" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" :icon="Delete" @click="removeMemberRow($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button :disabled="memberSaving" @click="memberDialogVisible = false">取消</el-button>
        <el-button v-if="memberEditing" type="primary" :loading="memberSaving" @click="saveMembers">{{ memberSaving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.full-field {
  width: 100%;
}

.member-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

.table-card {
  border-radius: 8px;
}

.table-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}

.table-actions :deep(.el-button) {
  margin-left: 0;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 640px) {
  .pagination-row {
    justify-content: flex-start;
  }
}
</style>
