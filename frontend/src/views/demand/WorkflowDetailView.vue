<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ArrowLeft, ChatRound, Check, CircleCheck, Close, CopyDocument, Document, EditPen, Folder, Refresh, View, Warning } from '@element-plus/icons-vue'
import DOMPurify from 'dompurify'
import { ElMessage, ElMessageBox } from 'element-plus'
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
import { useRoute, useRouter } from 'vue-router'
import 'highlight.js/styles/github.css'

import { http } from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'
import agentAvatar from '../../assets/images/agent-avatar.png'
import userAvatar from '../../assets/images/user-avatar.png'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const demand = ref(null)
const workflow = ref(null)
const stageSession = ref(null)
const workspace = ref(null)
const workspaceFiles = ref([])
const currentFilePath = ref('')
const selectedFilePath = ref('')
const gateChecks = ref([])
const localProjects = ref([])
const bridgeClients = ref([])
const bridgeCommands = ref([])
const codeContexts = ref([])
const loading = ref(false)
const blockingId = ref('')
const bridgeClientDialogVisible = ref(false)
const bridgeClientSaving = ref(false)
const bridgeClientSaved = ref(false)
const bridgeCommandDialogVisible = ref(false)
const bridgeCommandSaving = ref(false)
const codeContextScanning = ref(false)
const codeContextConfirmDialogVisible = ref(false)
const codeContextConfirming = ref(false)
const codeContextIgnoring = ref(false)
const bridgeLogDialogVisible = ref(false)
const selectedBridgeCommand = ref(null)
const pendingCodeContextScan = ref(null)
const selectedCodeContextProjectKeys = ref([])
const messageContent = ref('')
const messageSending = ref(false)
const stageCompleting = ref(false)
const fileSaving = ref(false)
const suppressAutoSave = ref(false)
const lastSavedFileContent = ref('')
const autoSaveTimer = ref(null)
const codeContextScanPollTimer = ref(null)
const codeContextScanPollCount = ref(0)
const workspaceRef = ref(null)
const messageListRef = ref(null)
const explorerWidth = ref(370)
const previewWidth = ref(620)
const codeContextHeight = ref(300)
const previewMode = ref('edit')
const chatVisible = ref(true)

const stageDraftForm = ref({
  artifact_title: '',
  artifact_type: 'prd',
  artifact_content: ''
})

const bridgeClientForm = ref({
  client_name: '',
  client_key: '',
  metadata: ''
})

const bridgeCommandForm = ref({
  local_project_id: null,
  command_type: 'shell',
  command_text: ''
})

const bridgeStartCommand = computed(() => {
  const origin = window.location.origin.replace(':5173', ':8765')
  const clientKey = bridgeClientForm.value.client_key || '<客户端标识>'
  return `npx --registry https://registry.npmjs.org/ @opendevflow/bridge --server ${origin} --client-key ${clientKey} --root <本地代码根目录>`
})

const defaultBridgeClientKey = () => {
  const username = String(auth.user?.username || '').trim().toLowerCase()
  const normalized = username
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized ? `bridge-${normalized}` : `bridge-${Date.now()}`
}

const copyBridgeStartCommand = async () => {
  if (!bridgeClientSaved.value) {
    ElMessage.warning('请先保存 Bridge 客户端')
    return
  }
  try {
    await navigator.clipboard.writeText(bridgeStartCommand.value)
    ElMessage.success('启动命令已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制命令')
  }
}

const updateStageDraftForm = async (patch, options = {}) => {
  suppressAutoSave.value = true
  stageDraftForm.value = {
    ...stageDraftForm.value,
    ...patch
  }
  if (options.markSaved) {
    lastSavedFileContent.value = stageDraftForm.value.artifact_content || ''
  }
  await nextTick()
  suppressAutoSave.value = false
}

const canViewWorkflow = computed(() => auth.hasPermission('workflow:view'))
const canBlockWorkflow = computed(() => auth.hasPermission('workflow:block'))
const canViewStageSession = computed(() => auth.hasPermission('stage_session:view'))
const canMessageStageSession = computed(() => auth.hasPermission('stage_session:message'))
const canCompleteStageSession = computed(() => auth.hasPermission('stage_session:complete'))
const canViewWorkspace = computed(() => auth.hasPermission('workspace:view'))
const canUpdateWorkspaceFile = computed(() => auth.hasPermission('workspace:file:update'))
const canViewStageGate = computed(() => auth.hasPermission('stage_gate:view'))
const canCheckStageGate = computed(() => auth.hasPermission('stage_gate:check'))
const canViewLocalProject = computed(() => auth.hasPermission('local_project:view'))
const canViewLocalBridge = computed(() => auth.hasPermission('local_bridge:view'))
const canManageLocalBridge = computed(() => auth.hasPermission('local_bridge:manage'))
const canCreateBridgeCommand = computed(() => auth.hasPermission('local_bridge:command'))
const canViewCodeContext = computed(() => auth.hasPermission('code_context:view'))
const canCreateCodeContext = computed(() => auth.hasPermission('code_context:create'))
const currentCodeContext = computed(() => codeContexts.value.find((item) => item.is_current) || codeContexts.value[0] || null)
const onlineBridgeClient = computed(() => bridgeClients.value.find((item) => item.status === 'online') || null)

const workspaceTree = computed(() => {
  const root = []
  const nodeByPath = new Map()
  const ensureDir = (parts) => {
    let collection = root
    let currentPath = ''
    for (const part of parts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part
      let node = nodeByPath.get(currentPath)
      if (!node) {
        node = { id: currentPath, label: part, path: currentPath, type: 'dir', children: [] }
        nodeByPath.set(currentPath, node)
        collection.push(node)
      }
      collection = node.children
    }
    return collection
  }
  workspaceFiles.value.forEach((file) => {
    const parts = file.path.split('/')
    const name = parts.pop()
    const collection = ensureDir(parts)
    collection.push({ id: file.path, label: name, path: file.path, type: 'file', size: file.size })
  })
  const sortNodes = (items) => {
    items.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1
      return a.label.localeCompare(b.label)
    })
    items.forEach((item) => {
      if (item.children?.length) sortNodes(item.children)
    })
  }
  sortNodes(root)
  return root
})

const workspaceGridStyle = computed(() => {
  if (selectedFilePath.value) {
    if (!chatVisible.value) {
      return {
        gridTemplateColumns: `${explorerWidth.value}px 4px minmax(360px, 1fr)`
      }
    }
    return {
      gridTemplateColumns: `${explorerWidth.value}px 4px ${previewWidth.value}px 4px minmax(360px, 1fr)`
    }
  }
  return {
    gridTemplateColumns: `${explorerWidth.value}px 4px minmax(360px, 1fr)`
  }
})

const isMarkdownFile = computed(() => /\.(md|markdown)$/i.test(selectedFilePath.value || ''))

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

const escapeHtml = (value) => String(value || '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;')

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
    const langClass = lang ? ` language-${lang}` : ''
    return `<pre><code class="hljs${langClass}">${highlighted}</code></pre>`
  }
})

const renderMarkdown = (content) => DOMPurify.sanitize(markdown.render(String(content || '')), {
  USE_PROFILES: { html: true }
})

const scrollMessagesToBottom = async () => {
  await nextTick()
  const list = messageListRef.value
  if (!list) return
  list.scrollTop = list.scrollHeight
}

const renderedPreview = computed(() => {
  const content = stageDraftForm.value.artifact_content || ''
  if (!isMarkdownFile.value) {
    return `<pre>${escapeHtml(content)}</pre>`
  }
  return renderMarkdown(content)
})
const workflowStatusLabel = (status) => ({
  running: '运行中',
  blocked: '阻塞',
  done: '已完成',
  archived: '已归档'
}[status] || status)

