# Tenant onboarding through the change workflow

Design for taking a tenant request from a natural-language ticket to deployed and
verified switch and firewall configuration, inside the existing change workflow.

## Principles

1. **The requester states the business need, never network details.** Who the tenant is,
   which applications or servers, what traffic is needed, and when.
2. **Infrahub is the source of truth.** It knows what exists and how it is connected, and it
   holds the placement rules and resource pools. Where things go is derived from it,
   never typed into a ticket.
3. **AI only reads the ticket.** Claude turns the text into a fixed, structured form.
   Everything after that is deterministic code: placement, allocation, config
   generation and checks.
4. **The change tool is in charge** of states, approvals and the audit trail. The
   automation acts only when the ticket reaches a state that allows it.
5. **Everything the change record needs is generated**, not copied in by hand.

## Roles

| Role | Responsibility |
|---|---|
| Requester | Describes the business need in the ticket |
| Change tool (ServiceNow / Jira / …) | Change record, states, approvals, audit trail |
| Change service | Small app reacting to ticket states and driving the steps below |
| Claude | Ticket text → structured business request |
| Infrahub | Source of truth: topology, tenants, policy, pools, placement rules; one branch per change |
| Ansible + Arista AVD | Switch configs: build, diff, deploy, verify (`demo/ansible`) |
| Firewall automation | PAN-OS / Panorama configs: build, diff, deploy, verify |
| Approvers / change board | Approve or reject, as today |

## 1. The business request

Example ticket:

> Please onboard new tenant **Acme Corp** for their **customer portal** (servers
> **acme-srv1** and **acme-srv2**). They need outbound web browsing and HTTPS, and the
> portal must be reachable from the internet on HTTPS. Go-live next Tuesday.

What Claude extracts. These fields are the whole form; there are no location fields:

```json
{
  "tenant": "acme",
  "application": "customer portal",
  "servers": ["acme-srv1", "acme-srv2"],
  "outbound": ["web-browsing", "ssl"],
  "published_services": [{"name": "acme-web", "port": 443, "protocol": "tcp"}],
  "constraints": [],
  "requested_date": "next Tuesday",
  "unclear_points": []
}
```

`constraints` holds only business constraints the ticket states, such as "EU only" or
"both data centers". `unclear_points` lists what Claude could not determine; the change
service turns these into a question on the ticket instead of guessing.

## 2. Placement: deriving the network details from Infrahub

Placement runs as code, in the Infrahub generator, and produces the **resolved request**
that the configuration build uses (`demo/ansible/intents/acme.json` is an example).

| Derived value | Source in Infrahub |
|---|---|
| Server ports, leaf switches, rack, data center | Server → interface → cable → leaf port → leaf → location |
| Firewall | Location → protecting firewall (e.g. DC1 → fw01) |
| Fabric-to-firewall link | Firewall → its fabric uplink (fw01 ethernet1/1 ↔ border1 Ethernet40) |
| Panorama device group / template / rulebase | Firewall → device group, template stack |
| VLAN, VNI, subnet, gateway IP | Tenant pools for that data center |
| Zone, subinterface and object names | Naming rules |

For anything not yet in Infrahub, placement rules decide: default data center, capacity
per leaf pair, naming.

**When the requester is asked anything**, it's only when the source of truth can't decide,
and the question is phrased in business terms:

- The servers are not in Infrahub yet. This is resolved by the rack and onboarding
  process (a separate change), not by asking for ports.
- A business choice the rules cannot make: "Should Acme run in DC1, DC2 or both?"
- The rules give more than one valid answer and policy says a person chooses.

The change record states each decision and why, for example *"leaf3/leaf4: acme-srv1/2
are cabled there. fw01: protects DC1."*

## 3. End to end, by change state

