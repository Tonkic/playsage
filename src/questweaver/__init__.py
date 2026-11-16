"""Legacy import compatibility; implementation and module identities belong to PlaySage.

Keep historical policies importable without loading a second set of model classes
or creating a separate lock/storage domain. New code must import ``playsage``.
"""

import sys as _sys
from importlib import import_module as _import_module

from playsage import __version__

_MODULES = (
    "runtime", "models", "adapters", "registry", "demo", "evidence",
    "grid_route", "memory", "rule_validation", "offline_cli", "cli",
)

for _name in _MODULES:
    _module = _import_module(f"playsage.{_name}")
    _sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module

__all__ = ["__version__"]
