import bcrypt


def hash_password(plain_password: str) -> str:
    # Generate salt
    salt = bcrypt.gensalt(rounds=12)

    # Hash password (returns bytes)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)

    # Convert bytes → string for DB storage
    return hashed.decode("utf-8")


def verify_password(plain_password: str, stored_hash: str) -> bool:
    # Convert stored string → bytes
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        stored_hash.encode("utf-8")
    )