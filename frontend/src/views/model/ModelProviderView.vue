<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Check, Delete, Edit, Plus, Refresh, Search, Star } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const testingId = ref('')
const fetchingId = ref('')
const deletingId = ref('')
const providers = ref([])
const providerTypes = ref([])
const availableModels = ref([])
const dialogVisible = ref(false)
const editingId = ref('')

const filters = reactive({
  q: '',
  status: ''
})

const form = reactive({
  name: '',
  provider_type: 'openai_compatible',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  default_model: '',
  is_default: false,
  status: 'active'
})

const canCreate = () => auth.hasPermission('model_provider:create')
const canUpdate = () => auth.hasPermission('model_provider:update')
const canDelete = () => auth.hasPermission('model_provider:delete')

const providerTypeLabel = (value) => providerTypes.value.find((item) => item.value === value)?.label || value
const statusLabel = (value) => (value === 'active' ? '启用' : '停用')

const filteredProviders = () => {
  const keyword = filters.q.trim().toLowerCase()
  return providers.value.filter((provider) => {
    const matchKeyword = !keyword ||
      provider.name.toLowerCase().includes(keyword) ||
      provider.provider_type.toLowerCase().includes(keyword) ||
      (provider.default_model || '').toLowerCase().includes(keyword)
    const matchStatus = !filters.status || provider.status === filters.status
    return matchKeyword && matchStatus
  })
}

const loadProviderTypes = async () => {
  const { data } = await http.get('/model-providers/provider-types')
  providerTypes.value = data.items || []
}

const loadProviders = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/model-providers')
    providers.value = data.items || []
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.q = ''
  filters.status = ''
}

const resetForm = () => {
  editingId.value = ''
  availableModels.value = []
  Object.assign(form, {
    name: '',
    provider_type: 'openai_compatible',
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    default_model: '',
    is_default: false,
    status: 'active'
  })
}

const onProviderTypeChange = () => {
  const type = providerTypes.value.find((item) => item.value === form.provider_type)
  if (type?.default_base_url) {
    form.base_url = type.default_base_url
  }
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (provider) => {
  editingId.value = provider.id
  availableModels.value = provider.default_model ? [provider.default_model] : []
  Object.assign(form, {
    name: provider.name,
    provider_type: provider.provider_type,
    base_url: provider.base_url,
    api_key: '',
    default_model: provider.default_model || '',
    is_default: provider.is_default,
    status: provider.status
  })
  dialogVisible.value = true
}

const buildPayload = () => {
  const payload = {
    name: form.name.trim(),
    provider_type: form.provider_type,
    base_url: form.base_url.trim(),
    default_model: form.default_model.trim() || null,
    is_default: form.is_default,
    status: form.status
  }
  if (form.api_key.trim()) {
    payload.api_key = form.api_key.trim()
  }
  return payload
}

const save = async () => {
  if (saving.value) return
  if (!form.name.trim() || !form.base_url.trim()) {
    ElMessage.warning('请填写配置名称和接口地址')
    return
  }
  if (!editingId.value && !form.api_key.trim()) {
    ElMessage.warning('新增配置需要填写 API Key')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await http.patch(`/model-providers/${editingId.value}`, buildPayload())
    } else {
      await http.post('/model-providers', buildPayload())
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await loadProviders()
  } finally {
    saving.value = false
  }
}

const remove = async (provider) => {
  if (deletingId.value) return
  await ElMessageBox.confirm(`确认删除模型配置「${provider.name}」吗？`, '删除模型配置', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning'
  })
  deletingId.value = provider.id
  try {
    await http.delete(`/model-providers/${provider.id}`)
    ElMessage.success('已删除')
    await loadProviders()
  } finally {
    deletingId.value = ''
  }
}

const setDefault = async (provider) => {
  if (!canUpdate()) return
  await http.post(`/model-providers/${provider.id}/default`)
  ElMessage.success('已设为默认模型服务')
  await loadProviders()
}

const testProvider = async (provider) => {
  if (testingId.value) return
  testingId.value = provider.id
  try {
    const { data } = await http.post(`/model-providers/${provider.id}/test`)
    ElMessage.success(`连接成功，可用模型 ${data.model_count} 个`)
  } finally {
    testingId.value = ''
  }
}

