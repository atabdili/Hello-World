# Infrahub firewall schema: vendor-neutral core + Palo Alto PAN-OS

An [Infrahub](https://github.com/opsmill/infrahub) schema for firewalls and security policy.
The core is vendor-neutral, and a PAN-OS / Panorama extension sits on top of it.

* **`schemas/security/security.yml`**: the vendor-neutral layer (`Security*`). It includes zones,
  address, service and application objects, rulebases, security and NAT rules, firewalls, firewall
  interfaces and HA groups. It is derived from OpsMill
  [schema-library](https://github.com/opsmill/schema-library) `experimental/security` and reshaped
  so that every cross-reference targets a generic that vendors can implement.
* **`schemas/paloalto/panos.yml`**: the Palo Alto layer (`Panos*`). It includes Panorama, device
  groups, templates and template stacks, vsys, PAN-OS interface types, virtual routers and static
  routes, PAN-OS-only objects (IP wildcards, EDLs, dynamic address groups, app filters, schedules),
  security profiles and profile groups, and PAN-OS security and NAT rules. It also extends
  `BuiltinTag` with a PAN-OS tag color.

Read [docs/tenant-change-workflow.md](docs/tenant-change-workflow.md) for the end-to-end change workflow,
[docs/design.md](docs/design.md) for the modelling decisions and
[docs/mapping.md](docs/mapping.md) for the kind ↔ PAN-OS XPath ↔ Terraform ↔ OpenConfig mapping.

## Where the model comes from

| Source | Used for |
|---|---|
| OpsMill schema-library (`base/*`, `experimental/security`) | Base `Dcim`/`Ipam`/`Location` schema and the starting shape of the security model |
| [PaloAltoNetworks/pan-os-codegen](https://github.com/PaloAltoNetworks/pan-os-codegen) specs | PAN-OS field names, enums and XPaths. These specs also generate the `panos` Terraform provider v2 and the `pango` SDK, so they cover both the XML API and Terraform. |
| OpenConfig (interfaces, if-aggregate, network-instance, acl) | Neutral naming for interfaces, routing instances and rule actions. OpenConfig has no zone, NAT or object model. |

`tools/panos_spec_to_infrahub.py` turns any pan-os-codegen spec into a draft Infrahub node, or into
a mapping row with `--mapping`. Use it to bootstrap new object types and to diff the curated schema
when PAN-OS changes:

```bash
scripts/fetch_upstream.sh                         # pinned clones into vendor/
tools/panos_spec_to_infrahub.py vendor/pan-os-codegen/specs/objects/profiles/antivirus.yaml
tools/panos_spec_to_infrahub.py --mapping vendor/pan-os-codegen/specs/policies/*.yaml
```

## Validate

```bash
scripts/validate.sh            # INFRAHUB_VERSION=1.12.2 by default
```

The script installs `infrahub-server` into `.venv` and runs Infrahub's own schema processing
(`SchemaBranch.process()`) offline. It needs no server or database. It adds two lints for
problems the server accepts silently: unknown `menu_placement` and reserved relationship names.
CI runs the same script (`.github/workflows/schema.yml`).

## Load into Infrahub

```bash
scripts/fetch_upstream.sh
infrahubctl schema load vendor/schema-library/base schemas/security schemas/paloalto
```

To model only another vendor, or a vendor-agnostic estate, load just `base` + `schemas/security`.
