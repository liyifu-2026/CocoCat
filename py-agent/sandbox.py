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
