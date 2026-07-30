from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from src.domain.community.value_objects import CommunityId

from .value_objects import CommunityGroupId

_MINIMUM_MEMBERS = 2
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    without_marks = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    slug = _NON_ALPHANUMERIC.sub("-", without_marks.lower())
    return slug.strip("-")


class CommunityGroupDomainError(Exception):
    pass


class InvalidCommunityGroupNameError(CommunityGroupDomainError):
    pass


class CommunityGroupBelowMinimumMembersError(CommunityGroupDomainError):
    pass


class CommunityAlreadyMemberError(CommunityGroupDomainError):
    pass


class CommunityNotMemberError(CommunityGroupDomainError):
    pass


class DuplicateCommunityGroupSlugError(CommunityGroupDomainError):
    pass


class ConcurrentModificationError(CommunityGroupDomainError):
    pass


class CommunityGroup(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: CommunityGroupId
    name: str
    member_community_ids: tuple[CommunityId, ...]
    version: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        return _slugify(self.name)

    @model_validator(mode="after")
    def _check_invariants(self) -> CommunityGroup:
        self._check_name_is_valid(self.name)
        self._check_members_are_valid(self.member_community_ids)
        return self

    def add_member(self, community_id: CommunityId) -> None:
        if community_id in self.member_community_ids:
            raise CommunityAlreadyMemberError(
                f"Community {community_id} is already a member of this group"
            )
        self.member_community_ids = self.member_community_ids + (community_id,)

    def remove_member(self, community_id: CommunityId) -> None:
        if community_id not in self.member_community_ids:
            raise CommunityNotMemberError(
                f"Community {community_id} is not a member of this group"
            )
        remaining = tuple(
            member for member in self.member_community_ids if member != community_id
        )
        if len(remaining) < _MINIMUM_MEMBERS:
            raise CommunityGroupBelowMinimumMembersError(
                f"A community group must have at least {_MINIMUM_MEMBERS} members"
            )
        self.member_community_ids = remaining

    @classmethod
    def _check_name_is_valid(cls, name: str) -> None:
        if not name.strip():
            raise InvalidCommunityGroupNameError(
                "Community group name must not be empty"
            )
        if not _slugify(name):
            raise InvalidCommunityGroupNameError(
                f"Community group name {name!r} does not yield a valid slug"
            )

    @staticmethod
    def _check_members_are_valid(member_community_ids: tuple[CommunityId, ...]) -> None:
        if len(member_community_ids) < _MINIMUM_MEMBERS:
            raise CommunityGroupBelowMinimumMembersError(
                f"A community group must have at least {_MINIMUM_MEMBERS} members"
            )
        if len(set(member_community_ids)) != len(member_community_ids):
            raise ValueError("Member community ids must be unique within a group")
