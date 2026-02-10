import asyncio
from concurrent.futures import ThreadPoolExecutor

import jwt
from passlib import pwd
from passlib.context import CryptContext

from app.schemas.login import JWTPayload
from app.configs import APP_SETTINGS

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# 创建线程池执行器
_executor = ThreadPoolExecutor(max_workers=None)

# ALGORITHM = "HS256"


def create_access_token(*, data: JWTPayload):
    payload = data.model_dump().copy()
    secret_key = str(APP_SETTINGS.SECRET_KEY)
    algorithm = str(APP_SETTINGS.JWT_ALGORITHM)
    encoded_jwt = jwt.encode(payload, secret_key, algorithm=algorithm)
    return encoded_jwt


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    异步验证密码
    使用 run_in_executor 避免阻塞 Event Loop
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, pwd_context.verify, plain_password, hashed_password)


async def get_password_hash(password: str) -> str:
    """
    异步生成密码哈希
    使用 run_in_executor 避免阻塞 Event Loop
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, pwd_context.hash, password)


def verify_password_sync(plain_password: str, hashed_password: str) -> bool:
    """同步验证密码（仅供非 async 环境使用）"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash_sync(password: str) -> str:
    """同步生成密码哈希（仅供非 async 环境使用）"""
    return pwd_context.hash(password)


def generate_password() -> str:
    return pwd.genword()
