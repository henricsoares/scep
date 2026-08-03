import secrets

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


def issue_run_credential() -> tuple[str, str]:
    plaintext = secrets.token_urlsafe(48)
    return plaintext, _hasher.hash(plaintext)


def verify_run_credential(plaintext: str, credential_hash: str) -> bool:
    return _hasher.verify(plaintext, credential_hash)
