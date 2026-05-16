#!/usr/bin/env python3
"""Update the model catalog JSON from modelpedia npm package + provider APIs.

Usage:
    python scripts/update-model-catalog.py              # extract from npm package only
    python scripts/update-model-catalog.py --fetch      # also query provider /models APIs
"""

import json
import os
import subprocess
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_UI = os.path.join(PROJECT_ROOT, "web-ui")
OUTPUT = os.path.join(WEB_UI, "public", "model-catalog.json")
MODELPEDIA_CJS = os.path.join(WEB_UI, "node_modules", "modelpedia", "dist", "index.cjs")


def extract_from_npm() -> dict:
    """Extract allModels and providers from the installed modelpedia package."""
    if not os.path.exists(MODELPEDIA_CJS):
        print("modelpedia not installed. Run: cd web-ui && npm install modelpedia")
        sys.exit(1)

    # Try updating to latest version first
    print("  Checking for modelpedia updates...")
    subprocess.run(["npm", "update", "modelpedia"], cwd=WEB_UI, capture_output=True)

    result = subprocess.run(
        ["node", "-e", """
            const m = require(process.argv[1]);
            const data = {
                providers: m.providers,
                models: m.allModels,
                updated: new Date().toISOString().split('T')[0],
            };
            process.stdout.write(JSON.stringify(data));
        """, MODELPEDIA_CJS],
        cwd=WEB_UI,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def fetch_provider_models(name: str, base_url: str, api_key: str = "") -> list[str]:
    """Call a provider's /models endpoint to discover new model IDs."""
    import urllib.request
    import urllib.error

    url = base_url.rstrip("/") + "/models"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return []

    models = data.get("data", [])
    ids = [m["id"] for m in models if "id" in m]

    if not ids:
        models = data.get("models", [])
        ids = [m.get("id") or m.get("name", "") for m in models if isinstance(m, dict)]

    print(f"  ✓ {name}: {len(ids)} models")
    return ids


def merge_new_models(catalog: dict, provider_api_models: dict[str, list[str]]) -> dict:
    """Merge API-discovered model IDs into the catalog.

    New model IDs get minimal stub entries (no metadata from scraping).
    Existing entries from modelpedia keep their rich metadata.
    """
    # Map CocoCat provider name → modelpedia provider ID
    COCOCAT_TO_MP = {
        "gemini": "google",
        "dashscope": "alibaba",
        "aws-bedrock": "amazon",
    }

    existing_ids = {m["id"] for m in catalog["models"]}

    for coco_name, api_ids in provider_api_models.items():
        mp_id = COCOCAT_TO_MP.get(coco_name, coco_name)
        for model_id in api_ids:
            if model_id in existing_ids:
                continue
            existing_ids.add(model_id)
            catalog["models"].append({
                "id": model_id,
                "name": model_id,
                "provider": mp_id,
                "source": "api-discovered",
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "status": "active",
            })

    return catalog


def main():
    fetch_mode = "--fetch" in sys.argv

    print("Extracting modelpedia data...")
    catalog = extract_from_npm()
    print(f"  {len(catalog['models'])} models, {len(catalog['providers'])} providers")

    if fetch_mode:
        print("\nFetching provider /models APIs...")
        auth_path = os.path.join(PROJECT_ROOT, "config", "auth.json")
        auth = {}
        if os.path.exists(auth_path):
            with open(auth_path) as f:
                auth = json.load(f)

        # Provider base URLs for /models API queries
        # Only providers with known /models endpoint support
        PROVIDER_APIS = [
            ("deepseek", "https://api.deepseek.com"),
            ("openai", "https://api.openai.com/v1"),
            ("groq", "https://api.groq.com/openai/v1"),
            ("together", "https://api.together.xyz/v1"),
            ("fireworks", "https://api.fireworks.ai/inference/v1"),
            ("siliconflow", "https://api.siliconflow.cn/v1"),
            ("mistral", "https://api.mistral.ai/v1"),
            ("openrouter", "https://openrouter.ai/api/v1"),
            ("deepinfra", "https://api.deepinfra.com/v1/openai"),
            ("cerebras", "https://api.cerebras.ai/v1"),
            ("xai", "https://api.x.ai/v1"),
            ("moonshot", "https://api.moonshot.cn/v1"),
            ("ollama", "http://localhost:11434/v1"),
        ]

        provider_api_models = {}
        for name, base_url in PROVIDER_APIS:
            key = auth.get(name, "")
            ids = fetch_provider_models(name, base_url, key)
            if ids:
                provider_api_models[name] = ids
        catalog = merge_new_models(catalog, provider_api_models)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\nWritten: {OUTPUT} ({size_kb:.0f} KB)")
    print(f"Total: {len(catalog['models'])} models, updated: {catalog['updated']}")


if __name__ == "__main__":
    main()
