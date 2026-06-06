<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { Delete, Edit, Key, Plus, Refresh, Search, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const props = defineProps({
  section: {
    type: String,
    default: 'users'
  }
})

const auth = useAuthStore()
const loading = ref(false)
const users = ref([])
const roles = ref([])
const menus = ref([])
const departments = ref([])
const companies = ref([])
const auditLogs = ref([])
const auditTotal = ref(0)
const auditActions = ref([])
const auditDetail = ref(null)
const auditDetailVisible = ref(false)
const keyword = ref('')
const departmentKeyword = ref('')
const auditFilter = reactive({
  action: '',
  target_type: '',
  page: 1,
  page_size: 10
})
const userDialogVisible = ref(false)
const roleDialogVisible = ref(false)
const menuDialogVisible = ref(false)
const passwordDialogVisible = ref(false)
const editingUserId = ref('')
const editingRoleId = ref('')
const editingMenuId = ref('')
const passwordUser = ref(null)
const menuTreeRef = ref(null)
const menuTableRef = ref(null)
const menuExpandedRowKeys = ref([])
const selectedDepartmentId = ref('')
const selectedCompanyId = ref('')
const syncingUserForm = ref(false)
const userSaving = ref(false)
const roleSaving = ref(false)
const menuSaving = ref(false)
const passwordSaving = ref(false)
const deletingUserId = ref('')
const deletingRoleId = ref('')
const deletingMenuId = ref('')

const userForm = reactive({
  username: '',
  display_name: '',
  email: '',
  password: '',
  is_active: true,
  role_ids: [],
  company_id: null,
  department_id: null,
  dev_group_ids: []
})

const roleForm = reactive({
  name: '',
  description: '',
  menu_ids: [],
  data_scope: 'self',
  custom_department_ids: []
})

const menuForm = reactive({
  parent_id: null,
  menu_name: '',
  menu_type: 'C',
  path: '',
  component: '',
  permission: '',
  icon: '',
  order_num: 0,
  visible: true,
  status: 'active'
})

const passwordForm = reactive({
  password: ''
})

// 数据范围文案映射
const DATA_SCOPE_LABELS = {
  all: '全部数据',
  custom_dept: '自定义组织架构数据',
  dept: '本组织架构数据',
  dept_and_child: '本组织架构及以下数据',
  self: '仅本人数据'
}

const DATA_SCOPE_OPTIONS = [
  { value: 'all', label: DATA_SCOPE_LABELS.all },
  { value: 'custom_dept', label: DATA_SCOPE_LABELS.custom_dept },
  { value: 'dept', label: DATA_SCOPE_LABELS.dept },
  { value: 'dept_and_child', label: DATA_SCOPE_LABELS.dept_and_child },
  { value: 'self', label: DATA_SCOPE_LABELS.self }
]

const isSuperAdmin = computed(() => auth.isAdmin)
const userDialogTitle = computed(() => (editingUserId.value ? '编辑用户' : '新增用户'))
const roleDialogTitle = computed(() => (editingRoleId.value ? '编辑角色' : '新增角色'))
const menuDialogTitle = computed(() => (editingMenuId.value ? '编辑菜单' : '新增菜单'))
const currentCompanyId = computed(() => selectedCompanyId.value || auth.user?.company_id || '')
const currentCompanyName = computed(() => {
  const id = currentCompanyId.value
  return companies.value.find((company) => company.id === id)?.name || auth.user?.company_name || ''
})
const adminRoleIdSet = computed(() => new Set(roles.value.filter((role) => role.name === 'admin').map((role) => role.id)))
const userFormIsSystemAdmin = computed(() => userForm.role_ids.some((roleId) => adminRoleIdSet.value.has(roleId)))

const menuTree = computed(() => {
  const nodes = menus.value.map((menu) => ({
    ...menu,
    label: menu.menu_name,
    children: []
  }))
  const byId = new Map(nodes.map((menu) => [menu.id, menu]))
  const roots = []
  nodes.forEach((menu) => {
    if (menu.parent_id && byId.has(menu.parent_id)) {
      byId.get(menu.parent_id).children.push(menu)
    } else {
      roots.push(menu)
    }
  })
  const sortTree = (items) => {
    items.sort((a, b) => (a.order_num - b.order_num) || a.menu_name.localeCompare(b.menu_name))
    items.forEach((item) => sortTree(item.children))
    return items
  }
  return sortTree(roots)
})

const menuParentOptions = computed(() => menus.value.filter((menu) => menu.id !== editingMenuId.value && menu.menu_type !== 'F'))

const defaultExpandedMenuKeys = computed(() => {
  const hasVisibleMenuChild = new Set(
    menus.value
      .filter((menu) => menu.parent_id && menu.menu_type !== 'F')
      .map((menu) => menu.parent_id)
  )
  return menus.value
    .filter((menu) => menu.menu_type !== 'F' && hasVisibleMenuChild.has(menu.id))
    .map((menu) => menu.id)
})

const departmentTree = computed(() => {
  const filterText = departmentKeyword.value.trim().toLowerCase()
  const source = departments.value.filter((dept) => {
    const matchesType = dept.org_type === 'department'
    const matchesText = !filterText || dept.name.toLowerCase().includes(filterText)
    return matchesType && matchesText
  })
  const nodes = source.map((dept) => ({ ...dept, children: [] }))
  const byId = new Map(nodes.map((dept) => [dept.id, dept]))
  const roots = []
  nodes.forEach((dept) => {
    if (dept.parent_id && byId.has(dept.parent_id)) {
      byId.get(dept.parent_id).children.push(dept)
    } else {
      roots.push(dept)
    }
  })
  const sortTree = (items) => {
    items.sort((a, b) => (a.order_num - b.order_num) || a.name.localeCompare(b.name))
    items.forEach((item) => sortTree(item.children))
    return items
  }
  return [
    {
      id: '',
      name: '全部',
      children: sortTree(roots)
    }
  ]
})

const menuTypeLabel = (type) => ({ M: '目录', C: '菜单', F: '按钮' }[type] || type)

const menuTypeTag = (type) => ({ M: 'primary', C: 'success', F: 'warning' }[type] || 'info')

const orgTypeLabel = (type) => ({ department: '部门', project_group: '项目组', dev_group: '开发组' }[type] || type || '组织架构')

const departmentOptions = computed(() => departments.value.filter((dept) => dept.org_type === 'department'))

const devGroupOptions = computed(() => departments.value.filter((dept) => dept.org_type === 'dev_group' && dept.status === 'active'))

const ROLE_NAME_LABELS = {
  admin: '超级管理员',
  user: '普通用户',
  company_admin: '公司管理员',
  org_admin: '组织管理员',
  org_manager: '组织管理员',
  demand_manager: '需求管理员',
  demand_member: '需求参与人',
  auditor: '审计员'
}

const roleDisplayName = (role) => {
  if (!role) return '-'
  if (typeof role === 'string') {
    const matched = roles.value.find((item) => item.name === role)
    return matched ? roleDisplayName(matched) : ROLE_NAME_LABELS[role] || role
  }
  return ROLE_NAME_LABELS[role.name] || role.description || role.name
}

const companyName = (companyId) => {
  if (!companyId) return '-'
  return companies.value.find((company) => company.id === companyId)?.name || companyId
}

const userCompanyLabel = (user) => {
  if (!user.company_id && user.roles?.includes('admin')) return '系统级'
  return user.company_name || companyName(user.company_id)
}

const userDepartmentLabel = (user) => {
  if (!user.department_id && user.roles?.includes('admin')) return '不归属组织架构'
  return user.department_name || '-'
}

const userDevGroupLabel = (user) => {
  return user.dev_group_names?.length ? user.dev_group_names.join('、') : '-'
}

const formatJson = (value) => JSON.stringify(value || {}, null, 2)

const loadRoles = async () => {
  const { data } = await http.get('/admin/roles')
  roles.value = data.items
}

const loadMenus = async () => {
  const { data } = await http.get('/admin/menus')
  menus.value = data.items
  menuExpandedRowKeys.value = defaultExpandedMenuKeys.value
}

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
    selectedCompanyId.value = auth.user?.company_id || ''
  }
}

