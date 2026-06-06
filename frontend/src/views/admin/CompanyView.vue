<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const deletingId = ref('')
const companies = ref([])
const dialogVisible = ref(false)
const editingId = ref('')
const filters = reactive({
  q: '',
  status: ''
})

const form = reactive({
  name: '',
  code: '',
  status: 'active'
})

const canCreate = () => auth.hasPermission('system:company:create')
const canUpdate = () => auth.hasPermission('system:company:update')
const canDelete = () => auth.hasPermission('system:company:delete')

const loadCompanies = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/admin/companies', {
      params: {
        q: filters.q || undefined,
        status: filters.status || undefined
      }
    })
    companies.value = data.items
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.q = ''
  filters.status = ''
  loadCompanies()
}

const resetForm = () => {
  editingId.value = ''
  Object.assign(form, {
    name: '',
    code: '',
    status: 'active'
  })
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (company) => {
  editingId.value = company.id
  Object.assign(form, {
    name: company.name,
    code: company.code,
    status: company.status
  })
  dialogVisible.value = true
}

const save = async () => {
  if (saving.value) return
  if (!form.name.trim() || !form.code.trim()) {
    ElMessage.warning('请填写公司名称和编码')
    return
  }
  const payload = {
    name: form.name.trim(),
    code: form.code.trim(),
    status: form.status
  }
  saving.value = true
  try {
    if (editingId.value) {
      await http.put(`/admin/companies/${editingId.value}`, payload)
    } else {
      await http.post('/admin/companies', payload)
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await loadCompanies()
  } finally {
    saving.value = false
  }
}

const remove = async (company) => {
  if (deletingId.value) return
  await ElMessageBox.confirm(`确认删除公司「${company.name}」吗？`, '删除公司', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingId.value = company.id
  try {
    await http.delete(`/admin/companies/${company.id}`)
    ElMessage.success('已删除')
    await loadCompanies()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  } finally {
    deletingId.value = ''
  }
}

onMounted(loadCompanies)
</script>

<template>
  <section class="page">
    <div class="list-header">
      <div class="filter-bar">
        <div class="filter-item">
          <label>关键字</label>
          <el-input
            v-model="filters.q"
            clearable
            placeholder="搜索公司名称或编码"
            class="filter-input"
            :prefix-icon="Search"
            @keyup.enter="loadCompanies"
            @clear="loadCompanies"
          />
        </div>
        <div class="filter-item">
          <label>状态</label>
          <el-select v-model="filters.status" clearable placeholder="公司状态" class="filter-input" @change="loadCompanies">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </div>
        <div class="filter-actions">
          <el-button type="primary" :icon="Search" @click="loadCompanies">搜索</el-button>
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
    </div>

    <div class="list-actions-row">
      <div class="toolbar">
        <el-button :icon="Refresh" @click="loadCompanies">刷新</el-button>
        <el-button v-if="canCreate()" type="primary" :icon="Plus" @click="openCreate">新增公司</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card" v-loading="loading">
      <el-table :data="companies" row-key="id">
        <el-table-column prop="name" label="公司名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="code" label="公司编码" width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="canUpdate()" link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete()" link type="danger" :icon="Delete" :loading="deletingId === row.id" :disabled="Boolean(deletingId)" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑公司' : '新增公司'" width="520px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="公司名称" required>
          <el-input v-model="form.name" placeholder="例如 默认公司" />
        </el-form-item>
        <el-form-item label="公司编码" required>
          <el-input v-model="form.code" placeholder="例如 default" />
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
  </section>
</template>

<style scoped>
.table-card {
  border-radius: 8px;
}

.full-field {
  width: 100%;
}
</style>
