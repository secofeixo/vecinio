from uuid import uuid4

import pytest

from src.application.community_group.remove_community_from_group import (
    CommunityGroupNotFoundError,
    RemoveCommunityFromGroup,
)
from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import (
    CommunityGroup,
    CommunityGroupBelowMinimumMembersError,
    CommunityNotMemberError,
)
from src.domain.community_group.value_objects import CommunityGroupId
from tests.fakes.in_memory_community_group_repository import (
    InMemoryCommunityGroupRepository,
)


def make_group(member_community_ids: tuple[CommunityId, ...]) -> CommunityGroup:
    return CommunityGroup(
        id=CommunityGroupId.generate(),
        name="206-208",
        member_community_ids=member_community_ids,
    )


@pytest.mark.asyncio
async def test_removes_member_when_above_minimum() -> None:
    community_a, community_b, community_c = (
        CommunityId.generate(),
        CommunityId.generate(),
        CommunityId.generate(),
    )
    group = make_group((community_a, community_b, community_c))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = RemoveCommunityFromGroup(group_repository)
    result = await use_case.execute(
        group_id=group.id.value, community_id=community_c.value
    )

    assert result.member_community_ids == (community_a, community_b)


@pytest.mark.asyncio
async def test_rejects_when_group_does_not_exist() -> None:
    group_repository = InMemoryCommunityGroupRepository()

    use_case = RemoveCommunityFromGroup(group_repository)

    with pytest.raises(CommunityGroupNotFoundError):
        await use_case.execute(group_id=uuid4(), community_id=uuid4())


@pytest.mark.asyncio
async def test_propagates_below_minimum_members_error() -> None:
    community_a, community_b = CommunityId.generate(), CommunityId.generate()
    group = make_group((community_a, community_b))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = RemoveCommunityFromGroup(group_repository)

    with pytest.raises(CommunityGroupBelowMinimumMembersError):
        await use_case.execute(group_id=group.id.value, community_id=community_b.value)


@pytest.mark.asyncio
async def test_propagates_not_a_member_error() -> None:
    community_a, community_b = CommunityId.generate(), CommunityId.generate()
    group = make_group((community_a, community_b))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = RemoveCommunityFromGroup(group_repository)

    with pytest.raises(CommunityNotMemberError):
        await use_case.execute(group_id=group.id.value, community_id=uuid4())
