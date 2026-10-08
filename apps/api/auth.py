import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

INSECURE_SECRETS = {"supersecret", "secret", "changeme", "your-secret-key", "your_jwt_secret", "test", "supersecret_dev_key"}
SECRET_KEY = os.getenv("JWT_SECRET")

is_testing = os.getenv("ENVIRONMENT") == "test" or os.getenv("TESTING") == "1"

if not SECRET_KEY or SECRET_KEY in INSECURE_SECRETS or len(SECRET_KEY) < 16:
    if is_testing:
        SECRET_KEY = "test_environment_secure_jwt_secret_key_1234567890"
    else:
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: JWT_SECRET environment variable is missing, too short, or set to an insecure default. "
            "The application refuses to start without a real, secure secret (at least 16 characters)."
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    if is_testing:
        fernet = Fernet(Fernet.generate_key())
    else:
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: ENCRYPTION_KEY environment variable is missing. "
            "The application refuses to start without a Fernet encryption key to protect stored tokens."
        )
else:
    try:
        fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    except Exception as e:
        if is_testing:
            fernet = Fernet(Fernet.generate_key())
        else:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: ENCRYPTION_KEY is invalid. It must be a 32-byte url-safe base64 key: {e}")


def encrypt_token(token: str) -> str:
    if not fernet:
        return token
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    if not fernet:
        return encrypted_token
    return fernet.decrypt(encrypted_token.encode()).decode()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
