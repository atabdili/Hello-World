#!/usr/bin/env python3
"""Bootstrap draft Infrahub schema nodes from PAN-OS data-model specs.

Source: https://github.com/PaloAltoNetworks/pan-os-codegen  (specs/**.yaml)
Those specs are what Palo Alto generates the `panos` Terraform provider (v2)
and the `pango` Go SDK from, and they carry the PAN-OS XPath of every field --
i.e. they are the most machine-readable description of the PAN-OS XML API.

The output is a *draft*: it is meant to be diffed against / copied into the
curated schemas/paloalto/panos.yml, not loaded as-is.

Mapping rules
  string            -> Text
  bool / yes|no enum-> Boolean
  int64             -> Number
  enum              -> Dropdown (choices from spec)
  list[string]      -> List          (# TODO: often a relationship, e.g. members/tags/zones)
  object            -> flattened one level as <parent>_<child>, deeper -> JSON
  variants          -> <group>_type Dropdown + flattened variant fields (all optional)

Usage
  tools/panos_spec_to_infrahub.py specs/objects/address.yaml [...]          # draft YAML
  tools/panos_spec_to_infrahub.py --mapping specs/objects/*.yaml [...]      # markdown rows
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

SKIP_PARAMS = {"audit-comment-version", "audit-comment-wo"}


def _norm(name: str) -> str:
    out = re.sub(r"[^a-z0-9_]", "_", name.lower().replace("-", "_"))
    out = re.sub(r"_+", "_", out).strip("_")
    return out if len(out) >= 3 else f"{out}_value"  # Infrahub: min 3 chars


def _pascal(name: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[-_ ]+", name) if p)


def _enum_values(p: dict) -> list[str]:
    return [str(v["value"]) for v in (p.get("spec") or {}).get("values") or []]


def _attr(name: str, p: dict, optional: bool) -> dict:
    t = p.get("type")
    a: dict = {"name": name}
    if p.get("description"):
        a["description"] = p["description"].strip()[:128]
    if t == "bool":
        a["kind"] = "Boolean"
    elif t == "int64":
        a["kind"] = "Number"
    elif t == "enum":
        vals = _enum_values(p)
        if set(vals) <= {"yes", "no"}:
            a["kind"] = "Boolean"
        else:
            a["kind"] = "Dropdown"
            a["choices"] = [{"name": _norm(v) if not v.isdigit() else v, "label": v} for v in vals]
    elif t == "list":
        a["kind"] = "List"
        a["_todo"] = "list of names: consider a relationship"
    elif t == "object":
        a["kind"] = "JSON"
    else:
        a["kind"] = "Text"
    a["optional"] = optional or not p.get("required", False)
    return a


def _flatten(spec: dict, prefix: str = "", depth: int = 0, force_optional: bool = False) -> list[dict]:
    attrs: list[dict] = []
    if not spec:
        return attrs
    for p in spec.get("params") or []:
        if p["name"] in SKIP_PARAMS:
            continue
        name = _norm(f"{prefix}{p['name']}")
        if p.get("type") == "object" and depth < 1:
            attrs.extend(_flatten(p.get("spec") or {}, f"{prefix}{p['name']}_", depth + 1, force_optional))
        else:
            attrs.append(_attr(name, p, force_optional))
    variants = spec.get("variants") or []
    if variants:
        groups: dict[int, list[dict]] = {}
        for v in variants:
            groups.setdefault(v.get("variant_group_id", 0), []).append(v)
        for gid, members in groups.items():
            sel = _norm(f"{prefix}type" if gid == 0 else f"{prefix}type_{gid}")
            attrs.append({
                "name": sel,
                "kind": "Dropdown",
                "optional": True,
                "description": "Variant selector (exactly one of the following).",
                "choices": [{"name": _norm(m["name"]), "label": m["name"]} for m in members],
            })
            for m in members:
                name = _norm(f"{prefix}{m['name']}")
                if m.get("type") == "object" and depth < 1:
                    attrs.extend(_flatten(m.get("spec") or {}, f"{prefix}{m['name']}_", depth + 1, True))
                else:
                    attrs.append(_attr(name, m, True))
    return attrs


def _terraform_resources(d: dict) -> list[str]:
    cfg = d.get("terraform_provider_config") or {}
    if cfg.get("skip_resource"):
        return []
    out = []
    variants = cfg.get("resource_variants") or ["singular"]
    if "singular" in variants and cfg.get("suffix"):
        out.append(f"panos_{cfg['suffix']}")
    if "plural" in variants:
        # mirrors pan-os-codegen pkg/generate/generator.go
        if cfg.get("resource_type") == "uuid" and cfg.get("plural_name"):
            out.append(f"panos_{cfg['suffix']}_{cfg['plural_name']}")
        elif cfg.get("plural_suffix"):
            out.append(f"panos_{cfg['plural_suffix']}")
    return out


def _xpaths(d: dict) -> dict[str, str]:
    leaf = "/".join((d.get("panos_xpath") or {}).get("path") or [])
    res = {}
    for loc in d.get("locations") or []:
        base = "/".join((loc.get("xpath") or {}).get("path") or [])
        res[loc["name"]] = f"/{base}/{leaf}".replace("//", "/")
    return res


def to_node(path: Path) -> dict:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    attrs = [{"name": "name", "kind": "Text", "optional": False}] if d.get("entries") else []
    attrs += _flatten(d.get("spec") or {})
    node = {
        "name": _pascal(d["name"]),
        "namespace": "Panos",
        "description": ((d.get("terraform_provider_config") or {}).get("description") or d["name"])[:128],
        "attributes": [],
        "_source": {
            "spec": str(path),
            "terraform": _terraform_resources(d),
            "locations": list(_xpaths(d)),
        },
    }
    for a in attrs:
        todo = a.pop("_todo", None)
        if todo:
            a["description"] = (f"TODO {todo}. " + a.get("description", ""))[:128]
        node["attributes"].append(a)
    return node


def to_mapping_row(path: Path) -> str:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    xp = _xpaths(d)
    first = next(iter(xp.items()), ("", ""))
    tf = ", ".join(f"`{r}`" for r in _terraform_resources(d)) or "—"
    return f"| `{d['name']}` | {tf} | {', '.join(xp)} | `{first[1]}` |"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="+", type=Path)
    ap.add_argument("--mapping", action="store_true", help="emit markdown mapping rows instead of YAML")
    args = ap.parse_args()

    if args.mapping:
        print("| spec | Terraform resource(s) | PAN-OS locations | XPath (first location) |")
        print("|---|---|---|---|")
        for p in args.specs:
            print(to_mapping_row(p))
        return 0

    nodes = []
    for p in args.specs:
        node = to_node(p)
        src = node.pop("_source")
        print(f"# {node['namespace']}{node['name']}: from {src['spec']}; terraform={src['terraform']}; "
              f"locations={src['locations']}", file=sys.stderr)
        nodes.append(node)
    yaml.safe_dump({"version": "1.0", "nodes": nodes}, sys.stdout, sort_keys=False, width=120)
    return 0


if __name__ == "__main__":
    sys.exit(main())
