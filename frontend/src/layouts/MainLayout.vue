<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  Briefcase,
  Collection,
  Connection,
  Cpu,
  Document,
  DocumentChecked,
  Files,
  Folder,
  House,
  Fold,
  FullScreen,
  Menu,
  Moon,
  Odometer,
  Lock,
  Memo,
  Setting,
  Share,
  SwitchButton,
  SetUp,
  Tickets,
  Expand,
  Sunny,
  User,
  UserFilled
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isCollapsed = ref(false)
const isDark = ref(localStorage.getItem('opendevflow-theme') === 'dark')

const iconMap = {
  Briefcase,
  Collection,
  Connection,
  Cpu,
  Document,
  DocumentChecked,
  Files,
  Folder,
  House,
  Fold,
  FullScreen,
  Menu,
  Moon,
  Odometer,
  Lock,
  Memo,
  Setting,
  Share,
  SetUp,
  Tickets,
  Expand,
  Sunny,
  User,
  UserFilled
}

const displayName = computed(() => auth.user?.display_name || auth.user?.username || '用户')
const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())

const fallbackMenus = computed(() => {
  if (!auth.isAdmin) return []
  return [
    {
      id: 'dashboard',
      menu_name: '首页',
      menu_type: 'C',
      path: '/dashboard',
      icon: 'House'
    },
    {
      id: 'system',
      menu_name: '系统管理',
      menu_type: 'M',
      path: '/admin',
      icon: 'Setting',
      children: [
        { id: 'company', menu_name: '公司管理', menu_type: 'C', path: '/admin/company', icon: 'Briefcase' },
        { id: 'users', menu_name: '用户管理', menu_type: 'C', path: '/admin/users', icon: 'User' },
        { id: 'roles', menu_name: '角色管理', menu_type: 'C', path: '/admin/roles', icon: 'UserFilled' },
        { id: 'menus', menu_name: '菜单管理', menu_type: 'C', path: '/admin/menus', icon: 'Menu' },
        { id: 'skills', menu_name: 'Skill 管理', menu_type: 'C', path: '/admin/skills', icon: 'Collection' },
        { id: 'organizations', menu_name: '组织架构', menu_type: 'C', path: '/admin/organizations', icon: 'Share' },
        { id: 'audit', menu_name: '审计日志', menu_type: 'C', path: '/admin/audit-logs', icon: 'DocumentChecked' }
      ]
    }
  ]
})

const sidebarMenus = computed(() => {
  const menus = auth.user?.menus || []
  return menus.length ? menus : fallbackMenus.value
})

const menuIcon = (name) => iconMap[name] || Tickets

const visibleChildren = (menu) => (menu.children || []).filter((child) => child.visible !== false && child.menu_type !== 'F')
const activeMenu = computed(() => router.currentRoute.value.meta.activeMenu || router.currentRoute.value.path)
const asideWidth = computed(() => (isCollapsed.value ? '64px' : '188px'))

const findMenuTrail = (menus, targetPath, parents = []) => {
  for (const menu of menus) {
    if (menu.visible === false || menu.menu_type === 'F') continue
    const current = [...parents, menu]
    if (menu.path === targetPath) return current
    const found = findMenuTrail(menu.children || [], targetPath, current)
    if (found.length) return found
  }
  return []
}

const resolveBreadcrumbPath = (item, params) => {
  const sourcePath = item.pathFromParams || item.path
  if (!sourcePath) return ''
  return Object.entries(params || {}).reduce(
    (path, [key, value]) => path.replace(`:${key}`, String(value)),
    sourcePath
  )
}

const breadcrumbs = computed(() => {
  const route = router.currentRoute.value
  const configured = route.meta.breadcrumb
  if (Array.isArray(configured) && configured.length) {
    return configured.map((item) => ({
      title: item.title,
      path: resolveBreadcrumbPath(item, route.params) || route.path
    }))
  }
  const trail = findMenuTrail(sidebarMenus.value, activeMenu.value)
  const names = trail
    .filter((item) => item.menu_name)
    .map((item) => ({ title: item.menu_name, path: item.path }))
  const routeTitle = route.meta.title
  if (routeTitle && !names.some((item) => item.title === routeTitle)) {
    names.push({ title: routeTitle, path: route.path })
  }
  return names.length ? names : [{ title: routeTitle || '首页', path: route.path }]
})

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleFullscreen = async () => {
  if (!document.fullscreenElement) {
    await document.documentElement.requestFullscreen?.()
  } else {
    await document.exitFullscreen?.()
  }
}

const applyTheme = () => {
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('opendevflow-theme', isDark.value ? 'dark' : 'light')
}

const toggleTheme = () => {
  isDark.value = !isDark.value
  applyTheme()
}

const logout = () => {
  auth.logout()
  router.push('/login')
}

const goProfile = () => {
  router.push('/profile')
}

const lockScreen = () => {
  const currentPath = router.currentRoute.value.fullPath
  localStorage.setItem('screen-lock-path', currentPath || '/dashboard')
  localStorage.setItem('screen-lock', 'true')
  sessionStorage.setItem('opendevflow_lock_redirect', currentPath)
  router.push('/lock')
}