const loadDepartments = async () => {
  // 普通用户可能没有部门读权限，失败时静默忽略
  try {
    const { data } = await http.get('/departments', {
      params: { company_id: currentCompanyId.value || undefined }
    })
    departments.value = data.items
  } catch {
    departments.value = []
  }
}

const loadDepartmentsByCompany = async (companyId) => {
  try {
    const { data } = await http.get('/departments', {
      params: { company_id: companyId || undefined }
    })
    departments.value = data.items
  } catch {
    departments.value = []
  }
}

const loadUsers = async () => {
  const { data } = await http.get('/admin/users', {
    params: {
      q: keyword.value || undefined,
      company_id: currentCompanyId.value || undefined,
      department_id: selectedDepartmentId.value || undefined
    }
  })
  users.value = data.items
}

const loadAuditLogs = async () => {
  const { data } = await http.get('/admin/audit-logs', {
    params: {
      q: keyword.value || undefined,
      action: auditFilter.action || undefined,
      target_type: auditFilter.target_type || undefined,
      page: auditFilter.page,
      page_size: auditFilter.page_size
    }
  })
  auditLogs.value = data.items
  auditTotal.value = data.total
  auditActions.value = data.actions || auditActions.value
}

const loadData = async () => {
  loading.value = true
  try {
    if (props.section === 'users') {
      await loadCompanies()
      await Promise.all([loadUsers(), loadRoles(), loadDepartments()])
    } else if (props.section === 'roles') {
      await loadCompanies()
      await Promise.all([loadRoles(), loadMenus(), loadDepartments()])
    } else if (props.section === 'menus') {
      await loadMenus()
    } else if (props.section === 'audit') {
      await loadAuditLogs()
    }
  } finally {
    loading.value = false
  }
}

