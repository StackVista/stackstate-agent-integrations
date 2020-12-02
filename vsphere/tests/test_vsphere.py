# stdlib
import unittest

# 3p
from mock import Mock, MagicMock
from pyVmomi import vim  # pylint: disable=E0611
import simplejson as json
import pytest

try:
    from Queue import Queue
except ImportError:
    from queue import Queue
import requests
from vmware.vapi.bindings.stub import ApiClient
from vmware.vapi.lib.connect import get_requests_connector
from vmware.vapi.stdlib.client.factories import StubConfigurationFactory

from vmware.vapi.vsphere.client import StubFactory
from com.vmware.cis.tagging_client import TagModel, CategoryModel

from stackstate_checks.vsphere import VSphereCheck
from stackstate_checks.base.stubs import topology, aggregator

CHECK_NAME = "vsphere-test"


def vsphere_client():
    stub_config = StubConfigurationFactory.new_std_configuration(
        get_requests_connector(session=requests.session(), url='https://localhost/vapi'))
    stub_factory = StubFactory(stub_config)
    client = ApiClient(stub_factory)
    return client


class VsphereTag(TagModel):
    """
    Helper, generate a mocked TagModel from the given attributes.
    """

    def __init__(self, id, name, category_id):
        self.name = name
        self.description = "stackstate defined atributes"
        self.category_id = category_id
        self.id = id
        super(VsphereTag, self).__init__(self.id, self.category_id, self.name, self.description)


class VsphereCategory(CategoryModel):
    """
    Helper, generate a mocked CategoryModel from the given attributes.
    """

    def __init__(self, id, name):
        self.name = name
        self.description = "stackstate category"
        self.id = id
        super(VsphereCategory, self).__init__(self.id, self.name, self.description)


class MockedMOR(Mock):
    """
    Helper, generate a mocked Managed Object Reference (MOR) from the given attributes.
    """

    def __init__(self, **kwargs):
        # Deserialize `spec`
        if 'spec' in kwargs:
            kwargs['spec'] = getattr(vim, kwargs['spec'])

        # Mocking
        super(MockedMOR, self).__init__(**kwargs)

        # Handle special attributes
        name = kwargs.get('name')
        is_labeled = kwargs.get('label', False)

        self.name = name
        self.parent = None
        self.customValue = []

        if is_labeled:
            self.customValue.append(Mock(value="StackStateMonitored"))


class MockedContainer(Mock):
    TYPES = [vim.Datacenter, vim.Datastore, vim.HostSystem, vim.VirtualMachine]

    def __init__(self, **kwargs):
        # Mocking
        super(MockedContainer, self).__init__(**kwargs)

        self.topology = kwargs.get('topology')
        self.view_idx = 0

    def container_view(self, topology_node, vimtype):
        view = []

        def get_child_topology(attribute):
            entity = getattr(topology_node, attribute)
            try:
                for child in entity:
                    child_topology = self.container_view(child, vimtype)
                    view.extend(child_topology)
            except TypeError:
                child_topology = self.container_view(entity, vimtype)
                view.extend(child_topology)

        if isinstance(topology_node, vimtype):
            view = [topology_node]

        if hasattr(topology_node, 'childEntity'):
            get_child_topology('childEntity')
        elif hasattr(topology_node, 'hostFolder'):
            get_child_topology('hostFolder')
        elif hasattr(topology_node, 'host'):
            get_child_topology('host')
        elif hasattr(topology_node, 'vm'):
            get_child_topology('vm')

        return view

    @property
    def view(self):
        view = self.container_view(self.topology, self.TYPES[self.view_idx])
        self.view_idx += 1
        self.view_idx = self.view_idx % len(self.TYPES)
        return view


