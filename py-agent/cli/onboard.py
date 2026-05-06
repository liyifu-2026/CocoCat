"""Interactive onboarding — configure API keys and test connection."""
import os
import sys
from pathlib import Path


def _find_env_path() -> Path:
    """Find project root .env file."""
    # Walk up from py-agent/ to find project root
    here = Path(__file__).resolve().parent.parent.parent
    return here / ".env"


def _ensure_env():
    """Create .env if it doesn't exist."""
    env_path = _find_env_path()
    if not env_path.exists():
        env_path.write_text("# CocoCat configuration\n")
    return env_path


def _load_env() -> dict:
    """Load existing .env vars (simple parser, no dotenv dep)."""
    env_path = _find_env_path()
    result = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip().strip('"').strip("'")
    return result


def _save_env(updates: dict):
    """Merge updates into .env and write."""
    env_path = _ensure_env()
    existing = _load_env()
    existing.update(updates)
    lines = []
    for k, v in existing.items():
        lines.append(f'{k}="{v}"')
    env_path.write_text("\n".join(lines) + "\n")
    print(f"  Saved to {env_path}")


_PROVIDERS = [
    ("DEEPSEEK_API_KEY", "DeepSeek", "https://api.deepseek.com"),
    ("OPENAI_API_KEY", "OpenAI / Compatible", "https://api.openai.com/v1"),
    ("ANTHROPIC_API_KEY", "Anthropic Claude", "https://api.anthropic.com"),
    ("SILICONFLOW_API_KEY", "SiliconFlow (硅基流动)", "https://api.siliconflow.cn/v1"),
    ("GEMINI_API_KEY", "Google Gemini", "https://generativelanguage.googleapis.com"),
]


def run():
    print()
    print("=" * 50)
    print("  CocoCat  —  Quick Setup")
    print("=" * 50)
    print()

    existing = _load_env()
    updates = {}
    configured = 0

    for env_key, name, default_base in _PROVIDERS:
        current = existing.get(env_key) or os.environ.get(env_key, "")
        if current:
            print(f"  ✓ {name:25s}  already configured")
            configured += 1
            continue

        val = input(f"  {name:25s}  API key (or Enter to skip): ").strip()
        if val:
            updates[env_key] = val
            updates[env_key.replace("_API_KEY", "_BASE_URL")] = default_base
            configured += 1

    print()

    if updates:
        _save_env(updates)
        # Set for current session
        for k, v in updates.items():
            os.environ.setdefault(k, v)

    if configured == 0:
        print("  No API keys configured. Set at least one to use CocoCat.")
        print()
        return

    print(f"\n  {configured} provider(s) configured. Testing connection...\n")

    # Test the first available provider
    test_key = None
    test_model = ""
    for env_key, _, _ in _PROVIDERS:
        key = updates.get(env_key) or existing.get(env_key) or os.environ.get(env_key, "")
        if key:
            test_key = env_key
            if "ANTHROPIC" in env_key:
                test_model = "claude-sonnet-4-20250514"
            elif "GEMINI" in env_key:
                test_model = "gemini-2.0-flash"
            else:
                test_model = "deepseek-chat" if "DEEPSEEK" in env_key else "gpt-4o-mini"
            break

    if test_key:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from providers import make_provider

            provider = make_provider(model=test_model)
            resp = provider.chat_with_retry(
                messages=[{"role": "user", "content": "Say exactly: OK"}],
                max_tokens=10,
                temperature=0,
            )
            if resp.finish_reason != "error":
                print(f"  ✓ Connection OK: {test_model} responded")
            else:
                print(f"  ✗ Connection failed: {resp.content[:100]}")
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")

    print()
    print("  Setup complete! Run 'python py-agent/cli/commands.py agent' to start.")
    print("=" * 50)
    print()


if __name__ == "__main__":
    run()
