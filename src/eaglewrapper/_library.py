"""Read item metadata straight from an Eagle library folder, without the HTTP API.

An Eagle library (``<name>.library``) keeps one folder per item, ``images/<id>.info/``,
each with a ``metadata.json`` (name, tags, size, palettes, ...). The library's own
``metadata.json`` (folders, smart folders, tag groups) sits at the top and is not an item.
"""
import concurrent.futures
import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from loguru import logger

def name_filter(prefixes: Optional[Sequence[str]]) -> Callable[[Dict[str, Any]], bool]:
    """Build the test for ``name_start_filters``: a name has to start with every prefix."""
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    prefixes = list(prefixes or [])
    if not prefixes:
        return lambda item: True
    def keep(item: Dict[str, Any]) -> bool:
        name = item.get('name')
        return isinstance(name, str) and all(name.startswith(prefix) for prefix in prefixes)
    return keep


def item_metadata_paths(library_path: str) -> List[Path]:
    """Every ``metadata.json`` under the library folder except the library's own one."""
    library = Path(library_path)
    return [path for path in library.glob('**/metadata.json') if path.parent != library]


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(str(path), 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning('[Eagle] Skipped {}: {}', path, e)
        return None
    return data if isinstance(data, dict) and data else None


def read_items(library_path: str, name_start_filters: Optional[Sequence[str]] = None,
               max_workers: int = 4) -> List[Dict[str, Any]]:
    """Load the metadata of every item in a library folder, optionally filtered by name prefix.

    Unreadable files are skipped with a warning. Results are in file-system order.
    """
    keep = name_filter(name_start_filters)
    logger.debug('[Eagle] Start getting images INFO...')
    started = datetime.datetime.now()
    paths = item_metadata_paths(library_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        items = [item for item in executor.map(_load, paths) if item is not None and keep(item)]
    seconds = (datetime.datetime.now() - started).total_seconds()
    logger.debug('[Eagle] Get all images INFO cost :: {:.2f} sec(s)', seconds)
    return items
