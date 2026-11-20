# Source mapping

Infrahub kind ↔ PAN-OS XML API (XPath) ↔ Terraform `panos` provider v2 ↔ OpenConfig.

The XPath and Terraform columns come from pan-os-codegen specs, generated with
`tools/panos_spec_to_infrahub.py --mapping` at the commit pinned in `scripts/fetch_upstream.sh`.
XPaths are shown for the first location. `$rulebase` is `pre-rulebase`, `post-rulebase` or `rulebase`.

OpenConfig has no model for zones, security policy, NAT objects or Panorama, so the neutral layer
borrows only from openconfig-interfaces, openconfig-if-aggregate, openconfig-network-instance and
openconfig-acl (rule actions). "—" means there is no equivalent.

## Policy objects

| Infrahub kind | pan-os-codegen spec | Terraform | XPath | OpenConfig |
|---|---|---|---|---|
| `SecurityIPAddress`, `SecurityPrefix`, `SecurityIPRange`, `SecurityFQDN`, `PanosIPWildcard` | `objects/address.yaml` (variants ip-netmask / ip-range / fqdn / ip-wildcard) | `panos_address`, `panos_addresses` | `/config/shared/address` | — |
| `SecurityAddressGroup` (static), `PanosDynamicAddressGroup` | `objects/address-group.yaml` (variants static / dynamic.filter) | `panos_address_group` | `/config/shared/address-group` | — |
| `PanosExternalDynamicList` | `objects/external-dynamic-list.yaml` | `panos_external_dynamic_list` | `/config/shared/external-list` | — |
| `SecurityService` | `objects/service.yaml` (protocol tcp/udp, port, source-port) | `panos_service` | `/config/shared/service` | — |
| `SecurityServiceGroup` | `objects/service-group.yaml` | `panos_service_group` | `/config/shared/service-group` | — |
| `SecurityApplication` | predefined App-ID content (custom: `objects/application.yaml`) | `panos_application` (custom apps) | `/config/shared/application` | — |
| `SecurityApplicationGroup` | `objects/application-group.yaml` | `panos_application_group` | `/config/shared/application-group` | — |
| `PanosApplicationFilter` | not in codegen yet | — | `/config/shared/application-filter` | — |
| `BuiltinTag.panos_color` | `objects/administrative-tag.yaml` | `panos_administrative_tag` | `/config/shared/tag` | — |
| `PanosSchedule` | `objects/schedule.yaml` | `panos_schedule` | `/config/shared/schedule` | — |
| `PanosSecurityProfile` | `objects/profiles/{antivirus,url-filtering,vulnerability,file-blocking,wildfire-analysis}.yaml`, `network/profiles/anti-spyware-profile.yaml` | `panos_antivirus_security_profile`, `panos_url_filtering_security_profile`, … | `/config/shared/profiles/<type>` | — |
| `PanosSecurityProfileGroup` | `objects/profiles/security-profile-group.yaml` | `panos_security_profile_group` | `/config/shared/profile-group` | — |
| `PanosLogForwardingProfile` | `objects/profiles/log-forwarding.yaml` | `panos_log_forwarding_profile` | `/config/shared/log-settings/profiles` | — |
| `PanosCertificateProfile` | `objects/profiles/certificate.yaml` | `panos_certificate_profile` | `/config/panorama/certificate-profile` | — |

## Policies

| Infrahub kind | pan-os-codegen spec | Terraform | XPath | OpenConfig |
|---|---|---|---|---|
| `SecurityPolicy` / `PanosRulebase` | rulebase container | — | `/config/shared/$rulebase` | `acl-set` (loosely) |
| `SecurityPolicyRule` / `PanosSecurityRule` | `policies/security-policy-rule.yaml` | `panos_security_policy`, `panos_security_policy_rules` | `/config/shared/$rulebase/security/rules` | `acl-entry` + `actions/forwarding-action` |
| `SecurityNatRule` / `PanosNatRule` | `policies/network-address-translation.yaml` | `panos_nat_policy`, `panos_nat_policy_rules` | `/config/shared/$rulebase/nat/rules` | — |

### PAN-OS security rule field map

| PAN-OS field | Infrahub |
|---|---|
| `from` / `to` | `source_zones` / `destination_zones` |
| `source` / `destination` | `source_addresses` + `source_address_groups` / `destination_*` |
| `negate-source` / `negate-destination` | `negate_source` / `negate_destination` |
| `source-user` | `source_users` (List) |
| `source-hip` / `destination-hip` | `source_hip` / `destination_hip` (List) |
| `application` | `applications` |
| `service` (`application-default`, `any`, names) | `application_default`, `services` + `service_groups` (empty = any) |
| `category` | `url_categories` (List) |
| `action` | `action` + `reject_mode` (see design.md) |
| `rule-type` | `rule_type` |
| `log-start` / `log-end` / `log-setting` | `log_start` / `log` / `log_forwarding_profile` |
| `profile-setting.group` / `.profiles.*` | `profile_group` / `security_profiles` |
| `schedule` | `schedule` |
| `disabled` | `enabled` (inverted) |
| `tag` / `group-tag` | `tags` / `group_tag` |
| `target.devices` / `target.negate` | `target_firewalls` / `target_negate` |
| `disable-server-response-inspection`, `icmp-unreachable`, `uuid` | same names (snake_case) |
| `description` | `description` |
| not modeled yet | `qos.marking`, `source-imei`, `source-imsi`, `source-nw-slice`, `disable-inspect` |

