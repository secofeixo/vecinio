import { describe, expect, it } from 'vitest'
import { groupUnitsByCommunity } from '@/utils/groupUnitsByCommunity'

describe('groupUnitsByCommunity', () => {
  it('returns an empty array for an empty input', () => {
    expect(groupUnitsByCommunity([])).toEqual([])
  })

  it('groups multiple units from the same community into one group', () => {
    const units = [
      {
        id: 'unit-1',
        identifier: '1A',
        participation_coefficient: '0.6',
        community_id: 'community-1',
        community_name: 'Comunidad Uno',
        community_address: { street: 'Calle Uno', number: '1', city: 'Vigo', postal_code: '36201', province: 'Pontevedra' },
      },
      {
        id: 'unit-2',
        identifier: '1B',
        participation_coefficient: '0.4',
        community_id: 'community-1',
        community_name: 'Comunidad Uno',
        community_address: { street: 'Calle Uno', number: '1', city: 'Vigo', postal_code: '36201', province: 'Pontevedra' },
      },
    ]

    const groups = groupUnitsByCommunity(units)

    expect(groups).toHaveLength(1)
    expect(groups[0].communityId).toBe('community-1')
    expect(groups[0].communityName).toBe('Comunidad Uno')
    expect(groups[0].units).toEqual([
      { id: 'unit-1', identifier: '1A', participationCoefficient: '0.6' },
      { id: 'unit-2', identifier: '1B', participationCoefficient: '0.4' },
    ])
  })

  it('creates one group per distinct community, preserving first-seen order', () => {
    const units = [
      {
        id: 'unit-1',
        identifier: '1A',
        participation_coefficient: '0.6',
        community_id: 'community-1',
        community_name: 'Comunidad Uno',
        community_address: { street: 'Calle Uno', number: '1', city: 'Vigo', postal_code: '36201', province: 'Pontevedra' },
      },
      {
        id: 'unit-2',
        identifier: '2C',
        participation_coefficient: '1',
        community_id: 'community-2',
        community_name: 'Comunidad Dos',
        community_address: { street: 'Calle Dos', number: '2', city: 'Vigo', postal_code: '36202', province: 'Pontevedra' },
      },
    ]

    const groups = groupUnitsByCommunity(units)

    expect(groups.map((g) => g.communityId)).toEqual(['community-1', 'community-2'])
    expect(groups[0].units).toHaveLength(1)
    expect(groups[1].units).toHaveLength(1)
  })

  it('does not mutate its input', () => {
    const units = [
      {
        id: 'unit-1',
        identifier: '1A',
        participation_coefficient: '0.6',
        community_id: 'community-1',
        community_name: 'Comunidad Uno',
        community_address: { street: 'Calle Uno', number: '1', city: 'Vigo', postal_code: '36201', province: 'Pontevedra' },
      },
    ]
    const snapshot = JSON.parse(JSON.stringify(units))

    groupUnitsByCommunity(units)

    expect(units).toEqual(snapshot)
  })
})