const confirmLogout = async () => {
  await ElMessageBox.confirm('确定注销并退出系统吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  logout()
}

onMounted(applyTheme)
</script>

<template>
  <el-container class="shell">
    <el-aside :width="asideWidth" class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="brand">
        <img src="/favicon.svg" alt="" class="brand-icon" />
        <span v-if="!isCollapsed">OpenDevFlow</span>
      </div>
      <el-menu
        router
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :unique-opened="true"
        class="menu"
      >
        <template v-for="menu in sidebarMenus" :key="menu.id">
          <el-sub-menu v-if="visibleChildren(menu).length" :index="menu.path || menu.id">
            <template #title>
              <el-icon><component :is="menuIcon(menu.icon)" /></el-icon>
              <span>{{ menu.menu_name }}</span>
            </template>
            <template v-for="child in visibleChildren(menu)" :key="child.id">
              <el-sub-menu v-if="visibleChildren(child).length" :index="child.path || child.id">
                <template #title>
                  <el-icon><component :is="menuIcon(child.icon)" /></el-icon>
                  <span>{{ child.menu_name }}</span>
                </template>
                <el-menu-item
                  v-for="grandchild in visibleChildren(child)"
                  :key="grandchild.id"
                  :index="grandchild.path"
                >
                  <el-icon><component :is="menuIcon(grandchild.icon)" /></el-icon>
                  <span>{{ grandchild.menu_name }}</span>
                </el-menu-item>
              </el-sub-menu>
              <el-menu-item v-else :index="child.path">
                <el-icon><component :is="menuIcon(child.icon)" /></el-icon>
                <span>{{ child.menu_name }}</span>
              </el-menu-item>
            </template>
          </el-sub-menu>
          <el-menu-item v-else-if="menu.menu_type !== 'F'" :index="menu.path">
            <el-icon><component :is="menuIcon(menu.icon)" /></el-icon>
            <span>{{ menu.menu_name }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <div class="topbar-left">
          <el-tooltip :content="isCollapsed ? '展开菜单' : '折叠菜单'" placement="bottom">
            <button class="icon-button" type="button" @click="toggleSidebar">
              <el-icon><component :is="isCollapsed ? Expand : Fold" /></el-icon>
            </button>
          </el-tooltip>
          <el-breadcrumb separator="/" class="breadcrumb">
            <el-breadcrumb-item
              v-for="(item, index) in breadcrumbs"
              :key="`${item.path}-${item.title}`"
              :to="index < breadcrumbs.length - 1 && item.path ? item.path : undefined"
            >
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-tools">
          <el-tooltip :content="isDark ? '切换白天模式' : '切换黑夜模式'" placement="bottom">
            <button class="icon-button" type="button" @click="toggleTheme">
              <el-icon><component :is="isDark ? Sunny : Moon" /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip content="全屏" placement="bottom">
            <button class="icon-button" type="button" @click="toggleFullscreen">
              <el-icon><FullScreen /></el-icon>
            </button>
          </el-tooltip>
          <el-dropdown trigger="click" popper-class="user-menu-popper">
            <button class="user-entry" type="button">
              <el-avatar :size="34" class="user-avatar">{{ avatarText }}</el-avatar>
              <span class="current-user">{{ displayName }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="UserFilled" @click="goProfile">个人中心</el-dropdown-item>
                <el-dropdown-item :icon="Lock" @click="lockScreen">锁定屏幕</el-dropdown-item>
                <el-dropdown-item divided :icon="SwitchButton" @click="confirmLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.shell {
  height: 100vh;
  overflow: hidden;
}

.shell :deep(.el-main) {
  min-height: 0;
  overflow: auto;
  background: var(--app-bg-color, var(--el-bg-color-page));
}

.sidebar {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color);
  transition: width 0.2s ease;
  overflow-x: hidden;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
}

.brand-icon {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
}

.menu {
  border-right: 0;
}

.menu :deep(.el-menu-item),
.menu :deep(.el-sub-menu__title) {
  height: 48px;
}

.sidebar:not(.collapsed) .menu :deep(.el-menu-item),
.sidebar:not(.collapsed) .menu :deep(.el-sub-menu__title) {
  padding-left: 22px !important;
  padding-right: 14px;
}

.sidebar:not(.collapsed) .menu :deep(.el-sub-menu .el-menu .el-menu-item),
.sidebar:not(.collapsed) .menu :deep(.el-sub-menu .el-menu .el-sub-menu__title) {
  padding-left: 44px !important;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 14px 0 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  height: 100%;
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 56px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-text-color-regular);
  cursor: pointer;
  font-size: 20px;
}

.icon-button:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.breadcrumb {
  min-width: 0;
  font-size: 14px;
}

.topbar-tools {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 100%;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 44px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  cursor: pointer;
  color: inherit;
}

.user-entry:hover .current-user {
  color: #2563eb;
}

.user-avatar {
  background: #e0f2fe;
  color: #0369a1;
  font-weight: 700;
}

.current-user {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 600;
}

:global(.dark .sidebar),
:global(.dark .topbar) {
  background: var(--el-bg-color);
  border-color: var(--el-border-color);
}

:global(.dark .brand),
:global(.dark .current-user),
:global(.dark .el-menu-item),
:global(.dark .el-sub-menu__title) {
  color: var(--el-text-color-primary);
}

:global(.dark .menu),
:global(.dark .el-menu) {
  background: var(--el-bg-color);
}

:global(.dark .icon-button) {
  color: var(--el-text-color-regular);
}

:global(.dark .icon-button:hover) {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}
</style>
