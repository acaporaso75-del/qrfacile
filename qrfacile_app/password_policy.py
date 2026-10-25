MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def new_password_error(password: str) -> str:
    length = len(password or "")
    if length < MIN_PASSWORD_LENGTH:
        return f"Password minimo {MIN_PASSWORD_LENGTH} caratteri."
    if length > MAX_PASSWORD_LENGTH:
        return f"Password massimo {MAX_PASSWORD_LENGTH} caratteri."
    return ""
