from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.quota.create_quota import (
    CommunityNotFoundError,
    CreateQuota,
    OverlappingOrdinaryQuotaError,
)
from src.domain.community.community import Community
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.quota.quota import EmptyQuotaAllocationsError, InvalidQuotaTotalError
from src.domain.quota.value_objects import QuotaType
from tests.fakes.in_memory_community_repository import InMemoryCommunityRepository
from tests.fakes.in_memory_quota_repository import InMemoryQuotaRepository


def make_address() -> Address:
    return Address(
        street="Calle Mayor",
        number="1",
        city="Madrid",
        postal_code="28001",
        province="Madrid",
    )


def make_unit(coefficient: str) -> Unit:
    unit_id = UnitId.generate()
    return Unit(
        id=unit_id,
        identifier=f"unit-{unit_id.value}",
        participation_coefficient=ParticipationCoefficient(value=Decimal(coefficient)),
    )


def make_community(units: tuple[Unit, ...] = ()) -> Community:
    return Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=make_address(),
        cif=CIF(value="H12345674"),
        units=units,
    )


@pytest.mark.asyncio
async def test_creates_quota_with_one_allocation_per_unit() -> None:
    units = (make_unit("0.5"), make_unit("0.5"))
    community = make_community(units)
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()

    use_case = CreateQuota(quota_repository, community_repository)
    quota_id = await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    quota = await quota_repository.get_by_id(quota_id)
    assert quota is not None
    assert quota.total == Decimal("100.00")
    assert {allocation.unit_id for allocation in quota.allocations} == {
        unit.id for unit in units
    }
    assert sum(
        (allocation.amount for allocation in quota.allocations), Decimal("0")
    ) == Decimal("100.00")


@pytest.mark.asyncio
async def test_raises_community_not_found_error_when_community_missing() -> None:
    quota_repository = InMemoryQuotaRepository()
    community_repository = InMemoryCommunityRepository()

    use_case = CreateQuota(quota_repository, community_repository)

    with pytest.raises(CommunityNotFoundError):
        await use_case.execute(
            community_id=uuid4(),
            type=QuotaType.ORDINARY,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            lines=[("Ascensor", Decimal("100.00"))],
        )


@pytest.mark.asyncio
async def test_propagates_empty_allocations_error_when_community_has_no_units() -> None:
    community = make_community(units=())
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()

    use_case = CreateQuota(quota_repository, community_repository)

    with pytest.raises(EmptyQuotaAllocationsError):
        await use_case.execute(
            community_id=community.id.value,
            type=QuotaType.ORDINARY,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            lines=[("Ascensor", Decimal("100.00"))],
        )


@pytest.mark.asyncio
async def test_propagates_invalid_total_error_unchanged() -> None:
    community = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()

    use_case = CreateQuota(quota_repository, community_repository)

    with pytest.raises(InvalidQuotaTotalError):
        await use_case.execute(
            community_id=community.id.value,
            type=QuotaType.ORDINARY,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            lines=[("Ascensor", Decimal("0.00"))],
        )


@pytest.mark.asyncio
async def test_raises_overlapping_ordinary_quota_error() -> None:
    community = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()
    use_case = CreateQuota(quota_repository, community_repository)
    await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 6, 30),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    with pytest.raises(OverlappingOrdinaryQuotaError):
        await use_case.execute(
            community_id=community.id.value,
            type=QuotaType.ORDINARY,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 9, 30),
            lines=[("Ascensor", Decimal("100.00"))],
        )


@pytest.mark.asyncio
async def test_raises_overlapping_ordinary_quota_error_on_shared_boundary_day() -> None:
    community = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()
    use_case = CreateQuota(quota_repository, community_repository)
    await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    with pytest.raises(OverlappingOrdinaryQuotaError):
        await use_case.execute(
            community_id=community.id.value,
            type=QuotaType.ORDINARY,
            period_start=date(2026, 12, 31),
            period_end=date(2027, 6, 30),
            lines=[("Ascensor", Decimal("100.00"))],
        )


@pytest.mark.asyncio
async def test_ordinary_quota_starting_day_after_existing_one_ends_succeeds() -> None:
    community = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()
    use_case = CreateQuota(quota_repository, community_repository)
    await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    quota_id = await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2027, 1, 1),
        period_end=date(2027, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    assert await quota_repository.get_by_id(quota_id) is not None


@pytest.mark.asyncio
async def test_extraordinary_quota_never_checked_against_overlap() -> None:
    community = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community)
    quota_repository = InMemoryQuotaRepository()
    use_case = CreateQuota(quota_repository, community_repository)
    await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )
    await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.EXTRAORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Obra", Decimal("500.00"))],
    )

    extraordinary_quota_id = await use_case.execute(
        community_id=community.id.value,
        type=QuotaType.EXTRAORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Otra obra", Decimal("200.00"))],
    )

    assert await quota_repository.get_by_id(extraordinary_quota_id) is not None


@pytest.mark.asyncio
async def test_overlap_check_is_scoped_per_community() -> None:
    community_a = make_community((make_unit("1"),))
    community_b = make_community((make_unit("1"),))
    community_repository = InMemoryCommunityRepository()
    await community_repository.save(community_a)
    await community_repository.save(community_b)
    quota_repository = InMemoryQuotaRepository()
    use_case = CreateQuota(quota_repository, community_repository)
    await use_case.execute(
        community_id=community_a.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    quota_id = await use_case.execute(
        community_id=community_b.id.value,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[("Ascensor", Decimal("100.00"))],
    )

    assert await quota_repository.get_by_id(quota_id) is not None