const selectDepartment = (node) => {
  selectedDepartmentId.value = node.id || ''
  loadUsers()
}

const changeCompany = async () => {
  selectedDepartmentId.value = ''
  departmentKeyword.value = ''
  if (props.section === 'users') {
    await Promise.all([loadDepartments(), loadUsers()])
  } else if (props.section === 'roles') {
    await loadDepartments()
  }
}

const resetUserSearch = () => {
  keyword.value = ''
  departmentKeyword.value = ''
  selectedDepartmentId.value = ''
  loadUsers()
}

const resetUserForm = () => {
  editingUserId.value = ''
  Object.assign(userForm, {
    username: '',
    display_name: '',
    email: '',
    password: '',
    is_active: true,
    role_ids: [],
    company_id: currentCompanyId.value || null,
    department_id: null,
    dev_group_ids: []
  })
}

const resetRoleForm = () => {
  editingRoleId.value = ''
  Object.assign(roleForm, {
    name: '',
    description: '',
    menu_ids: [],
    data_scope: 'self',
    custom_department_ids: []
  })
  menuTreeRef.value?.setCheckedKeys([])
}

const resetMenuForm = () => {
  editingMenuId.value = ''
  Object.assign(menuForm, {
    parent_id: null,
    menu_name: '',
    menu_type: 'C',
    path: '',
    component: '',
    permission: '',
    icon: '',
    order_num: 0,
    visible: true,
    status: 'active'
  })
}

const openCreateUser = () => {
  resetUserForm()
  userDialogVisible.value = true
}

const openEditUser = async (user) => {
  editingUserId.value = user.id
  if (isSuperAdmin.value && user.company_id && user.company_id !== currentCompanyId.value) {
    await loadDepartmentsByCompany(user.company_id)
  }
  syncingUserForm.value = true
  Object.assign(userForm, {
    username: user.username,
    display_name: user.display_name,
    email: user.email || '',
    password: '',
    is_active: user.is_active,
    role_ids: [...user.role_ids],
    company_id: user.company_id || null,
    department_id: user.department_id || null,
    dev_group_ids: user.dev_group_ids ? [...user.dev_group_ids] : []
  })
  await nextTick()
  syncingUserForm.value = false
  userDialogVisible.value = true
}

const saveUser = async () => {
  if (userSaving.value) return
  const payload = {
    username: userForm.username.trim(),
    display_name: userForm.display_name.trim(),
    email: userForm.email.trim() || null,
    is_active: userForm.is_active,
    role_ids: userForm.role_ids,
    company_id: userFormIsSystemAdmin.value ? null : (userForm.company_id || currentCompanyId.value || null),
    department_id: userFormIsSystemAdmin.value ? null : (userForm.department_id || null),
    dev_group_ids: userFormIsSystemAdmin.value ? [] : userForm.dev_group_ids
  }
  if (!payload.display_name || (!editingUserId.value && !payload.username)) {
    ElMessage.warning('请填写必要信息')
    return
  }
  if (!userFormIsSystemAdmin.value && (!payload.company_id || !payload.department_id)) {
    ElMessage.warning('请选择所属公司和所属部门')
    return
  }
  userSaving.value = true
  try {
    if (editingUserId.value) {
      await http.put(`/admin/users/${editingUserId.value}`, payload)
    } else {
      if (!userForm.password) {
        ElMessage.warning('请设置初始密码')
        return
      }
      await http.post('/admin/users', { ...payload, password: userForm.password })
    }
    ElMessage.success('已保存')
    userDialogVisible.value = false
    await loadUsers()
  } finally {
    userSaving.value = false
  }
}

