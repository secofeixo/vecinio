from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from src.domain.community.community import Community
from src.domain.community.unit import Unit
from src.domain.community.value_objects import (
    CIF,
    Address,
    CommunityId,
    ParticipationCoefficient,
    UnitId,
)
from src.domain.quota.quota import ConcurrentModificationError, Quota
from src.domain.quota.quota_allocation import QuotaAllocation
from src.domain.quota.quota_line import QuotaLine
from src.domain.quota.value_objects import QuotaId, QuotaType
from src.infrastructure.persistence.community_repository import (
    PostgresCommunityRepository,
)
from src.infrastructure.persistence.quota_repository import PostgresQuotaRepository


async def make_persisted_community(
    session: AsyncSession,
    coefficients: tuple[str, ...] = ("1",),
    cif: str = "H12345674",
) -> Community:
    units = tuple(
        Unit(
            id=UnitId.generate(),
            identifier=f"unit-{index}",
            participation_coefficient=ParticipationCoefficient(value=Decimal(value)),
        )
        for index, value in enumerate(coefficients)
    )
    community = Community(
        id=CommunityId.generate(),
        name="Edificio Sol",
        address=Address(
            street="Calle Mayor",
            number="1",
            city="Madrid",
            postal_code="28001",
            province="Madrid",
        ),
        cif=CIF(value=cif),
        units=units,
    )
    await PostgresCommunityRepository(session).save(community)
    await session.commit()
    return community


