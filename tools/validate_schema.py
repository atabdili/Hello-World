#!/usr/bin/env python3
"""Offline Infrahub schema validation.

Loads Infrahub's internal + core schema, then every YAML file/dir passed on the
command line (in order), and runs the same `SchemaBranch.process()` pipeline the
Infrahub server runs on `infrahubctl schema load` -- without needing a running
server or database.

Requires the `infrahub-server` Python package (same minor version as your
Infrahub instance), e.g.:

    uv venv -p 3.12 .venv && uv pip install --python .venv infrahub-server==1.12.2
    .venv/bin/python tools/validate_schema.py <schema-library>/base <schema-library>/extensions/vrf schemas/

Exit code 0 = schema accepted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(x for x in p.rglob("*.yml") if not x.name.startswith(".")))
            files.extend(sorted(x for x in p.rglob("*.yaml") if not x.name.startswith(".")))
        elif p.is_file():
            files.append(p)
        else:
            sys.exit(f"not found: {p}")
    return files


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    from infrahub import config
    from infrahub.core.schema import SchemaRoot, core_models, internal_schema

    config.load_and_exit(config_file_name="/nonexistent-infrahub.toml")  # defaults only
    from infrahub.core.schema.schema_branch import SchemaBranch

    branch = SchemaBranch(cache={}, name="validate")
    branch.load_schema(SchemaRoot(**internal_schema))
    branch.load_schema(SchemaRoot(**core_models))

    # Relationship names Infrahub adds to every node itself; redefining one
    # silently replaces the built-in (e.g. object profiles stop working).
    reserved = {"profiles", "member_of_groups", "subscriber_of_groups", "object_template"}
    problems: list[str] = []

    for f in _collect(argv):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "version" not in data:
            print(f"skip (not a schema file): {f}")
            continue
        for item in (data.get("generics") or []) + (data.get("nodes") or []):
            for rel in item.get("relationships") or []:
                if rel.get("name") in reserved:
                    problems.append(f"{item['namespace']}{item['name']}.{rel['name']} uses a reserved relationship name")
        try:
            root = SchemaRoot(**{k: v for k, v in data.items() if k != "version"})
        except Exception as exc:  # pydantic validation error
            print(f"FAIL parsing {f}:\n{exc}")
            return 1
        branch.load_schema(root)
        print(f"loaded {f}  (generics={len(root.generics)}, nodes={len(root.nodes)})")

    try:
        branch.process()
    except Exception as exc:
        print(f"\nFAIL: {type(exc).__name__}: {exc}")
        return 1

    # Extra lint: the server silently moves items with an unknown menu_placement
    # to the default menu, so catch it here.
    for kind in branch.node_names + branch.generic_names:
        sch = branch.get(kind, duplicate=False)
        target = getattr(sch, "menu_placement", None)
        if target and sch.include_in_menu:
            if not branch.has(target) or not branch.get(target, duplicate=False).include_in_menu:
                problems.append(f"{kind}.menu_placement -> {target} (missing or not include_in_menu)")
    if problems:
        print("\nFAIL (lint):\n  " + "\n  ".join(problems))
        return 1

    print(f"\nOK: schema processed ({len(branch.node_names)} nodes, {len(branch.generic_names)} generics)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
