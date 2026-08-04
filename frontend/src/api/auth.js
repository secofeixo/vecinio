import client from '@/api/client'

export function register({ email, password }) {
  return client.post('/auth/register', { email, password }).then((r) => r.data)
}

export function login({ email, password }) {
  return client.post('/auth/login', { email, password }).then((r) => r.data)
}

export function logout(refreshToken) {
  return client.post('/auth/logout', { refresh_token: refreshToken })
}
