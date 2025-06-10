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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const requiresAdmin = to.matched.some((record) => record.meta.requiresAdmin)

  // Debug logging for navigation tracking
  if (import.meta.env.DEV) {
    console.log(`[Router] Navigating from ${from.path} to ${to.path}`, {
      requiresAuth,
      requiresAdmin,
      isAuthenticated: authStore.isAuthenticated,
      isInitialized: authStore.isInitialized,
      userRole: authStore.user?.role
    })
  }

  // Only initialize auth store if route requires authentication or we're checking login redirect
  if (requiresAuth || to.path === '/login') {
    if (!authStore.isInitialized) {
      if (import.meta.env.DEV) {
        console.log('[Router] Initializing auth store')
      }
      await authStore.init()
    }
  }

  // Check if route requires authentication
  if (requiresAuth) {
    if (!authStore.isAuthenticated) {
      if (import.meta.env.DEV) {
        console.log('[Router] Redirecting to login - not authenticated')
      }
      next('/login')
      return
    }

    // Check if route requires admin privileges
    if (requiresAdmin) {
      if (authStore.user?.role !== 'Admin') {
        if (import.meta.env.DEV) {
          console.log('[Router] Redirecting to cases - insufficient privileges')
        }
        // Redirect directly to cases instead of root to avoid extra redirect
        next('/cases')
        return
      }
    }
  }

  // If on login page and already authenticated, redirect to cases
  if (to.path === '/login' && authStore.isAuthenticated) {
    if (import.meta.env.DEV) {
      console.log('[Router] Redirecting to cases - already authenticated')
    }
    next('/cases')
    return
  }

  if (import.meta.env.DEV) {
    console.log('[Router] Navigation allowed')
  }
  next()
})

export default router
