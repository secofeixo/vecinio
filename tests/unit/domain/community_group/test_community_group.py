import pytest

from src.domain.community.value_objects import CommunityId
from src.domain.community_group.community_group import (
    CommunityAlreadyMemberError,
    CommunityGroup,
    CommunityGroupBelowMinimumMembersError,
    CommunityNotMemberError,
    InvalidCommunityGroupNameError,
)
from src.domain.community_group.value_objects import CommunityGroupId


def make_group(
    name: str = "Jardín", member_community_ids: tuple[CommunityId, ...] | None = None
) -> CommunityGroup:
    return CommunityGroup(
        id=CommunityGroupId.generate(),
        name=name,
        member_community_ids=member_community_ids
        or (CommunityId.generate(), CommunityId.generate()),
    )


def test_creates_group_with_two_members() -> None:
    community_a = CommunityId.generate()
    community_b = CommunityId.generate()

    group = make_group(member_community_ids=(community_a, community_b))

    assert group.member_community_ids == (community_a, community_b)


def test_rejects_fewer_than_two_members() -> None:
    with pytest.raises(CommunityGroupBelowMinimumMembersError):
        make_group(member_community_ids=(CommunityId.generate(),))


def test_rejects_duplicate_members() -> None:
    shared = CommunityId.generate()

    with pytest.raises(ValueError):
        make_group(member_community_ids=(shared, shared))


def test_rejects_empty_name() -> None:
    with pytest.raises(InvalidCommunityGroupNameError):
        make_group(name="   ")


def test_rejects_name_whose_slug_is_empty() -> None:
    with pytest.raises(InvalidCommunityGroupNameError):
        make_group(name="¡¡¡!!!")


def test_slug_strips_accents_and_lowercases() -> None:
    accented = make_group(name="Jardín")
    plain = make_group(name="jardin")

    assert accented.slug == "jardin"
    assert accented.slug == plain.slug


def test_slug_replaces_non_alphanumeric_with_hyphens_and_collapses() -> None:
    group = make_group(name="Peña  206 -- 208!!")

    assert group.slug == "pena-206-208"


def test_add_member_appends_and_recomputes_state() -> None:
    group = make_group()
    new_member = CommunityId.generate()

    group.add_member(new_member)

    assert new_member in group.member_community_ids
    assert len(group.member_community_ids) == 3


def test_add_member_rejects_already_member() -> None:
    community_a, community_b = CommunityId.generate(), CommunityId.generate()
    group = make_group(member_community_ids=(community_a, community_b))

    with pytest.raises(CommunityAlreadyMemberError):
        group.add_member(community_a)


def test_remove_member_removes_when_above_minimum() -> None:
    community_a, community_b, community_c = (
        CommunityId.generate(),
        CommunityId.generate(),
        CommunityId.generate(),
    )
    group = make_group(member_community_ids=(community_a, community_b, community_c))

    group.remove_member(community_c)

    assert group.member_community_ids == (community_a, community_b)


def test_remove_member_raises_when_dropping_below_minimum() -> None:
    community_a, community_b = CommunityId.generate(), CommunityId.generate()
    group = make_group(member_community_ids=(community_a, community_b))

    with pytest.raises(CommunityGroupBelowMinimumMembersError):
        group.remove_member(community_b)


def test_remove_member_raises_when_not_a_member() -> None:
    group = make_group()

    with pytest.raises(CommunityNotMemberError):
        group.remove_member(CommunityId.generate())
