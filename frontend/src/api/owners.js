import client from '@/api/client'

export function getMyUnits() {
  return client.get('/owners/me/units').then((r) => r.data)
}
