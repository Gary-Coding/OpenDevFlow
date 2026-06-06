<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Connection, Document, Files, Refresh, Setting } from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdownLanguage from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import MarkdownIt from 'markdown-it'
import 'highlight.js/styles/github.css'

import { http } from '../../api/http'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdownLanguage)
hljs.registerLanguage('md', markdownLanguage)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('xml', xml)

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
  typographer: true,
  highlight(code, language) {
    const lang = language && hljs.getLanguage(language) ? language : ''
    const highlighted = lang
      ? hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
      : hljs.highlightAuto(code).value
    return `<pre><code class="hljs${lang ? ` language-${lang}` : ''}">${highlighted}</code></pre>`
  }
})

const loading = ref(false)
const detailLoading = ref(false)
const bindingsLoading = ref(false)
const templatesLoading = ref(false)
const skills = ref([])
const workflowTemplates = ref([])
const repositorySource = ref(null)
const selectedTemplateKey = ref('full')
const selectedStageKey = ref('demand_planning')
const selectedSkillKey = ref('')
const skillDetail = ref(null)
const bindings = ref([])
const activeTab = ref('document')
const sourceDialogVisible = ref(false)
const sourceSaving = ref(false)
const sourceForm = reactive({
  git_url: '',
  git_ref: 'main',
  root_path: 'skills',
  entry_file: 'SKILL.md'
})

const skillByKey = computed(() => Object.fromEntries(skills.value.map((skill) => [skill.key, skill])))
const selectedTemplate = computed(() => workflowTemplates.value.find((item) => item.key === selectedTemplateKey.value) || workflowTemplates.value[0] || null)
const currentStages = computed(() => (selectedTemplate.value?.stages || []).map((stage) => ({
  key: stage.stage_key,
  name: stage.stage_name,
  desc: stage.description
})))
const stageBindingMap = computed(() => currentStages.value.reduce((map, stage) => {
  map[stage.key] = bindings.value
    .filter((item) => item.stage_key === stage.key && (item.template_key || 'full') === selectedTemplateKey.value)
    .sort((a, b) => a.order_num - b.order_num)
  return map
}, {}))
const selectedStage = computed(() => currentStages.value.find((stage) => stage.key === selectedStageKey.value) || currentStages.value[0])
const selectedStageBindings = computed(() => stageBindingMap.value[selectedStageKey.value] || [])
const stageSkillsByStage = computed(() => currentStages.value.reduce((map, stage) => {
  const skillMap = new Map()
  for (const binding of stageBindingMap.value[stage.key] || []) {
    const current = skillMap.get(binding.skill_key)
    const template = {
      key: binding.template_key || 'full',
      is_default: binding.is_default,
      order_num: binding.order_num
    }
    if (current) {
      current.templates.push(template)
      current.is_default = current.is_default || binding.is_default
      current.order_num = Math.min(current.order_num, binding.order_num)
      continue
    }
    skillMap.set(binding.skill_key, {
      skill_key: binding.skill_key,
      stage_key: binding.stage_key,
      skill: binding.skill || skillByKey.value[binding.skill_key],
      templates: [template],
      is_default: binding.is_default,
      order_num: binding.order_num
    })
  }
  map[stage.key] = [...skillMap.values()].sort((a, b) => a.order_num - b.order_num || a.skill_key.localeCompare(b.skill_key))
  return map
}, {}))
const selectedStageSkills = computed(() => stageSkillsByStage.value[selectedStageKey.value] || [])
const selectedSkill = computed(() => skills.value.find((item) => item.key === selectedSkillKey.value) || null)
const selectedSkillBindings = computed(() => selectedStageBindings.value.filter((item) => item.skill_key === selectedSkillKey.value))
const stripFrontMatter = (content) => String(content || '').replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '')
const renderedContent = computed(() => DOMPurify.sanitize(markdown.render(stripFrontMatter(skillDetail.value?.entry_content || '')), {
  USE_PROFILES: { html: true }
}))

const templateLabel = (key) => ({
  full: '完整流程',
  hotfix: '缺陷修复',
  tweak: '小需求'
}[key] || key || '-')

const roleLabel = (role) => ({
  guide: '流程引导',
  product: '产品',
  design: '设计',
  architect: '架构',
  developer: '开发',
  reviewer: '评审',
  qa: '测试',
  delivery: '交付'
}[role] || role || '-')

const resetSourceForm = () => {
  Object.assign(sourceForm, {
    git_url: '',
    git_ref: 'main',
    root_path: 'skills',
    entry_file: 'SKILL.md'
  })
}

