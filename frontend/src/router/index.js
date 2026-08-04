import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import CommunityCreateView from '@/views/CommunityCreateView.vue'
import CommunityDetailView from '@/views/CommunityDetailView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/communities/new' },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/register', name: 'register', component: RegisterView, meta: { public: true } },
    { path: '/communities/new', name: 'community-create', component: CommunityCreateView },
    {
      path: '/communities/:id',
      name: 'community-detail',
      component: CommunityDetailView,
      props: true,
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) return true

  // useAuthStore() must be called here, inside the guard, not at module
  // top-level: Pinia isn't installed on the app yet when this file first
  // evaluates.
  const auth = useAuthStore()
  if (!auth.isAuthenticated) {
    return { name: 'login' }
  }
  return true
})

export default router
