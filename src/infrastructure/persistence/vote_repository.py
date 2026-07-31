from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.community.value_objects import CommunityId
from src.domain.identity.value_objects import AccountId
from src.domain.vote.repository import VoteRepository
from src.domain.vote.value_objects import VoteId
from src.domain.vote.vote import ConcurrentModificationError, Vote
from src.domain.vote.vote_option import VoteOption
from src.domain.vote.vote_result import VoteResult

from .models import VoteModel


class PostgresVoteRepository(VoteRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, vote: Vote) -> None:
        expected_version = vote.version
        new_version = expected_version + 1
        stmt = pg_insert(VoteModel).values(
            id=vote.id.value,
            community_id=vote.community_id.value,
            title=vote.title,
            description=vote.description,
            options=[option.model_dump(mode="json") for option in vote.options],
            end_date=vote.end_date,
            created_by_account_id=vote.created_by_account_id.value,
            result=(
                vote.result.model_dump(mode="json") if vote.result is not None else None
            ),
            version=new_version,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VoteModel.id],
            set_={
                "community_id": stmt.excluded.community_id,
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "options": stmt.excluded.options,
                "end_date": stmt.excluded.end_date,
                "created_by_account_id": stmt.excluded.created_by_account_id,
                "result": stmt.excluded.result,
                "version": stmt.excluded.version,
            },
            # Only takes effect on the update path (a brand-new row always
            # inserts regardless of expected_version): if another transaction
            # already advanced the version past what this aggregate was read
            # at, the WHERE fails, the update is skipped, and the statement
            # affects zero rows instead of silently overwriting the newer data.
            where=(VoteModel.version == expected_version),
        )
        # rowcount is unreliable for INSERT ... ON CONFLICT DO UPDATE ... WHERE
        # with the async psycopg driver (reports -1), so RETURNING is used to
        # detect a skipped update instead: a row comes back on insert or a
        # matched update, nothing comes back when the WHERE excludes the row.
        try:
            result = await self._session.execute(stmt.returning(VoteModel.id))
        except IntegrityError:
            # Any IntegrityError leaves the underlying connection in an
            # aborted transaction, unusable until rolled back.
            await self._session.rollback()
            raise

        if result.first() is None:
            raise ConcurrentModificationError(
                f"Vote {vote.id.value} was modified concurrently; expected "
                f"version {expected_version}"
            )
        vote.version = new_version

    async def get_by_id(self, vote_id: VoteId) -> Vote | None:
        stmt = select(VoteModel).where(VoteModel.id == vote_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def exists_open_vote_for_community(self, community_id: CommunityId) -> bool:
        stmt = select(
            select(VoteModel.id)
            .where(
                VoteModel.community_id == community_id.value,
                VoteModel.result.is_(None),
            )
            .exists()
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())

    @staticmethod
    def _to_domain(model: VoteModel) -> Vote:
        return Vote(
            id=VoteId(value=model.id),
            community_id=CommunityId(value=model.community_id),
            title=model.title,
            description=model.description,
            options=tuple(
                VoteOption.model_validate(option) for option in model.options
            ),
            end_date=model.end_date,
            created_by_account_id=AccountId(value=model.created_by_account_id),
            result=(
                VoteResult.model_validate(model.result)
                if model.result is not None
                else None
            ),
            version=model.version,
        )
