import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '../layouts/MainLayout.vue'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/auth/LoginView.vue') },
  { path: '/lock', name: 'lock', meta: { requiresAuth: true }, component: () => import('../views/auth/LockView.vue') },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', meta: { title: '首页', permissions: ['dashboard:view'] }, component: () => import('../views/dashboard/DashboardView.vue') },
      { path: 'profile', name: 'profile', meta: { title: '个人中心' }, component: () => import('../views/user/ProfileView.vue') },
      { path: 'admin', redirect: '/admin/users' },
      { path: 'admin/company', name: 'admin-company', meta: { title: '公司管理', permissions: ['system:company:list'] }, component: () => import('../views/admin/CompanyView.vue') },
      { path: 'admin/users', name: 'admin-users', meta: { title: '用户管理', permissions: ['system:user:list'] }, component: () => import('../views/admin/AdminView.vue'), props: { section: 'users' } },
      { path: 'admin/roles', name: 'admin-roles', meta: { title: '角色管理', permissions: ['system:role:list'] }, component: () => import('../views/admin/AdminView.vue'), props: { section: 'roles' } },
      { path: 'admin/menus', name: 'admin-menus', meta: { title: '菜单管理', permissions: ['system:menu:list'] }, component: () => import('../views/admin/AdminView.vue'), props: { section: 'menus' } },
      { path: 'admin/skills', name: 'admin-skills', meta: { title: 'Skill 管理', permissions: ['system:skill:list'] }, component: () => import('../views/admin/SkillManagementView.vue') },
      { path: 'admin/organizations', name: 'admin-organizations', meta: { title: '组织架构', permissions: ['system:department:list'] }, component: () => import('../views/organization/DepartmentView.vue') },
      { path: 'admin/departments', redirect: '/admin/organizations' },
      { path: 'admin/audit-logs', name: 'admin-audit', meta: { title: '审计日志', permissions: ['system:audit:list'] }, component: () => import('../views/admin/AdminView.vue'), props: { section: 'audit' } },
      { path: 'model-providers', name: 'model-providers', meta: { title: '模型配置', permissions: ['model_provider:list'] }, component: () => import('../views/model/ModelProviderView.vue') },
      { path: 'demands', name: 'demands', meta: { title: '需求管理', permissions: ['demand:list'] }, component: () => import('../views/demand/DemandView.vue') },
      {
        path: 'demands/:id',
        name: 'demand-detail',
        meta: {
          title: '需求详情',
          permissions: ['demand:list'],
          activeMenu: '/demands',
          breadcrumb: [
            { title: '需求管理', path: '/demands' },
            { title: '需求详情' }
          ]
        },
        component: () => import('../views/demand/DemandDetailView.vue')
      },
      {
        path: 'demands/:demandId/workflows/:workflowId',
        name: 'workflow-detail',
        meta: {
          title: '工作流详情',
          permissions: ['workflow:view'],
          activeMenu: '/demands',
          breadcrumb: [
            { title: '需求管理', path: '/demands' },
            { title: '需求详情', pathFromParams: '/demands/:demandId' },
            { title: '工作流详情' }
          ]
        },
        component: () => import('../views/demand/WorkflowDetailView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (auth.token && !auth.user) {
    await auth.loadMe().catch(() => auth.logout())
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.roles && !to.meta.roles.some((role) => auth.user?.roles?.includes(role))) {
    return { name: 'admin-users' }
  }
  if (to.meta.permissions && !to.meta.permissions.some((permission) => auth.hasPermission(permission))) {
    return { name: 'admin-users' }
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
