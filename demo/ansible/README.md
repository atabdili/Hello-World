# Fabric side of the tenant change, with Ansible + Arista AVD

The `arista.avd` collection (6.5.0) renders and deploys the switch configs. Each step of
your change workflow is one `change.sh` stage, and each stage writes evidence to
`build/change-record/` for attaching to the change ticket.

## Change states → stages

| Change state | Command | Device access | Output for the change record |
|---|---|---|---|
| **Assess** | `./change.sh assess CHG0012345 intents/acme.json` | no | `summary.yml` (affected CIs, untouched CIs, additive-only or modify, backout command), `diff/<device>.diff` |
| **Scheduled** (just before the window) | `./change.sh precheck CHG0012345` | read (`--check --diff`) | running vs intended diff; anything beyond the approved diff = drift, so stop |
| **Implement** | `./change.sh implement CHG0012345` | write | deploy log, pre-change running-config backups |
| **Verify** | `./change.sh verify CHG0012345` | read | ANTA test report (AVD derives the tests from the fabric data) |
| **Backout** | `./change.sh backout CHG0012345` | write | redeploys the baseline build (full config replace) |

`precheck`, `implement`, `verify` and `backout` are limited to the affected CIs found by `assess`.

Output of `assess` for the acme tenant:

```
change: CHG0012345
affected_cis: border1,leaf3,leaf4
untouched: spine1
change_type: additive-only
implementation_plan: diff/*.diff
backout_plan: ./change.sh backout CHG0012345  (redeploys build/baseline)
```

`change_type: additive-only` is what lets the change service route this as a
**standard change**. A diff that removes or modifies lines comes out as `modify`,
which routes to the change board.

## How it works

```
inventory/group_vars/DC1/fabric.yml    fabric baseline (spines, leaves, pools, ASNs)
inventory/group_vars/DC1/tenants.yml   GENERATED tenants/servers/firewalls for one branch
                │
playbooks/build.yml     arista.avd.eos_designs + eos_cli_config_gen → build/<baseline|change>/intended/configs
playbooks/deploy.yml    arista.avd.eos_config_deploy_eapi (full replace; --check --diff for precheck)
playbooks/validate.yml  arista.avd.eos_validate_state (ANTA)
```

`assess` builds twice, once with the tenants already in service (`intents/in-service/`)
and once with those plus the new request, then diffs the results. Because deploys are
full-config replaces, backout means deploying the baseline build again.

## Connecting to Infrahub

| Offline demo (here) | With Infrahub |
|---|---|
| `inventory/static.yml` | `inventory/infrahub.yml` (`opsmill.infrahub.inventory`, one copy per change with `branch:` set) |
| `tools/intent_to_avd_vars.py intents/*.json` writes `tenants.yml` | `playbooks/fetch_tenant_vars.yml` pulls the `avd-tenant-vars` artifact for the branch (main = baseline, change branch = change) |

The Infrahub side of the wiring is syntax-checked only, not run against a live
Infrahub: the artifact transform, the `compose` and `groups` expressions, and the
device role names all depend on your data.

## Setup

```bash
pip install "pyavd==6.5.0" "ansible-core>=2.16" netaddr anta   # pyavd must equal the arista.avd version
ansible-galaxy collection install -r requirements.yml -p collections
export EOS_USER=... EOS_PASSWORD=...                           # eAPI credentials, from your vault/CI
```
