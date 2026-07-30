from uuid import uuid4

import pytest

from src.application.community_group.create_community_group import (
    CommunityNotFoundError,
    CreateCommunityGroup,
)
from src.domain.community.community import Community
from src.domain.community.value_objects import CIF, Address, CommunityId
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


@pytest.mark.asyncio
async def test_creates_group_when_all_communities_exist() -> None:
    community_a, community_b = make_community(), make_community()
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community_a)
    await community_repository.save(community_b)
    group_repository = InMemoryCommunityGroupRepository()

    use_case = CreateCommunityGroup(group_repository, community_repository)
    group_id = await use_case.execute(
        name="206-208",
        community_ids=[community_a.id.value, community_b.id.value],
    )

    persisted = await group_repository.get_by_id(group_id)
    assert persisted is not None
    assert persisted.name == "206-208"
    assert persisted.member_community_ids == (community_a.id, community_b.id)


@pytest.mark.asyncio
async def test_rejects_when_a_community_does_not_exist() -> None:
    community_a = make_community()
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community_a)
    group_repository = InMemoryCommunityGroupRepository()

    use_case = CreateCommunityGroup(group_repository, community_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            name="206-208",
            community_ids=[community_a.id.value, uuid4()],
        )
