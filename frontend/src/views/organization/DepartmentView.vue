<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ArrowDown, ArrowUp, Delete, Edit, Plus, Refresh, Search, UserFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const deletingId = ref('')
const memberSaving = ref(false)
const departments = ref([])
const companies = ref([])
const tableRef = ref(null)
const dialogVisible = ref(false)
const memberDialogVisible = ref(false)
const editingId = ref('')
const memberDept = ref(null)
const users = ref([])
const memberRows = ref([])
const memberEditing = ref(false)
const userSearchLoading = ref(false)
const expanded = ref(true)
const selectedCompanyId = ref('')
const filters = reactive({
  name: '',
  org_type: '',
  status: ''
})

const form = reactive({
  parent_id: null,
  org_type: 'department',
  name: '',
  order_num: 0,
  status: 'active'
})

const dialogTitle = computed(() => (editingId.value ? '编辑组织架构' : '新增组织架构'))
const isSuperAdmin = computed(() => auth.isAdmin)
const currentCompanyId = computed(() => selectedCompanyId.value || auth.user?.company_id || '')

// 组织架构下拉选项（编辑时排除自身，避免设置自己为父）
const parentOptions = computed(() => {
  return departments.value.filter((d) => {
    if (d.id === editingId.value || d.org_type === 'dev_group') return false
    if (form.org_type === 'department') return d.org_type === 'department'
    if (form.org_type === 'project_group') return d.org_type === 'department'
    if (form.org_type === 'dev_group') return ['department', 'project_group'].includes(d.org_type)
    return false
  })
})

const filteredDepartments = computed(() => {
  const name = filters.name.trim().toLowerCase()
  return departments.value.filter((dept) => {
    const matchesName = !name || dept.name.toLowerCase().includes(name)
    const matchesType = !filters.org_type || dept.org_type === filters.org_type
    const matchesStatus = !filters.status || dept.status === filters.status
    return matchesName && matchesType && matchesStatus
  })
})

const departmentTree = computed(() => {
  const source = filteredDepartments.value
  const visibleIds = new Set(source.map((dept) => dept.id))
  const nodes = source.map((dept) => ({ ...dept, children: [] }))
  const byId = new Map(nodes.map((dept) => [dept.id, dept]))
  const roots = []
  nodes.forEach((dept) => {
    if (dept.parent_id && byId.has(dept.parent_id)) {
      byId.get(dept.parent_id).children.push(dept)
    } else if (dept.parent_id && !visibleIds.has(dept.parent_id)) {
      roots.push(dept)
    } else {
      roots.push(dept)
    }
  })
  const sortTree = (items) => {
    items.sort((a, b) => (a.order_num - b.order_num) || a.name.localeCompare(b.name))
    items.forEach((item) => sortTree(item.children))
    return items
  }
  return sortTree(roots)
})

const parentName = (parentId) => {
  if (!parentId) return '-'
  const parent = departments.value.find((d) => d.id === parentId)
  return parent ? parent.name : parentId
}

const orgTypeLabel = (type) => ({ department: '部门', project_group: '项目组', dev_group: '开发组' }[type] || type || '-')

const orgTypeTag = (type) => ({ department: 'primary', project_group: 'warning', dev_group: 'success' }[type] || 'info')

const memberRoleLabel = (role) => ({ leader: '组长', member: '成员' }[role] || role)

const loadCompanies = async () => {
  if (!isSuperAdmin.value) {
    companies.value = auth.user?.company_id
      ? [{ id: auth.user.company_id, name: auth.user.company_name || '当前公司' }]
      : []
    selectedCompanyId.value = auth.user?.company_id || ''
    return
  }
  const { data } = await http.get('/admin/companies')
  companies.value = data.items || []
  if (!selectedCompanyId.value) {
    selectedCompanyId.value = auth.user?.company_id || companies.value[0]?.id || ''
  }
}

const resetFilters = () => {
  filters.name = ''
  filters.org_type = ''
  filters.status = ''
}

const setExpanded = async (value) => {
  expanded.value = value
  await nextTick()
  const walk = (items) => {
    items.forEach((item) => {
      tableRef.value?.toggleRowExpansion(item, value)
      if (item.children?.length) walk(item.children)
    })
  }
  walk(departmentTree.value)
}

const loadDepartments = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/departments', {
      params: { company_id: currentCompanyId.value || undefined }
    })
    departments.value = data.items
  } finally {
    loading.value = false
  }
}

const mergeUsers = (items) => {
  const byId = new Map(users.value.map((user) => [user.id, user]))
  items.forEach((user) => byId.set(user.id, user))
  users.value = Array.from(byId.values())
}