const workflowTypeLabel = (type) => ({
  full: '标准需求',
  hotfix: '缺陷修复',
  tweak: '小需求/小优化'
}[type] || type)

const artifactTypeLabel = (type) => ({
  prd: 'PRD',
  user_story: '用户故事',
  acceptance_criteria: '验收标准',
  openspec_proposal: 'OpenSpec Proposal',
  openspec_design: 'OpenSpec Design',
  openspec_tasks: 'OpenSpec Tasks',
  dev_plan: '开发计划',
  test_plan: '测试计划',
  acceptance_report: '验收结论',
  delivery_summary: '交付总结',
  other: '其他'
}[type] || type)

const artifactTypeByStage = (stageKey) => ({
  demand_planning: 'prd',
  product_design: 'openspec_design',
  development: 'dev_plan',
  acceptance_review: 'test_plan',
  issue_confirm: 'acceptance_criteria',
  fix_implementation: 'dev_plan',
  regression_verify: 'test_plan',
  change_confirm: 'acceptance_criteria',
  self_test: 'dev_plan',
  delivery_archive: 'delivery_summary'
}[stageKey] || 'other')
const currentStage = computed(() => {
  const item = workflow.value
  if (!item) return null
  if (item.status === 'done' || item.status === 'archived') {
    return item.stages?.[item.stages.length - 1] || null
  }
  return item.stages?.find((stage) => ['current', 'blocked'].includes(stage.status))
    || item.stages?.find((stage) => stage.stage_key === item.current_stage)
    || item.stages?.[0]
})

const isLastStage = computed(() => {
  const stages = workflow.value?.stages || []
  return Boolean(currentStage.value && stages[stages.length - 1]?.id === currentStage.value.id)
})

const quickCommands = computed(() => {
  const stageKey = currentStage.value?.stage_key
  const commandMap = {
    demand_planning: [
      { command: '/discover', label: '需求澄清', prompt: '/discover 请基于当前需求上下文进行需求澄清，输出背景、目标、范围、风险和待确认问题。' },
      { command: '/prd', label: '生成 PRD', prompt: '/prd 请基于已澄清内容生成 PRD、用户故事和验收标准。' }
    ],
    product_design: [
      { command: '/design', label: '产品设计', prompt: '/design 请输出页面、字段、状态、权限和交互设计。' },
      { command: '/spec', label: 'OpenSpec', prompt: '/spec 请生成 proposal、design、tasks 和 spec delta。' }
    ],
    development: [
      { command: '/plan', label: '开发计划', prompt: '/plan 请生成文件级、步骤级、可验证的开发计划。' },
      { command: '/build', label: '开发实施', prompt: '/build 请按已批准计划推进代码实施，并记录验证结果。' }
    ],
    acceptance_review: [
      { command: '/review', label: '代码审查', prompt: '/review 请审查本次实现的正确性、回归风险、权限数据问题和测试缺口。' },
      { command: '/qa', label: 'QA 验收', prompt: '/qa 请基于 PRD、验收标准和实现结果生成测试计划、用例和验收结论。' }
    ],
    delivery_archive: [
      { command: '/ship', label: '交付归档', prompt: '/ship 请汇总需求、设计、实施、审查、QA、风险和后续事项，生成交付归档结论。' }
    ],
    issue_confirm: [
      { command: '/discover', label: '问题确认', prompt: '/discover 请澄清缺陷现象、影响范围、复现路径、期望行为和修复边界。' }
    ],
    fix_implementation: [
      { command: '/plan', label: '修复计划', prompt: '/plan 请生成缺陷修复的定位、修改和验证计划。' },
      { command: '/build', label: '修复实施', prompt: '/build 请按修复计划推进代码修改，并记录自测和验证结果。' }
    ],
    regression_verify: [
      { command: '/review', label: '修复审查', prompt: '/review 请审查缺陷修复是否完整、是否引入回归风险。' },
      { command: '/qa', label: '回归验证', prompt: '/qa 请生成并执行回归验证用例，输出缺陷关闭结论。' }
    ],
    change_confirm: [
      { command: '/prd', label: '变更确认', prompt: '/prd 请整理小需求/小优化的目标、范围、验收标准和非目标。' }
    ],
    self_test: [
      { command: '/build', label: '实施自测', prompt: '/build 请推进轻量实施和自测，并记录验证结果。' }
    ]
  }
  return [
    ...(commandMap[stageKey] || []),
    { command: '/next', label: '下一步', prompt: '/next 请检查当前阶段 gate 和已有产物，建议下一步动作。' }
  ]
})

const latestGateCheck = computed(() => gateChecks.value[0] || null)

const gateStatusLabel = (status) => ({
  passed: '已通过',
  failed: '待完善',
  pending: '待校验'
}[status] || status || '未校验')

const gateStatusType = (status) => ({
  passed: 'success',
  failed: 'danger',
  pending: 'info'
}[status] || 'info')
const loadDemand = async () => {
  const { data } = await http.get(`/demands/${route.params.demandId}`)
  demand.value = data
}

const loadWorkflow = async () => {
  if (!canViewWorkflow.value) return
  const { data } = await http.get(`/demands/${route.params.demandId}/workflows`)
  workflow.value = (data.items || []).find((item) => item.id === route.params.workflowId) || null
  if (!workflow.value) {
    ElMessage.error('工作流不存在')
    router.push(`/demands/${route.params.demandId}`)
  }
}

const loadStageSession = async () => {
  if (!canViewStageSession.value) return
  const { data } = await http.get(`/demands/${route.params.demandId}/workflows/${route.params.workflowId}/current-stage-session`)
  stageSession.value = data
  await updateStageDraftForm({
    artifact_title: data.draft_title || `${currentStage.value?.stage_name || '当前阶段'} - 阶段产物`,
    artifact_type: data.draft_type || artifactTypeByStage(currentStage.value?.stage_key),
    artifact_content: data.draft_content || ''
  })
  await scrollMessagesToBottom()
}

const loadStageExecutionState = async () => {
  if (!stageSession.value?.id) return
  const requests = []
  if (canViewStageGate.value) {
    requests.push(http.get(`/demands/stage-sessions/${stageSession.value.id}/gate-checks`).then(({ data }) => {
      gateChecks.value = data.items || []
    }))
  }
  await Promise.all(requests)
}