const loadRepositorySource = async () => {
  const { data } = await http.get('/skills/repository-source')
  repositorySource.value = data
}

const loadWorkflowTemplates = async () => {
  templatesLoading.value = true
  try {
    const { data } = await http.get('/demands/workflow-templates')
    workflowTemplates.value = data.items || []
    if (!workflowTemplates.value.some((item) => item.key === selectedTemplateKey.value)) {
      selectedTemplateKey.value = workflowTemplates.value[0]?.key || 'full'
    }
  } finally {
    templatesLoading.value = false
  }
}

const loadSkills = async () => {
  loading.value = true
  try {
    const { data } = await http.get('/skills')
    skills.value = data.items || []
  } finally {
    loading.value = false
  }
}

const loadBindings = async () => {
  bindingsLoading.value = true
  try {
    const { data } = await http.get('/skills/stage-bindings')
    bindings.value = data.items || []
  } finally {
    bindingsLoading.value = false
  }
}

const fallbackSkillDetail = (skillKey) => {
  const skill = skillByKey.value[skillKey]
  if (!skill) return null
  return {
    ...skill,
    entry_file: skill.entry_file || 'SKILL.md',
    entry_content: '',
    files: [],
    content_available: false,
    content_source: 'metadata'
  }
}

const loadSkillDetail = async (skillKey, file) => {
  if (!skillKey) return
  selectedSkillKey.value = skillKey
  if (!file) {
    skillDetail.value = fallbackSkillDetail(skillKey)
  }
  detailLoading.value = true
  try {
    const { data } = await http.get(`/skills/${skillKey}`, {
      params: file ? { file } : {}
    })
    skillDetail.value = data
  } catch {
    if (!skillDetail.value || skillDetail.value.key !== skillKey) {
      skillDetail.value = fallbackSkillDetail(skillKey)
    }
  } finally {
    detailLoading.value = false
  }
}

const openSourceDialog = () => {
  const source = repositorySource.value
  Object.assign(sourceForm, {
    git_url: source?.git_url || '',
    git_ref: source?.git_ref || 'main',
    root_path: source?.root_path || 'skills',
    entry_file: source?.entry_file || 'SKILL.md'
  })
  sourceDialogVisible.value = true
}

const saveRepositorySource = async () => {
  if (!sourceForm.git_url.trim()) {
    ElMessage.warning('请填写仓库地址')
    return
  }
  sourceSaving.value = true
  try {
    await http.patch('/skills/repository-source', {
      git_url: sourceForm.git_url.trim(),
      git_ref: sourceForm.git_ref.trim() || 'main',
      root_path: sourceForm.root_path.trim() || 'skills',
      entry_file: sourceForm.entry_file.trim() || 'SKILL.md'
    })
    ElMessage.success('Skill 仓库来源已更新')
    sourceDialogVisible.value = false
    await Promise.all([loadRepositorySource(), loadSkills()])
    await loadSkillDetail(selectedSkillKey.value)
  } finally {
    sourceSaving.value = false
  }
}

const selectStage = async (stageKey) => {
  selectedStageKey.value = stageKey
  activeTab.value = 'document'
  const defaultBinding = selectedStageBindings.value.find((item) => item.is_default) || selectedStageBindings.value[0]
  if (defaultBinding) {
    await loadSkillDetail(defaultBinding.skill_key)
  } else {
    selectedSkillKey.value = ''
    skillDetail.value = null
  }
}

const selectTemplate = async (templateKey) => {
  selectedTemplateKey.value = templateKey
  const firstStage = currentStages.value[0]
  if (firstStage) {
    await selectStage(firstStage.key)
  } else {
    selectedStageKey.value = ''
    selectedSkillKey.value = ''
    skillDetail.value = null
  }
}

const refresh = async () => {
  await Promise.all([loadWorkflowTemplates(), loadRepositorySource(), loadSkills(), loadBindings()])
  const stageStillExists = currentStages.value.some((stage) => stage.key === selectedStageKey.value)
  await selectStage(stageStillExists ? selectedStageKey.value : currentStages.value[0]?.key)
}

onMounted(refresh)
</script>

