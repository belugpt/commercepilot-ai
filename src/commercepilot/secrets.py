"""Local Windows secrets use user-scoped DPAPI; other hosts inject environment."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

ALLOWED = frozenset({"WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_GRAPH_VERSION", "WHATSAPP_SEND_ENABLED", "WHATSAPP_MEDIA_ENABLED",
    "OPENAI_API_KEY", "COMMERCEPILOT_MODEL", "COMMERCEPILOT_PLANNER"})


def crypt(data: bytes, decrypt=False):
    if os.name != "nt":
        raise RuntimeError("Local secret storage requires Windows DPAPI; use environment secrets on this host")
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = api.CryptUnprotectData if decrypt else api.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Local secret protection failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


def read_secrets(path):
    target = Path(path)
    if not target.exists():
        return {}
    data = json.loads(crypt(target.read_bytes(), decrypt=True))
    if not isinstance(data, dict) or set(data) - ALLOWED or not all(isinstance(v, str) for v in data.values()):
        raise ValueError("Invalid local secret configuration")
    return data


def save_secrets(path, values):
    if set(values) - ALLOWED or not all(isinstance(v, str) and v for v in values.values()):
        raise ValueError("Unsupported or empty secret setting")
    target = Path(path)
    merged = {**read_secrets(target), **values}
    encrypted = crypt(json.dumps(merged).encode())
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_suffix(".tmp")
    staging.write_bytes(encrypted)
    staging.replace(target)


def load_environment(path):
    for name, value in read_secrets(path).items():
        os.environ.setdefault(name, value)
