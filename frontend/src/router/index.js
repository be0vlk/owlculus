import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Login from '../views/Login.vue'
import SettingsView from '../views/Settings.vue'

const routes = [
  {
    path: '/',
    redirect: '/cases',
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
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
    component: SettingsView,
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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Track navigation state to prevent race conditions
let navigationInProgress = false

// Navigation guard
router.beforeEach(async (to, from, next) => {
  // Prevent concurrent navigation
  if (navigationInProgress && to.path === from.path) {
    next(false)
    return
  }

  navigationInProgress = true

  try {
    const authStore = useAuthStore()

    // Wait for auth store to be initialized
    if (!authStore.isInitialized) {
      await authStore.init()
    }

    // Check if route requires authentication
    if (to.matched.some((record) => record.meta.requiresAuth)) {
      if (!authStore.isAuthenticated) {
        next('/login')
        return
      }

      // Check if route requires admin privileges
      if (to.matched.some((record) => record.meta.requiresAdmin)) {
        if (authStore.user?.role !== 'Admin') {
          next('/')
          return
        }
      }
    }

    // Check if route is forbidden for analysts
    if (to.matched.some((record) => record.meta.isAnalyst)) {
      if (authStore.user?.role === 'Analyst') {
        next('/')
        return
      }
    }

    // If on login page and already authenticated, redirect to cases
    if (to.path === '/login' && authStore.isAuthenticated) {
      next('/cases')
      return
    }

    next()
  } finally {
    // Reset navigation flag after a short delay
    setTimeout(() => {
      navigationInProgress = false
    }, 100)
  }
})

export default router
