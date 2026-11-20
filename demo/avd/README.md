# Fabric config through Arista AVD

Renders the fabric side of the tenant demo with [AVD](https://avd.arista.com) through
`pyavd` (the Python library behind the `arista.avd` Ansible collection), and shows the
per-device diff a tenant adds.

```bash
pip install pyavd pyyaml          # tested with pyavd 6.5.0
./render.py fabric.yml tenant_acme.json --out build/
#   spine1     +0 -0
#   leaf3      +22 -0     vlan 210, Port-Channel10/Ethernet10 to acme-srv1, VXLAN VNI 10210, EVPN
#   leaf4      +22 -0
#   border1    +16 -0     vlan 210, Ethernet40 trunk to fw01, VXLAN VNI 10210, EVPN
```

`build/<device>.cfg` is the full EOS config and `build/<device>.diff` is what the tenant changes.

## Pipeline

```
ticket ─► Claude extraction ─► resolve + allocate (Infrahub) ─► tenant intent (tenant_acme.json)
                                                                     │
                     ┌───────────────────────────────────────────────┴──────────────────┐
                     ▼                                                                  ▼
   tenant_to_avd(): intent ─► AVD eos_designs keys                    PAN-OS transform (same intent):
     tenants[].l2vlans  (VLAN + VNI)                                   ethernet1/1.210, zone acme,
     servers[]          (leaf ports / port-channel)                    address acme-net, rules, NAT
     firewalls[]        (border-leaf trunk to fw01)
                     ▼
   pyavd: validate_inputs → get_avd_facts → get_device_structured_config → get_device_config
                     ▼
               EOS config per device  ──►  Infrahub artifact  ──►  deploy (CloudVision / eAPI / Ansible)
```

The VLAN ID, VNI, switch ports and firewall port all come from the **same** intent, so
the fabric trunk and the firewall subinterface can't drift apart.

## Where the inputs come from

`fabric.yml` is written by hand here to keep the demo self-contained. In the full
Infrahub demo it is the output of an Infrahub Python transform that reads the devices,
interfaces, BGP ASNs and pools from Infrahub and emits these same keys. So Infrahub
holds the data, and AVD is only the config engine.

Two ways to run AVD in the pipeline:

| Option | How | When |
|---|---|---|
| **pyavd inside an Infrahub transform** (this script's logic) | The transform returns EOS config as an Infrahub artifact. | Configs show up in the proposed change before merge. Best for the demo. |
| **Ansible `arista.avd`** (`eos_designs` + `eos_cli_config_gen` / `cv_deploy`) with the `opsmill.infrahub` inventory plugin | CI job after merge. | Teams already running AVD with Ansible and CloudVision. |
