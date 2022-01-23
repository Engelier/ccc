#!/usr/bin/env python3
import ipaddress
import sys
import yaml
from typing import Union


CONTRACT_SCOPES = ['application-profile', 'context', 'global', 'tenant']
CONTRACT_TYPES = ['consumer', 'provider']
SUBNET_SCOPES = ['private', 'public', 'shared']


def fail_on_missing(obj: Union[dict, list], key: str, obj_name: str, *args: str) -> None:
    if key not in obj or (isinstance(obj, dict) and not obj[key]):
        print("ERROR:", key, "missing in", obj_name, ":", " -> ".join(args), file=sys.stderr)
        sys.exit(1)


def fail_on_present(obj: Union[dict, list], key: str, obj_name: str, *args: str) -> None:
    if key in obj:
        print("ERROR:", key, "redeclared in", obj_name, ":", " -> ".join(args), file=sys.stderr)
        sys.exit(1)


if len(sys.argv) != 2:
    print("ERROR: requires exactly one argument: The path to the input configuration to validate")
    sys.exit(1)

config_file = sys.argv[1]
try:
    with open(config_file, "r") as f:
        parsed_config = yaml.safe_load(f.read())
except yaml.YAMLError as e:
    print("Unable to parse YAML configutation", e)
    sys.exit(1)
except FileNotFoundError:
    print("ERROR: file not found:", config_file)
    sys.exit(1)
except PermissionError:
    print("ERROR: Permission denied:", config_file)
    sys.exit(1)

ansible_config = {
    'application_profiles': [],
    'bridge_domains': [],
    'bridge_domain_subnets': [],
    'contracts': [],
    'contract_subjects': [],
    'contract_subject_to_filters': [],
    'endpoint_groups': [],
    'endpoint_group_contracts': [],
    'filters': [],
    'tenants': [],
    'vrfs': [],
}