<template>
  <section class="page skill-page">
    <el-card shadow="never" class="template-switch-card page-card">
      <div class="template-switch">
        <el-segmented
          v-model="selectedTemplateKey"
          :options="workflowTemplates.map((item) => ({ label: item.name, value: item.key }))"
          :disabled="templatesLoading"
          @change="selectTemplate"
        />
        <div class="template-actions">
          <el-button :icon="Setting" size="small" @click="openSourceDialog">修改仓库来源</el-button>
          <el-button :icon="Refresh" :loading="loading || bindingsLoading || templatesLoading" size="small" @click="refresh">刷新</el-button>
        </div>
      </div>
    </el-card>

    <div class="skill-layout">
      <el-card shadow="never" class="skill-list-card page-card">
        <template #header>
          <div class="card-header">
            <span>工作流阶段</span>
            <div class="stage-header-actions">
              <el-tag size="small" effect="plain">{{ currentStages.length }}</el-tag>
            </div>
          </div>
        </template>
        <div v-loading="bindingsLoading || templatesLoading" class="stage-list">
          <button
            v-for="(stage, index) in currentStages"
            :key="stage.key"
            class="stage-item"
            :class="{ active: selectedStageKey === stage.key }"
            type="button"
            @click="selectStage(stage.key)"
          >
            <div class="stage-index">{{ index + 1 }}</div>
            <div class="stage-content">
              <div class="stage-name">{{ stage.name }}</div>
              <div class="stage-desc">{{ stage.desc }}</div>
              <div class="stage-meta">
                <el-tag size="small" effect="plain">{{ stageSkillsByStage[stage.key]?.length || 0 }} 个 Skill</el-tag>
              </div>
            </div>
          </button>
        </div>
      </el-card>

      <div class="skill-main">
        <el-card shadow="never" class="skill-detail-card page-card" v-loading="detailLoading">
          <template #header>
            <div class="card-header">
              <div class="detail-title">
                <el-icon><Document /></el-icon>
                <span>{{ selectedSkill?.name || 'Skill 详情' }}</span>
              </div>
              <el-tag v-if="selectedSkill" :type="selectedSkill.status === 'active' ? 'success' : 'info'" effect="plain">
                {{ selectedSkill.status === 'active' ? '启用' : '停用' }}
              </el-tag>
            </div>
          </template>

          <div class="bound-skill-list">
            <button
              v-for="item in selectedStageSkills"
              :key="item.skill_key"
              class="bound-skill-item"
              :class="{ active: selectedSkillKey === item.skill_key }"
              type="button"
              @click="loadSkillDetail(item.skill_key)"
            >
              <div class="bound-skill-main">
                <span>{{ item.skill?.name || item.skill_key }}</span>
                <em>{{ item.skill_key }}</em>
              </div>
              <div class="bound-skill-tags">
                <el-tag
                  v-for="template in item.templates"
                  :key="template.key"
                  size="small"
                  effect="plain"
                >
                  {{ selectedTemplate?.name || templateLabel(template.key) }}
                </el-tag>
                <el-tag v-if="item.is_default" size="small" type="success" effect="plain">默认</el-tag>
                <el-tag size="small" type="info" effect="plain">{{ roleLabel(item.skill?.role) }}</el-tag>
              </div>
            </button>
          </div>

          <el-empty v-if="!skillDetail" description="请选择 Skill" />
          <template v-else>
            <div class="skill-overview">
              <div class="overview-main">
                <div class="overview-name">
                  <span>{{ skillDetail.name }}</span>
                  <el-tag size="small" effect="plain">{{ skillDetail.key }}</el-tag>
                </div>
                <div class="overview-desc">{{ skillDetail.description || '-' }}</div>
              </div>
              <div class="overview-meta">
                <div class="meta-item">
                  <span>角色</span>
                  <strong>{{ roleLabel(skillDetail.role) }}</strong>
                </div>
                <div class="meta-item">
                  <span>阶段</span>
                  <strong>{{ selectedStage.name }}</strong>
                </div>
                <div class="meta-item">
                  <span>版本</span>
                  <strong>{{ skillDetail.version || '-' }}</strong>
                </div>
                <div class="meta-item">
                  <span>来源</span>
                  <strong>Git</strong>
                </div>
              </div>
            </div>

            <el-tabs v-model="activeTab" class="skill-tabs">
              <el-tab-pane name="document">
                <template #label>
                  <span class="tab-label"><el-icon><Document /></el-icon>说明文档</span>
                </template>
                <div class="doc-toolbar">
                  <span>{{ skillDetail.entry_file || 'SKILL.md' }}</span>
                  <span>{{ skillDetail.sub_path || '-' }}</span>
                </div>
                <el-empty v-if="!skillDetail.entry_content" description="暂无可预览内容" :image-size="80" />
                <div v-else class="markdown-body" v-html="renderedContent" />
              </el-tab-pane>

              <el-tab-pane name="files">
                <template #label>
                  <span class="tab-label"><el-icon><Files /></el-icon>GitHub 文件</span>
                </template>
                <div class="file-grid">
                  <el-empty v-if="!skillDetail.files?.length" description="GitHub 未读取到文件" :image-size="70" />
                  <button
                    v-for="file in skillDetail.files || []"
                    :key="file.path"
                    class="file-item"
                    type="button"
                    @click="loadSkillDetail(skillDetail.key, file.path); activeTab = 'document'"
                  >
                    <el-icon><Document /></el-icon>
                    <span>{{ file.path }}</span>
                    <em>{{ file.size }} B</em>
                  </button>
                </div>
              </el-tab-pane>

              <el-tab-pane name="bindings">
                <template #label>
                  <span class="tab-label"><el-icon><Connection /></el-icon>阶段绑定</span>
                </template>
                <el-table v-loading="bindingsLoading" :data="selectedSkillBindings" row-key="id">
                  <el-table-column label="模板" width="130" align="center">
                    <template #default>{{ selectedTemplate?.name || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="阶段" min-width="160" show-overflow-tooltip>
                    <template #default>{{ selectedStage.name }}</template>
                  </el-table-column>
                  <el-table-column label="默认" width="80" align="center">
                    <template #default="{ row }">
                      <el-tag v-if="row.is_default" size="small" type="success" effect="plain">默认</el-tag>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="order_num" label="顺序" width="80" align="center" />
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </template>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="sourceDialogVisible" title="修改 Skill 仓库来源" width="680px" @closed="resetSourceForm">
      <el-form label-width="96px">
        <el-form-item label="仓库地址" required>
          <el-input
            v-model="sourceForm.git_url"
            placeholder="支持 GitHub、Gitee、GitLab 仓库地址"
          />
        </el-form-item>
        <el-form-item label="分支/Tag" required>
          <el-input v-model="sourceForm.git_ref" placeholder="main" />
        </el-form-item>
        <el-form-item label="仓库根目录">
          <el-input v-model="sourceForm.root_path" placeholder="例如 skills" />
        </el-form-item>
        <el-form-item label="入口文件" required>
          <el-input v-model="sourceForm.entry_file" placeholder="SKILL.md" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="sourceSaving" @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceSaving" @click="saveRepositorySource">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.skill-page {
  min-width: 0;
}

