from uuid import uuid4

import pytest

from src.application.community_group.add_community_to_group import (
    AddCommunityToGroup,
    CommunityGroupNotFoundError,
    CommunityNotFoundError,
)
from src.domain.community.community import Community
from src.domain.community.value_objects import CIF, Address, CommunityId
from src.domain.community_group.community_group import (
    CommunityAlreadyMemberError,
    CommunityGroup,
)
from src.domain.community_group.value_objects import CommunityGroupId
from tests.fakes.in_memory_community_group_repository import (
    InMemoryCommunityGroupRepository,
)
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository


def make_community() -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=Address(
            street="Calle Mayor",
            number="1",
            city="Madrid",
            postal_code="28001",
            province="Madrid",
        ),
        cif=CIF(value="H12345674"),
    )


def make_group(member_community_ids: tuple[CommunityId, ...]) -> CommunityGroup:
    return CommunityGroup(
        id=CommunityGroupId.generate(),
        name="206-208",
        member_community_ids=member_community_ids,
    )


@pytest.mark.asyncio
async def test_adds_existing_community_to_existing_group() -> None:
    community_a, community_b, community_c = (
        make_community(),
        make_community(),
        make_community(),
    )
    community_repository = InMemoryCommunityRepository()
    for community in (community_a, community_b, community_c):
        await community_repository.save(community)
    group = make_group((community_a.id, community_b.id))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = AddCommunityToGroup(group_repository, community_repository)
    result = await use_case.execute(
        group_id=group.id.value, community_id=community_c.id.value
    )

    assert community_c.id in result.member_community_ids


@pytest.mark.asyncio
async def test_rejects_when_group_does_not_exist() -> None:
    community_repository = InMemoryCommunityRepository()
    community = make_community()
    await community_repository.save(community)
    group_repository = InMemoryCommunityGroupRepository()

    use_case = AddCommunityToGroup(group_repository, community_repository)

    with pytest.raises(CommunityGroupNotFoundError):
        await use_case.execute(group_id=uuid4(), community_id=community.id.value)


@pytest.mark.asyncio
async def test_rejects_when_community_does_not_exist() -> None:
    community_a, community_b = make_community(), make_community()
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community_a)
    await community_repository.save(community_b)
    group = make_group((community_a.id, community_b.id))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = AddCommunityToGroup(group_repository, community_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(group_id=group.id.value, community_id=uuid4())


@pytest.mark.asyncio
async def test_rejects_when_community_already_a_member() -> None:
    community_a, community_b = make_community(), make_community()
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community_a)
    await community_repository.save(community_b)
    group = make_group((community_a.id, community_b.id))
    group_repository = InMemoryCommunityGroupRepository()
    await group_repository.save(group)

    use_case = AddCommunityToGroup(group_repository, community_repository)

    with pytest.raises(CommunityAlreadyMemberError):
        await use_case.execute(
            group_id=group.id.value, community_id=community_a.id.value
        )
