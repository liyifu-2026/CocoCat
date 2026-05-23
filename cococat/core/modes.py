from dataclasses import dataclass
from pathlib import Path

import yaml


def _default_modes_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "modes"


@dataclass(frozen=True)
class ModeConfig:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: tuple[str, ...]
    skills: tuple[str, ...]


def _dict_to_mode_config(data: dict) -> ModeConfig:
    return ModeConfig(
        id=data["id"],
        name=data["name"],
        description=data["description"],
        system_prompt=data["system_prompt"],
        tools=tuple(data.get("tools", [])),
        skills=tuple(data.get("skills", [])),
    )


def load_mode(mode_id: str, modes_dir: Path | None = None) -> ModeConfig:
    dir_ = modes_dir or _default_modes_dir()
    path = dir_ / f"{mode_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Mode config not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return _dict_to_mode_config(data)


def list_modes(modes_dir: Path | None = None) -> list[ModeConfig]:
    dir_ = modes_dir or _default_modes_dir()
    modes = []
    for path in sorted(dir_.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        modes.append(_dict_to_mode_config(data))
    return modes
