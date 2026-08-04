import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '@/api/auth'

const ACCESS_TOKEN_KEY = 'vecinio_access_token'
const REFRESH_TOKEN_KEY = 'vecinio_refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem(ACCESS_TOKEN_KEY))
  const refreshToken = ref(localStorage.getItem(REFRESH_TOKEN_KEY))

  const isAuthenticated = computed(() => accessToken.value !== null)

  function setTokens(tokens) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
    localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
  }

  function clearTokens() {
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }

  async function register(credentials) {
    await authApi.register(credentials)
  }

  async function login(credentials) {
    const tokens = await authApi.login(credentials)
    setTokens(tokens)
  }

  function logout() {
    const tokenToRevoke = refreshToken.value
    clearTokens()
    if (tokenToRevoke) {
      // Best-effort revocation; the user is logged out client-side regardless.
      authApi.logout(tokenToRevoke).catch(() => {})
    }
  }

  return { accessToken, refreshToken, isAuthenticated, register, login, logout }
})