const deleteUser = async (user) => {
  if (deletingUserId.value) return
  await ElMessageBox.confirm(`确认删除用户「${user.username}」吗？`, '删除用户', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingUserId.value = user.id
  try {
    await http.delete(`/admin/users/${user.id}`)
    ElMessage.success('已删除')
    await loadUsers()
  } finally {
    deletingUserId.value = ''
  }
}

const openResetPassword = (user) => {
  passwordUser.value = user
  passwordForm.password = ''
  passwordDialogVisible.value = true
}

const resetPassword = async () => {
  if (passwordSaving.value) return
  if (!passwordForm.password) {
    ElMessage.warning('请输入新密码')
    return
  }
  passwordSaving.value = true
  try {
    await http.post(`/admin/users/${passwordUser.value.id}/reset-password`, {
      password: passwordForm.password
    })
    ElMessage.success('密码已重置')
    passwordDialogVisible.value = false
  } finally {
    passwordSaving.value = false
  }
}

const openCreateRole = () => {
  resetRoleForm()
  roleDialogVisible.value = true
  setTimeout(() => menuTreeRef.value?.setCheckedKeys([]), 0)
}

const openEditRole = (role) => {
  editingRoleId.value = role.id
  Object.assign(roleForm, {
    name: role.name,
    description: role.description || '',
    menu_ids: role.menu_ids ? [...role.menu_ids] : [],
    data_scope: role.data_scope || 'self',
    custom_department_ids: role.custom_department_ids ? [...role.custom_department_ids] : []
  })
  roleDialogVisible.value = true
  setTimeout(() => menuTreeRef.value?.setCheckedKeys(roleForm.menu_ids), 0)
}

const saveRole = async () => {
  if (roleSaving.value) return
  roleForm.menu_ids = menuTreeRef.value?.getCheckedKeys(false) || []
  const payload = {
    name: roleForm.name.trim(),
    description: roleForm.description.trim() || null,
    menu_ids: roleForm.menu_ids,
    data_scope: roleForm.data_scope,
    company_id: currentCompanyId.value || null,
    custom_department_ids: roleForm.data_scope === 'custom_dept' ? roleForm.custom_department_ids : []
  }
  if (!payload.name) {
    ElMessage.warning('请填写角色标识')
    return
  }
  roleSaving.value = true
  try {
    if (editingRoleId.value) {
      await http.put(`/admin/roles/${editingRoleId.value}`, payload)
    } else {
      await http.post('/admin/roles', payload)
    }
    ElMessage.success('已保存')
    roleDialogVisible.value = false
    await loadRoles()
  } finally {
    roleSaving.value = false
  }
}

const syncCheckedPermissions = () => {
  roleForm.menu_ids = menuTreeRef.value?.getCheckedKeys(false) || []
}

const checkAllPermissions = () => {
  const keys = menus.value.map((menu) => menu.id)
  menuTreeRef.value?.setCheckedKeys(keys)
  roleForm.menu_ids = keys
}

const clearAllPermissions = () => {
  menuTreeRef.value?.setCheckedKeys([])
  roleForm.menu_ids = []
}

const openCreateMenu = (parent = null) => {
  resetMenuForm()
  if (parent) {
    menuForm.parent_id = parent.id
    menuForm.menu_type = parent.menu_type === 'C' ? 'F' : 'C'
  }
  menuDialogVisible.value = true
}

const openEditMenu = (menu) => {
  editingMenuId.value = menu.id
  Object.assign(menuForm, {
    parent_id: menu.parent_id || null,
    menu_name: menu.menu_name,
    menu_type: menu.menu_type,
    path: menu.path || '',
    component: menu.component || '',
    permission: menu.permission || '',
    icon: menu.icon || '',
    order_num: menu.order_num,
    visible: menu.visible,
    status: menu.status
  })
  menuDialogVisible.value = true
}

const saveMenu = async () => {
  if (menuSaving.value) return
  if (!menuForm.menu_name.trim()) {
    ElMessage.warning('请填写菜单名称')
    return
  }
  const payload = {
    parent_id: menuForm.parent_id || null,
    menu_name: menuForm.menu_name.trim(),
    menu_type: menuForm.menu_type,
    path: menuForm.path.trim() || null,
    component: menuForm.component.trim() || null,
    permission: menuForm.permission.trim() || null,
    icon: menuForm.icon.trim() || null,
    order_num: menuForm.order_num,
    visible: menuForm.visible,
    status: menuForm.status
  }
  menuSaving.value = true
  try {
    if (editingMenuId.value) {
      await http.patch(`/admin/menus/${editingMenuId.value}`, payload)
    } else {
      await http.post('/admin/menus', payload)
    }
    ElMessage.success('已保存')
    menuDialogVisible.value = false
    await loadMenus()
  } finally {
    menuSaving.value = false
  }
}

const deleteMenu = async (menu) => {
  if (deletingMenuId.value) return
  await ElMessageBox.confirm(`确认删除菜单「${menu.menu_name}」吗？`, '删除菜单', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingMenuId.value = menu.id
  try {
    await http.delete(`/admin/menus/${menu.id}`)
    ElMessage.success('已删除')
    await loadMenus()
  } finally {
    deletingMenuId.value = ''
  }
}

const deleteRole = async (role) => {
  if (deletingRoleId.value) return
  await ElMessageBox.confirm(`确认删除角色「${role.name}」吗？`, '删除角色', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingRoleId.value = role.id
  try {
    await http.delete(`/admin/roles/${role.id}`)
    ElMessage.success('已删除')
    await loadRoles()
  } finally {
    deletingRoleId.value = ''
  }
}

const searchAuditLogs = () => {
  auditFilter.page = 1
  loadAuditLogs()
}

const openAuditDetail = (log) => {
  auditDetail.value = log
  auditDetailVisible.value = true
}

watch(() => props.section, () => {
  keyword.value = ''
  departmentKeyword.value = ''
  selectedDepartmentId.value = ''
  auditFilter.action = ''
  auditFilter.target_type = ''
  auditFilter.page = 1
  loadData()
})

watch(() => userForm.company_id, async (companyId) => {
  if (!userDialogVisible.value || !isSuperAdmin.value || syncingUserForm.value || userFormIsSystemAdmin.value) return
  userForm.department_id = null
  userForm.dev_group_ids = []
  await loadDepartmentsByCompany(companyId)
})

watch(() => userForm.role_ids, async () => {
  if (!userDialogVisible.value || syncingUserForm.value) return
  if (userFormIsSystemAdmin.value) {
    userForm.company_id = null
    userForm.department_id = null
    userForm.dev_group_ids = []
  } else if (!userForm.company_id && currentCompanyId.value) {
    userForm.company_id = currentCompanyId.value
    await loadDepartmentsByCompany(userForm.company_id)
  }
})

onMounted(loadData)
</script>

<template>
  <section class="page admin-page">
    <div class="list-header">
      <div class="filter-bar">
        <template v-if="section === 'users'">
          <div v-if="isSuperAdmin" class="filter-item">
            <label>维护公司</label>
            <el-select v-model="selectedCompanyId" placeholder="选择公司" class="filter-input" @change="changeCompany">
              <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
            </el-select>
          </div>
          <div class="filter-item">
            <label>用户信息</label>
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索用户名、姓名、邮箱"
              class="filter-input wide"
              :prefix-icon="Search"
              @keyup.enter="loadUsers"
              @clear="loadUsers"
            />
          </div>
          <div class="filter-actions">
            <el-button type="primary" :icon="Search" @click="loadUsers">搜索</el-button>
            <el-button :icon="Refresh" @click="keyword = ''; loadUsers()">重置</el-button>
          </div>
        </template>
        <template v-else-if="section === 'roles' && isSuperAdmin">
          <div class="filter-item">
            <label>维护公司</label>
            <el-select v-model="selectedCompanyId" placeholder="选择公司" class="filter-input" @change="changeCompany">
              <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
            </el-select>
          </div>
        </template>
        <template v-else-if="section === 'audit'">
          <div class="filter-item">
            <label>关键字</label>
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索操作者、动作、内容"
              class="filter-input wide"
              :prefix-icon="Search"
              @keyup.enter="searchAuditLogs"
              @clear="searchAuditLogs"
            />
          </div>
          <div class="filter-item">
            <label>操作类型</label>
            <el-select v-model="auditFilter.action" clearable placeholder="操作类型" class="filter-input" @change="searchAuditLogs">
              <el-option v-for="item in auditActions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>
          <div class="filter-item">
            <label>目标类型</label>
            <el-select v-model="auditFilter.target_type" clearable placeholder="目标类型" class="filter-input small" @change="searchAuditLogs">
              <el-option label="用户" value="user" />
              <el-option label="角色" value="role" />
            </el-select>
          </div>
          <div class="filter-actions">
            <el-button type="primary" :icon="Search" @click="searchAuditLogs">搜索</el-button>
            <el-button :icon="Refresh" @click="keyword = ''; auditFilter.action = ''; auditFilter.target_type = ''; searchAuditLogs()">重置</el-button>
          </div>
        </template>
      </div>
    </div>

    <div class="list-actions-row">
      <div class="toolbar">
        <template v-if="section === 'users'">
          <el-button :icon="Refresh" @click="loadUsers">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateUser">新增用户</el-button>
        </template>
        <template v-else-if="section === 'roles'">
          <el-button :icon="Refresh" @click="loadRoles">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateRole">新增角色</el-button>
        </template>
        <template v-else-if="section === 'menus'">
          <el-button :icon="Refresh" @click="loadMenus">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateMenu()">新增菜单</el-button>
        </template>
        <template v-else-if="section === 'audit'">
          <el-button :icon="Refresh" @click="loadAuditLogs">刷新</el-button>
        </template>
        <template v-else>
          <el-button :icon="Refresh" @click="loadData">刷新</el-button>
        </template>
      </div>
    </div>

    <template v-if="section === 'users'">
      <div class="user-management-layout">
        <aside class="department-filter">
          <el-input
            v-model="departmentKeyword"
            clearable
            placeholder="请输入组织架构名称"
            :prefix-icon="Search"
            @clear="selectedDepartmentId = ''; loadUsers()"
          />
          <el-tree
            class="department-tree"
            :data="departmentTree"
            node-key="id"
            default-expand-all
            highlight-current
            :expand-on-click-node="false"
            :props="{ label: 'name', children: 'children' }"
            @node-click="selectDepartment"
          />
        </aside>

        <el-card shadow="never" class="admin-card user-table-card" v-loading="loading">
        <el-table :data="users" row-key="id">
        <el-table-column prop="username" label="用户名" width="140" show-overflow-tooltip />
        <el-table-column prop="display_name" label="姓名" width="120" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column v-if="isSuperAdmin" label="所属公司" width="150" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ userCompanyLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="所属部门" width="140" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ userDepartmentLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="参与开发组" min-width="150" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ userDevGroupLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="角色" width="180" align="center">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role" size="small" effect="plain">{{ roleDisplayName(role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Edit" @click="openEditUser(row)">编辑</el-button>
            <el-button link type="primary" :icon="Key" @click="openResetPassword(row)">重置密码</el-button>
            <el-button link type="danger" :icon="Delete" :loading="deletingUserId === row.id" :disabled="Boolean(deletingUserId)" @click="deleteUser(row)">删除</el-button>
          </template>
        </el-table-column>
          </el-table>
        </el-card>
      </div>
    </template>

    <el-card v-else shadow="never" class="admin-card" v-loading="loading">
      <el-table v-if="section === 'roles'" :data="roles" row-key="id">
        <el-table-column prop="name" label="角色标识" width="160" show-overflow-tooltip />
        <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="数据范围" min-width="180" align="center">
          <template #default="{ row }">
            <el-tag effect="plain" size="small">{{ DATA_SCOPE_LABELS[row.data_scope] || row.data_scope || '-' }}</el-tag>
            <div v-if="row.data_scope === 'custom_dept' && row.custom_department_names?.length" class="custom-dept-list">
              <el-tag
                v-for="name in row.custom_department_names"
                :key="name"
                size="small"
                type="info"
                effect="plain"
              >
                {{ name }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Edit" @click="openEditRole(row)">编辑</el-button>
            <el-button link type="danger" :icon="Delete" :loading="deletingRoleId === row.id" :disabled="Boolean(deletingRoleId)" @click="deleteRole(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-table
        v-else-if="section === 'menus'"
        ref="menuTableRef"
        :data="menuTree"
        row-key="id"
        :expand-row-keys="menuExpandedRowKeys"
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="menu_name" label="菜单名称" width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="menuTypeTag(row.menu_type)" size="small" effect="plain">{{ menuTypeLabel(row.menu_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由地址" width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ row.path || '-' }}</template>
        </el-table-column>
        <el-table-column prop="component" label="组件标识" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.component || '-' }}</template>
        </el-table-column>
        <el-table-column prop="permission" label="权限标识" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ row.permission || '-' }}</template>
        </el-table-column>
        <el-table-column prop="order_num" label="排序" width="90" align="center" />
        <el-table-column label="可见" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.visible ? 'success' : 'info'" size="small" effect="plain">{{ row.visible ? '显示' : '隐藏' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="row.menu_type !== 'F'" link type="primary" :icon="Plus" @click="openCreateMenu(row)">新增</el-button>
            <el-button link type="primary" :icon="Edit" @click="openEditMenu(row)">编辑</el-button>
            <el-button link type="danger" :icon="Delete" :loading="deletingMenuId === row.id" :disabled="Boolean(deletingMenuId)" @click="deleteMenu(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <template v-else>
        <el-table :data="auditLogs" row-key="id">
          <el-table-column label="时间" width="180" align="center">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作者" min-width="150" align="center">
            <template #default="{ row }">
              <div class="actor-cell">
                <strong>{{ row.actor_display_name || row.actor_username || '未知用户' }}</strong>
                <span v-if="row.actor_username">{{ row.actor_username }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" min-width="150" align="center">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.action_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="目标" min-width="220">
            <template #default="{ row }">
              <span>{{ row.target_type || '-' }}</span>
              <span class="muted-id">{{ row.target_id || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="260">
            <template #default="{ row }">
              {{ row.metadata?.username || row.metadata?.name || row.metadata?.after?.name || row.metadata?.after?.display_name || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" :icon="View" @click="openAuditDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-row">
          <el-pagination
            v-model:current-page="auditFilter.page"
            v-model:page-size="auditFilter.page_size"
            layout="total, sizes, prev, pager, next"
            :total="auditTotal"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="loadAuditLogs"
            @size-change="searchAuditLogs"
          />
        </div>
      </template>
    </el-card>

    <el-dialog v-model="userDialogVisible" :title="userDialogTitle" width="560px" @closed="resetUserForm">
      <el-form label-position="top">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" :disabled="Boolean(editingUserId)" placeholder="例如 zhangsan" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="userForm.display_name" placeholder="例如 张三" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="可选" />
        </el-form-item>
        <el-form-item v-if="!editingUserId" label="初始密码" required>
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item v-if="isSuperAdmin && !userFormIsSystemAdmin" label="所属公司" required>
          <el-select v-model="userForm.company_id" placeholder="选择公司" class="full-field">
            <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="!userFormIsSystemAdmin" label="所属公司" required>
          <el-input :model-value="currentCompanyName || '-'" disabled />
        </el-form-item>
        <el-form-item v-if="!userFormIsSystemAdmin" label="所属部门" required>
          <el-select v-model="userForm.department_id" clearable placeholder="选择主归属部门" class="full-field">
            <el-option v-for="d in departmentOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!userFormIsSystemAdmin" label="参与开发组">
          <el-select v-model="userForm.dev_group_ids" multiple clearable filterable placeholder="选择用户参与的开发组" class="full-field">
            <el-option v-for="d in devGroupOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="系统级账号">
          <el-input model-value="超级管理员不归属任何公司和组织架构" disabled />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="userForm.role_ids" multiple clearable placeholder="选择角色" class="full-field">
            <el-option v-for="role in roles" :key="role.id" :label="roleDisplayName(role)" :value="role.id">
              <div class="role-option">
                <span>{{ roleDisplayName(role) }}</span>
                <small>{{ role.name }}</small>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="状态" required>
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="userSaving" @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">{{ userSaving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" :title="roleDialogTitle" width="720px" @closed="resetRoleForm">
      <el-form label-position="top">
        <el-form-item label="角色标识" required>
          <el-input v-model="roleForm.name" placeholder="例如 operator" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" placeholder="角色用途说明" />
        </el-form-item>
        <el-form-item label="数据范围" required>
          <el-select v-model="roleForm.data_scope" class="full-field">
            <el-option
              v-for="opt in DATA_SCOPE_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="roleForm.data_scope === 'custom_dept'" label="自定义组织架构" required>
          <el-select v-model="roleForm.custom_department_ids" multiple clearable placeholder="选择组织架构" class="full-field">
            <el-option v-for="d in departments" :key="d.id" :label="`${d.name}（${orgTypeLabel(d.org_type)}）`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="菜单权限" required>
          <div class="permission-tree-panel">
            <div class="permission-tree-toolbar">
              <span>已选择 {{ roleForm.menu_ids.length }} 个菜单或按钮</span>
              <div>
                <el-button link type="primary" @click="checkAllPermissions">全选</el-button>
                <el-button link @click="clearAllPermissions">清空</el-button>
              </div>
            </div>
            <el-tree
              ref="menuTreeRef"
              :data="menuTree"
              show-checkbox
              node-key="id"
              :props="{ label: 'menu_name', children: 'children' }"
              @check="syncCheckedPermissions"
            >
              <template #default="{ data }">
                <div class="permission-tree-node">
                  <span>{{ data.menu_name }}</span>
                  <span>{{ data.permission || menuTypeLabel(data.menu_type) }}</span>
                </div>
              </template>
            </el-tree>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="roleSaving" @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleSaving" @click="saveRole">{{ roleSaving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="menuDialogVisible" :title="menuDialogTitle" width="640px" @closed="resetMenuForm">
      <el-form label-position="top">
        <el-form-item label="上级菜单">
          <el-select v-model="menuForm.parent_id" clearable placeholder="选择上级菜单（留空表示根目录）" class="full-field">
            <el-option v-for="menu in menuParentOptions" :key="menu.id" :label="menu.menu_name" :value="menu.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="菜单类型" required>
          <el-radio-group v-model="menuForm.menu_type">
            <el-radio-button label="M">目录</el-radio-button>
            <el-radio-button label="C">菜单</el-radio-button>
            <el-radio-button label="F">按钮</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="菜单名称" required>
          <el-input v-model="menuForm.menu_name" placeholder="例如 用户管理" />
        </el-form-item>
        <el-form-item v-if="menuForm.menu_type !== 'F'" label="路由地址" required>
          <el-input v-model="menuForm.path" placeholder="例如 /admin/users" />
        </el-form-item>
        <el-form-item v-if="menuForm.menu_type === 'C'" label="组件标识" required>
          <el-input v-model="menuForm.component" placeholder="例如 admin/AdminView:users" />
        </el-form-item>
        <el-form-item label="权限标识" required>
          <el-input v-model="menuForm.permission" placeholder="例如 system:user:list" />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="menuForm.icon" placeholder="例如 User" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="排序" required>
            <el-input-number v-model="menuForm.order_num" :min="0" />
          </el-form-item>
          <el-form-item label="状态" required>
            <el-select v-model="menuForm.status" class="full-field">
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </el-form-item>
          <el-form-item label="显示状态" required>
            <el-switch v-model="menuForm.visible" active-text="显示" inactive-text="隐藏" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="menuSaving" @click="menuDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="menuSaving" @click="saveMenu">{{ menuSaving ? '保存中' : '保存' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="重置密码" width="420px">
      <el-form label-position="top">
        <el-form-item :label="`用户：${passwordUser?.username || ''}`" required>
          <el-input v-model="passwordForm.password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="passwordSaving" @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSaving" @click="resetPassword">{{ passwordSaving ? '重置中' : '确认重置' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="auditDetailVisible" title="审计详情" width="720px">
      <el-descriptions v-if="auditDetail" :column="2" border>
        <el-descriptions-item label="时间">{{ formatDate(auditDetail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="操作者">
          {{ auditDetail.actor_display_name || auditDetail.actor_username || '未知用户' }}
        </el-descriptions-item>
        <el-descriptions-item label="操作">{{ auditDetail.action_label }}</el-descriptions-item>
        <el-descriptions-item label="权限动作">{{ auditDetail.action }}</el-descriptions-item>
        <el-descriptions-item label="目标类型">{{ auditDetail.target_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="目标 ID">{{ auditDetail.target_id || '-' }}</el-descriptions-item>
      </el-descriptions>
      <pre class="audit-json">{{ formatJson(auditDetail?.metadata) }}</pre>
    </el-dialog>
  </section>
</template>

<style scoped>
.admin-page {
  gap: 18px;
}

.admin-card {
  border-radius: 8px;
}

.user-management-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.department-filter {
  min-height: 520px;
  padding: 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.department-tree {
  margin-top: 12px;
  --el-tree-node-hover-bg-color: var(--el-fill-color-light);
}

.department-tree :deep(.el-tree-node__content) {
  min-height: 32px;
  border-radius: 4px;
}

.user-table-card {
  min-width: 0;
}

.full-field {
  width: 100%;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.custom-dept-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.permission-tree-panel {
  width: 100%;
  max-height: 420px;
  overflow: auto;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding-right: 6px;
}

.permission-tree-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 13px;
}

.permission-node,
.permission-tree-node {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.permission-tree-node span:last-child {
  color: #94a3b8;
  font-size: 12px;
}

.role-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.role-option small {
  color: #94a3b8;
  font-size: 12px;
}

.actor-cell {
  display: grid;
  gap: 2px;
}

.actor-cell strong {
  color: #172033;
  font-size: 14px;
}

.actor-cell span,
.muted-id {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.audit-json {
  max-height: 360px;
  overflow: auto;
  margin: 16px 0 0;
  padding: 12px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.6;
}

.admin-card :deep(.el-tag + .el-tag) {
  margin-left: 6px;
}

@media (max-width: 900px) {
  .list-header {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar {
    min-width: 0;
    flex-wrap: wrap;
  }

  .user-management-layout {
    grid-template-columns: 1fr;
  }

  .department-filter {
    min-height: auto;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