const loadUsers = async (companyId = currentCompanyId.value, keyword = '') => {
  userSearchLoading.value = true
  try {
    const { data } = await http.get('/admin/users', {
      params: {
        company_id: companyId || undefined,
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
  } catch (err) {
    if (!keyword) users.value = []
    ElMessage.error(err?.response?.data?.detail || '用户列表加载失败')
  } finally {
    userSearchLoading.value = false
  }
}

const changeCompany = async () => {
  resetForm()
  memberDialogVisible.value = false
  memberEditing.value = false
  await loadDepartments()
}

const resetForm = () => {
  editingId.value = ''
  Object.assign(form, {
    parent_id: null,
    org_type: 'department',
    name: '',
    order_num: 0,
    status: 'active'
  })
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openCreateChild = (dept) => {
  if (dept.org_type === 'dev_group') {
    ElMessage.warning('开发组下不能新增子级')
    return
  }
  resetForm()
  form.parent_id = dept.id
  form.org_type = dept.org_type === 'department' ? 'project_group' : 'dev_group'
  dialogVisible.value = true
}

const openEdit = (dept) => {
  editingId.value = dept.id
  Object.assign(form, {
    parent_id: dept.parent_id,
    org_type: dept.org_type || 'department',
    name: dept.name,
    order_num: dept.order_num,
    status: dept.status
  })
  dialogVisible.value = true
}

const save = async () => {
  if (saving.value) return
  if (!form.name.trim()) {
    ElMessage.warning('请填写组织架构名称')
    return
  }
  if (form.org_type !== 'department' && !form.parent_id) {
    ElMessage.warning('项目组和开发组必须选择上级组织架构')
    return
  }
  const payload = {
    company_id: currentCompanyId.value || null,
    parent_id: form.parent_id || null,
    org_type: form.org_type,
    name: form.name.trim(),
    order_num: form.order_num,
    status: form.status
  }
  saving.value = true
  try {
    if (editingId.value) {
      await http.patch(`/departments/${editingId.value}`, payload)
    } else {
      await http.post('/departments', payload)
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await loadDepartments()
  } finally {
    saving.value = false
  }
}

const remove = async (dept) => {
  if (deletingId.value) return
  await ElMessageBox.confirm(`确认删除组织架构「${dept.name}」吗？`, '删除组织架构', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingId.value = dept.id
  try {
    await http.delete(`/departments/${dept.id}`)
    ElMessage.success('已删除')
    await loadDepartments()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deletingId.value = ''
  }
}

const openMembers = async (dept) => {
  if (dept.org_type !== 'dev_group') {
    ElMessage.warning('成员只能维护在开发组上')
    return
  }
  memberDept.value = dept
  memberEditing.value = false
  memberDialogVisible.value = true
  await loadMembers(dept.id)
}

const loadMembers = async (deptId) => {
  const { data } = await http.get(`/departments/${deptId}/members`)
  mergeUsers(data.items || [])
  memberRows.value = (data.items || []).map((item) => ({
    user_id: item.user_id,
    username: item.username,
    display_name: item.display_name,
    email: item.email,
    member_role: item.member_role
  }))
}

const editMembers = async () => {
  memberEditing.value = true
  await loadUsers(memberDept.value?.company_id || currentCompanyId.value)
}

const cancelEditMembers = async () => {
  memberEditing.value = false
  if (memberDept.value) {
    await loadMembers(memberDept.value.id)
  }
}

const searchUsers = (keyword) => {
  loadUsers(memberDept.value?.company_id || currentCompanyId.value, keyword.trim())
}

const addMemberRow = () => {
  if (!memberEditing.value) return
  memberRows.value.push({ user_id: '', member_role: 'member' })
}

const removeMemberRow = (index) => {
  if (!memberEditing.value) return
  memberRows.value.splice(index, 1)
}

const saveMembers = async () => {
  if (memberSaving.value) return
  const payload = memberRows.value
    .filter((item) => item.user_id)
    .map((item) => ({ user_id: item.user_id, member_role: item.member_role || 'member' }))
  if (new Set(payload.map((item) => item.user_id)).size !== payload.length) {
    ElMessage.warning('成员不能重复')
    return
  }
  memberSaving.value = true
  try {
    await http.put(`/departments/${memberDept.value.id}/members`, payload)
    ElMessage.success('成员已保存')
    memberEditing.value = false
    await loadMembers(memberDept.value.id)
  } finally {
    memberSaving.value = false
  }
}

onMounted(async () => {
  await loadCompanies()
  await loadDepartments()
})
</script>

<template>
  <section class="page">
    <div class="list-header">
      <div class="filter-bar">
        <div v-if="isSuperAdmin" class="filter-item">
          <label>维护公司</label>
          <el-select v-model="selectedCompanyId" placeholder="选择公司" class="filter-input" @change="changeCompany">
            <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
          </el-select>
        </div>
        <div class="filter-item">
          <label>组织架构名称</label>
          <el-input
            v-model="filters.name"
            clearable
            placeholder="请输入组织架构名称"
            class="filter-input"
            @keyup.enter="loadDepartments"
          />
        </div>
        <div class="filter-item">
          <label>类型</label>
          <el-select v-model="filters.org_type" clearable placeholder="组织类型" class="filter-input">
            <el-option label="部门" value="department" />
            <el-option label="项目组" value="project_group" />
            <el-option label="开发组" value="dev_group" />
          </el-select>
        </div>
        <div class="filter-item">
          <label>状态</label>
          <el-select v-model="filters.status" clearable placeholder="组织状态" class="filter-input">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </div>
        <div class="filter-actions">
          <el-button type="primary" :icon="Search" @click="loadDepartments">搜索</el-button>
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
    </div>

    <div class="list-actions-row">
      <div class="toolbar">
        <el-button :icon="Refresh" @click="loadDepartments">刷新</el-button>
        <el-button plain :icon="expanded ? ArrowUp : ArrowDown" @click="setExpanded(!expanded)">
          {{ expanded ? '折叠' : '展开' }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增</el-button>
      </div>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-table
        ref="tableRef"
        :data="departmentTree"
        row-key="id"
        default-expand-all
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="name" label="组织架构名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="orgTypeTag(row.org_type)" effect="plain">{{ orgTypeLabel(row.org_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="order_num" label="排序" width="120" align="center" />
        <el-table-column label="状态" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">
              {{ row.status === 'active' ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="310" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Edit" @click="openEdit(row)">修改</el-button>
            <el-button link type="primary" :icon="Plus" @click="openCreateChild(row)">新增</el-button>
            <el-button v-if="row.org_type === 'dev_group'" link type="primary" :icon="UserFilled" @click="openMembers(row)">成员</el-button>
            <el-button link type="danger" :icon="Delete" :loading="deletingId === row.id" :disabled="Boolean(deletingId)" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="上级组织架构">
          <el-select v-model="form.parent_id" clearable placeholder="选择上级组织架构（留空表示根节点）" class="full-field">
            <el-option v-for="d in parentOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="组织类型" required>
          <el-select v-model="form.org_type" class="full-field">
            <el-option label="部门" value="department" />
            <el-option label="项目组" value="project_group" />
            <el-option label="开发组" value="dev_group" />
          </el-select>
        </el-form-item>
        <el-form-item label="组织架构名称" required>
          <el-input v-model="form.name" placeholder="例如 研发部 / 来伊份项目组 / 交易开发组" />
        </el-form-item>
        <el-form-item label="排序" required>
          <el-input-number v-model="form.order_num" :min="0" />
        </el-form-item>
        <el-form-item label="状态" required>
          <el-select v-model="form.status" class="full-field">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ saving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="memberDialogVisible" :title="`维护开发组成员 - ${memberDept?.name || ''}`" width="720px" @closed="memberEditing = false">
      <div class="member-toolbar">
        <el-button v-if="!memberEditing" type="primary" plain :icon="Edit" :loading="memberSaving" @click="editMembers">修改</el-button>
        <template v-else>
          <el-button :disabled="memberSaving" @click="cancelEditMembers">取消修改</el-button>
          <el-button type="primary" plain :icon="Plus" :disabled="memberSaving" @click="addMemberRow">新增成员</el-button>
        </template>
      </div>
      <el-table :data="memberRows" border>
        <el-table-column label="成员" min-width="260">
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
              <template #empty>
                <div class="select-empty">暂无可选用户</div>
              </template>
            </el-select>
            <span v-else>{{ row.display_name || row.username || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成员角色" width="160" align="center">
          <template #default="{ row }">
            <el-select v-if="memberEditing" v-model="row.member_role" class="full-field">
              <el-option label="组长" value="leader" />
              <el-option label="成员" value="member" />
            </el-select>
            <el-tag v-else :type="row.member_role === 'leader' ? 'warning' : 'info'" effect="plain">
              {{ memberRoleLabel(row.member_role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="memberEditing" label="说明" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.member_role === 'leader' ? 'warning' : 'info'" effect="plain">
              {{ memberRoleLabel(row.member_role) }}
            </el-tag>
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

.select-empty {
  padding: 10px 12px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