const checkStageGate = async () => {
  if (!stageSession.value?.id || !canCheckStageGate.value) return
  const { data } = await http.post(`/demands/stage-sessions/${stageSession.value.id}/gate-checks`)
  gateChecks.value = [data, ...gateChecks.value]
  const details = data.details || '暂无详细说明。'
  const detailItems = details
    .split('\n')
    .map((item) => item.trim().replace(/^[-*]\s*/, ''))
    .filter(Boolean)
  const detailsHtml = detailItems.length
    ? `<ul>${detailItems.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    : `<p>${escapeHtml(details)}</p>`
  await ElMessageBox.alert(
    `<div class="gate-result-dialog">
      <p class="gate-result-summary">${data.summary || gateStatusLabel(data.status)}</p>
      <div class="gate-result-details">${detailsHtml}</div>
    </div>`,
    data.status === 'passed' ? '阶段检查已通过' : '阶段检查待完善',
    {
      confirmButtonText: '我知道了',
      dangerouslyUseHTMLString: true,
      customClass: 'gate-result-message-box',
      type: data.status === 'passed' ? 'success' : 'warning'
    }
  )
}

const loadWorkspace = async () => {
  if (!canViewWorkspace.value) return
  const [{ data: workspaceData }, { data: filesData }] = await Promise.all([
    http.get(`/demands/${route.params.demandId}/workspace`),
    http.get(`/demands/${route.params.demandId}/workspace/files`)
  ])
  workspace.value = workspaceData
  workspaceFiles.value = filesData.items || []
}

const loadLocalBridgeState = async () => {
  const requests = []
  if (canViewLocalProject.value) {
    requests.push(http.get(`/demands/${route.params.demandId}/local-projects`).then(({ data }) => {
      localProjects.value = data.items || []
    }))
  }
  if (canViewLocalBridge.value) {
    requests.push(http.get('/demands/local-bridge/clients').then(({ data }) => {
      bridgeClients.value = data.items || []
    }))
    requests.push(http.get(`/demands/${route.params.demandId}/local-bridge/commands`).then(({ data }) => {
      bridgeCommands.value = data.items || []
    }))
  }
  if (canViewCodeContext.value) {
    requests.push(http.get(`/demands/${route.params.demandId}/code-context`).then(({ data }) => {
      codeContexts.value = data.items || []
    }))
    requests.push(http.get(`/demands/${route.params.demandId}/code-context/scan-results/pending`).then(({ data }) => {
      pendingCodeContextScan.value = data.item || null
    }))
  }
  await Promise.all(requests)
  if (pendingCodeContextScan.value && !codeContextConfirmDialogVisible.value) {
    selectedCodeContextProjectKeys.value = []
    codeContextConfirmDialogVisible.value = true
  }
}

const stopCodeContextScanPolling = () => {
  if (codeContextScanPollTimer.value) {
    clearInterval(codeContextScanPollTimer.value)
    codeContextScanPollTimer.value = null
  }
  codeContextScanPollCount.value = 0
}

const startCodeContextScanPolling = () => {
  stopCodeContextScanPolling()
  codeContextScanPollTimer.value = setInterval(async () => {
    codeContextScanPollCount.value += 1
    await loadLocalBridgeState()
    const hasPendingScan = Boolean(pendingCodeContextScan.value)
    const hasRunningScan = bridgeCommands.value.some((item) => item.command_type === 'scan_workspace' && ['pending', 'running'].includes(item.status))
    if (hasPendingScan || (!hasRunningScan && codeContextScanPollCount.value >= 2) || codeContextScanPollCount.value >= 30) {
      stopCodeContextScanPolling()
      codeContextScanning.value = false
    }
  }, 2000)
}

const loadCurrentStageFile = async () => {
  if (!canViewWorkspace.value || !currentStage.value) return
  const { data } = await http.get(`/demands/${route.params.demandId}/workspace/stage-file`, {
    params: { stage: currentStage.value.stage_key }
  })
  currentFilePath.value = data.path
  if (selectedFilePath.value === data.path) {
    await updateStageDraftForm({
      artifact_title: data.path,
      artifact_type: artifactTypeByStage(currentStage.value.stage_key),
      artifact_content: data.content || stageDraftForm.value.artifact_content
    }, { markSaved: true })
  }
}

const loadWorkspaceFile = async (path) => {
  if (!canViewWorkspace.value || !path) return
  const { data } = await http.get(`/demands/${route.params.demandId}/workspace/file`, {
    params: { path }
  })
  selectedFilePath.value = data.path
  previewMode.value = 'edit'
  await updateStageDraftForm({
    artifact_title: data.path,
    artifact_type: data.path === currentFilePath.value ? artifactTypeByStage(currentStage.value?.stage_key) : 'other',
    artifact_content: data.content || ''
  }, { markSaved: true })
}

const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([loadDemand(), loadWorkflow()])
    await Promise.all([loadWorkspace(), loadStageSession(), loadLocalBridgeState()])
    await loadStageExecutionState()
    await loadCurrentStageFile()
  } finally {
    loading.value = false
  }
}

const openBridgeClientDialog = () => {
  bridgeClientForm.value = {
    client_name: '',
    client_key: defaultBridgeClientKey(),
    metadata: ''
  }
  bridgeClientSaved.value = false
  bridgeClientDialogVisible.value = true
}

const saveBridgeClient = async () => {
  if (bridgeClientSaving.value) return
  if (!bridgeClientForm.value.client_name.trim() || !bridgeClientForm.value.client_key.trim()) {
    ElMessage.warning('请填写客户端名称和标识')
    return
  }
  bridgeClientSaving.value = true
  try {
    await http.post('/demands/local-bridge/clients', bridgeClientForm.value)
    ElMessage.success('Bridge 客户端已登记')
    bridgeClientSaved.value = true
    await loadLocalBridgeState()
  } finally {
    bridgeClientSaving.value = false
  }
}

const scanCodeContext = async () => {
  if (codeContextScanning.value) return
  codeContextScanning.value = true
  try {
    await http.post(`/demands/${route.params.demandId}/code-context/scan`)
    ElMessage.success('已下发扫描任务，扫描完成后请确认本次需求相关项目')
    await loadLocalBridgeState()
    startCodeContextScanPolling()
  } catch (error) {
    codeContextScanning.value = false
    throw error
  }
}

const resetCodeContextConfirmState = () => {
  selectedCodeContextProjectKeys.value = []
  stopCodeContextScanPolling()
  codeContextScanning.value = false
}

const confirmCodeContextScan = async () => {
  if (!pendingCodeContextScan.value || codeContextConfirming.value) return
  if (!selectedCodeContextProjectKeys.value.length) {
    ElMessage.warning('请至少选择一个本次需求相关项目')
    return
  }
  codeContextConfirming.value = true
  try {
    await http.post(
      `/demands/${route.params.demandId}/code-context/scan-results/${pendingCodeContextScan.value.id}/confirm`,
      { project_keys: selectedCodeContextProjectKeys.value }
    )
    ElMessage.success('代码上下文已确认')
    pendingCodeContextScan.value = null
    codeContextConfirmDialogVisible.value = false
    resetCodeContextConfirmState()
    await loadLocalBridgeState()
  } finally {
    codeContextConfirming.value = false
  }
}

const ignoreCodeContextScan = async () => {
  if (!pendingCodeContextScan.value || codeContextIgnoring.value || codeContextConfirming.value) return
  codeContextIgnoring.value = true
  try {
    await http.post(`/demands/${route.params.demandId}/code-context/scan-results/${pendingCodeContextScan.value.id}/ignore`)
    ElMessage.info('已取消加入代码上下文')
    pendingCodeContextScan.value = null
    codeContextConfirmDialogVisible.value = false
    resetCodeContextConfirmState()
  } finally {
    codeContextIgnoring.value = false
  }
}

const closeCodeContextConfirmDialog = async (done) => {
  await ignoreCodeContextScan()
  done()
}

const openBridgeCommandDialog = (project) => {
  bridgeCommandForm.value = {
    local_project_id: project.id,
    command_type: 'shell',
    command_text: 'git status'
  }
  bridgeCommandDialogVisible.value = true
}

const createBridgeCommand = async () => {
  if (bridgeCommandSaving.value) return
  if (!bridgeCommandForm.value.local_project_id || !bridgeCommandForm.value.command_text.trim()) {
    ElMessage.warning('请选择本地项目并填写命令')
    return
  }
  bridgeCommandSaving.value = true
  try {
    await http.post(`/demands/${route.params.demandId}/local-bridge/commands`, {
      ...bridgeCommandForm.value,
      workflow_id: route.params.workflowId
    })
    ElMessage.success('命令已下发，等待 Bridge 执行')
    bridgeCommandDialogVisible.value = false
    await loadLocalBridgeState()
  } finally {
    bridgeCommandSaving.value = false
  }
}

const openBridgeLogDialog = (command) => {
  selectedBridgeCommand.value = command
  bridgeLogDialogVisible.value = true
}

const blockWorkflow = async () => {
  if (!workflow.value || blockingId.value) return
  let value = ''
  try {
    const result = await ElMessageBox.prompt('请输入阻塞原因', '阻塞工作流', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputErrorMessage: '请填写阻塞原因'
    })
    value = result.value
  } catch {
    return
  }
  blockingId.value = workflow.value.id
  try {
    const { data } = await http.post(`/demands/${workflow.value.id}/block`, { blocked_reason: value.trim() })
    ElMessage.success(data.message || '工作流已阻塞')
    await refreshData()
  } finally {
    blockingId.value = ''
  }
}

const resumeWorkflow = async () => {
  if (!workflow.value || blockingId.value) return
  blockingId.value = workflow.value.id
  try {
    const { data } = await http.post(`/demands/${workflow.value.id}/resume`)
    ElMessage.success(data.message || '工作流已恢复')
    await refreshData()
  } finally {
    blockingId.value = ''
  }
}

const sendStageMessage = async () => {
  if (!stageSession.value || messageSending.value) return
  const content = messageContent.value.trim()
  if (!content) {
    ElMessage.warning('请输入要发送的内容')
    return
  }
  messageSending.value = true
  const token = localStorage.getItem('token')
  const userMessage = {
    id: `user-${Date.now()}`,
    role: 'user',
    content,
    created_at: new Date().toISOString()
  }
  const assistantMessage = {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  }
  stageSession.value = {
    ...stageSession.value,
    messages: [...(stageSession.value.messages || []), userMessage, assistantMessage]
  }
  messageContent.value = ''
  await scrollMessagesToBottom()
  try {
    const response = await fetch(`/api/v1/demands/stage-sessions/${stageSession.value.id}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ content })
    })
    if (!response.ok || !response.body) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || 'AI 会话发送失败')
    }
    await readMessageStream(response.body, assistantMessage.id)
  } catch (err) {
    ElMessage.error(err?.message || 'AI 会话调用失败')
  } finally {
    messageSending.value = false
  }
}

