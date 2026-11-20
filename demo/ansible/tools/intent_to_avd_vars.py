#!/usr/bin/env python3
"""Render inventory/group_vars/DC1/tenants.yml from resolved tenant intents.

Offline stand-in for the Infrahub transform behind the "avd-tenant-vars"
artifact: same input (tenant intents), same output (AVD eos_designs keys).

    tools/intent_to_avd_vars.py                     > inventory/group_vars/DC1/tenants.yml  # baseline
    tools/intent_to_avd_vars.py intents/acme.json   > inventory/group_vars/DC1/tenants.yml  # with tenant
"""
from __future__ import annotations

import json
import sys

import yaml


def tenant_to_avd(t: dict) -> dict:
    """The firewall is the tenant gateway, so the fabric only carries the VLAN
    at L2 (EVPN/VXLAN l2vlan) to the border leaf facing the firewall."""
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


def main(paths: list[str]) -> int:
    out: dict[str, list] = {"tenants": [], "servers": [], "firewalls": []}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for key, items in tenant_to_avd(json.load(fh)).items():
                out[key].extend(items)
    print("# GENERATED - do not edit. Source intents: " + (", ".join(paths) or "none (baseline)"))
    yaml.safe_dump(out, sys.stdout, sort_keys=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
