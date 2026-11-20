#!/usr/bin/env python3
"""Render Arista EOS configs with AVD (pyavd) for a fabric, with and without a tenant.

    render.py fabric.yml [tenant.json] --out build/

Without a tenant file it renders the baseline; with one it merges the tenant
into the AVD inputs, renders again and writes a unified diff per device. That
diff is exactly what the proposed change shows for the fabric side.

Requires: pip install pyavd  (tested with pyavd 6.5.0)
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import sys
from pathlib import Path

import pyavd
import yaml


def tenant_to_avd(t: dict) -> dict:
    """Map the vendor-neutral tenant intent onto AVD eos_designs keys.

    The firewall is the tenant's default gateway, so the fabric only carries
    the VLAN at L2 (EVPN/VXLAN l2vlan) to the border leaf facing the firewall.
    """
    vlan = str(t["vlan_id"])
    return {
        "tenants": [{
            "name": t["tenant_name"].upper(),
            "mac_vrf_vni_base": t["vni_base"],
            "l2vlans": [{"id": t["vlan_id"], "name": t["tenant_name"]}],
        }],
        "servers": [{
            "name": s["name"],
            "adapters": [{
                "endpoint_ports": s["endpoint_ports"],
                "switch_ports": s["switch_ports"],
                "switches": s["switches"],
                "mode": "access",
                "vlans": vlan,
                **({"port_channel": {"mode": "active"}} if s.get("lacp") else {}),
            }],
        } for s in t["server_attachments"]],
        "firewalls": [{
            "name": t["firewall"]["name"],
            "adapters": [{
                "endpoint_ports": [t["firewall"]["endpoint_port"]],
                "switch_ports": [t["firewall"]["switch_port"]],
                "switches": [t["firewall"]["switch"]],
                "mode": "trunk",
                "vlans": vlan,
            }],
        }],
    }


def merge(fabric: dict, extra: dict) -> dict:
    out = copy.deepcopy(fabric)
    for key in ("tenants", "servers", "firewalls"):
        out[key] = list(out.get(key) or []) + list(extra.get(key) or [])
    return out


def render(fabric: dict) -> dict[str, str]:
    hosts = fabric.pop("avd_hosts")
    all_inputs = {}
    for host, node_type in hosts.items():
        inputs = {**copy.deepcopy(fabric), "hostname": host, "type": node_type}
        result = pyavd.validate_inputs(inputs)
        if result.validation_result.violations:
            for v in result.validation_result.violations:
                print(f"{host}: invalid AVD input: {v}", file=sys.stderr)
            sys.exit(1)
        all_inputs[host] = result.validated_data
    facts = pyavd.get_avd_facts(all_inputs)
    configs = {}
    for host in hosts:
        structured = pyavd.get_device_structured_config(host, all_inputs[host], facts)
        configs[host] = pyavd.get_device_config(structured)
    return configs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fabric", type=Path)
    ap.add_argument("tenant", type=Path, nargs="?")
    ap.add_argument("--out", type=Path, default=Path("build"))
    args = ap.parse_args()

    fabric = yaml.safe_load(args.fabric.read_text())
    before = render(copy.deepcopy(fabric))
    after = before
    if args.tenant:
        after = render(merge(fabric, tenant_to_avd(json.loads(args.tenant.read_text()))))

    args.out.mkdir(parents=True, exist_ok=True)
    for host, cfg in after.items():
        (args.out / f"{host}.cfg").write_text(cfg)
        diff = list(difflib.unified_diff(before[host].splitlines(True), cfg.splitlines(True),
                                         f"{host} (running intent)", f"{host} (with tenant)"))
        if diff:
            (args.out / f"{host}.diff").write_text("".join(diff))
        added = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        removed = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        print(f"{host:10} +{added} -{removed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
