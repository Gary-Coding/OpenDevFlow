#!/usr/bin/env node
import { spawn } from 'node:child_process'
import fs from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import WebSocket from 'ws'

const args = new Map()
for (let index = 2; index < process.argv.length; index += 2) {
  const key = process.argv[index]
  const value = process.argv[index + 1]
  if (key?.startsWith('--')) {
    args.set(key.slice(2), value && !value.startsWith('--') ? value : 'true')
  }
}

const printHelp = () => {
  console.log(`
OpenDevFlow Bridge

用法：
  npx @opendevflow/bridge --server http://localhost:8765 --client-key <客户端标识> --root <本地代码根目录>

参数：
  --server       OpenDevFlow 后端地址，默认 http://localhost:8765
  --client-key   平台中登记的 Bridge 客户端标识，也可使用 OPENDEVFLOW_CLIENT_KEY
  --root         本地代码根目录，默认当前目录，也可使用 OPENDEVFLOW_ROOT
  --help         查看帮助

示例：
  npx @opendevflow/bridge --server http://localhost:8765 --client-key muke-mac --root /Users/muke/projects
`.trim())
}

if (args.has('help') || args.has('h')) {
  printHelp()
  process.exit(0)
}

const server = (args.get('server') || process.env.OPENDEVFLOW_SERVER || 'http://localhost:8765').replace(/\/$/, '')
const clientKey = args.get('client-key') || process.env.OPENDEVFLOW_CLIENT_KEY
const rootPath = path.resolve(args.get('root') || process.env.OPENDEVFLOW_ROOT || process.cwd())

if (!clientKey) {
  console.error('缺少 client key，请使用 --client-key 或 OPENDEVFLOW_CLIENT_KEY')
  process.exit(1)
}

const running = new Set()
const dangerousPatterns = [
  /(^|\s)rm\s+-rf(\s|$)/,
  /(^|\s)sudo(\s|$)/,
  /(^|\s)chmod\s+-R(\s|$)/,
  /(^|\s)chown\s+-R(\s|$)/,
  />\s*\/dev\/(?:disk|rdisk)/,
  /mkfs\./,
]

const toWsUrl = (base) => `${base.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')}/api/v1/demands/local-bridge/ws?client_key=${encodeURIComponent(clientKey)}`

const api = async (path, body) => {
  const response = await fetch(`${server}/api/v1/demands${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ${response.status}: ${text}`)
  }
  return response.json()
}

const uploadCodeContext = async (snapshot) => {
  const response = await fetch(`${server}/api/v1/demands/local-bridge/code-context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_key: clientKey, ...snapshot }),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ${response.status}: ${text}`)
  }
  return response.json()
}

const appendLog = async (commandId, chunk, status = 'running') => {
  await api(`/local-bridge/commands/${commandId}/logs`, { client_key: clientKey, chunk, status })
}

const complete = async (commandId, status, outputSummary, exitCode) => {
  await api(`/local-bridge/commands/${commandId}/complete`, {
    client_key: clientKey,
    status,
    output_summary: outputSummary,
    exit_code: exitCode,
  })
}

const rejectCommand = async (command, reason) => {
  await appendLog(command.id, `Bridge 拒绝执行：${reason}\n`, 'failed')
  await complete(command.id, 'failed', reason, 126)
}

const exists = async (filePath) => {
  try {
    await fs.access(filePath)
    return true
  } catch {
    return false
  }
}

const readSmallFile = async (filePath, limit = 8000) => {
  try {
    const stat = await fs.stat(filePath)
    if (stat.size > limit) return ''
    return await fs.readFile(filePath, 'utf8')
  } catch {
    return ''
  }
}

const detectProject = async (dir) => {
  const markers = [
    ['package.json', 'node'],
    ['pom.xml', 'maven'],
    ['build.gradle', 'gradle'],
    ['go.mod', 'go'],
    ['pyproject.toml', 'python'],
    ['Cargo.toml', 'rust'],
  ]
  for (const [file, type] of markers) {
    if (await exists(path.join(dir, file))) {
      return { marker: file, type }
    }
  }
  return null
}

const walkProjects = async (dir, depth = 0, projects = []) => {
  // 限制扫描深度和项目数量，避免用户误把整个磁盘作为代码根目录时拖慢本机。
  if (depth > 3 || projects.length >= 80) return projects
  const detected = await detectProject(dir)
  if (detected) {
    projects.push({ dir, ...detected })
    return projects
  }
  let entries = []
  try {
    entries = await fs.readdir(dir, { withFileTypes: true })
  } catch {
    return projects
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    if (['.git', 'node_modules', 'dist', 'build', 'target', '.venv', 'venv', '.idea'].includes(entry.name)) continue
    await walkProjects(path.join(dir, entry.name), depth + 1, projects)
  }
  return projects
}

const gitSummary = async (cwd) => new Promise((resolve) => {
  const child = spawn('git status --short --branch', { cwd, shell: true })
  let output = ''
  child.stdout.on('data', (data) => { output += data.toString() })
  child.stderr.on('data', (data) => { output += data.toString() })
  child.on('close', () => resolve(output.trim()))
})