const fetchModelsForRow = async (provider) => {
  if (fetchingId.value) return
  fetchingId.value = provider.id
  try {
    const { data } = await http.get(`/model-providers/${provider.id}/models`)
    ElMessage.success(`已获取 ${data.items.length} 个模型`)
  } finally {
    fetchingId.value = ''
  }
}

const fetchModelsForForm = async () => {
  if (!editingId.value) {
    ElMessage.warning('请先保存配置后再获取模型')
    return
  }
  fetchingId.value = editingId.value
  try {
    const { data } = await http.get(`/model-providers/${editingId.value}/models`)
    availableModels.value = data.items || []
    if (!form.default_model && availableModels.value.length) {
      form.default_model = availableModels.value[0]
    }
    ElMessage.success(`已获取 ${availableModels.value.length} 个模型`)
  } finally {
    fetchingId.value = ''
  }
}

onMounted(async () => {
  await Promise.all([loadProviderTypes(), loadProviders()])
})
</script>

<template>
  <section class="page">
    <div class="list-header">
      <div class="filter-bar">
        <div class="filter-item">
          <label>关键字</label>
          <el-input v-model="filters.q" clearable placeholder="搜索配置名称 / 类型 / 模型" class="filter-input wide" :prefix-icon="Search" />
        </div>
        <div class="filter-item">
          <label>状态</label>
          <el-select v-model="filters.status" clearable placeholder="配置状态" class="filter-input">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </div>
        <div class="filter-actions">
          <el-button type="primary" :icon="Search">搜索</el-button>
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
    </div>

    <div class="list-actions-row">
      <div class="toolbar">
        <el-button :icon="Refresh" @click="loadProviders">刷新</el-button>
        <el-button v-if="canCreate()" type="primary" :icon="Plus" @click="openCreate">新增模型配置</el-button>
      </div>
    </div>

    <el-card shadow="never" class="table-card" v-loading="loading">
      <el-table :data="filteredProviders()" row-key="id">
        <el-table-column prop="name" label="配置名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="接口类型" width="130" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ providerTypeLabel(row.provider_type) }}</template>
        </el-table-column>
        <el-table-column prop="base_url" label="接口地址" min-width="260" show-overflow-tooltip />
        <el-table-column label="默认模型" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.default_model || '-' }}</template>
        </el-table-column>
        <el-table-column label="Key" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.has_api_key ? 'success' : 'info'" effect="plain">{{ row.has_api_key ? '已配置' : '未配置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="primary" effect="plain">默认</el-tag>
            <el-button v-else-if="canUpdate()" link type="primary" :icon="Star" @click="setDefault(row)">设默认</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Check" :loading="testingId === row.id" :disabled="Boolean(testingId)" @click="testProvider(row)">测试</el-button>
            <el-button link type="primary" :icon="Refresh" :loading="fetchingId === row.id" :disabled="Boolean(fetchingId)" @click="fetchModelsForRow(row)">模型</el-button>
            <el-button v-if="canUpdate()" link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete()" link type="danger" :icon="Delete" :loading="deletingId === row.id" :disabled="Boolean(deletingId)" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模型配置' : '新增模型配置'" width="680px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="配置名称" required>
          <el-input v-model="form.name" placeholder="请输入配置名称" />
        </el-form-item>
        <el-form-item label="接口类型" required>
          <el-select v-model="form.provider_type" class="full-field" @change="onProviderTypeChange">
            <el-option v-for="item in providerTypes" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口地址" required>
          <el-input v-model="form.base_url" placeholder="例如 https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item :label="editingId ? 'API Key（留空表示不修改）' : 'API Key'" :required="!editingId">
          <el-input v-model="form.api_key" type="password" show-password placeholder="请输入你自己的模型服务 API Key" />
        </el-form-item>
        <el-form-item label="默认模型">
          <div class="model-select-row">
            <el-select v-model="form.default_model" filterable allow-create clearable placeholder="填写或选择模型" class="full-field">
              <el-option v-for="model in availableModels" :key="model" :label="model" :value="model" />
            </el-select>
            <el-button :icon="Refresh" :loading="fetchingId === editingId" :disabled="!editingId" @click="fetchModelsForForm">获取模型</el-button>
          </div>
        </el-form-item>
        <el-form-item label="状态" required>
          <el-select v-model="form.status" class="full-field">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.is_default">设为默认模型服务</el-checkbox>
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

.model-select-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}
</style>
