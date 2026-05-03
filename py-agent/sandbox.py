import sys, os, re
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

_DANGEROUS_PATTERNS_WIN = [
    r"del\s+[/\\][fFsS]",
    r"rmdir\s+[/\\][sS]\s+[/\\][qQ]",
    r"format\s+\w:",
    r"diskpart",
    r"shutdown\s+[/\\]",
    r"restart-computer",
    r"%0\|%0",
    r"runas\s+[/\\]",
    r"net\s+user\s+",
    r"route\s+",
    r"netsh\s+",
    r"ipconfig\s+[/\\]release",
    r"choco\s+install",
    r"winget\s+install",
    r"reg\s+(delete|add)",
]

_DANGEROUS_PATTERNS_LIN = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshred\b",
    r"\bshutdown\s+-[hrP]",
    r"\breboot\b",
    r"\bpoweroff\b",
    r":\(\)\{\:\|:\&\};:",
    r"\bsudo\b",
    r"\bsu\s+-",
    r"\bchmod\s+4777",
    r"\biptables\b",
    r"\bifconfig\s+down",
    r"\b(apt|yum|dnf|apk)\s+(install|remove|purge)",
    r"pip\s+install\s+--system",
]

_INTERNAL_IPS = [
    r"127\.0\.0\.\d+",
    r"10\.\d+\.\d+\.\d+",
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+",
    r"192\.168\.\d+\.\d+",
    r"169\.254\.169\.254",
]

_DANGEROUS_PATTERNS = _DANGEROUS_PATTERNS_WIN if IS_WINDOWS else _DANGEROUS_PATTERNS_LIN


class CommandValidator:
    def validate(self, command: str, mode: str) -> tuple:
        command_lower = command.lower()
        # mode is reserved for PermissionEnforcer (future use)
        for pat in _DANGEROUS_PATTERNS:
            if re.search(pat, command_lower):
                return False, f"dangerous pattern detected: {pat}"
        if self._has_ssrf(command_lower):
            return False, "command targets internal network (SSRF)"
        return True, ""

    def _has_ssrf(self, cmd: str) -> bool:
        has_http = bool(re.search(r"\b(curl|wget|invoke-webrequest|iwr)\b", cmd))
        if not has_http:
            return False
        for ip_pat in _INTERNAL_IPS:
            if re.search(ip_pat, cmd):
                return True
        return False


_SECRET_ENV_PATTERNS = re.compile(
    r"(key|secret|token|password|credential|auth|api_key|api_secret)",
    re.IGNORECASE
)


class EnvironmentSanitizer:
    def sanitize(self, env: dict) -> dict:
        clean = env.copy()
        keys_to_remove = []
        for k in clean:
            if _SECRET_ENV_PATTERNS.search(k):
                keys_to_remove.append(k)
        for k in keys_to_remove:
            del clean[k]
        return clean


class PathValidator:
    def validate(self, path: str, workspace: Path) -> tuple:
        try:
            resolved = Path(path).resolve()
            ws = workspace.resolve()
            resolved_str = str(resolved)
            ws_str = str(ws)
            if IS_WINDOWS:
                resolved_str = resolved_str.casefold()
                ws_str = ws_str.casefold()
            if not resolved_str.startswith(ws_str):
                return False, "path outside workspace"
            return True, ""
        except Exception as e:
            return False, f"path validation error: {e}"


class OutputTruncator:
    def truncate(self, output: str, max_chars: int = 10000) -> str:
        if len(output) <= max_chars:
            return output
        return output[:max_chars] + f"\n... (truncated, {len(output) - max_chars} more chars)"


import shutil

_UNSHARE_AVAILABLE = not IS_WINDOWS and shutil.which("unshare") is not None
_NAMESPACE_SANDBOX_ENABLED = os.environ.get("LINUX_NAMESPACE_SANDBOX", "").lower() in ("1", "true", "yes")
_NETWORK_ISOLATION = os.environ.get("LINUX_NETWORK_ISOLATION", "").lower() in ("1", "true", "yes")


def wrap_with_namespace(command: str) -> str:
    if IS_WINDOWS or not _UNSHARE_AVAILABLE or not _NAMESPACE_SANDBOX_ENABLED:
        return command
    args = [
        "unshare", "--user", "--map-root-user",
        "--mount", "--ipc", "--pid", "--uts", "--fork",
    ]
    if _NETWORK_ISOLATION:
        args.append("--net")
    args.extend(["sh", "-lc", command])
    return " ".join(args)


import time
import tempfile


def atomic_write(path: str, content: str) -> None:
    """Write content to path atomically (tmp file + rename)."""
    path = os.path.abspath(path)
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".atomic_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(fd)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


class FileLock:
    """Cross-platform file lock using advisory locking."""

    def __init__(self, lock_path: str, timeout: float = 5.0):
        self.lock_path = os.path.abspath(lock_path)
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                self.fd = os.open(self.lock_path + ".lock",
                                  os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                if time.time() > deadline:
                    raise TimeoutError(f"Could not acquire lock for {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, *args):
        if self.fd:
            os.close(self.fd)
        lock_file = self.lock_path + ".lock"
        try:
            os.remove(lock_file)
        except OSError:
            pass
