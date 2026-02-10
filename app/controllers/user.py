from datetime import datetime

from tortoise.transactions import in_transaction

from app.core.crud import CRUDBase
from app.core.constants import ErrorCode
from app.core.exceptions import HTTPException
from app.models.system import LogDetailType, LogType, Role, StatusType, User, Log
from app.schemas.login import CredentialsSchema
from app.schemas.users import UserCreate, UserUpdate, UserSearch
from app.utils.security import get_password_hash, verify_password


class UserController(CRUDBase[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(model=User)

    async def get_by_email(self, user_email: str) -> User | None:
        return await self.model.filter(user_email=user_email).first()

    async def get_by_username(self, user_name: str) -> User | None:
        return await self.model.filter(user_name=user_name).first()

    async def create(self, obj_in: UserCreate) -> User:  # type: ignore
        # 密码哈希计算移到事务外（异步且不阻塞）
        obj_in.password = await get_password_hash(password=obj_in.password)

        if not obj_in.nick_name:
            obj_in.nick_name = obj_in.user_name

        async with in_transaction():
            obj = await super().create(
                obj_in, exclude={"byUserRoles", "by_user_role_code_list"}
            )
            if obj_in.by_user_role_code_list:
                await self.update_roles_by_code(obj, obj_in.by_user_role_code_list)
            return obj

    async def update(self, user_id: int, obj_in: UserUpdate) -> User:  # type: ignore
        # 密码哈希计算移到事务外（异步且不阻塞）
        if obj_in.password:
            obj_in.password = await get_password_hash(password=obj_in.password)
        else:
            obj_in.password = None
            
        try:
            async with in_transaction():
                obj = await super().update(
                    id=user_id, obj_in=obj_in, exclude={"byUserRoles", "by_user_role_code_list"}
                )
                if obj_in.by_user_role_code_list:
                    await self.update_roles_by_code(obj, obj_in.by_user_role_code_list)
                return obj
        except Exception as e:
            import traceback
            from loguru import logger
            logger.error(f"Failed to update user {user_id}: {e}")
            logger.error(traceback.format_exc())
            raise e

    async def update_last_login(self, user_id: int) -> None:
        user = await self.model.get(id=user_id)
        user.last_login = datetime.now()
        await user.save()

    async def authenticate(self, credentials: CredentialsSchema) -> User:
        user = await self.model.filter(user_name=credentials.user_name).first()

        if not user:
            await Log.create(
                log_type=LogType.UserLog, by_user=None, log_detail_type=LogDetailType.UserLoginUserNameVaild
            )
            raise HTTPException(code=ErrorCode.AUTH_LOGIN_FAILED, msg="Incorrect username or password!")

        verified = await verify_password(credentials.password, user.password)

        if not verified:
            await Log.create(
                log_type=LogType.UserLog, by_user=user, log_detail_type=LogDetailType.UserLoginErrorPassword
            )
            raise HTTPException(code=ErrorCode.AUTH_LOGIN_FAILED, msg="Incorrect username or password!")

        if user.status_type == StatusType.disable:
            await Log.create(log_type=LogType.UserLog, by_user=user, log_detail_type=LogDetailType.UserLoginForbid)
            raise HTTPException(code=ErrorCode.AUTH_LOGIN_FAILED, msg="This user has been disabled.")

        return user

    async def search(self, obj_in: UserSearch) -> tuple[int, list[User]]:
        """
        高级搜索用户
        """
        from tortoise.expressions import Q

        q = Q()
        if obj_in.user_name:
            q &= Q(user_name__contains=obj_in.user_name)
        if obj_in.user_gender:
            q &= Q(user_gender=obj_in.user_gender)
        if obj_in.nick_name:
            q &= Q(nick_name__contains=obj_in.nick_name)
        if obj_in.user_phone:
            q &= Q(user_phone__contains=obj_in.user_phone)
        if obj_in.user_email:
            q &= Q(user_email__contains=obj_in.user_email)
        if obj_in.status_type:
            q &= Q(status_type=obj_in.status_type)
        if obj_in.by_user_role_code_list:
            q &= Q(by_user_roles__role_code__in=obj_in.by_user_role_code_list)

        return await self.list(
            page=obj_in.current,
            page_size=obj_in.size,
            search=q,
            order=["id"],
            prefetch=["by_user_roles"],
            distinct=True,  # 涉及多对多关联查询，必须去重
        )

    @staticmethod
    async def update_roles(user: User, role_id_list: list[int] | str) -> bool:
        if not role_id_list:
            return False

        if isinstance(role_id_list, str):
            role_id_list = role_id_list.split("|")

        await user.by_user_roles.clear()
        user_role_objs = await Role.filter(id__in=role_id_list)

        for user_role_obj in user_role_objs:
            await user.by_user_roles.add(user_role_obj)

        return True

    @staticmethod
    async def update_roles_by_code(user: User, roles_code_list: list[str] | str) -> bool:
        if not roles_code_list:
            return False

        if isinstance(roles_code_list, str):
            roles_code_list = roles_code_list.split("|")

        user_role_objs = await Role.filter(role_code__in=roles_code_list)
        await user.by_user_roles.clear()
        for user_role_obj in user_role_objs:
            await user.by_user_roles.add(user_role_obj)

        return True


user_controller = UserController()
