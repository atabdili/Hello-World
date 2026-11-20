#!/usr/bin/env bash
# Change-workflow driver for the fabric side. The change service calls one
# stage per change-record state; every stage writes its evidence to
# build/change-record/ for attaching to the ticket.
#
#   ./change.sh assess    CHG0012345 intents/acme.json   # Assess: render + diff, no device access
#   ./change.sh precheck  CHG0012345                     # Scheduled: running vs intended (drift)
#   ./change.sh implement CHG0012345                     # Implement: deploy change build
#   ./change.sh verify    CHG0012345                     # Verify: ANTA post-checks
#   ./change.sh backout   CHG0012345                     # Backout: redeploy baseline build
#
# Offline, tenant vars come from intents/ via tools/intent_to_avd_vars.py.
# With Infrahub, replace render_vars() by:
#   ansible-playbook playbooks/fetch_tenant_vars.yml -e infrahub_branch=<main|CHG-branch>
set -euo pipefail
cd "$(dirname "$0")"

stage=${1:?stage}; chg=${2:?change number}; shift 2
rec=build/change-record; mkdir -p "$rec"
in_service=(intents/in-service/*.json)          # tenants already on main
[ -e "${in_service[0]}" ] || in_service=()

render_vars() { tools/intent_to_avd_vars.py "$@" > inventory/group_vars/DC1/tenants.yml; }
build()       { ansible-playbook playbooks/build.yml -e build_name="$1" >"$rec/build-$1.log"; }
affected()    { ls "$rec"/diff/*.diff 2>/dev/null | xargs -rn1 basename | sed 's/\.diff$//' | paste -sd, -; }

case "$stage" in
  assess)
    render_vars "${in_service[@]}";      build baseline
    render_vars "${in_service[@]}" "$@"; build change
    rm -rf "$rec/diff"; mkdir -p "$rec/diff"
    for cfg in build/change/intended/configs/*.cfg; do
      dev=$(basename "$cfg" .cfg)
      diff -u --label "$dev (baseline)" --label "$dev ($chg)" \
        "build/baseline/intended/configs/$dev.cfg" "$cfg" > "$rec/diff/$dev.diff" || true
      [ -s "$rec/diff/$dev.diff" ] || rm "$rec/diff/$dev.diff"
    done
    {
      echo "change: $chg"
      echo "affected_cis: $(affected)"
      echo "untouched: $(comm -23 <(ls build/change/intended/configs | sed 's/\.cfg$//' | sort) \
                                 <(affected | tr , '\n' | sort) | paste -sd, -)"
      echo "change_type: $(grep -q '^-[^-]' "$rec"/diff/*.diff && echo modify || echo additive-only)"
      echo "implementation_plan: diff/*.diff"
      echo "backout_plan: ./change.sh backout $chg  (redeploys build/baseline)"
    } > "$rec/summary.yml"
    render_vars "${in_service[@]}"      # leave the working tree at baseline
    cat "$rec/summary.yml" ;;
  precheck)  ansible-playbook playbooks/deploy.yml -e build_name=change --check --diff --limit "$(affected)" | tee "$rec/precheck.log" ;;
  implement) ansible-playbook playbooks/deploy.yml -e build_name=change --limit "$(affected)" | tee "$rec/implement.log" ;;
  verify)    ansible-playbook playbooks/validate.yml -e build_name=change --limit "$(affected)" | tee "$rec/verify.log" ;;
  backout)   ansible-playbook playbooks/deploy.yml -e build_name=baseline --limit "$(affected)" | tee "$rec/backout.log" ;;
  *) echo "unknown stage $stage" >&2; exit 2 ;;
esac