cache_tenants = []
fail_on_missing(parsed_config, 'tenants', 'config')
for tenant in parsed_config['tenants']:
    fail_on_missing(tenant, 'name', 'tenant')
    tenant_name = tenant['name']
    fail_on_missing(tenant, 'description', 'tenant', tenant_name)
    fail_on_missing(tenant, 'application_profiles', 'tenant', tenant_name)
    fail_on_missing(tenant, 'bridge_domains', 'tenant', tenant_name)
    fail_on_missing(tenant, 'vrfs', 'tenant', tenant_name)
    fail_on_missing(tenant, 'contracts', 'tenant', tenant_name)
    fail_on_present(cache_tenants, tenant_name, 'tenants')
    cache_tenants.append(tenant_name)
    ansible_config['tenants'].append({'tenant': tenant_name, 'description': tenant['description']})

    cache_vrfs = []
    for vrf in tenant['vrfs']:
        fail_on_missing(vrf, 'name', 'vrf', tenant_name)
        vrf_name = vrf['name']
        fail_on_present(cache_vrfs, vrf_name, tenant_name)
        cache_vrfs.append(vrf_name)
        ansible_config['vrfs'].append({'tenant': tenant_name, 'vrf': vrf_name})

    cache_contracts = []
    cache_filters = []
    for contract in tenant['contracts']:
        fail_on_missing(contract, 'name', 'contract', tenant_name)
        contract_name = contract['name']
        fail_on_missing(contract, 'scope', 'contract', tenant_name, contract_name)
        contract_scope = contract['scope']
        fail_on_missing(CONTRACT_SCOPES, contract_scope, 'valid contract scopes', tenant_name, contract_name)
        fail_on_missing(contract, 'subject', 'contract', tenant_name, contract_name)
        fail_on_present(cache_contracts, contract_name, tenant_name)
        cache_contracts.append(contract_name)
        ansible_config['contracts'].append({'tenant': tenant_name, 'contract': contract_name, 'scope': contract['scope']})

        cache_subjects = []
        for subject in contract['subject']:
            fail_on_missing(subject, 'name', 'subject', tenant_name, contract_name)
            subject_name = subject['name']
            fail_on_missing(subject, 'filter', 'subject', tenant_name, contract_name, subject_name)
            filter_name = subject['filter']
            fail_on_present(cache_subjects, subject_name, tenant_name, contract_name)
            cache_subjects.append(subject_name)
            ansible_config['contract_subjects'].append({'tenant': tenant_name, 'subject': subject_name, 'contract': contract_name})
            ansible_config['contract_subject_to_filters'].append({'tenant': tenant_name, 'contract': contract_name, 'subject': subject_name, 'filter': filter_name})
            if filter_name not in cache_filters:
                ansible_config['filters'].append({'tenant': tenant_name, 'filter': filter_name})
                cache_filters.append(filter_name)

    cache_bd = []
    cache_subnets = []
    for bridge_domain in tenant['bridge_domains']:
        fail_on_missing(bridge_domain, 'name', 'bridge_domain', tenant_name)
        bd_name = bridge_domain['name']
        fail_on_missing(bridge_domain, 'subnets', 'bridge_domain', tenant_name, bd_name)
        fail_on_missing(bridge_domain, 'vrf', 'bridge_domain', tenant_name, bd_name)
        vrf_name = bridge_domain['vrf']
        fail_on_missing(cache_vrfs, vrf_name, 'vrfs', tenant_name, bd_name)
        fail_on_present(cache_bd, bd_name, tenant_name)
        cache_bd.append(bd_name)
        ansible_config['bridge_domains'].append({'tenant': tenant_name, 'bd': bd_name, 'vrf': vrf_name})
        for subnet in bridge_domain['subnets']:
            fail_on_missing(subnet, 'name', 'subnet', tenant_name, bd_name)
            subnet_gateway = subnet['name']
            fail_on_missing(subnet, 'mask', 'subnet', tenant_name, bd_name, subnet_gateway)
            subnet_mask = subnet['mask']
            subnet_name = "{}/{}".format(subnet_gateway, subnet_mask)
            fail_on_missing(subnet, 'scope', 'subnet', tenant_name, bd_name, subnet_name)
            subnet_scope = subnet['scope']
            fail_on_missing(SUBNET_SCOPES, subnet_scope, 'valid subnet scopes', tenant_name, bd_name, subnet_name)
            fail_on_present(cache_subnets, subnet_name, tenant_name, bd_name)
            cache_subnets.append(subnet_name)
            ansible_config['bridge_domain_subnets'].append({'tenant': tenant_name, 'bd': bd_name, 'gateway': subnet_gateway, 'mask': subnet_mask})

    cache_ap = []
    for application_profile in tenant['application_profiles']:
        fail_on_missing(application_profile, 'name', 'application_profiles', tenant_name)
        application_profile_name = application_profile['name']
        fail_on_missing(application_profile, 'description', 'application_profiles', tenant_name, application_profile_name)
        fail_on_missing(application_profile, 'epgs', 'application_profiles', tenant_name, application_profile_name)
        fail_on_present(cache_ap, application_profile_name, tenant_name)
        cache_ap.append(application_profile_name)
        ansible_config['application_profiles'].append({'tenant': tenant_name, 'ap': application_profile_name, 'description': application_profile['description']})
        cache_epg = []
        for epg in application_profile['epgs']:
            fail_on_missing(epg, 'name', 'epgs', tenant_name, application_profile_name)
            epg_name = epg['name']
            fail_on_missing(epg, 'bd', 'epgs', tenant_name, application_profile_name, epg_name)
            epg_bd = epg['bd']
            fail_on_missing(cache_bd, epg_bd, 'bridge_domains', tenant_name, application_profile_name, epg_name)
            fail_on_missing(epg, 'contracts', 'epgs', tenant_name, application_profile_name, epg_name)
            fail_on_present(cache_epg, epg_name, 'epgs', tenant_name, application_profile_name)
            cache_epg.append(epg_name)
            ansible_config['endpoint_groups'].append({'tenant': tenant_name, 'ap': application_profile_name, 'bd': epg_bd, 'epg': epg_name})
            for contract in epg['contracts']:
                fail_on_missing(contract, 'name', 'ap_contract', tenant_name, application_profile_name, epg_name)
                contract_name = contract['name']
                fail_on_missing(cache_contracts, contract_name, 'contracts', tenant_name, application_profile_name, epg_name)
                fail_on_missing(contract, 'type', 'ap_contract', tenant_name, application_profile_name, epg_name, contract_name)
                contract_type = contract['type']
                fail_on_missing(CONTRACT_TYPES, contract_type, 'valid contract types', tenant_name, application_profile_name, epg_name, contract_name)
                ansible_config['endpoint_group_contracts'].append({'tenant': tenant_name, 'ap': application_profile_name, 'epg': epg_name, 'contract': contract_name, 'type': contract_type})


print(ansible_config)
