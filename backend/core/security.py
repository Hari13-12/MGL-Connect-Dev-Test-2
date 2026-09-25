import re
from argon2 import PasswordHasher, Type

_hasher = PasswordHasher(type=Type.ID)


def validate_password(password: str, minimum: int) -> bool:
    return (len(password) >= minimum and bool(re.search(r"[a-z]", password))
            and bool(re.search(r"[A-Z]", password)) and bool(re.search(r"\d", password))
            and bool(re.search(r"[^A-Za-z0-9]", password)))


def hash_password(password: str) -> str:
    return _hasher.hash(password)
