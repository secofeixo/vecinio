from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.identity.account import (
    Account,
    ConcurrentModificationError,
    DuplicateEmailError,
)
from src.domain.identity.repository import AccountRepository
from src.domain.identity.value_objects import AccountId, Email
from src.domain.owner.value_objects import OwnerId

from .models import AccountModel

_EMAIL_UNIQUE_CONSTRAINT = "uq_accounts_email"


class PostgresAccountRepository(AccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, account: Account) -> None:
        expected_version = account.version
        new_version = expected_version + 1
        stmt = pg_insert(AccountModel).values(
            id=account.id.value,
            email=account.email.value,
            password_hash=account.password_hash,
            owner_id=account.owner_id.value if account.owner_id is not None else None,
            version=new_version,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AccountModel.id],
            set_={
                "email": stmt.excluded.email,
                "password_hash": stmt.excluded.password_hash,
                "owner_id": stmt.excluded.owner_id,
                "version": stmt.excluded.version,
            },
            # Only takes effect on the update path (a brand-new row always
            # inserts regardless of expected_version): if another transaction
            # already advanced the version past what this aggregate was read
            # at, the WHERE fails, the update is skipped, and the statement
            # affects zero rows instead of silently overwriting the newer data.
            where=(AccountModel.version == expected_version),
        )
        # rowcount is unreliable for INSERT ... ON CONFLICT DO UPDATE ... WHERE
        # with the async psycopg driver (reports -1), so RETURNING is used to
        # detect a skipped update instead: a row comes back on insert or a
        # matched update, nothing comes back when the WHERE excludes the row.
        try:
            result = await self._session.execute(stmt.returning(AccountModel.id))
        except IntegrityError as error:
            # Any IntegrityError leaves the underlying connection in an aborted
            # transaction, unusable until rolled back. Roll back here rather
            # than leaving it to the caller: once translated into a domain
            # exception below, nothing about that exception signals that the
            # session itself is broken.
            await self._session.rollback()
            if self._violates_email_uniqueness(error):
                raise DuplicateEmailError(
                    f"An account with email {account.email.value} already exists"
                ) from error
            raise

        if result.first() is None:
            raise ConcurrentModificationError(
                f"Account {account.id.value} was modified concurrently; "
                f"expected version {expected_version}"
            )
        account.version = new_version

    async def get_by_id(self, account_id: AccountId) -> Account | None:
        stmt = select(AccountModel).where(AccountModel.id == account_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def get_by_email(self, email: Email) -> Account | None:
        stmt = select(AccountModel).where(AccountModel.email == email.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    @staticmethod
    def _violates_email_uniqueness(error: IntegrityError) -> bool:
        diag = getattr(error.orig, "diag", None)
        return getattr(diag, "constraint_name", None) == _EMAIL_UNIQUE_CONSTRAINT

    @staticmethod
    def _to_domain(model: AccountModel) -> Account:
        return Account(
            id=AccountId(value=model.id),
            email=Email(value=model.email),
            password_hash=model.password_hash,
            owner_id=(
                OwnerId(value=model.owner_id) if model.owner_id is not None else None
            ),
            version=model.version,
        )