const sendQuickCommand = async (item) => {
  if (!canMessageStageSession.value || !stageSession.value || messageSending.value) return
  messageContent.value = item.prompt
  await sendStageMessage()
}

const readMessageStream = async (body, assistantMessageId) => {
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const rawEvent of events) {
      handleStreamEvent(rawEvent, assistantMessageId)
    }
  }
  if (buffer.trim()) {
    handleStreamEvent(buffer, assistantMessageId)
  }
}

const handleStreamEvent = (rawEvent, assistantMessageId) => {
  const lines = rawEvent.split('\n')
  const event = lines.find((line) => line.startsWith('event:'))?.replace('event:', '').trim()
  const dataLine = lines.find((line) => line.startsWith('data:'))
  if (!event || !dataLine) return
  const payload = JSON.parse(dataLine.replace('data:', '').trim())
  if (event === 'delta') {
    appendAssistantDelta(assistantMessageId, payload.content || '')
    return
  }
  if (event === 'done') {
    stageSession.value = payload
    const nextDraftContent = payload.draft_content || ''
    const hasDraftUpdate = nextDraftContent && nextDraftContent !== stageDraftForm.value.artifact_content
    if (hasDraftUpdate) {
      updateStageDraftForm({
        artifact_title: payload.draft_title || stageDraftForm.value.artifact_title,
        artifact_type: payload.draft_type || stageDraftForm.value.artifact_type,
        artifact_content: nextDraftContent
      })
    }
    loadStageExecutionState()
    scrollMessagesToBottom()
    return
  }
  if (event === 'error') {
    appendAssistantDelta(assistantMessageId, `\n${payload.detail || 'AI 会话调用失败'}`)
    throw new Error(payload.detail || 'AI 会话调用失败')
  }
}

const appendAssistantDelta = (messageId, content) => {
  if (!content) return
  const messages = stageSession.value?.messages || []
  const target = messages.find((message) => message.id === messageId)
  if (target) {
    target.content += content
    scrollMessagesToBottom()
  }
}

