from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .value_objects import AccountId, RefreshTokenId


class RefreshToken(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: RefreshTokenId
    account_id: AccountId
    token_hash: str
    expires_at: datetime
    revoked: bool = False

    def is_usable(self, *, now: datetime) -> bool:
        return not self.revoked and now < self.expires_at
