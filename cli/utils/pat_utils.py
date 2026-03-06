from pathlib import Path
from cryptography.fernet import Fernet

KEY_PATH = Path.home() / ".shellai_github_token.key"
TOKEN_PATH = Path.home() / ".shellai_github_token"

def load_or_create_key():
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    return key

def save_github_token(token):
    key = load_or_create_key()
    f = Fernet(key)
    encrypted = f.encrypt(token.encode())

    TOKEN_PATH.write_bytes(encrypted)
    print("GitHub token saved securely.")

def get_github_token():
    if not KEY_PATH.exists() or not TOKEN_PATH.exists():
        return None
    
    key = KEY_PATH.read_bytes()
    encrypted = TOKEN_PATH.read_bytes()
    f = Fernet(key)
    return f.decrypt(encrypted).decode()
