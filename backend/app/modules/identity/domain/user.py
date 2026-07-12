from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class AccountType(StrEnum):
    HUMAN = "Human"
    TECHNICAL_CLIENT = "TechnicalClient"


class AccountStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class HumanRole(StrEnum):
    PLATFORM_ADMINISTRATOR = "PlatformAdministrator"
    FACILITY_OPERATOR = "FacilityOperator"
    EV_DRIVER = "EVDriver"
    RESEARCHER = "Researcher"
    DATA_SCIENTIST = "DataScientist"


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or not EMAIL_RE.match(normalized):
        raise ValueError("invalid email")
    return normalized


def validate_password(password: str, normalized_email: str) -> None:
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("password must contain a lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("password must contain a numeric character")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("password must contain a special character")
    if normalized_email in password.lower():
        raise ValueError("password must not contain the email address")


@dataclass(frozen=True)
class User:
    id: UUID
    email: str
    display_name: str
    password_hash: str
    account_type: AccountType
    status: AccountStatus
    roles: tuple[HumanRole, ...]
    facility_ids: tuple[UUID, ...]
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        account_type: AccountType,
        status: AccountStatus,
        roles: list[HumanRole],
        facility_ids: list[UUID],
    ) -> User:
        now = datetime.now(UTC)
        user = cls(
            uuid4(),
            normalize_email(email),
            display_name.strip(),
            password_hash,
            account_type,
            status,
            tuple(dict.fromkeys(roles)),
            tuple(dict.fromkeys(facility_ids)),
            now,
            now,
        )
        user.validate()
        return user

    def validate(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display name is required")
        if not self.password_hash:
            raise ValueError("password hash is required")
        if self.account_type == AccountType.HUMAN:
            if self.status == AccountStatus.ACTIVE and not self.roles:
                raise ValueError("Active Human accounts must have at least one Role")
            if self.facility_ids and HumanRole.FACILITY_OPERATOR not in self.roles:
                raise ValueError("Facility assignments require the FacilityOperator Role")
        else:
            if self.roles:
                raise ValueError("Technical Client accounts must not have Human Roles")
            if self.facility_ids:
                raise ValueError("Technical Client accounts must not have Facility assignments")

    def with_profile(
        self, *, display_name: str | None = None, status: AccountStatus | None = None
    ) -> User:
        user = replace(
            self,
            display_name=display_name or self.display_name,
            status=status or self.status,
            updated_at=datetime.now(UTC),
        )
        user.validate()
        return user

    def with_roles(self, roles: list[HumanRole]) -> User:
        user = replace(self, roles=tuple(dict.fromkeys(roles)), updated_at=datetime.now(UTC))
        user.validate()
        return user

    def with_facilities(self, facility_ids: list[UUID]) -> User:
        user = replace(
            self, facility_ids=tuple(dict.fromkeys(facility_ids)), updated_at=datetime.now(UTC)
        )
        user.validate()
        return user

    def with_last_login(self) -> User:
        return replace(self, last_login_at=datetime.now(UTC), updated_at=datetime.now(UTC))
