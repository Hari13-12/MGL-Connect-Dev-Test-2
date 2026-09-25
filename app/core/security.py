import re

from argon2 import PasswordHasher

from app.core.config import settings

_hasher = PasswordHasher()


def validate_password(password: str) -> None:
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError("Password does not meet security requirements")
    if not all(re.search(pattern, password) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w\s]")):
        raise ValueError("Password does not meet security requirements")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)
