"""The package contract is independent of each upstream runtime."""

import hashlib
import stat
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Game = Literal["zzz", "ww", "ef", "hsr"]
Backend = Literal["maa", "sra", "onedragon", "ok-ww", "ok-ef", "mock"]
Status = Literal["draft", "candidate", "verified", "stale"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Compatibility(StrictModel):
    resolution: list[int] = Field(min_length=2, max_length=2)
    game_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def positive_resolution(self):
        if any(n <= 0 for n in self.resolution):
            raise ValueError("resolution must contain positive width and height")
        return self


class Execution(StrictModel):
    preferred_backend: Backend
    supported_backends: list[Backend] = Field(min_length=1)


class Entrypoint(StrictModel):
    type: Literal["pipeline", "python", "native"]
    path: str = Field(min_length=1)


class Verification(StrictModel):
    required_scene: str = Field(min_length=1)
    fresh_screenshot: Literal[True] = True


class Limits(StrictModel):
    max_retries: int = Field(default=0, ge=0, le=10)
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    max_actions: int = Field(default=20, ge=1, le=1000)


class EventManifest(StrictModel):
    id: str = Field(pattern=r"^(zzz|ww|ef|hsr)\.[a-z0-9][a-z0-9-]*$")
    game: Game
    name: str = Field(min_length=1)
    gameplay: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    status: Status = "draft"
    compatibility: Compatibility
    execution: Execution
    entrypoints: dict[Backend, Entrypoint]
    verification: Verification
    limits: Limits = Field(default_factory=Limits)

    @model_validator(mode="after")
    def coherent(self):
        if self.id.split(".")[0] != self.game:
            raise ValueError("event id must start with its game")
        supported = self.execution.supported_backends
        if len(supported) != len(set(supported)):
            raise ValueError("duplicate supported backend")
        if self.execution.preferred_backend not in supported:
            raise ValueError("preferred backend is not supported")
        if set(supported) != set(self.entrypoints):
            raise ValueError("every supported backend requires exactly one entrypoint")
        return self


def package_file(root: Path, relative: str) -> Path:
    # Reject Windows paths on POSIX as well as on Windows.
    if "\\" in relative or ":" in relative or PurePosixPath(relative).is_absolute():
        raise ValueError("package paths must use relative POSIX paths")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing file or path outside package: {relative}")
    return path


def is_redirect(path: Path) -> bool:
    # Windows directory junctions are reparse points, not necessarily symlinks.
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def load_package(root: Path) -> tuple[EventManifest, str]:
    if is_redirect(root):
        raise ValueError(f"linked package roots are not allowed: {root}")
    root = root.resolve()
    manifest_path = package_file(root, "event.yaml")
    try:
        data = yaml.safe_load(manifest_path.read_text("utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid event YAML: {manifest_path}") from exc
    manifest = EventManifest.model_validate(data)
    package_file(root, "SKILL.md")
    for entry in manifest.entrypoints.values():
        package_file(root, entry.path)
    digest = hashlib.sha256()
    # Rules, assets and tests are all part of the reviewed version.
    for file in sorted(root.rglob("*")):
        if "__pycache__" in file.parts or file.suffix == ".pyc":
            continue
        if is_redirect(file):
            raise ValueError(f"links are not allowed in event packages: {file}")
        if file.is_file():
            relative = file.relative_to(root).as_posix()
            digest.update(relative.encode() + b"\0" + file.read_bytes() + b"\0")
    return manifest, digest.hexdigest()
