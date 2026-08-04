export function groupUnitsByCommunity(units) {
  const groups = []
  const groupsByCommunityId = new Map()

  for (const unit of units) {
    let group = groupsByCommunityId.get(unit.community_id)
    if (!group) {
      group = {
        communityId: unit.community_id,
        communityName: unit.community_name,
        communityAddress: unit.community_address,
        units: [],
      }
      groupsByCommunityId.set(unit.community_id, group)
      groups.push(group)
    }
    group.units.push({
      id: unit.id,
      identifier: unit.identifier,
      participationCoefficient: unit.participation_coefficient,
    })
  }

  return groups
}
