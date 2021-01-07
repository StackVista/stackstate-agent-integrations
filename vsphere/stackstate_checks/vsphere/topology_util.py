# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)


# different component types
class vsphere_component_types:
    VM = "vsphere-VirtualMachine"
    DATACENTER = "vsphere-Datacenter"
    HOST = "vsphere-HostSystem"
    DATASTORE = "vsphere-Datastore"
    CLUSTERCOMPUTERESOURCE = "vsphere-ClusterComputeResource"
    COMPUTERESOURCE = "vsphere-ComputeResource"


# different relation types
class vsphere_relation_types:
    VM_HOST = 'vsphere-vm-is-hosted-on'
    VM_DATASTORE = 'vsphere-vm-uses-datastore'
    HOST_COMPUTERESOURCE = 'vsphere-hostsystem-belongs-to'
    DATASTORE_COMPUTERESOURCE = 'vsphere-datastore-belongs-to'
    HOST_DATASTORE = 'vsphere-hostsystem-uses-datastore'
    DATASTORE_DATACENTER = 'vsphere-datastore-is-located-on'
    CLUSTERCOMPUTERESOURCE_DATACENTER = 'vsphere-clustercomputeresource-is-located-on'
    COMPUTERESOURCE_DATACENTER = 'vsphere-computeresources-is-located-on'


# different topology layers
class vsphere_layers:
    DATASTORE = 'VSphere Datastores'
    HOST = 'VSphere Hosts'
    VM = 'VSphere VMs'
    COMPUTERESOURCE = 'VSphere Compute Resources'
    DATACENTER = 'VSphere Datacenter'


def add_label_pair(label_list, key, value):
    label_list.append("{0}:{1}".format(key, value))
