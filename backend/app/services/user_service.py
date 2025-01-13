"""
User service layer handling all user-related business logic
"""

from sqlmodel import Session
from fastapi import HTTPException

from app.database import models, crud
from app import schemas
from app.core.dependencies import admin_only


class UserService:
    def __init__(self, db: Session):
        self.db = db

    @admin_only()
    async def create_user(
        self, user: schemas.UserCreate, current_user: models.User
    ) -> models.User:
        # Check for existing username
        if await crud.get_user_by_username(self.db, username=user.username):
            raise HTTPException(status_code=400, detail="Username already registered")

        # Check for existing email
        if await crud.get_user_by_email(self.db, email=user.email):
            raise HTTPException(status_code=400, detail="Email already registered")

        return await crud.create_user(self.db, user=user)

    @admin_only()
    async def get_users(
        self, current_user: models.User, skip: int = 0, limit: int = 100
    ) -> list[models.User]:
        return await crud.get_users(self.db, skip=skip, limit=limit)

    async def update_user(
        self, user_id: int, user_update: schemas.UserUpdate, current_user: models.User
    ) -> models.User:
        if current_user.role != "Admin" and current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        db_user = await crud.get_user(self.db, user_id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check username uniqueness if being updated
        if user_update.username and user_update.username != db_user.username:
            existing_user = await crud.get_user_by_username(
                self.db, username=user_update.username
            )
            if existing_user:
                raise HTTPException(status_code=400, detail="Username already taken")

        # Check email uniqueness if being updated
        if user_update.email and user_update.email != db_user.email:
            existing_user = await crud.get_user_by_email(
                self.db, email=user_update.email
            )
            if existing_user:
                raise HTTPException(status_code=400, detail="Email already registered")

        return await crud.update_user(self.db, user_id=user_id, user=user_update)

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_user: models.User,
    ) -> models.User:
        db_user = await crud.get_user(self.db, user_id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        try:
            return await crud.change_user_password(
                self.db,
                user=db_user,
                current_password=current_password,
                new_password=new_password,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @admin_only()
    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: models.User
    ) -> models.User:
        db_user = await crud.get_user(self.db, user_id=user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        return await crud.admin_reset_password(
            self.db, user=db_user, new_password=new_password
        )
