from dataclasses import dataclass
from pathlib import Path

import yaml


MODES_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "modes"


@dataclass(frozen=True)
class ModeConfig:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _dict_to_mode_config(data: dict) -> ModeConfig:
    return ModeConfig(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        system_prompt=data["system_prompt"],
        tools=tuple(data.get("tools", [])),
        skills=tuple(data.get("skills", [])),
    )


def load_mode(mode_id: str) -> ModeConfig:
    path = MODES_DIR / f"{mode_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Mode config not found: {path}")
    return _dict_to_mode_config(_load_yaml(path))


def list_modes() -> list[ModeConfig]:
    modes = []
    for path in sorted(MODES_DIR.glob("*.yaml")):
        modes.append(_dict_to_mode_config(_load_yaml(path)))
    return modes
