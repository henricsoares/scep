from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_model import RoleModel, UserFacilityModel, UserModel

FIXED_ROLES = [r.value for r in HumanRole]


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def seed_roles(self) -> None:
        existing = set(self.session.scalars(select(RoleModel.name)).all())
        for name in FIXED_ROLES:
            if name not in existing:
                self.session.add(RoleModel(id=uuid4(), name=name))
        self.session.commit()

    def add(self, user: User) -> User:
        self.seed_roles()
        model = self._to_model(user)
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        return self.get(user.id) or user

    def get(self, user_id: UUID) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.roles), selectinload(UserModel.facilities))
            .where(UserModel.id == user_id)
        )
        model = self.session.scalar(stmt)
        return None if model is None else self._to_domain(model)

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.roles), selectinload(UserModel.facilities))
            .where(UserModel.email == email)
        )
        model = self.session.scalar(stmt)
        return None if model is None else self._to_domain(model)

    def list(
        self,
        *,
        status: AccountStatus | None = None,
        role: HumanRole | None = None,
        account_type: AccountType | None = None,
    ) -> list[User]:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.roles), selectinload(UserModel.facilities))
            .order_by(UserModel.created_at)
        )
        if status:
            stmt = stmt.where(UserModel.status == status.value)
        if account_type:
            stmt = stmt.where(UserModel.account_type == account_type.value)
        models = list(self.session.scalars(stmt).unique().all())
        users = [self._to_domain(m) for m in models]
        if role:
            users = [u for u in users if role in u.roles]
        return users

    def update(self, user: User) -> User:
        self.seed_roles()
        model = self.session.get(UserModel, user.id)
        if model is None:
            raise ValueError("user not found")
        model.display_name = user.display_name
        model.status = user.status.value
        model.updated_at = user.updated_at
        model.last_login_at = user.last_login_at
        role_map = {r.name: r for r in self.session.scalars(select(RoleModel)).all()}
        model.roles = [role_map[r.value] for r in user.roles]
        model.facilities = [
            UserFacilityModel(user_id=user.id, facility_id=f) for f in user.facility_ids
        ]
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        return self.get(user.id) or user

    def active_admin_count(self, *, exclude_id: UUID | None = None) -> int:
        users = self.list(status=AccountStatus.ACTIVE, role=HumanRole.PLATFORM_ADMINISTRATOR)
        return len([u for u in users if u.id != exclude_id])

    def platform_admin_exists(self) -> bool:
        return bool(self.list(role=HumanRole.PLATFORM_ADMINISTRATOR, status=AccountStatus.ACTIVE))

    def _to_model(self, user: User) -> UserModel:
        role_map = {r.name: r for r in self.session.scalars(select(RoleModel)).all()}
        return UserModel(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            password_hash=user.password_hash,
            account_type=user.account_type.value,
            status=user.status.value,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            roles=[role_map[r.value] for r in user.roles],
            facilities=[
                UserFacilityModel(user_id=user.id, facility_id=f) for f in user.facility_ids
            ],
        )

    def _to_domain(self, m: UserModel) -> User:
        return User(
            id=m.id,
            email=m.email,
            display_name=m.display_name,
            password_hash=m.password_hash,
            account_type=AccountType(m.account_type),
            status=AccountStatus(m.status),
            roles=tuple(HumanRole(r.name) for r in sorted(m.roles, key=lambda r: r.name)),
            facility_ids=tuple(f.facility_id for f in m.facilities),
            created_at=m.created_at,
            updated_at=m.updated_at,
            last_login_at=m.last_login_at,
        )