def create_topology(topology_json):
    """
    Helper, recursively generate a vCenter topology from a JSON description.
    Return a `MockedMOR` object.
    Examples:
      ```
      topology_desc = "
        {
          "childEntity": [
            {
              "hostFolder": {
                "childEntity": [
                  {
                    "spec": "ClusterComputeResource",
                    "name": "compute_resource1"
                  }
                ]
              },
              "spec": "Datacenter",
              "name": "datacenter1"
            }
          ],
          "spec": "Folder",
          "name": "rootFolder"
        }
      "
      topo = create_topology(topology_desc)
      assert isinstance(topo, Folder)
      assert isinstance(topo.childEntity[0].name) == "compute_resource1"
      ```
    """

    def rec_build(topology_desc):
        """
        Build MORs recursively.
        """
        parsed_topology = {}

        for field, value in topology_desc.items():
            parsed_value = value
            if isinstance(value, dict):
                parsed_value = rec_build(value)
            elif isinstance(value, list):
                parsed_value = [rec_build(obj) for obj in value]
            else:
                parsed_value = value
            parsed_topology[field] = parsed_value

        mor = MockedMOR(**parsed_topology)

        # set parent
        for field, value in topology_desc.items():
            if isinstance(parsed_topology[field], list):
                for m in parsed_topology[field]:
                    if isinstance(m, MockedMOR):
                        m.parent = mor
            elif isinstance(parsed_topology[field], MockedMOR):
                parsed_topology[field].parent = mor

        return mor

    with open("./tests/data/" + topology_json, "r") as f:
        return rec_build(json.load(f))


