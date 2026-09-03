import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

export const routes = [
  {
    path: '/',
    redirect: '/cases',
  },
  {
    path: '/setup',
    name: 'Setup',
    component: () => import('../views/Setup.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/cases',
    name: 'Cases',
    component: () => import('../views/MainDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/clients',
    name: 'Clients',
    component: () => import('../views/ClientsDashboard.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/plugins',
    name: 'Plugins',
    component: () => import('../views/PluginsDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/case/:id',
    name: 'CaseDetails',
    component: () => import('../views/CaseDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/strixy',
    name: 'StrixyChat',
    component: () => import('../views/StrixyChat.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('../views/AdminDashboard.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/hunts',
    name: 'Hunts',
    component: () => import('../views/HuntsDashboard.vue'),
    meta: { requiresAuth: true, requiresNotAnalyst: true },
  },
  {
    path: '/hunts/execution/:id',
    name: 'HuntExecution',
    component: () => import('../views/HuntExecution.vue'),
    meta: { requiresAuth: true, requiresNotAnalyst: true },
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('../views/tasks/TaskDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tasks/:id',
    name: 'TaskDetail',
    component: () => import('../views/tasks/TaskDetail.vue'),
    meta: { requiresAuth: true },
  },
]

export function createAppRouter(history = createWebHistory(), appRoutes = routes) {
  const router = createRouter({ history, routes: appRoutes })

  router.beforeEach(async (to, from, next) => {
    const authStore = useAuthStore()
    const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
    const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
    const requiresNotAnalyst = to.matched.some((record) => record.meta.requiresNotAnalyst)
    const isSetupRoute = to.path === '/setup'
    const isLoginRoute = to.path === '/login'

    if (requiresAuth || isLoginRoute || isSetupRoute) {
      if (!authStore.isInitialized) {
        await authStore.init()
      }
    }

    if (authStore.setupRequired && (requiresAuth || isLoginRoute)) {
      next('/setup')
      return
    }

    if (isSetupRoute) {
      if (authStore.isAuthenticated) {
        next('/cases')
        return
      }

      if (!authStore.setupRequired) {
        next('/login')
        return
      }
    }

    if (requiresAuth) {
      if (!authStore.isAuthenticated) {
        next('/login')
        return
      }

      if (requiresAdmin && authStore.user?.role !== 'Admin') {
        next('/cases')
        return
      }

      if (requiresNotAnalyst && authStore.user?.role === 'Analyst') {
        next('/cases')
        return
      }
    }

    if (isLoginRoute && authStore.isAuthenticated) {
      next('/cases')
      return
    }

    next()
  })

  return router
}

const router = createAppRouter()

// Listen for unauthorized API responses and redirect to login
// This prevents circular dependency with the API service
let isHandlingUnauthorized = false
window.addEventListener('api:unauthorized', () => {
  if (!isHandlingUnauthorized) {
    isHandlingUnauthorized = true
    router.push('/login').finally(() => {
      setTimeout(() => {
        isHandlingUnauthorized = false
      }, 100)
    })
  }
})

export default router
