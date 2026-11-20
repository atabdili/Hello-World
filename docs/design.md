# Design notes

## Layers

```
OpsMill schema-library base          Dcim*, Interface*, Ipam*, Location*, Organization*, BuiltinTag
        ▲
schemas/security/security.yml        Security*   vendor-neutral (generics + default nodes)
        ▲
schemas/paloalto/panos.yml           Panos*      PAN-OS / Panorama nodes + extensions
```

A second vendor (for example `schemas/fortinet/fortios.yml` with `Fortios*`) sits next to `paloalto/`
and inherits the same `Security*` generics.

## The pattern: point at generics, specialise with nodes

Infrahub generics can't inherit from other generics. A node can inherit from several generics,
and a relationship can target a generic. The neutral layer is built on those two facts:

* Every cross-reference (rule → address, interface → zone, NAT → service, …) targets a `SecurityGeneric*`
  generic, not a concrete node.
* The neutral layer also ships plain default nodes (`SecurityZone`, `SecurityIPAddress`,
  `SecurityPolicyRule`, …) so it can be used on its own.
* A vendor adds nodes that inherit the same generics and add vendor fields, for example
  `PanosSecurityRule ⊂ SecurityGenericPolicyRule` or `PanosZone ⊂ SecurityGenericZone`.
  The vendor nodes then work wherever a neutral node would.
* Queries, transforms and checks that only use the generic fields (`SecurityGenericPolicyRule { action
  source_zones … }`) work across every vendor. Vendor-specific templates query the `Panos*` kind.

When a PAN-OS object has no vendor-specific fields, the neutral node is reused: address/prefix/range/FQDN,
static address and service groups, services, applications and application groups. A `Panos*` node
exists only where PAN-OS differs.

## Scopes = PAN-OS "locations"

Every PAN-OS object lives in a *location*: `shared`, `device-group`, `vsys`, `template` or
`template-stack` (see `locations:` in each pan-os-codegen spec). The neutral `SecurityGenericScope`
generic models this, and each location type is a node that inherits it:

| PAN-OS location | Infrahub node |
|---|---|
| Panorama `shared` | `PanosPanorama` (the Panorama itself is the shared scope) |
| `device-group` | `PanosDeviceGroup` (with `parent` for the hierarchy) |
| `vsys` | `PanosVsys` |
| `template` / `template-stack` | `PanosTemplate` / `PanosTemplateStack` |
| other vendors / predefined content | `SecurityScope` |

Objects are unique per scope (`[scope, name]`), and their human-friendly ID is `[scope name, object name]`.
Scope names must therefore be globally unique. For a vsys, use names like `fw01:vsys1`.

## Mapping decisions

| Topic | Decision |
|---|---|
| Rule action | Neutral `permit / deny / drop / reject`, close to openconfig-acl ACCEPT/DROP/REJECT. PAN-OS `allow`→permit, `deny`→deny, `drop`→drop, `reset-*`→reject + `PanosSecurityRule.reject_mode`. |
| `any` | An empty many-relationship means `any`. |
| `application-default` | `PanosSecurityRule.application_default = true` (the default). When true, `services` is ignored. |
| Rule order | `index` attribute, unique per policy. Infrahub relationships are unordered. |
| Pre / post / local rulebase | `PanosRulebase.rulebase`, with one rulebase of each type per scope. |
| Mixed member lists | PAN-OS `source`/`destination` mix addresses, groups and EDLs. These are split into `*_addresses` (`SecurityGenericAddress`: host/prefix/range/FQDN/wildcard/EDL) and `*_address_groups` (static + dynamic groups), as OpsMill does. Rendering concatenates them. |
| Administrative tags | `BuiltinTag` + `panos_color` (extension). Dynamic address groups reference tags by name in `filter`. |
| Template-stack order | `PanosTemplateStackEntry.priority`, because the order of a relationship isn't preserved. |
| Interfaces in templates | Interfaces always belong to the **firewall** (`DcimInterface.device` is mandatory). Template membership is a rendering concern. |
| Security profiles | Referenced by name only (`PanosSecurityProfile` + `profile_type`). Profile bodies are on the roadmap. |
| HA | Neutral `SecurityHighAvailabilityGroup` (mode, group id, members). |
| Reserved names | Avoid relationship names Infrahub adds itself (`profiles`, `member_of_groups`, `subscriber_of_groups`, `object_template`). `tools/validate_schema.py` checks for this. |

## Infrahub constraints found while building

* Human-friendly IDs can follow only **one** relationship hop, so rules have no HFID (they use uniqueness
  constraints instead).
* `description` is limited to 128 characters, and attribute and relationship names need at least 3 characters.
* An unknown `menu_placement` is not rejected. The item silently moves to the default menu,
  so the validator lints for this.
* Mismatched relationship `identifier`s are not rejected either. You get two one-sided relationships instead
  of one bidirectional relationship. Paired identifiers are named `<owner>__<member>` to make mistakes easy to spot.

## Roadmap (not in v0)

* Security-profile bodies (AV, anti-spyware, vulnerability, URL filtering, file blocking, WildFire):
  bootstrap them from `pan-os-codegen/specs/objects/profiles/*.yaml`.
* Decryption, PBF and authentication rulebases (same pattern as `GenericPolicyRule`).
* IPsec/IKE (`network/tunnels/ipsec.yaml`, `network/ike-gateway.yaml`, crypto profiles).
* GlobalProtect, User-ID, dynamic user groups.
* Routing protocols. Prefer the OpsMill `routing_*` extensions and link them from `PanosVirtualRouter`.
* `disable_override` and other Panorama override flags.
* Transforms (Jinja2 → PAN-OS set/XML, or → Terraform `tfvars`) and generators. Example object data.