| # | Change state | What happens | Touches the network? |
|---|---|---|---|
| 1 | **New** | Requester raises the ticket; moving it to "Ready for automation" notifies the change service. | No |
| 2 | **New → Assess** | Claude extracts the business request. If anything is unclear, the change service asks on the ticket and waits. | No |
| 3 | **Assess** | Infrahub branch `CHG<number>-<tenant>` is created. Placement and allocation run, then the generator creates the tenant objects on the branch. | No |
| 4 | **Assess** | Switch configs are built without and with the tenant, then compared (Ansible + AVD). Firewall changes are built. Checks run: VLAN consistency between fabric and firewall, gateway inside the subnet, zone bound, rules use the new zone. | No |
| 5 | **Assess → Authorize** | The change record is filled in automatically (next section). Risk and the change category are computed. | No |
| 6 | **Authorize** | Standard change: peer approval. Normal change: change board. Failing checks block approval. | No |
| 7 | **Scheduled** | Just before the window: rebase the branch, rebuild, re-run checks, compare live device configs with what's expected. Any unexpected difference stops the change. | Read only |
| 8 | **Implement** | Merge the branch, back up configs, deploy switches and firewall, log each step on the ticket. | Yes |
| 9 | **Verify** | Post-checks on the devices. If they fail, automatic backout: redeploy pre-change configs and revert in Infrahub. | Read; write on backout |
| 10 | **Closed** | Ticket closed with the full evidence trail. | No |

## 4. Generated change record

| Field | Generated from |
|---|---|
| Description | Ticket text + extracted business request |
| Placement decisions | Placement step, with the reason for each |
| Affected CIs | Devices with a non-empty diff (leaf3, leaf4, border1, fw01); untouched devices listed |
| Implementation plan | Per-device config diffs |
| Backout plan | Redeploy pre-change builds (already rendered) + revert the Infrahub merge |
| Test plan | VLAN/VNI up, EVPN routes, trunk up; firewall subinterface up; policy tests (acme → internet 443 allow, internet → acme 22 deny) |
| Risk / category | Additive only + matches the tenant template → standard change; anything else → normal change |
| Schedule | Requested date checked against change windows |

## 5. What Infrahub must hold for this to work

This only works if this data is accurate. That is the main dependency, and also the
main argument for having a source of truth.

| Data | Status in the current schema |
|---|---|
| Servers and their cabling to leaf ports | Base DCIM (`DcimInterface`, `DcimEndpoint`, cables) - needs populating |
| Leaves, border leaves, fabric pools, ASNs | Base DCIM/IPAM - needs populating |
| VLAN / VNI / prefix pools per data center | Infrahub resource pools - needs creating |
| Location → protecting firewall | **Missing** - add a relationship (e.g. on `SecurityGenericFirewall`) |
| Firewall → fabric uplink | **Missing** - link firewall interface to the border-leaf interface |
| Firewall → Panorama device group / template stack | Present (`PanosFirewall`) |
| Firewall subinterface → VLAN object | **Missing** - `PanosSubInterface` stores a VLAN number only; link it to `IpamVLAN` so fabric and firewall share one object |
| Zone → tenant | **Missing** - optional `tenant` on `SecurityGenericZone` |
| Business request (`TenantService`) | **Missing** - node holding the extracted request + ticket number |
| Placement rules (default DC, leaf capacity, naming) | **Missing** - generator configuration |

## 6. Status

| Piece | Status |
|---|---|
| Vendor-neutral + PAN-OS schema | Built, validated offline |
| Switch build / diff / impact (Ansible + AVD) | Built, tested offline (`demo/ansible`) |
| Switch precheck / deploy / verify / backout | Written, not yet run against devices |
| Ticket → Claude → business request | Designed |
| Placement + generator + checks in Infrahub | Designed; needs the schema additions above |
| Firewall build and deploy | Designed |
| Change tool connector | Needs the change tool and its state names |

## Open questions

1. Which change tool is used, and what are the change states called?
2. Can tenant onboarding be a standard change, or must every firewall change go to the
   change board?
3. Placement rules: is there a default data center, and how is leaf-pair capacity measured?
