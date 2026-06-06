<script setup>
import { computed, onMounted, ref } from 'vue'
import { ArrowLeft, Plus, Refresh, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const demand = ref(null)
const loading = ref(false)
const workflowLoading = ref(false)
const workflowCreating = ref(false)
const workflowDialogVisible = ref(false)
const workflows = ref([])
const workflowTemplates = ref([])
const workflowForm = ref({ template_key: 'full' })

const canViewWorkflow = computed(() => auth.hasPermission('workflow:view'))
const canCreateWorkflow = computed(() => auth.hasPermission('workflow:create'))

const typeLabel = (type) => ({
  new_business: '新业务需求',
  new_project: '新项目需求',
  optimization: '优化需求',
  bugfix: '缺陷修复',
  refactor: '重构需求'
}[type] || type || '-')

const demandStatusLabel = (status) => ({
  active: '进行中',
  blocked: '阻塞',
  delivered: '已交付',
  archived: '已归档'
}[status] || status || '-')

const demandStatusType = (status) => ({
  active: 'primary',
  blocked: 'danger',
  delivered: 'success',
  archived: 'info'
}[status] || 'info')

const workflowStatusLabel = (status) => ({
  running: '运行中',
  blocked: '阻塞',
  done: '已完成',
  archived: '已归档'
}[status] || status)

const workflowStatusType = (status) => ({
  running: 'primary',
  blocked: 'danger',
  done: 'success',
  archived: 'info'
}[status] || 'info')

const workflowTypeLabel = (type) => ({
  full: '标准需求',
  hotfix: '缺陷修复',
  tweak: '小需求/小优化'
}[type] || type)

const currentStageName = (workflow) => {
  return workflow.stages?.find((stage) => stage.stage_key === workflow.current_stage)?.stage_name || workflow.current_stage || '-'
}

const completedStageCount = (workflow) => {
  const stages = workflow.stages || []
  if (!stages.length) return 0
  const done = stages.filter((stage) => ['passed', 'skipped'].includes(stage.status)).length
  return workflow.status === 'done' || workflow.status === 'archived' ? stages.length : done
}

const stageProgress = (workflow) => {
  const stages = workflow.stages || []
  if (!stages.length) return '0/0'
  return `${completedStageCount(workflow)}/${stages.length}`
}

const stageProgressPercentage = (workflow) => {
  const stages = workflow.stages || []
  if (!stages.length) return 0
  return Math.round((completedStageCount(workflow) / stages.length) * 100)
}

const stageStatusLabel = (status) => ({
  pending: '待处理',
  current: '当前',
  blocked: '阻塞',
  passed: '已完成',
  skipped: '已跳过'
}[status] || status || '-')

const stageStatusType = (status) => ({
  pending: 'info',
  current: 'primary',
  blocked: 'danger',
  passed: 'success',
  skipped: 'info'
}[status] || 'info')

const isCurrentStage = (workflow, stage) => {
  return stage.stage_key === workflow.current_stage || ['current', 'blocked'].includes(stage.status)
}

const defaultTemplateKey = () => {
  if (demand.value?.type === 'bugfix') return 'hotfix'
  if (['optimization', 'refactor'].includes(demand.value?.type)) return 'tweak'
  return 'full'
}

const loadDemand = async () => {
  loading.value = true
  try {
    const { data } = await http.get(`/demands/${route.params.id}`)
    demand.value = data
  } finally {
    loading.value = false
  }
}

const loadWorkflows = async () => {
  if (!canViewWorkflow.value) return
  workflowLoading.value = true
  try {
    const { data } = await http.get(`/demands/${route.params.id}/workflows`)
    workflows.value = data.items || []
  } finally {
    workflowLoading.value = false
  }
}

const loadWorkflowTemplates = async () => {
  if (!canViewWorkflow.value) return
  const { data } = await http.get('/demands/workflow-templates')
  workflowTemplates.value = data.items || []
}

const openWorkflowDialog = () => {
  workflowForm.value.template_key = defaultTemplateKey()
  workflowDialogVisible.value = true
}

const createWorkflow = async () => {
  if (workflowCreating.value) return
  workflowCreating.value = true
  try {
    await http.post(`/demands/${route.params.id}/workflows`, {
      template_key: workflowForm.value.template_key
    })
    ElMessage.success('新一轮工作流已创建')
    workflowDialogVisible.value = false
    await loadWorkflows()
  } finally {
    workflowCreating.value = false
  }
}

const goBack = () => {
  router.push('/demands')
}

const openWorkflow = (workflow) => {
  router.push(`/demands/${route.params.id}/workflows/${workflow.id}`)
}

onMounted(async () => {
  await loadDemand()
  await Promise.all([loadWorkflowTemplates(), loadWorkflows()])
})
</script>

<template>
  <section class="page demand-detail-page" v-loading="loading">
    <div class="detail-header">
      <div class="detail-title-area">
        <div class="detail-heading">
          <div class="detail-title-row">
            <h1>{{ demand?.title || '需求详情' }}</h1>
            <el-tag :type="demandStatusType(demand?.status)" effect="plain">{{ demandStatusLabel(demand?.status) }}</el-tag>
          </div>
          <div class="detail-meta">
            {{ typeLabel(demand?.type) }} / {{ demand?.department_name || '-' }} / 期望上线 {{ demand?.expected_live_at || '-' }}
          </div>
        </div>
      </div>
      <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
    </div>

    <el-card shadow="never" class="detail-card">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="需求标题" :span="2">{{ demand?.title }}</el-descriptions-item>
        <el-descriptions-item label="需求类型">{{ typeLabel(demand?.type) }}</el-descriptions-item>
        <el-descriptions-item label="归属开发组">{{ demand?.department_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="期望上线">{{ demand?.expected_live_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建人">{{ demand?.creator_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="需求描述" :span="2">{{ demand?.description }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" class="detail-card">
      <div class="list-actions-row">
        <div class="toolbar">
          <el-button :icon="Refresh" :loading="workflowLoading" @click="loadWorkflows">刷新</el-button>
          <el-button v-if="canCreateWorkflow" type="primary" :icon="Plus" :loading="workflowCreating" @click="openWorkflowDialog">
            新建一轮工作流
          </el-button>
        </div>
      </div>

      <el-empty v-if="!canViewWorkflow" description="当前角色没有查看工作流权限" />
      <el-empty
        v-else-if="!workflowLoading && !workflows.length"
        description="当前需求还没有工作流，请先新建一轮工作流并选择流程类型"
      >
        <el-button v-if="canCreateWorkflow" type="primary" :icon="Plus" @click="openWorkflowDialog">
          新建一轮工作流
        </el-button>
      </el-empty>
      <el-table v-else v-loading="workflowLoading" :data="workflows" row-key="id">
        <el-table-column type="expand" width="44">
          <template #default="{ row }">
            <div class="workflow-stage-detail">
              <div
                v-for="(stage, index) in row.stages || []"
                :key="stage.id || stage.stage_key"
                class="workflow-stage-item"
                :class="{ current: isCurrentStage(row, stage) }"
              >
                <div class="stage-index">{{ index + 1 }}</div>
                <div class="stage-content">
                  <div class="stage-name">{{ stage.stage_name }}</div>
                  <div class="stage-key">{{ stage.stage_key }}</div>
                </div>
                <el-tag size="small" :type="stageStatusType(stage.status)" effect="plain">
                  {{ stageStatusLabel(stage.status) }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="轮次" width="120" align="center">
          <template #default="{ $index }">第 {{ workflows.length - $index }} 轮</template>
        </el-table-column>
        <el-table-column label="流程类型" width="150" align="center">
          <template #default="{ row }">
            <el-tag effect="plain">{{ workflowTypeLabel(row.workflow_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="工作流进度" min-width="280">
          <template #default="{ row }">
            <div class="workflow-progress-cell">
              <div class="workflow-progress-meta">
                <span>当前：{{ currentStageName(row) }}</span>
                <span>{{ stageProgress(row) }}</span>
              </div>
              <el-progress
                :percentage="stageProgressPercentage(row)"
                :stroke-width="6"
                :show-text="false"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="workflowStatusType(row.status)" effect="light">{{ workflowStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="更新时间" width="180" align="center">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" :icon="View" @click="openWorkflow(row)">进入工作流</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="workflowDialogVisible" title="新建一轮工作流" width="680px">
      <el-form label-position="top">
        <el-form-item label="流程类型" required>
          <el-radio-group v-model="workflowForm.template_key" class="template-radio-group">
            <el-radio-button
              v-for="template in workflowTemplates"
              :key="template.key"
              :label="template.key"
            >
              {{ template.name }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <div
          v-for="template in workflowTemplates.filter((item) => item.key === workflowForm.template_key)"
          :key="template.key"
          class="template-preview"
        >
          <div class="template-description">{{ template.description }}</div>
          <el-steps :active="0" finish-status="success" align-center>
            <el-step v-for="stage in template.stages" :key="stage.stage_key" :title="stage.stage_name" />
          </el-steps>
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="workflowCreating" @click="workflowDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="workflowCreating" @click="createWorkflow">{{ workflowCreating ? '创建中' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.demand-detail-page {
  min-width: 0;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.detail-title-area {
  flex: 1;
  min-width: 0;
}

.detail-heading {
  min-width: 0;
}

.detail-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.detail-title-row h1 {
  margin: 0;
  color: #111827;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-meta {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-card {
  border-radius: 8px;
}

.template-radio-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.template-radio-group :deep(.el-radio-button__inner) {
  border-radius: 4px;
}

.template-preview {
  padding: 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.template-description {
  margin-bottom: 14px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.6;
}

.workflow-progress-cell {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.workflow-progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.workflow-progress-meta span:first-child {
  min-width: 0;
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-progress-meta span:last-child {
  flex: 0 0 auto;
  color: var(--el-text-color-secondary);
}

.workflow-stage-detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
  padding: 10px 16px 12px 64px;
  background: var(--el-fill-color-extra-light);
}

.workflow-stage-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
}

.workflow-stage-item.current {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.stage-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 700;
}

.workflow-stage-item.current .stage-index {
  background: var(--el-color-primary);
  color: #fff;
}

.stage-content {
  min-width: 0;
  flex: 1;
}

.stage-name {
  overflow: hidden;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-key {
  margin-top: 2px;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .detail-header,
  .detail-title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .detail-title-row h1,
  .detail-meta {
    white-space: normal;
  }

  .workflow-stage-detail {
    grid-template-columns: 1fr;
    padding-left: 16px;
  }
}
</style>
