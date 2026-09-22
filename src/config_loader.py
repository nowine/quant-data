"""File loader for etf_config.json — reads, parses, validates.

This is the file-IO seam that sits between config.py (which exposes the 4 list
constants) and the JSON file on disk. It owns:
- File reading (utf-8)
- JSON parsing
- Schema validation (delegates to config_schema.validate_config)
- Default fill for missing top-level keys (per ADR-004 §"empty config valid")
- Deep-copy on return (per ADR-003 §test_output_dicts_are_independent principle)

Public seam:
    - load_config(path) -> dict
        Reads JSON from disk and returns the validated config dict.
        On any failure raises ConfigLoadError (fail-fast per ADR-004 Q13-A).

    - ConfigLoadError
        Unified exception for file / parse / schema failures. The message
        is structured so 皮皮 can fix the JSON file directly without reading
        code.

No caching here (per ADR-004 Q14-A: cron uses isolated sessions; one load
per process is fine).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Union

from src.config_schema import ConfigSchemaError, validate_config

PathLike = Union[str, Path]

# Four required output keys (in stable order). Missing top-level keys in the
# JSON file default to these empties so downstream consumers always see the
# same shape.
_OUTPUT_KEYS = ("etf_watch_list", "user_holdings", "index_watch_list", "sector_mapping")


class ConfigLoadError(Exception):
    """Raised when etf_config.json cannot be loaded.

    Wraps three underlying failure modes:
    - File not found / not readable
    - Invalid JSON
    - Schema validation failure

    In all cases the message names the offending path so 皮皮 can fix the
    JSON file directly without reading code.
    """


def _empty_result() -> dict[str, Any]:
    """Return the canonical empty config (deep-copied per call)."""
    return {
        "etf_watch_list": [],
        "user_holdings": [],
        "index_watch_list": [],
        "sector_mapping": {},
    }


def _read_text(path: Path) -> str:
    """Read file as utf-8. Empty file → ConfigLoadError."""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ConfigLoadError(
            f"etf_config.json is empty: {path}\n"
            f"  hint: the file must contain a JSON object, even if just '{{}}'."
        )
    return text


def _parse_json(text: str, path: Path) -> dict:
    """Parse JSON text. Re-raise parse errors as ConfigLoadError."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigLoadError(
            f"etf_config.json is not valid JSON: {path}\n"
            f"  parse error at line {e.lineno} col {e.colno}: {e.msg}\n"
            f"  hint: validate with `python3 -m json.tool {path}`."
        ) from e
    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"etf_config.json must be a JSON object at top level: {path}\n"
            f"  got {type(data).__name__}; expected 'object'."
        )
    return data


def _fill_defaults(data: dict) -> dict[str, Any]:
    """Return a new dict with all 4 output keys present (defaults filled).

    Deep-copies so callers can mutate without affecting subsequent loads
    (mirrors ADR-003 test_output_dicts_are_independent principle).
    """
    result = _empty_result()
    for key in _OUTPUT_KEYS:
        if key in data and data[key] is not None:
            # Deep-copy to insulate caller's mutation from future loads.
            result[key] = copy.deepcopy(data[key])
    return result


def load_config(path: PathLike) -> dict[str, Any]:
    """Read etf_config.json from disk and validate it.

    Args:
        path: Path to the JSON file (str or pathlib.Path). The file must
            exist, be readable as utf-8, contain a JSON object, and pass
            schema validation (see src.config_schema).

    Returns:
        dict with exactly 4 keys (etf_watch_list, user_holdings,
        index_watch_list, sector_mapping). Missing top-level keys in the
        file default to empty containers.

    Raises:
        ConfigLoadError: On any failure. The message names the file path
            and the underlying issue (file / parse / schema).
    """
    p = Path(path).resolve()

    if not p.exists():
        raise ConfigLoadError(
            f"etf_config.json not found: {p}\n"
            f"  hint: pass --config <path-to-etf_config.json> to the collector.\n"
            f"  See docs/DEPLOY.md §配置外部化 for the expected path."
        )

    text = _read_text(p)
    data = _parse_json(text, p)

    try:
        validate_config(data)
    except ConfigSchemaError as e:
        # Re-raise with file path context so 皮皮 knows which file to fix.
        raise ConfigLoadError(
            f"etf_config.json failed schema validation: {p}\n{e}"
        ) from e

    return _fill_defaults(data)