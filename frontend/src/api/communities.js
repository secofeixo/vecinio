import client from '@/api/client'

export function createCommunity(payload) {
  return client.post('/communities', payload).then((r) => r.data)
}

export function getCommunity(id) {
  return client.get(`/communities/${id}`).then((r) => r.data)
}
