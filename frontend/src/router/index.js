import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/',
    redirect: '/cases',
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

const router = createRouter({
  history: createWebHistory(),
  routes,
})

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

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)
  const requiresNotAnalyst = to.matched.some((record) => record.meta.requiresNotAnalyst)

  // Only initialize auth store if route requires authentication or we're checking login redirect
  if (requiresAuth || to.path === '/login') {
    if (!authStore.isInitialized) {
      await authStore.init()
    }
  }

  // Check if route requires authentication
  if (requiresAuth) {
    if (!authStore.isAuthenticated) {
      next('/login')
      return
    }

    // Check if route requires admin privileges
    if (requiresAdmin) {
      if (authStore.user?.role !== 'Admin') {
        // Redirect directly to cases instead of root to avoid extra redirect
        next('/cases')
        return
      }
    }

    // Check if route restricts Analyst access
    if (requiresNotAnalyst) {
      if (authStore.user?.role === 'Analyst') {
        // Redirect analysts to cases page
        next('/cases')
        return
      }
    }
  }

  // If on login page and already authenticated, redirect to cases
  if (to.path === '/login' && authStore.isAuthenticated) {
    next('/cases')
    return
  }

  next()
})

export default router