.template-switch-card {
  margin-bottom: 12px;
}

.template-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.template-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.skill-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
}

.page-card {
  border-radius: 8px;
}

.card-header,
.detail-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.detail-title {
  justify-content: flex-start;
  font-weight: 700;
}

.stage-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.stage-list {
  display: grid;
  gap: 8px;
  max-height: calc(100vh - 240px);
  overflow: auto;
}

.stage-item,
.bound-skill-item,
.file-item {
  width: 100%;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  cursor: pointer;
  text-align: left;
}

.stage-item {
  display: flex;
  gap: 8px;
  padding: 10px;
}

.stage-item.active,
.bound-skill-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.stage-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 12px;
  font-weight: 700;
}

.stage-item.active .stage-index {
  background: var(--el-color-primary);
  color: #fff;
}

.stage-content {
  display: grid;
  flex: 1;
  gap: 5px;
  min-width: 0;
}

.stage-name {
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-desc {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.stage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.skill-main {
  min-width: 0;
}

.bound-skill-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.bound-skill-item {
  display: grid;
  gap: 8px;
  padding: 10px;
}

.bound-skill-main {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.bound-skill-main span {
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bound-skill-main em {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bound-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.file-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.file-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-item em {
  color: var(--el-text-color-secondary);
  font-style: normal;
}

.skill-overview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-extra-light);
}

.overview-main {
  min-width: 0;
}

.overview-name {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 16px;
  font-weight: 700;
}

.overview-desc {
  overflow: hidden;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.overview-meta {
  display: grid;
  grid-template-columns: repeat(4, auto);
  gap: 12px;
}

.meta-item {
  display: grid;
  gap: 3px;
  min-width: 72px;
}

.meta-item span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.meta-item strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.skill-tabs {
  min-width: 0;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.doc-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.file-grid {
  display: grid;
  gap: 8px;
  max-height: 56vh;
  overflow: auto;
}

.markdown-body {
  min-height: 360px;
  max-height: 60vh;
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.75;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: 16px 0 10px;
  line-height: 1.35;
}

.markdown-body :deep(p),
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
}

.markdown-body :deep(pre) {
  margin: 10px 0;
  padding: 0;
  overflow: auto;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}

.markdown-body :deep(pre .hljs) {
  padding: 12px;
  background: var(--el-fill-color-light);
}

.markdown-body :deep(code) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
}

@media (max-width: 1000px) {
  .skill-layout,
  .skill-overview {
    grid-template-columns: 1fr;
  }

  .overview-meta {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