const buildSnapshot = async () => {
  // 快照只上传项目结构、Git 状态和构建标记摘要，不上传完整源码内容。
  const projects = await walkProjects(rootPath)
  const sections = [`# Code Context Snapshot`, ``, `- Root Path: ${rootPath}`, `- Project Count: ${projects.length}`, ``]
  const rootGit = await gitSummary(rootPath)
  if (rootGit) sections.push(`## Git Status`, '```text', rootGit.slice(0, 4000), '```', '')
  sections.push('## Projects')
  for (const project of projects) {
    const relative = path.relative(rootPath, project.dir) || '.'
    sections.push(``, `### ${relative}`, `- Type: ${project.type}`, `- Marker: ${project.marker}`, `- Path: ${project.dir}`)
    const markerContent = await readSmallFile(path.join(project.dir, project.marker))
    if (markerContent) {
      sections.push(`- ${project.marker}:`, '```text', markerContent.slice(0, 4000), '```')
    }
  }
  return {
    projectCount: projects.length,
    projects: projects.map((project, index) => {
      const relative = path.relative(rootPath, project.dir) || '.'
      const projectKey = relative === '.' ? path.basename(rootPath) : relative.replace(/[\\/]+/g, '-')
      return {
        project_key: projectKey || `project-${index + 1}`,
        project_name: relative === '.' ? path.basename(rootPath) : path.basename(project.dir),
        local_path: project.dir,
        project_type: project.type,
        branch_name: '',
      }
    }),
    content: sections.join('\n'),
  }
}

const scanWorkspace = async (command) => {
  await api(`/local-bridge/commands/${command.id}/claim`, {
    client_key: clientKey,
    chunk: `开始扫描代码根目录：${rootPath}\n`,
    status: 'running',
  })
  const snapshot = await buildSnapshot()
  await uploadCodeContext({
    demand_id: command.demand_id,
    source_ref: 'local-bridge',
    root_path: rootPath,
    project_count: snapshot.projectCount,
    snapshot_content: snapshot.content,
    projects: snapshot.projects,
  })
  await appendLog(command.id, `扫描完成，识别项目数：${snapshot.projectCount}\n`)
  await complete(command.id, 'success', `扫描完成，识别项目数：${snapshot.projectCount}`, 0)
}

const validateCommand = (command) => {
  // 本地命令执行前做最小安全校验；更细的白名单和本地确认放在后续版本扩展。
  const text = command.command_text || ''
  if (!text.trim()) return '命令为空'
  if (dangerousPatterns.some((pattern) => pattern.test(text))) return '命令命中危险操作规则'
  if (!command.local_project_id) return '命令未绑定本地项目'
  if (!command.local_project_path) return '命令缺少本地项目路径'
  if (!path.isAbsolute(command.local_project_path)) return '本地项目路径必须是绝对路径'
  return ''
}

const runCommand = async (command) => {
  if (running.has(command.id)) return
  running.add(command.id)
  try {
    if (command.command_type === 'scan_workspace') {
      await scanWorkspace(command)
      return
    }
    const rejected = validateCommand(command)
    if (rejected) {
      await rejectCommand(command, rejected)
      return
    }
    await api(`/local-bridge/commands/${command.id}/claim`, {
      client_key: clientKey,
      chunk: `开始执行：${command.command_text}\n`,
      status: 'running',
    })

    const child = spawn(command.command_text, {
      cwd: command.local_project_path,
      shell: true,
      env: process.env,
    })
    let output = ''
    child.stdout.on('data', async (data) => {
      const text = data.toString()
      output += text
      await appendLog(command.id, text)
    })
    child.stderr.on('data', async (data) => {
      const text = data.toString()
      output += text
      await appendLog(command.id, text)
    })
    child.on('close', async (code) => {
      const status = code === 0 ? 'success' : 'failed'
      await complete(command.id, status, output.slice(-2000), code)
      running.delete(command.id)
    })
  } catch (error) {
    await complete(command.id, 'failed', error.message, 1)
    running.delete(command.id)
  }
}

const connect = () => {
  const ws = new WebSocket(toWsUrl(server))
  ws.on('open', () => {
    console.log('OpenDevFlow Bridge 已连接')
    console.log(`平台地址：${server}`)
    console.log(`代码根目录：${rootPath}`)
    console.log('请保持此终端窗口运行。关闭窗口后，平台将无法扫描代码上下文或执行本地命令。')
  })
  ws.on('message', (raw) => {
    try {
      const payload = JSON.parse(raw.toString())
      if (payload.type === 'commands') {
        for (const command of payload.items || []) runCommand(command)
      } else if (payload.type === 'error') {
        console.error(payload.detail)
      }
    } catch (error) {
      console.error(`消息处理失败：${error.message}`)
    }
  })
  ws.on('close', () => {
    console.log('Bridge 连接已断开，3 秒后自动重连...')
    setTimeout(connect, 3000)
  })
  ws.on('error', (error) => {
    console.error(`Bridge websocket error: ${error.message}`)
  })
}

connect()