const completeStageSession = async () => {
  if (!stageSession.value || stageCompleting.value) return
  const stages = workflow.value?.stages || []
  const currentIndex = stages.findIndex((stage) => stage.id === currentStage.value?.id)
  const nextStage = currentIndex >= 0 ? stages[currentIndex + 1] : null
  const currentStageName = currentStage.value?.stage_name || '当前阶段'
  const confirmMessage = isLastStage.value
    ? `确认将「${currentStageName}」标记为完成，并结束当前工作流？此操作会改变工作流状态，请确认当前阶段产物和验收结论已经确认。`
    : `确认将「${currentStageName}」标记为完成，并进入「${nextStage?.stage_name || '下一阶段'}」？此操作会改变工作流阶段，请确认当前阶段产物已经保存且通过审核。`
  try {
    await ElMessageBox.confirm(confirmMessage, isLastStage.value ? '确认结束工作流' : '确认推进阶段', {
      confirmButtonText: isLastStage.value ? '确认结束' : '确认进入下一步',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  const artifactTitle = stageDraftForm.value.artifact_title.trim() || selectedFilePath.value || currentFilePath.value || `${currentStage.value?.stage_name || '当前阶段'}产物`
  stageCompleting.value = true
  try {
    const { data } = await http.post(`/demands/stage-sessions/${stageSession.value.id}/complete`, {
      artifact_title: artifactTitle,
      artifact_type: stageDraftForm.value.artifact_type,
      artifact_content: stageDraftForm.value.artifact_content
    })
    ElMessage.success(data.message || '阶段已完成')
    await refreshData()
  } catch (error) {
    await loadStageExecutionState()
    ElMessage.error(error?.response?.data?.detail || '阶段完成失败')
  } finally {
    stageCompleting.value = false
  }
}

const saveCurrentStageFile = async () => {
  const path = selectedFilePath.value
  if (!path || fileSaving.value) return
  const content = stageDraftForm.value.artifact_content || ''
  if (content === lastSavedFileContent.value) return
  fileSaving.value = true
  try {
    await http.put(`/demands/${route.params.demandId}/workspace/file`, {
      content
    }, {
      params: { path }
    })
    lastSavedFileContent.value = content
    await loadWorkspace()
  } finally {
    fileSaving.value = false
  }
}

watch(
  () => stageDraftForm.value.artifact_content,
  () => {
    if (suppressAutoSave.value || !selectedFilePath.value || !canUpdateWorkspaceFile.value) return
    if (autoSaveTimer.value) {
      clearTimeout(autoSaveTimer.value)
    }
    autoSaveTimer.value = setTimeout(() => {
      saveCurrentStageFile()
    }, 800)
  }
)

onUnmounted(() => {
  if (autoSaveTimer.value) {
    clearTimeout(autoSaveTimer.value)
  }
  stopCodeContextScanPolling()
})

const handleFileNodeClick = (node) => {
  if (node.type !== 'file') return
  loadWorkspaceFile(node.path)
}

const closePreview = () => {
  selectedFilePath.value = ''
}

const togglePreviewMode = () => {
  previewMode.value = previewMode.value === 'edit' ? 'preview' : 'edit'
}

const openChat = () => {
  chatVisible.value = true
  scrollMessagesToBottom()
}

const closeChat = () => {
  chatVisible.value = false
}

const startResize = (target, event) => {
  event.preventDefault()
  if (target === 'context') {
    const startY = event.clientY
    const startHeight = codeContextHeight.value
    const explorerHeight = event.currentTarget.closest('.explorer-column')?.clientHeight || window.innerHeight
    const onMove = (moveEvent) => {
      const delta = startY - moveEvent.clientY
      const maxHeight = Math.max(260, explorerHeight - 180)
      codeContextHeight.value = Math.min(Math.max(startHeight + delta, 240), maxHeight)
    }
    const onUp = () => {
      document.body.classList.remove('is-row-resizing')
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    document.body.classList.add('is-row-resizing')
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return
  }
  const startX = event.clientX
  const startExplorerWidth = explorerWidth.value
  const startPreviewWidth = previewWidth.value
  const workspaceWidth = workspaceRef.value?.clientWidth || window.innerWidth
  const onMove = (moveEvent) => {
    const delta = moveEvent.clientX - startX
    if (target === 'explorer') {
      const maxWidth = selectedFilePath.value
        ? Math.max(240, workspaceWidth - previewWidth.value - 420)
        : Math.max(240, workspaceWidth - 420)
      explorerWidth.value = Math.min(Math.max(startExplorerWidth + delta, 370), maxWidth)
      return
    }
    const maxPreview = Math.max(360, workspaceWidth - explorerWidth.value - 420)
    previewWidth.value = Math.min(Math.max(startPreviewWidth + delta, 360), maxPreview)
  }
  const onUp = () => {
    document.body.classList.remove('is-column-resizing')
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  document.body.classList.add('is-column-resizing')
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

const goBack = () => {
  router.push(`/demands/${route.params.demandId}`)
}

onMounted(refreshData)
</script>

<template>
  <section class="workflow-detail-page" v-loading="loading">
    <template v-if="workflow">
      <header class="workspace-header">
        <div class="workspace-title">
          <el-button link :icon="ArrowLeft" @click="goBack">返回需求</el-button>
          <span class="workspace-name">{{ workflowTypeLabel(workflow.workflow_type) }}工作流</span>
          <el-tag v-if="currentStage" type="primary" effect="plain">{{ currentStage.stage_name }}</el-tag>
        </div>
        <div class="workspace-actions">
          <el-tag :type="workflow.status === 'blocked' ? 'danger' : 'success'" effect="plain">
            {{ workflowStatusLabel(workflow.status) }}
          </el-tag>
          <el-button :icon="Refresh" @click="refreshData">刷新</el-button>
          <el-button
            v-if="canBlockWorkflow && workflow.status === 'running'"
            :icon="Warning"
            type="warning"
            plain
            :loading="blockingId === workflow.id"
            :disabled="Boolean(blockingId || stageCompleting)"
            @click="blockWorkflow"
          >
            阻塞
          </el-button>
          <el-button
            v-if="canBlockWorkflow && workflow.status === 'blocked'"
            :icon="CircleCheck"
            type="success"
            plain
            :loading="blockingId === workflow.id"
            :disabled="Boolean(blockingId || stageCompleting)"
            @click="resumeWorkflow"
          >
            恢复
          </el-button>
        </div>
      </header>

      <main
        v-if="currentStage"
        ref="workspaceRef"
        class="workflow-workspace"
        :class="{ 'preview-open': selectedFilePath }"
        :style="workspaceGridStyle"
      >
        <aside class="explorer-column">
          <div class="explorer-header">
            <span>工作区文件</span>
            <el-button :icon="Refresh" text size="small" @click="loadWorkspace" />
          </div>
          <el-empty v-if="!canViewWorkspace" description="当前角色没有查看需求空间权限" :image-size="80" />
          <el-tree
            v-else
            class="workspace-tree"
            :data="workspaceTree"
            node-key="id"
            :expand-on-click-node="false"
            @node-click="handleFileNodeClick"
          >
            <template #default="{ node, data }">
              <div class="tree-node" :class="{ selected: data.path === selectedFilePath, file: data.type === 'file' }">
                <el-icon>
                  <component :is="data.type === 'dir' ? Folder : Document" />
                </el-icon>
                <span>{{ node.label }}</span>
              </div>
            </template>
          </el-tree>
          <div
            v-if="canViewLocalProject"
            class="row-resizer"
            @mousedown="startResize('context', $event)"
          />
          <div
            v-if="canViewLocalProject"
            class="local-project-panel"
            :style="{ height: `${codeContextHeight}px` }"
          >
            <div class="local-project-header">
              <div class="context-title">
                <span>代码上下文</span>
              </div>
              <div class="context-actions">
                <span v-if="onlineBridgeClient" class="bridge-connected-status">
                  <i />
                  已连接
                </span>
                <el-button
                  v-if="canManageLocalBridge && !onlineBridgeClient"
                  link
                  type="primary"
                  @click="openBridgeClientDialog"
                >
                  配置
                </el-button>
                <el-button
                  v-if="canCreateCodeContext"
                  link
                  type="primary"
                  :loading="codeContextScanning"
                  @click="scanCodeContext"
                >
                  扫描
                </el-button>
              </div>
            </div>
            <el-empty
              v-if="!localProjects.length"
              description="暂无项目，先扫描代码上下文"
              :image-size="32"
              class="compact-empty"
            />
            <div v-else class="local-project-list">
              <div v-for="project in localProjects" :key="project.id" class="local-project-item">
                <div class="local-project-main">
                  <strong>{{ project.project_name }}</strong>
                  <span>{{ project.project_key }} · {{ project.project_type }}</span>
                </div>
                <el-button
                  v-if="canCreateBridgeCommand"
                  text
                  type="primary"
                  size="small"
                  @click="openBridgeCommandDialog(project)"
                >
                  执行
                </el-button>
              </div>
            </div>
          </div>
          <div class="explorer-footer">
            <span class="explorer-file-count">{{ workspaceFiles.length }} files</span>
            <div class="explorer-footer-actions">
              <span v-if="currentCodeContext" class="code-context-meta">
                {{ currentCodeContext.project_count }} 个项目 · {{ formatDate(currentCodeContext.created_at) }}
              </span>
              <el-tag size="small" :type="currentCodeContext ? 'success' : 'info'" effect="plain">
                {{ currentCodeContext ? '已生成快照' : '暂无快照' }}
              </el-tag>
              <button
                v-if="canViewLocalBridge && bridgeCommands.length"
                class="bridge-command-link"
                type="button"
                @click="openBridgeLogDialog(bridgeCommands[0])"
              >
                {{ bridgeCommands.length }} 命令
              </button>
            </div>
          </div>
        </aside>
        <div class="column-resizer" @mousedown="startResize('explorer', $event)" />

        <aside v-if="selectedFilePath" class="preview-column">
          <div class="preview-header">
            <div class="preview-title">
              <Document class="preview-icon" />
              <span>{{ selectedFilePath }}</span>
              <el-tag size="small" effect="plain">{{ artifactTypeLabel(stageDraftForm.artifact_type) }}</el-tag>
            </div>
            <div class="preview-header-actions">
              <span v-if="canUpdateWorkspaceFile" class="autosave-status autosave-status-header">
                {{ fileSaving ? '自动保存中' : '已自动保存' }}
              </span>
              <el-tooltip v-if="!chatVisible" content="打开 AI 会话" placement="bottom">
                <button class="preview-mode-button" type="button" @click="openChat">
                  <el-icon><ChatRound /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="关闭文件预览" placement="bottom">
                <button class="chat-close-button" type="button" @click="closePreview">
                  <el-icon><Close /></el-icon>
                </button>
              </el-tooltip>
            </div>
          </div>

          <el-empty v-if="!canViewWorkspace" description="当前角色没有查看需求空间权限" :image-size="90" />
          <div v-else class="preview-body">
            <el-tooltip :content="previewMode === 'edit' ? '切换预览' : '切换编辑'" placement="left">
              <button class="preview-mode-button preview-mode-button-floating" type="button" @click="togglePreviewMode">
                <el-icon><component :is="previewMode === 'edit' ? View : EditPen" /></el-icon>
              </button>
            </el-tooltip>
            <el-input
              v-if="previewMode === 'edit'"
              v-model="stageDraftForm.artifact_content"
              class="draft-editor"
              type="textarea"
              resize="none"
              placeholder="当前阶段工作空间文件会在这里预览，也可以在确认前手工修订"
            />
            <div v-else class="markdown-preview" v-html="renderedPreview" />
          </div>

          <div class="preview-footer">
            <div class="preview-actions">
              <div class="stage-check-status">
                <span class="stage-check-label">阶段检查</span>
                <el-tag size="small" :type="gateStatusType(latestGateCheck?.status)" effect="plain">
                  {{ gateStatusLabel(latestGateCheck?.status) }}
                </el-tag>
                <el-button
                  v-if="canCheckStageGate"
                  link
                  type="primary"
                  :disabled="!stageSession || messageSending || stageCompleting"
                  @click="checkStageGate"
                >
                  手动检查
                </el-button>
              </div>
              <el-button
                v-if="canCompleteStageSession && workflow.status !== 'done' && workflow.status !== 'archived'"
                :icon="Check"
                type="primary"
                :loading="stageCompleting"
                :disabled="!stageSession || stageSession.status === 'completed'"
                @click="completeStageSession"
              >
                {{ stageCompleting ? '确认中' : (isLastStage ? '阶段完成，结束工作流' : '阶段完成，进入下一步') }}
              </el-button>
            </div>
          </div>
        </aside>
        <div v-if="selectedFilePath && chatVisible" class="column-resizer" @mousedown="startResize('preview', $event)" />

        <section v-if="chatVisible" class="chat-column">
          <div class="chat-header">
            <span>AI会话</span>
            <el-tooltip content="关闭 AI 会话" placement="bottom">
              <button class="chat-close-button" type="button" @click="closeChat">
                <el-icon><Close /></el-icon>
              </button>
            </el-tooltip>
          </div>
          <el-empty v-if="!canViewStageSession" description="当前角色没有查看阶段会话权限" :image-size="90" />
          <div v-else class="chat-panel">
            <div ref="messageListRef" class="message-list">
              <el-empty v-if="!stageSession?.messages?.length" description="当前阶段暂无会话" :image-size="90" />
              <div
                v-for="message in stageSession?.messages || []"
                :key="message.id"
                class="message-item"
                :class="`message-${message.role}`"
              >
                <img
                  v-if="message.role === 'assistant'"
                  :src="agentAvatar"
                  alt=""
                  class="message-avatar"
                />
                <div class="message-content">
                  <div class="message-role">{{ message.role === 'assistant' ? 'AI' : '我' }}</div>
                  <div
                    v-if="message.role === 'assistant'"
                    class="message-markdown"
                    v-html="renderMarkdown(message.content)"
                  />
                  <pre v-else>{{ message.content }}</pre>
                </div>
                <img
                  v-if="message.role === 'user'"
                  :src="userAvatar"
                  alt=""
                  class="message-avatar"
                />
              </div>
            </div>
            <div class="message-input">
              <div class="quick-command-bar">
                <button
                  v-for="item in quickCommands"
                  :key="item.command"
                  class="quick-command"
                  type="button"
                  :disabled="!canMessageStageSession || !stageSession || messageSending || workflow.status === 'done' || workflow.status === 'archived'"
                  @click="sendQuickCommand(item)"
                >
                  <span>{{ item.command }}</span>
                  <em>{{ item.label }}</em>
                </button>
              </div>
              <el-input
                v-model="messageContent"
                type="textarea"
                :rows="3"
                resize="none"
                placeholder="请输入消息"
                :disabled="!canMessageStageSession || workflow.status === 'done' || workflow.status === 'archived'"
                @keydown.enter.exact.prevent="sendStageMessage"
              />
              <div class="message-actions">
                <el-button
                  type="primary"
                  :loading="messageSending"
                  :disabled="!canMessageStageSession || !stageSession || workflow.status === 'done' || workflow.status === 'archived'"
                  @click="sendStageMessage"
                >
                  {{ messageSending ? '发送中' : '发送' }}
                </el-button>
              </div>
            </div>
          </div>
        </section>
      </main>
    </template>

    <el-dialog v-model="bridgeClientDialogVisible" title="登记本地 Bridge" width="560px">
      <el-form label-position="top">
        <el-form-item label="客户端名称" required>
          <el-input v-model="bridgeClientForm.client_name" placeholder="例如 我的 MacBook Pro" />
        </el-form-item>
        <el-form-item label="客户端标识" required>
          <el-input v-model="bridgeClientForm.client_key" placeholder="全局唯一，例如 muke-macbook" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="bridgeClientForm.metadata" type="textarea" :rows="3" placeholder="可选，记录本机用途或环境信息" />
        </el-form-item>
        <div class="bridge-command-tip">
          <div class="bridge-command-tip-header">
            <div>
              <strong>
                本机启动命令
                <el-tag size="small" :type="bridgeClientSaved ? 'success' : 'info'" effect="plain">
                  {{ bridgeClientSaved ? '已登记' : '待保存' }}
                </el-tag>
              </strong>
              <span>{{ bridgeClientSaved ? '在本机终端执行以下命令，并替换代码根目录。' : '请先保存客户端，保存成功后再复制命令启动 Bridge。' }}</span>
            </div>
            <el-button
              :icon="CopyDocument"
              text
              type="primary"
              :disabled="!bridgeClientSaved"
              @click="copyBridgeStartCommand"
            >
              复制
            </el-button>
          </div>
          <pre :class="{ muted: !bridgeClientSaved }">{{ bridgeStartCommand }}</pre>
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="bridgeClientSaving" @click="bridgeClientDialogVisible = false">{{ bridgeClientSaved ? '关闭' : '取消' }}</el-button>
        <el-button type="primary" :loading="bridgeClientSaving" @click="saveBridgeClient">
          {{ bridgeClientSaving ? '保存中' : bridgeClientSaved ? '重新保存' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="codeContextConfirmDialogVisible"
      title="确认代码上下文项目"
      width="760px"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
      :show-close="true"
      :before-close="closeCodeContextConfirmDialog"
    >
      <div v-if="pendingCodeContextScan" class="code-context-confirm">
        <el-alert
          title="请选择本次需求真正相关的项目。未选择的项目不会进入 AI 代码上下文，也不会绑定到当前需求。"
          type="warning"
          :closable="false"
          show-icon
        />
        <div class="code-context-confirm-meta">
          <span>扫描根目录：{{ pendingCodeContextScan.root_path || '-' }}</span>
          <span>识别项目：{{ pendingCodeContextScan.project_count }} 个</span>
        </div>
        <el-checkbox-group v-model="selectedCodeContextProjectKeys" class="code-context-project-options">
          <label
            v-for="project in pendingCodeContextScan.projects"
            :key="project.project_key"
            class="code-context-project-option"
          >
            <div class="code-context-project-main">
              <el-checkbox :value="project.project_key" />
              <strong>{{ project.project_name }}</strong>
              <span>{{ project.project_type }}</span>
            </div>
            <div class="code-context-project-path">
              <em>{{ project.local_path }}</em>
            </div>
          </label>
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button :loading="codeContextIgnoring" :disabled="codeContextConfirming" @click="ignoreCodeContextScan">
          {{ codeContextIgnoring ? '取消中' : '取消，不加入上下文' }}
        </el-button>
        <el-button type="primary" :loading="codeContextConfirming" @click="confirmCodeContextScan">
          {{ codeContextConfirming ? '确认中' : '确认并生成上下文' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="bridgeCommandDialogVisible" title="下发本地命令" width="620px">
      <el-form label-position="top">
        <el-form-item label="本地项目" required>
          <el-select v-model="bridgeCommandForm.local_project_id" class="full-field">
            <el-option
              v-for="project in localProjects"
              :key="project.id"
              :label="`${project.project_name}（${project.project_key}）`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="命令类型">
          <el-select v-model="bridgeCommandForm.command_type" class="full-field">
            <el-option label="Shell" value="shell" />
            <el-option label="测试" value="test" />
            <el-option label="构建" value="build" />
            <el-option label="Git" value="git" />
          </el-select>
        </el-form-item>
        <el-form-item label="命令" required>
          <el-input v-model="bridgeCommandForm.command_text" placeholder="例如 git status / npm test / pnpm build" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="bridgeCommandSaving" @click="bridgeCommandDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="bridgeCommandSaving" @click="createBridgeCommand">
          {{ bridgeCommandSaving ? '下发中' : '下发命令' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="bridgeLogDialogVisible" title="Bridge 命令日志" width="760px">
      <div v-if="selectedBridgeCommand" class="bridge-log-view">
        <div class="artifact-view-meta">
          <el-tag size="small" effect="plain">{{ selectedBridgeCommand.status }}</el-tag>
          <span>{{ selectedBridgeCommand.command_text }}</span>
        </div>
        <pre>{{ selectedBridgeCommand.logs || selectedBridgeCommand.output_summary || '暂无日志' }}</pre>
      </div>
    </el-dialog>

  </section>
</template>

<style scoped>
.workflow-detail-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  min-width: 0;
  margin: -20px;
  background: var(--el-bg-color);
}

.full-field {
  width: 100%;
}

.bridge-command-tip {
  margin-top: 4px;
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}

.bridge-command-tip-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.bridge-command-tip-header strong {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 650;
}

.bridge-command-tip-header :deep(.el-tag) {
  height: 18px;
  font-size: 10px;
}

.bridge-command-tip-header span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.bridge-command-tip pre {
  margin: 0;
  padding: 10px 12px;
  overflow: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-all;
}

.bridge-command-tip pre.muted {
  color: var(--el-text-color-placeholder);
}

.code-context-confirm {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.code-context-confirm-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.code-context-project-options {
  display: flex;
  max-height: 360px;
  flex-direction: column;
  gap: 8px;
  overflow: auto;
}

.code-context-project-option {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
  cursor: pointer;
}

.code-context-project-option:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-fill-color-lighter);
}

.code-context-project-main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.code-context-project-main :deep(.el-checkbox) {
  height: 20px;
  margin-right: 0;
}

.code-context-project-main strong {
  min-width: 0;
  overflow: hidden;
  flex: 0 1 auto;
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.code-context-project-main span {
  flex: 0 0 auto;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.code-context-project-path {
  padding-left: 28px;
}

.code-context-project-path em {
  display: block;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-style: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  padding: 0 12px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.workspace-title,
.workspace-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 0 0 auto;
}

.workspace-title {
  flex: 1;
}

.workspace-name {
  color: var(--el-text-color-primary);
  font-size: 15px;
  font-weight: 700;
}

.workflow-workspace {
  display: grid;
  flex: 1;
  min-height: 0;
  background: var(--el-bg-color);
}

.explorer-column,
.chat-column,
.preview-column {
  min-width: 0;
  min-height: 0;
}

.explorer-column {
  display: flex;
  flex-direction: column;
  background: #252526;
  color: #cccccc;
}

.column-resizer {
  width: 4px;
  min-width: 4px;
  background: var(--el-border-color-light);
  cursor: col-resize;
  transition: background 0.15s ease;
}

.column-resizer:hover {
  background: var(--el-color-primary);
}

:global(body.is-column-resizing) {
  cursor: col-resize;
  user-select: none;
}

:global(body.is-row-resizing) {
  cursor: row-resize;
  user-select: none;
}

.explorer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  padding: 0 8px 0 14px;
  color: #cccccc;
  font-size: 12px;
  letter-spacing: 0;
}

.explorer-header :deep(.el-button) {
  color: #cccccc;
}

.workspace-tree {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: transparent;
  color: #cccccc;
}

.row-resizer {
  flex: 0 0 5px;
  height: 5px;
  border-top: 1px solid #333333;
  border-bottom: 1px solid #333333;
  background: #2d2d2d;
  cursor: row-resize;
  transition: background 0.15s ease;
}

.row-resizer:hover {
  background: var(--el-color-primary);
}

.local-project-panel {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  min-height: 240px;
  padding: 8px 10px;
  overflow: hidden;
}

.local-project-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
  color: #cccccc;
  font-size: 12px;
  font-weight: 400;
}

.context-title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  white-space: nowrap;
}

.context-title > span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.context-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.context-actions :deep(.el-button) {
  min-width: 24px;
  padding: 0 1px;
  color: var(--el-color-primary);
  font-size: 11px;
  font-weight: 500;
}

.context-actions :deep(.el-button.is-loading) {
  min-width: 42px;
}

.context-actions :deep(.el-button:hover) {
  color: var(--el-color-primary-light-3);
}

.bridge-connected-status {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #8fbf7f;
  font-size: 11px;
  line-height: 1;
}

.bridge-connected-status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #67c23a;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.12);
}

.compact-empty {
  display: flex;
  min-height: 0;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
}

.compact-empty :deep(.el-empty__image) {
  opacity: 0.45;
}

.compact-empty :deep(.el-empty__description) {
  margin-top: 4px;
}

.compact-empty :deep(.el-empty__description p) {
  color: #7f858d;
  font-size: 11px;
  line-height: 1.4;
}

.code-context-meta {
  min-width: 0;
  flex: 0 1 auto;
  overflow: hidden;
  color: #7f858d;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.explorer-footer-actions {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;
  overflow: hidden;
}

.explorer-footer-actions :deep(.el-tag) {
  height: 18px;
  flex: 0 0 auto;
  padding: 0 5px;
  border-color: rgba(144, 147, 153, 0.24);
  background: rgba(144, 147, 153, 0.06);
  color: #8f969e;
  font-size: 10px;
  line-height: 16px;
}

.explorer-footer-actions :deep(.el-tag.el-tag--success) {
  border-color: rgba(103, 194, 58, 0.22);
  background: rgba(103, 194, 58, 0.07);
  color: #86b876;
}

.local-project-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.local-project-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid #333333;
  border-radius: 6px;
  background: #1f1f1f;
}

.local-project-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.local-project-main strong {
  overflow: hidden;
  color: #ffffff;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.local-project-main span {
  overflow: hidden;
  color: #9ca3af;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-tree::-webkit-scrollbar,
.local-project-panel::-webkit-scrollbar,
.message-list::-webkit-scrollbar,
.draft-editor :deep(.el-textarea__inner::-webkit-scrollbar),
.markdown-preview::-webkit-scrollbar {
  width: 3px;
  height: 3px;
}

.workspace-tree::-webkit-scrollbar-thumb,
.local-project-panel::-webkit-scrollbar-thumb,
.message-list::-webkit-scrollbar-thumb,
.draft-editor :deep(.el-textarea__inner::-webkit-scrollbar-thumb),
.markdown-preview::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: var(--el-color-primary);
}

.workspace-tree::-webkit-scrollbar-track,
.local-project-panel::-webkit-scrollbar-track,
.message-list::-webkit-scrollbar-track,
.draft-editor :deep(.el-textarea__inner::-webkit-scrollbar-track),
.markdown-preview::-webkit-scrollbar-track {
  background: transparent;
}

.workspace-tree :deep(.el-tree-node__content) {
  height: 28px;
  color: #cccccc;
  background: transparent;
}

.workspace-tree :deep(.el-tree-node__content:hover) {
  background: #2a2d2e;
}

.workspace-tree :deep(.el-tree-node__expand-icon) {
  color: #cccccc;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  width: 100%;
  height: 28px;
  color: #cccccc;
  font-size: 13px;
}

.tree-node .el-icon {
  flex: 0 0 auto;
  color: #dcb67a;
  font-size: 14px;
}

.tree-node.file .el-icon {
  color: #9cdcfe;
}

.tree-node span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-node.selected {
  color: #ffffff;
  font-weight: 650;
}

.explorer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 28px;
  min-height: 28px;
  padding: 0 12px;
  border-top: 1px solid #333333;
  color: #9ca3af;
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
}

.explorer-file-count {
  flex: 0 0 auto;
}

.bridge-command-link {
  flex: 0 0 auto;
  padding: 0;
  overflow: hidden;
  border: 0;
  background: transparent;
  color: #9cdcfe;
  cursor: pointer;
  font: inherit;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bridge-command-link:hover {
  color: #ffffff;
}

.chat-column {
  display: flex;
  flex-direction: column;
  background: var(--el-fill-color-extra-light);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 38px;
  padding: 0 12px 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-size: 13px;
  font-weight: 700;
}

.chat-close-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
}

.chat-close-button:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.message-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 16px;
  overflow: auto;
}

.message-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 88%;
}

.message-user {
  align-self: flex-end;
  justify-content: flex-end;
}

.message-assistant {
  align-self: flex-start;
}

.message-avatar {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 50%;
  background: var(--el-bg-color);
  object-fit: cover;
}

.message-content {
  min-width: 0;
  max-width: calc(100% - 40px);
}

.message-role {
  margin-bottom: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.message-user .message-role {
  text-align: right;
}

.message-item pre {
  margin: 0;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.message-user pre {
  border-color: #10b981;
  background: #10b981;
  color: #06291f;
}

.message-markdown {
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-size: 13px;
  line-height: 1.7;
  word-break: break-word;
}

.message-markdown :deep(h1),
.message-markdown :deep(h2),
.message-markdown :deep(h3),
.message-markdown :deep(h4),
.message-markdown :deep(h5),
.message-markdown :deep(h6) {
  margin: 10px 0 6px;
  color: var(--el-text-color-primary);
  font-weight: 700;
  line-height: 1.35;
}

.message-markdown :deep(h1) {
  font-size: 18px;
}

.message-markdown :deep(h2) {
  font-size: 16px;
}

.message-markdown :deep(h3) {
  font-size: 15px;
}

.message-markdown :deep(h4),
.message-markdown :deep(h5),
.message-markdown :deep(h6) {
  font-size: 14px;
}

.message-markdown :deep(p) {
  margin: 4px 0;
}

.message-markdown :deep(ul),
.message-markdown :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.message-markdown :deep(li) {
  margin: 3px 0;
}

.message-markdown :deep(blockquote) {
  margin: 8px 0;
  padding: 6px 10px;
  border-left: 3px solid var(--el-color-primary);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}

.message-markdown :deep(hr) {
  height: 1px;
  margin: 12px 0;
  border: 0;
  background: var(--el-border-color);
}

.message-markdown :deep(pre) {
  margin: 8px 0;
  padding: 0;
  overflow: auto;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}

.message-markdown :deep(pre .hljs) {
  padding: 10px;
  background: var(--el-fill-color-light);
}

.message-markdown :deep(code) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
}

.message-markdown :deep(p code),
.message-markdown :deep(li code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}

.message-input {
  padding: 12px 14px;
  border-top: 1px solid var(--el-border-color);
  background: var(--el-bg-color);
}

.quick-command-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.quick-command {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  background: var(--el-fill-color-extra-light);
  color: var(--el-text-color-primary);
  cursor: pointer;
  font-size: 12px;
}

.quick-command:hover:not(:disabled) {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.quick-command:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.quick-command span {
  color: var(--el-color-primary);
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
  font-weight: 700;
}

.quick-command em {
  font-style: normal;
}

.message-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.preview-column {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 50px;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  color: var(--el-text-color-primary);
  font-weight: 700;
}

.preview-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
}

.autosave-status-header {
  max-width: 100px;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-mode-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
}

.preview-mode-button:hover {
  color: var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.preview-mode-button-floating {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
}

.preview-title span {
  min-width: 0;
  flex: 0 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-title .el-tag {
  flex: 0 0 auto;
}

.preview-icon {
  width: 16px;
  height: 16px;
  color: var(--el-color-primary);
}

.preview-body {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 4px;
  background: var(--el-bg-color);
}

.draft-editor {
  flex: 1;
  min-height: 0;
}

.draft-editor :deep(.el-textarea__inner) {
  height: 100%;
  min-height: 100%;
  padding: 10px 38px 10px 10px;
  border-radius: 6px;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
  line-height: 1.7;
}

.markdown-preview {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 10px 38px 10px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
  font-size: 14px;
  line-height: 1.75;
}

.markdown-preview :deep(h1),
.markdown-preview :deep(h2),
.markdown-preview :deep(h3),
.markdown-preview :deep(h4),
.markdown-preview :deep(h5),
.markdown-preview :deep(h6) {
  margin: 18px 0 10px;
  color: var(--el-text-color-primary);
  font-weight: 700;
  line-height: 1.35;
}

.markdown-preview :deep(h1) {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
  font-size: 24px;
}

.markdown-preview :deep(h2) {
  font-size: 20px;
}

.markdown-preview :deep(h3) {
  font-size: 17px;
}

.markdown-preview :deep(p) {
  margin: 8px 0;
}

.markdown-preview :deep(ul) {
  margin: 8px 0;
  padding-left: 22px;
}

.markdown-preview :deep(li) {
  margin: 4px 0;
}

.markdown-preview :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--el-color-primary);
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
}

.markdown-preview :deep(hr) {
  height: 1px;
  margin: 16px 0;
  border: 0;
  background: var(--el-border-color);
}

.markdown-preview :deep(pre) {
  margin: 10px 0;
  padding: 0;
  overflow: auto;
  border-radius: 6px;
  background: var(--el-fill-color-light);
}

.markdown-preview :deep(pre .hljs) {
  padding: 12px;
  background: var(--el-fill-color-light);
}

.markdown-preview :deep(code) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    monospace;
}

.markdown-preview :deep(p code),
.markdown-preview :deep(li code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}

.preview-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-height: 56px;
  padding: 0 16px;
  border-top: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
}

.preview-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.stage-check-status {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.stage-check-label {
  white-space: nowrap;
}

.autosave-status {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.gate-result-dialog {
  color: var(--el-text-color-primary);
  font-size: 14px;
}

:global(.gate-result-message-box) {
  max-width: 560px;
}

:global(.gate-result-message-box .el-message-box__title) {
  font-size: 20px;
  line-height: 1.4;
}

:global(.gate-result-message-box .el-message-box__content) {
  padding-top: 8px;
}

:global(.gate-result-message-box .el-message-box__btns) {
  padding-top: 14px;
}

.gate-result-summary {
  margin: 0 0 12px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  font-weight: 600;
}

.gate-result-details {
  max-height: 320px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.65;
}

.gate-result-details ul {
  margin: 0;
  padding-left: 18px;
}

.gate-result-details li {
  margin: 4px 0;
  word-break: break-word;
}

.gate-result-details p {
  margin: 0;
}

.artifact-view-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.bridge-log-view pre {
  max-height: 460px;
  margin: 12px 0 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .workflow-detail-page {
    height: auto;
    min-height: calc(100vh - 56px);
    margin: -12px;
  }

  .workspace-header,
  .preview-footer {
    align-items: stretch;
    flex-direction: column;
    justify-content: flex-start;
    padding: 10px 12px;
  }

  .workspace-title,
  .workspace-actions,
  .preview-actions {
    flex-wrap: wrap;
  }

  .workflow-workspace {
    grid-template-columns: 1fr;
  }

  .workflow-workspace.preview-open {
    grid-template-columns: 1fr;
  }

  .workflow-workspace[style] {
    grid-template-columns: 1fr !important;
  }

  .column-resizer {
    display: none;
  }

  .explorer-column {
    min-height: 360px;
  }

  .chat-column {
    min-height: 560px;
    border-left: 0;
    border-bottom: 1px solid var(--el-border-color-light);
  }

  .preview-column {
    min-height: 620px;
  }

  .message-item {
    max-width: 100%;
  }
}
</style>