### PAN-OS NAT rule field map

| PAN-OS field | Infrahub |
|---|---|
| `from` / `to` / `to-interface` | `source_zones` / `destination_zones` / `to_interface` |
| `source` / `destination` / `service` | `source_addresses`(+groups) / `destination_addresses`(+groups) / `service` |
| `nat-type` | `nat_type` |
| `source-translation.{dynamic-ip-and-port,dynamic-ip,static-ip}` | `source_translation_type` |
| `…translated-address` / `…interface-address.interface` | `translated_source_addresses` / `translated_source_interface` |
| `static-ip.bi-directional` | `bidirectional` |
| `destination-translation` / `dynamic-destination-translation` | `destination_translation_type` = static / dynamic |
| `…translated-address` / `…translated-port` | `translated_destination_address` / `translated_destination_port` |
| `dynamic-destination-translation.distribution` | `dynamic_distribution` |
| `destination-translation.dns-rewrite.direction` | `dns_rewrite` |
| `active-active-device-binding`, `target.*`, `uuid` | same names |
| not modeled yet | `dynamic-ip.fallback`, `interface-address.ip/floating-ip` |

## Network

| Infrahub kind | pan-os-codegen spec | Terraform | XPath | OpenConfig |
|---|---|---|---|---|
| `SecurityZone` / `PanosZone` | `network/zone.yaml` | `panos_zone` | `/config/devices/$ngfw_device/vsys/$vsys/zone` | — |
| `PanosZoneProtectionProfile` | `network/profiles/zone-protection.yaml` | `panos_zone_protection_profile` | `…/network/profiles/zone-protection-profile` | — |
| `PanosInterfaceManagementProfile` | `network/profiles/interface-management-profile.yaml` | `panos_interface_management_profile` | `…/network/profiles/interface-management-profile` | — |
| `PanosEthernetInterface` | `network/interface/ethernet.yaml` | `panos_ethernet_interface` | `…/network/interface/ethernet` | `/interfaces/interface` (+ `ethernet/config/{port-speed,duplex-mode,aggregate-id}`) |
| `PanosAggregateInterface` | `network/interface/aggregate.yaml` | `panos_aggregate_interface` | `…/network/interface/aggregate-ethernet` | `/interfaces/interface/aggregation` |
| `PanosSubInterface` | `network/subinterface/ethernet/layer3.yaml` | `panos_ethernet_layer3_subinterface` | `…/ethernet/$parent/layer3/units/$name` | `/interfaces/interface/subinterfaces/subinterface` |
| `PanosLoopbackInterface` | `network/interface/loopback.yaml` | `panos_loopback_interface` | `…/network/interface/loopback/units` | `/interfaces/interface` (type softwareLoopback) |
| `PanosTunnelInterface` | `network/interface/tunnel.yaml` | `panos_tunnel_interface` | `…/network/interface/tunnel/units` | `/interfaces/interface` (type tunnel) |
| `PanosVlanInterface` | `network/interface/vlan.yaml` | `panos_vlan_interface` | `…/network/interface/vlan/units` | `/interfaces/interface/routed-vlan` |
| `PanosVirtualRouter` | `network/virtual-router.yaml`, `network/logical-router.yaml` | `panos_virtual_router`, `panos_logical_router` | `…/network/virtual-router` | `/network-instances/network-instance` (L3VRF) |
| `PanosStaticRoute` | `network/virtual-router-static-route-ipv4.yaml` | `panos_virtual_router_static_route_ipv4` | `…/virtual-router/$parent/routing-table/ip/static-route` | `…/protocols/protocol[STATIC]/static-routes/static` |

## Management plane

| Infrahub kind | pan-os-codegen spec | Terraform | XPath |
|---|---|---|---|
| `PanosPanorama` | — | — | `/config/devices/$panorama_device` |
| `PanosDeviceGroup` (+ `parent`) | `panorama/device-group.yaml`, `panorama/device-group-parent.yaml` | `panos_device_group`, `panos_device_group_parent` | `/config/devices/$panorama_device/device-group` |
| `PanosTemplate` | `panorama/template.yaml` | `panos_template` | `/config/devices/$panorama_device/template` |
| `PanosTemplateStack` (+ `PanosTemplateStackEntry`) | `panorama/template-stack.yaml` | `panos_template_stack` | `/config/devices/$panorama_device/template-stack` |
| `PanosVsys` | `device/vsys.yaml` | `panos_vsys` | `…/template/$template/config/devices/$ngfw_device/vsys` |
| `PanosFirewall` | — (device-level settings in `device/general.yaml`) | `panos_general_settings` | `/config/devices/$ngfw_device` |
