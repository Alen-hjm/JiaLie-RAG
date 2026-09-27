from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from .config import get_settings

password_hash = PasswordHash((BcryptHasher(), Argon2Hasher()))
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_token(subject: str) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": subject, "exp": expiry}, get_settings().secret_key, algorithm=ALGORITHM)


def read_token(token: str) -> str | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM]).get("sub")
    except JWTError:
        return None