def make_quota(
    community: Community,
    period_start: date = date(2026, 1, 1),  # noqa: B008
    period_end: date = date(2026, 12, 31),  # noqa: B008
    type: QuotaType = QuotaType.ORDINARY,  # noqa: B008
    total: Decimal = Decimal("100.00"),  # noqa: B008
) -> Quota:
    unit = community.units[0]
    return Quota(
        id=QuotaId.generate(),
        community_id=community.id,
        type=type,
        period_start=period_start,
        period_end=period_end,
        lines=(QuotaLine(concept="Ascensor", amount=total),),
        allocations=(
            QuotaAllocation(
                unit_id=unit.id,
                participation_coefficient=unit.participation_coefficient.value,
                amount=total,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_save_and_get_by_id_round_trips_all_fields(session: AsyncSession) -> None:
    community = await make_persisted_community(session)
    quota = make_quota(community)
    repository = PostgresQuotaRepository(session)

    await repository.save(quota)
    await session.commit()

    fetched = await repository.get_by_id(quota.id)

    assert fetched is not None
    assert fetched.id == quota.id
    assert fetched.community_id == quota.community_id
    assert fetched.type == quota.type
    assert fetched.period_start == quota.period_start
    assert fetched.period_end == quota.period_end
    assert fetched.lines == quota.lines
    assert fetched.total == quota.total
    assert fetched.allocations == quota.allocations
    assert fetched.supersedes_quota_id is None


@pytest.mark.asyncio
async def test_round_trips_multiple_lines_and_allocations_in_order(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session, coefficients=("0.6", "0.4"))
    lines = (
        QuotaLine(concept="Ascensor", amount=Decimal("70.00")),
        QuotaLine(concept="Jardín", amount=Decimal("30.00")),
    )
    allocations = (
        QuotaAllocation(
            unit_id=community.units[0].id,
            participation_coefficient=community.units[
                0
            ].participation_coefficient.value,
            amount=Decimal("60.00"),
        ),
        QuotaAllocation(
            unit_id=community.units[1].id,
            participation_coefficient=community.units[
                1
            ].participation_coefficient.value,
            amount=Decimal("40.00"),
        ),
    )
    quota = Quota(
        id=QuotaId.generate(),
        community_id=community.id,
        type=QuotaType.ORDINARY,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=lines,
        allocations=allocations,
    )
    repository = PostgresQuotaRepository(session)

    await repository.save(quota)
    await session.commit()

    fetched = await repository.get_by_id(quota.id)

    assert fetched is not None
    assert fetched.lines == lines
    assert fetched.allocations == allocations


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(session: AsyncSession) -> None:
    repository = PostgresQuotaRepository(session)

    fetched = await repository.get_by_id(QuotaId.generate())

    assert fetched is None


@pytest.mark.asyncio
async def test_save_called_twice_updates_instead_of_duplicating(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    quota = make_quota(community)
    repository = PostgresQuotaRepository(session)

    await repository.save(quota)
    await session.commit()

    # There is no update use case yet, but the repository contract must still
    # support re-saving the same aggregate instance without duplicating rows
    # (save() bumps quota.version internally on the first call above).
    await repository.save(quota)
    await session.commit()

    count = await session.execute(
        text("SELECT count(*) FROM quotas WHERE id = :id"), {"id": quota.id.value}
    )
    assert count.scalar_one() == 1

    line_count = await session.execute(
        text("SELECT count(*) FROM quota_lines WHERE quota_id = :id"),
        {"id": quota.id.value},
    )
    assert line_count.scalar_one() == 1

    allocation_count = await session.execute(
        text("SELECT count(*) FROM quota_allocations WHERE quota_id = :id"),
        {"id": quota.id.value},
    )
    assert allocation_count.scalar_one() == 1


@pytest.mark.asyncio
async def test_concurrent_save_raises_concurrent_modification_error(
    postgres_container: PostgresContainer, session: AsyncSession
) -> None:
    community = await make_persisted_community(session)
    quota = make_quota(community)
    setup_repository = PostgresQuotaRepository(session)
    await setup_repository.save(quota)
    await session.commit()

    url = postgres_container.get_connection_url()
    engine_two = create_async_engine(url)
    session_factory_two = async_sessionmaker(engine_two, expire_on_commit=False)

    try:
        async with session_factory_two() as session_two:
            repository_one = PostgresQuotaRepository(session)
            repository_two = PostgresQuotaRepository(session_two)

            quota_one = await repository_one.get_by_id(quota.id)
            quota_two = await repository_two.get_by_id(quota.id)
            assert quota_one is not None
            assert quota_two is not None

            # Quota has no mutating method in this increment, so both copies
            # are saved unmodified — what matters is that both were read at
            # the same version: the first save advances it, so the second
            # save's WHERE version = expected_version must find no match.
            await repository_one.save(quota_one)
            await session.commit()

            with pytest.raises(ConcurrentModificationError):
                await repository_two.save(quota_two)
            await session_two.rollback()
    finally:
        await engine_two.dispose()


@pytest.mark.asyncio
async def test_exists_overlapping_ordinary_true_for_genuinely_overlapping_periods(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    existing = make_quota(
        community, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
    )
    repository = PostgresQuotaRepository(session)
    await repository.save(existing)
    await session.commit()

    overlaps = await repository.exists_overlapping_ordinary(
        community.id, date(2026, 6, 1), date(2027, 6, 30)
    )

    assert overlaps is True


@pytest.mark.asyncio
async def test_exists_overlapping_ordinary_true_on_shared_boundary_day(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    existing = make_quota(
        community, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
    )
    repository = PostgresQuotaRepository(session)
    await repository.save(existing)
    await session.commit()

    # Existing quota ends 2026-12-31; new one starts on the exact same day —
    # inclusive on both bounds, so this must count as overlapping.
    overlaps = await repository.exists_overlapping_ordinary(
        community.id, date(2026, 12, 31), date(2027, 1, 15)
    )

    assert overlaps is True


@pytest.mark.asyncio
async def test_exists_overlapping_ordinary_false_for_genuinely_disjoint_periods(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    existing = make_quota(
        community, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
    )
    repository = PostgresQuotaRepository(session)
    await repository.save(existing)
    await session.commit()

    # Genuinely back-to-back, non-overlapping: the new period starts the day
    # after the existing one ends.
    overlaps = await repository.exists_overlapping_ordinary(
        community.id, date(2027, 1, 1), date(2027, 12, 31)
    )

    assert overlaps is False


@pytest.mark.asyncio
async def test_exists_overlapping_ordinary_false_across_different_communities(
    session: AsyncSession,
) -> None:
    community_a = await make_persisted_community(session, cif="H12345674")
    community_b = await make_persisted_community(
        session, coefficients=("0.5", "0.5"), cif="A58818501"
    )
    existing = make_quota(
        community_a, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31)
    )
    repository = PostgresQuotaRepository(session)
    await repository.save(existing)
    await session.commit()

    overlaps = await repository.exists_overlapping_ordinary(
        community_b.id, date(2026, 1, 1), date(2026, 12, 31)
    )

    assert overlaps is False


@pytest.mark.asyncio
async def test_exists_overlapping_ordinary_false_when_only_extraordinary_overlaps(
    session: AsyncSession,
) -> None:
    community = await make_persisted_community(session)
    existing = make_quota(
        community,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        type=QuotaType.EXTRAORDINARY,
    )
    repository = PostgresQuotaRepository(session)
    await repository.save(existing)
    await session.commit()

    overlaps = await repository.exists_overlapping_ordinary(
        community.id, date(2026, 1, 1), date(2026, 12, 31)
    )

    assert overlaps is False