@pytest.mark.usefixtures("instance")
class TestvSphereUnit(unittest.TestCase):
    """
    Unit tests for vSphere AgentCheck.
    """
    CHECK_NAME = "vsphere"

    def assertMOR(self, instance, name=None, spec=None, tags=None, count=None, subset=False):
        """
        Helper, assertion on vCenter Manage Object References.
        """
        instance_name = instance['name']
        candidates = []

        if spec:
            mor_list = self.check.morlist_raw[instance_name][spec]
        else:
            mor_list = [mor for _, mors in self.check.morlist_raw[instance_name].items() for mor in mors]

        for mor in mor_list:
            if name is not None and name != mor['hostname']:
                continue

            if spec is not None and spec != mor['mor_type']:
                continue

            if tags is not None:
                if subset:
                    if not set(tags).issubset(set(mor['tags'])):
                        continue
                elif set(tags) != set(mor['tags']):
                    continue

            candidates.append(mor)

        # Assertions
        if count:
            self.assertEquals(len(candidates), count)
        else:
            self.assertFalse(len(candidates))

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        * disable threading
        * create a unique container for MORs independent of the instance key
        """
        # Initialize
        config = {}
        self.check = VSphereCheck(CHECK_NAME, config, instances=[self.instance])

        # Disable threading
        self.check.pool = Mock(apply_async=lambda func, args: func(*args))

        # Create a container for MORs
        self.check.morlist_raw = {}

    def test_exclude_host(self):
        """
        Exclude hosts/vms not compliant with the user's `*_include` configuration.
        """
        # Method to test
        is_excluded = self.check._is_excluded

        # Sample(s)
        include_regexes = {
            'host_include': "f[o]+",
            'vm_include': "f[o]+",
        }

        # OK
        included_host = MockedMOR(spec="HostSystem", name="foo")
        included_vm = MockedMOR(spec="VirtualMachine", name="foo")

        self.assertFalse(is_excluded(included_host, include_regexes, None))
        self.assertFalse(is_excluded(included_vm, include_regexes, None))

        # Not OK!
        excluded_host = MockedMOR(spec="HostSystem", name="bar")
        excluded_vm = MockedMOR(spec="VirtualMachine", name="bar")

        self.assertTrue(is_excluded(excluded_host, include_regexes, None))
        self.assertTrue(is_excluded(excluded_vm, include_regexes, None))

    def test_exclude_non_labeled_vm(self):
        """
        Exclude "non-labeled" virtual machines when the user configuration instructs to.
        """
        # Method to test
        is_excluded = self.check._is_excluded

        # Sample(s)
        include_regexes = None
        include_only_marked = True

        # OK
        included_vm = MockedMOR(spec="VirtualMachine", name="foo", label=True)
        self.assertFalse(is_excluded(included_vm, include_regexes, include_only_marked))

        # Not OK
        included_vm = MockedMOR(spec="VirtualMachine", name="foo")
        self.assertTrue(is_excluded(included_vm, include_regexes, include_only_marked))

    def test_mor_discovery(self):
        """
        Explore the vCenter infrastructure to discover hosts, virtual machines.
        Input topology:
            ```
            rootFolder
                - datacenter1
                  - compute_resource1
                      - host1                   # Filtered out
                      - host2
                - folder1
                    - datacenter2
                      - compute_resource2
                          - host3
                            - vm1               # Not labeled
                            - vm2               # Filtered out
                            - vm3               # Powered off
                            - vm4
            ```
        """
        # Method to test
        discover_mor = self.check._discover_mor

        # Samples
        instance = {'name': 'vsphere_mock'}
        vcenter_topology = create_topology('vsphere_topology.json')
        tags = [u"toto"]
        include_regexes = {
            'host_include': "host[2-9]",
            'vm_include': "vm[^2]",
        }
        include_only_marked = True

        # mock pyvmomi stuff
        view_mock = MockedContainer(topology=vcenter_topology)
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': content_mock})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        # Discover hosts and virtual machines
        discover_mor(instance, tags, include_regexes, include_only_marked)

        # Assertions: 1 labaled+monitored VM + 2 hosts + 2 datacenters.
        self.assertMOR(instance, count=7)

        # ... on hosts
        self.assertMOR(instance, spec="host", count=2)
        self.assertMOR(
            instance,
            name="host2", spec="host",
            tags=[
                u"toto", u"vsphere_folder:rootFolder", u"vsphere_datacenter:datacenter1",
                u"vsphere_compute:compute_resource1", u"vsphere_cluster:compute_resource1",
                u"vsphere_type:host"
            ]
        )
        self.assertMOR(
            instance,
            name="host3", spec="host",
            tags=[
                u"toto", u"vsphere_folder:rootFolder", u"vsphere_folder:folder1",
                u"vsphere_datacenter:datacenter2", u"vsphere_compute:compute_resource2",
                u"vsphere_cluster:compute_resource2", u"vsphere_type:host"
            ]
        )

        # ...on VMs
        self.assertMOR(instance, spec="vm")
        self.assertMOR(
            instance,
            name="vm4", spec="vm", subset=True,
            tags=[
                u"toto", u"vsphere_folder:folder1", u"vsphere_datacenter:datacenter2",
                u"vsphere_compute:compute_resource2", u"vsphere_cluster:compute_resource2",
                u"vsphere_host:host3", u"vsphere_type:vm"
            ]
        )


@pytest.mark.usefixtures("instance")
class TestVsphereTopo(unittest.TestCase):
    CHECK_NAME = "vsphere"

    def mock_content(self, vimtype):
        # summary object for datastore
        ds_summary = MockedMOR(accessible="true", capacity=987959765, type="VMFS",
                               url='/vmfs/volumes/54183927-04f91918-a72a-6805ca147c55')
        # hardware and config object needed for vms
        vm_config_hardware = MockedMOR(numCPU=1, memoryMB=4096)
        config = MockedMOR(guestId='ubuntu64Guest', guestFullName='Ubuntu Linux (64-bit)', hardware=vm_config_hardware)

        datastore = MockedMOR(spec='Datastore', _moId="54183927-04f91918-a72a-6805ca147c55", name="WDC1TB")
        virtualmachine = MockedMOR(spec=u"VirtualMachine", name=u"Ubuntu", datastore=[datastore], config=config,
                                   _moId=u"vm-12")
        host = MockedMOR(spec=u"HostSystem", name=u"localhost.localdomain", datastore=[datastore], vm=[virtualmachine],
                         _moId="host-1")
        computeresource = MockedMOR(spec=u"ComputeResource", name="localhost", datastore=[datastore], host=[host],
                                    _moId="cr-1")
        clustercomputeresource = MockedMOR(spec="ClusterComputeResource", name="local",
                                           datastore=[datastore], host=[host], _moId="ccr-12")

        datacenter = MockedMOR(spec="Datacenter", name="da-Datacenter", _moId="54183347-04d231918",
                               hostFolder=MockedMOR(childEntity=[computeresource]), datastore=[datastore])

        if vimtype == 'vm':
            view_mock = MagicMock(view=[virtualmachine])
        elif vimtype == 'dc':
            view_mock = MagicMock(view=[datacenter])
        elif vimtype == 'ds':
            datastore.summary = ds_summary
            datastore.vm = [virtualmachine]
            view_mock = MagicMock(view=[datastore])
        elif vimtype == 'host':
            host.parent = computeresource
            view_mock = MagicMock(view=[host])
        elif vimtype == 'cluster':
            view_mock = MagicMock(view=[clustercomputeresource])
        else:
            view_mock = MagicMock(view=[computeresource])

        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        return content_mock

    def setUp(self):
        """
        Initialize and patch the check, i.e.
        * disable threading
        * create a unique container for MORs independent of the instance key
        """
        # Initialize
        config = {}
        self.check = VSphereCheck(CHECK_NAME, config, instances=[self.instance])

    def test_vsphere_vms(self):
        """
        Test if the vsphere_vms returns the VM list and labels
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns empty list of tags
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the vsphere check client object
        self.check.client = client

        content_mock = self.mock_content("vm")
        obj_list = self.check._vsphere_vms(content_mock, "ESXi")

        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['hostname'], 'Ubuntu')

        # check there should be no tags and labels extracted from vspher client
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # Check if labels are added
        self.assertTrue(obj_list[0]['topo_tags']["labels"])
        expected_name_label = obj_list[0]['topo_tags']["labels"][0]
        expected_guestid_label = obj_list[0]['topo_tags']["labels"][1]
        expected_numcpu_label = obj_list[0]['topo_tags']["labels"][3]
        expected_memory_label = obj_list[0]['topo_tags']["labels"][4]

        # Check if the labels are as expected
        self.assertEqual(expected_name_label, 'name:Ubuntu')
        self.assertEqual(expected_guestid_label, 'guestId:ubuntu64Guest')
        self.assertEqual(expected_numcpu_label, 'numCPU:1')
        self.assertEqual(expected_memory_label, 'memoryMB:4096')

    def test_vsphere_vms_metadata_datastore_exception(self):
        """
        Test if the vsphere_vms returns the VM list and labels even in case of exception occurred for datastore
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns empty list of tags
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the vsphere check client object
        self.check.client = client

        config = MockedMOR(guestId='ubuntu64Guest', guestFullName='Ubuntu Linux (64-bit)')
        virtualmachine = MockedMOR(spec=u"VirtualMachine", name=u"Ubuntu", config=config, _moId=u"vm-12")
        view_mock = MagicMock(view=[virtualmachine])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_vms(content_mock, "ESXi")

        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['hostname'], 'Ubuntu')

        # check there should be no identifiers extracted from vsphere client
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # No labels should be added as it throws exception because datastore doesn't exist
        self.assertEqual(len(obj_list[0]['topo_tags']["labels"]), 0)
        self.assertEqual(obj_list[0]['topo_tags']["layer"], "VSphere VMs")

    def test_vsphere_datacenters(self):
        """
        Test if the vsphere_datacenter returns the datacenter list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # mock the CategoryModel and TagModel for response
        category = VsphereCategory('345', 'stackstate-label')
        tags = VsphereTag('123', 'vishal-test', '345')

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=['123'])
        # get method of Tag returns a TagModel object which is returned
        client.tagging.Tag.get = MagicMock(return_value=tags)
        # get method of Category returns a CategoryModel object which is returned
        client.tagging.Category.get = MagicMock(return_value=category)

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        content_mock = self.mock_content("dc")
        obj_list = self.check._vsphere_datacenters(content_mock, "ESXi")

        # expect a label coming from Tagging model of datacenter
        expected_name_label = obj_list[0]['topo_tags']["labels"][0]
        self.assertEqual(expected_name_label, 'stackstate-label:vishal-test')
        # identifier should be empty
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        self.assertEqual(len(obj_list), 1)
        self.assertEqual(type(obj_list[0]['topo_tags']['datastores']), list)
        self.assertEqual(obj_list[0]['topo_tags']['datastores'][0], 'WDC1TB')
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'da-Datacenter')

    def test_vsphere_datacenters_metadata_exception(self):
        """
        Test if the vsphere_datacenter returns the datacenter list in case of optional data exception
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # mock the CategoryModel and TagModel for response
        category = VsphereCategory('345', 'stackstate-label')
        tags = VsphereTag('123', 'vishal-test', '345')

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=['123'])
        # get method of Tag returns a TagModel object which is returned
        client.tagging.Tag.get = MagicMock(return_value=tags)
        # get method of Category returns a CategoryModel object which is returned
        client.tagging.Category.get = MagicMock(return_value=category)

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        datacenter = MockedMOR(spec="Datacenter", name="da-Datacenter", _moId="54183347-04d231918")
        view_mock = MagicMock(view=[datacenter])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_datacenters(content_mock, "ESXi")

        # should have one component even if data section fails
        self.assertEqual(len(obj_list), 1)

        # expect a label coming from Tagging model of datacenter
        expected_name_label = obj_list[0]['topo_tags']["labels"][0]
        self.assertEqual(expected_name_label, 'stackstate-label:vishal-test')
        # identifier should be empty
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        self.assertEqual(obj_list[0]['topo_tags']['name'], 'da-Datacenter')

    def test_vsphere_datastores(self):
        """
        Test if the vsphere_datastores returns the datastores list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        content_mock = self.mock_content("dc")
        obj_list = self.check._vsphere_datacenters(content_mock, "ESXi")

        # expect an empty identifier list
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        content_mock = self.mock_content("ds")
        obj_list = self.check._vsphere_datastores(content_mock, "ESXi")

        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['type'], 'VMFS')
        self.assertEqual(obj_list[0]['topo_tags']['accessible'], 'true')
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'WDC1TB')
        self.assertEqual(obj_list[0]['topo_tags']['url'], '/vmfs/volumes/54183927-04f91918-a72a-6805ca147c55')
        self.assertEqual(type(obj_list[0]['topo_tags']['capacity']), str)

    def test_vsphere_datastores_metadata_exception(self):
        """
        Test if the vsphere_datastores returns the datastores list in case of exception as well
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        datastore = MockedMOR(spec='Datastore', _moId="54183927-04f91918-a72a-6805ca147c55", name="WDC1TB")
        view_mock = MagicMock(view=[datastore])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_datastores(content_mock, "ESXi")

        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'WDC1TB')

    def test_vsphere_hosts(self):
        """
        Test if the vsphere_hosts returns the hosts list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # mock the CategoryModel and TagModel for response
        category = VsphereCategory('345', 'stackstate-identifier')
        tags = VsphereTag('123', 'vishal-test', '345')

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=['123'])
        # get method of Tag returns a TagModel object which is returned
        client.tagging.Tag.get = MagicMock(return_value=tags)
        # get method of Category returns a CategoryModel object which is returned
        client.tagging.Category.get = MagicMock(return_value=category)

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        content_mock = self.mock_content("host")
        obj_list = self.check._vsphere_hosts(content_mock, "ESXi")

        # one identifier expected
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 1)
        self.assertEqual(obj_list[0]['topo_tags']['identifiers'][0], "vishal-test")

        # Check if host has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'localhost.localdomain')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-HostSystem')
        # Check if host list contains vm, datastore and computeresource
        self.assertEqual(obj_list[0]['topo_tags']['vms'][0], 'Ubuntu')
        self.assertEqual(obj_list[0]['topo_tags']['datastores'][0], 'WDC1TB')
        self.assertEqual(obj_list[0]['topo_tags']['computeresource'], 'localhost')

    def test_vsphere_hosts_metadata_exception(self):
        """
        Test if the vsphere_hosts returns the hosts list even in case of exception
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # mock the CategoryModel and TagModel for response
        category = VsphereCategory('345', 'stackstate-identifier')
        tags = VsphereTag('123', 'vishal-test', '345')

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=['123'])
        # get method of Tag returns a TagModel object which is returned
        client.tagging.Tag.get = MagicMock(return_value=tags)
        # get method of Category returns a CategoryModel object which is returned
        client.tagging.Category.get = MagicMock(return_value=category)

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        host = MockedMOR(spec=u"HostSystem", name=u"localhost.localdomain", _moId="host-1")
        view_mock = MagicMock(view=[host])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_hosts(content_mock, "ESXi")

        # one identifier expected
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 1)
        self.assertEqual(obj_list[0]['topo_tags']['identifiers'][0], "vishal-test")

        # Check if host has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'localhost.localdomain')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-HostSystem')
        # since exception had occurred while collecting datastores/vms, so noo labels should have been created
        self.assertEqual(len(obj_list[0]['topo_tags']['labels']), 0)

    def test_vsphere_clustercomputeresources(self):
        """
        Test if the vsphere_clustercomputeresources returns the cluster list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        content_mock = self.mock_content("cluster")
        obj_list = self.check._vsphere_clustercomputeresources(content_mock, "ESXi")

        # expect an empty identifier list
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # Check if clustercomputeresources has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'local')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-ClusterComputeResource')
        # Check if clustercomputeresources list contains host and datastore
        self.assertEqual(obj_list[0]['topo_tags']['hosts'][0], 'localhost.localdomain')
        self.assertEqual(obj_list[0]['topo_tags']['datastores'][0], 'WDC1TB')

    def test_vsphere_clustercomputeresources_metadata_exception(self):
        """
        Test if the vsphere_clustercomputeresources returns the cluster list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        clustercomputeresource = MockedMOR(spec="ClusterComputeResource", name="local", _moId="ccr-12")
        view_mock = MagicMock(view=[clustercomputeresource])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_clustercomputeresources(content_mock, "ESXi")

        # expect an empty identifier list
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # Check if clustercomputeresources has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'local')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-ClusterComputeResource')
        # since exception had occurred while collecting datastores/hosts, so no labels should have been created
        self.assertEqual(len(obj_list[0]['topo_tags']['labels']), 0)

    def test_vsphere_computeresources(self):
        """
        Test if the vsphere_computeresources returns the computeresource list
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        content_mock = self.mock_content("compute")
        obj_list = self.check._vsphere_computeresources(content_mock, "ESXi")

        # expect an empty identifier list
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # Check if computeresources has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'localhost')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-ComputeResource')
        # Check if computeresources list contains host and datastore
        self.assertEqual(obj_list[0]['topo_tags']['hosts'][0], 'localhost.localdomain')
        self.assertEqual(obj_list[0]['topo_tags']['datastores'][0], 'WDC1TB')

    def test_vsphere_computeresources_metadata_exception(self):
        """
        Test if the vsphere_computeresources returns the computeresource list even in case of exception
        """
        self.check._is_excluded = MagicMock(return_value=False)

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        computeresource = MockedMOR(spec=u"ComputeResource", name="localhost", _moId="cr-1")
        view_mock = MagicMock(view=[computeresource])
        viewmanager_mock = MagicMock(**{'CreateContainerView.return_value': view_mock})
        content_mock = MagicMock(viewManager=viewmanager_mock)
        obj_list = self.check._vsphere_computeresources(content_mock, "ESXi")

        # expect an empty identifier list
        self.assertEqual(len(obj_list[0]['topo_tags']['identifiers']), 0)

        # Check if computeresources has tags name and topo_type
        self.assertEqual(len(obj_list), 1)
        self.assertEqual(obj_list[0]['topo_tags']['name'], 'localhost')
        self.assertEqual(obj_list[0]['topo_tags']['topo_type'], 'vsphere-ComputeResource')
        # since exception had occurred while collecting datastores/hosts, so no labels should have been created
        self.assertEqual(len(obj_list[0]['topo_tags']['labels']), 0)

    def test_vsphere_vms_with_regex(self):
        """
        Test if the vsphere_vms_regex returns the empty VM list
        """
        self.check._is_excluded = MagicMock(return_value=True)

        content_mock = self.mock_content("vm")
        regex = {"vm_include": "host12"}
        obj_list_regex = self.check._vsphere_vms(content_mock, domain="ESXi", regexes=regex)

        self.assertEqual(len(obj_list_regex), 0)

    def test_get_topologyitems_sync(self):
        """
        Test if it returns the topology items and tags for VM
        """
        instance = {'name': 'vsphere_mock', 'host': "ESXi"}
        self.check._is_excluded = MagicMock(return_value=False)

        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': self.mock_content("vm")})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        # mock the vpshere client connect
        self.check.vsphere_client_connect = MagicMock()

        # mock the CategoryModel and TagModel for response
        category = VsphereCategory('345', 'stackstate-identifier')
        tags = VsphereTag('123', 'vishal-test', '345')

        # get the client
        client = vsphere_client()

        # list_attached_tags method returns list of tags ids of type string
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=['123'])
        # get method of Tag returns a TagModel object which is returned
        client.tagging.Tag.get = MagicMock(return_value=tags)
        # get method of Category returns a CategoryModel object which is returned
        client.tagging.Category.get = MagicMock(return_value=category)

        # assign the vsphere client object to the check vsphere client object
        self.check.client = client

        topo_dict = self.check.get_topologyitems_sync(instance)
        self.assertEqual(len(topo_dict["vms"]), 1)

        # Check if stackstate-identifier are as expected from vsphere tags and coming in identifiers section
        self.assertEqual(len(topo_dict["vms"][0]['topo_tags']['identifiers']), 1)
        self.assertEqual(topo_dict["vms"][0]['topo_tags']['identifiers'][0], 'vishal-test')

        # check if type of name is string rather than unicode
        self.assertEqual(type(topo_dict["vms"][0]['topo_tags']['name']), str)

        # Check if tags are as expected
        self.assertEqual(topo_dict["vms"][0]['topo_tags']['name'], 'Ubuntu')
        self.assertEqual(topo_dict["vms"][0]['topo_tags']['domain'], 'ESXi')
        self.assertEqual(topo_dict["vms"][0]['topo_tags']['layer'], 'VSphere VMs')
        self.assertEqual(topo_dict["vms"][0]["topo_tags"]["topo_type"], "vsphere-VirtualMachine")
        self.assertEqual(topo_dict["vms"][0]['topo_tags']['datastore'], ['54183927-04f91918-a72a-6805ca147c55'])

    def test_collect_topology_component(self):
        """
        Test the component collection from the topology for VirtualMachine
        """
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check._is_excluded = MagicMock(return_value=True)

        instance = {'name': 'vsphere_mock', 'host': 'test-esxi'}
        topo_items = {'datastores': [], 'clustercomputeresource': [], 'computeresource': [], 'hosts': [],
                      'datacenters': [], 'vms': [{'hostname': 'Ubuntu',
                                                  'topo_tags': {'topo_type': 'vsphere-VirtualMachine', 'name': 'Ubuntu',
                                                                'datastore': '54183927-04f91918-a72a-6805ca147c55'},
                                                  'mor_type': 'vm'}]}
        self.check.get_topologyitems_sync = MagicMock(return_value=topo_items)
        self.check.collect_topology(instance)
        snapshot = topology.get_snapshot(self.check.check_id)

        # Check if the returned topology contains 1 component
        self.assertEqual(len(snapshot['components']), 1)
        self.assertEqual(snapshot['components'][0]['id'], 'urn:vsphere:/test-esxi/vsphere-VirtualMachine/Ubuntu')

    def test_collect_topology_comp_relations(self):
        """
        Test the collection of components and relations from the topology for Datastore
        """
        # TODO this is needed because the topology retains data across tests
        topology.reset()

        self.check._is_excluded = MagicMock(return_value=True)

        topo_items = {"datastores": [{'mor_type': 'datastore',
                                      'topo_tags': {'accessible': True, 'topo_type': 'vsphere-Datastore',
                                                    'capacity': 999922073600, 'name': 'WDC1TB',
                                                    'url': '/vmfs/volumes/54183927-04f91918-a72a-6805ca147c55',
                                                    'type': 'VMFS', 'vms': ['UBUNTU_SECURE', 'W-NodeBox',
                                                                            'NAT', 'Z_CONTROL_MONITORING (.151)',
                                                                            'LEXX (.40)', 'parrot']}}], "vms": [],
                      'clustercomputeresource': [], 'computeresource': [], 'hosts': [], 'datacenters': []}

        instance = {'name': 'vsphere_mock', 'host': 'test-esxi'}
        self.check.get_topologyitems_sync = MagicMock(return_value=topo_items)
        self.check.collect_topology(instance)
        snapshot = topology.get_snapshot(self.check.check_id)

        # Check if the returned topology contains 1 component
        self.assertEqual(len(snapshot['components']), 1)
        self.assertEqual(snapshot['components'][0]['id'], 'urn:vsphere:/test-esxi/vsphere-Datastore/WDC1TB')

        # Check if the returned topology contains 6 relations for 6 VMs
        self.assertEqual(len(snapshot['relations']), 6)
        self.assertEqual(snapshot['relations'][0]['type'], 'vsphere-vm-uses-datastore')

    def test_get_topologyitems_with_vm_regexes(self):
        """
        Test if it returns the vm as per filter config
        """
        instance = {'name': 'vsphere_mock', 'host': "ESXi", "vm_include_only_regex": "VM"}

        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': self.mock_content("vm")})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        # mock the vpshere client connect
        self.check.vsphere_client_connect = MagicMock()

        topo_dict = self.check.get_topologyitems_sync(instance)
        self.assertEqual(len(topo_dict["vms"]), 0)

    def test_get_topologyitems_with_host_regexes(self):
        """
        Test if it returns the hosts as per filter config
        """
        instance = {'name': 'vsphere_mock', 'host': "ESXi", "host_include_only_regex": "localhost"}

        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': self.mock_content("host")})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        # mock the vpshere client connect
        self.check.vsphere_client_connect = MagicMock()
        # get the client
        client = vsphere_client()
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])
        self.check.client = client

        topo_dict = self.check.get_topologyitems_sync(instance)
        self.assertEqual(len(topo_dict["hosts"]), 1)
        self.assertEqual(len(topo_dict["hosts"][0]['topo_tags']['identifiers']), 0)

    def test_get_topologyitems_sync_no_unicode(self):
        """
        Test if the vms containing unicode objects are converted to string data type properly
        """
        instance = {'name': 'vsphere_mock', 'host': "ESXi"}

        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': self.mock_content("vm")})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        # mock the vpshere client connect
        self.check.vsphere_client_connect = MagicMock()
        # get the client
        client = vsphere_client()
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])
        self.check.client = client

        topo_dict = self.check.get_topologyitems_sync(instance)
        vm = topo_dict["vms"][0]
        self.assertIs(type(vm['hostname']), str)
        self.assertIs(type(vm['topo_tags']['name']), str)
        self.assertEqual(vm['hostname'], 'Ubuntu')
        self.assertEqual(vm['topo_tags']['name'], 'Ubuntu')

    def test_get_topologyitems_for_vm_with_session_relogin(self):
        """
        Test if it reconnects the sever and returns the vm even the server fails to make calls
        """
        instance = {'name': 'vsphere_mock', 'host': "ESXi"}

        server_mock = MagicMock()
        server_mock.configure_mock(**{'RetrieveContent.return_value': self.mock_content("vm")})
        # make this server call fails and see if it reconnects
        server_mock.configure_mock(**{'CurrentTime.side_effect': Exception("Unauthenticated")})
        self.check._smart_connect = MagicMock(return_value=server_mock)

        # mock the vpshere client connect
        self.check.vsphere_client_connect = MagicMock()
        # get the client
        client = vsphere_client()
        client.tagging.TagAssociation.list_attached_tags = MagicMock(return_value=[])
        self.check.client = client

        topo_dict = self.check.get_topologyitems_sync(instance)
        # Even the server failed to connect, it reconnects and process the vm
        self.assertEqual(len(topo_dict["vms"]), 1)

    def test_collect_metrics_max_query_metrics(self):
        """
        Test the component collection from the topology for VirtualMachine
        """
        self.check._is_excluded = MagicMock(return_value=True)
        self.check.start_pool()
        test_queue = Queue()

        instance = {'name': 'vsphere_mock', 'host': 'test-esxi', 'max_query_metrics': 3}

        # mock server
        server_mock = MagicMock()
        # server_mock.configure_mock(**{'RetrieveContent.return_value': content_mock})
        self.check._get_server_instance = MagicMock(return_value=server_mock)

        def _test_collect_metrics_atomic(_, mor, **kwargs):
            """Mock VSphere collect metric"""
            for m in mor['metrics']:
                self.check.gauge(
                    "vsphere.test_metric",
                    1.0,
                    hostname='test_hostname',
                    tags=['instance:test_instance', 'mor_name:' + mor['name']],
                )

            test_queue.put('finished %s' % mor['name'])

        self.check._collect_metrics_atomic = _test_collect_metrics_atomic
        self.check.morlist = {
            'vsphere_mock': {
                'mor_name_1': {
                    'name': 'mor_name_1',
                    'mor_type': 'vm',
                    'metrics': ['vm_metric_1', 'vm_metric_2'],
                },
                'mor_name_2': {
                    'name': 'mor_name_2',
                    'mor_type': 'host',
                    'metrics': ['host_metric_1'],
                },
                'mor_name_3': {
                    'name': 'mor_name_3',
                    'mor_type': 'vm',
                    'metrics': ['vm_metric_1', 'vm_metric_2', 'vm_metric_3'],
                },
            },
        }
        self.check.collect_metrics(instance)

        test_queue.get()  # mor_name_1
        test_queue.get()  # mor_name_2
        # Check if the returned the correct metrics
        aggregator.assert_metric('vsphere.test_metric', value=1.0,
                                 tags=['instance:test_instance', 'mor_name:mor_name_1'], count=2)
        aggregator.assert_metric('vsphere.test_metric', value=1.0,
                                 tags=['instance:test_instance', 'mor_name:mor_name_2'], count=1)
        aggregator.assert_metric('vsphere.test_metric', value=1.0,
                                 tags=['instance:test_instance', 'mor_name:mor_name_3'], count=0)

        self.check.stop_pool()
