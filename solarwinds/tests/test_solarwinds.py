# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import json
from stackstate_checks.base.utils.common import read_file, load_json_from_file

npm_topology = None
udt_topology_data = None


def test_build_where_clause(solarwinds_check):
    solarwinds_domain = "StackState_Domain"
    solarwinds_domain_values = ["Alkmaar Subset"]
    where_clause = solarwinds_check.build_where_clause(solarwinds_domain_values, solarwinds_domain)
    assert where_clause == "WHERE (N.CustomProperties.StackState_Domain = 'Alkmaar Subset')"


def test_get_npm_topology_data(requests_mock, test_instance, solarwinds_check):
    orion_server = test_instance.get("url")
    QUERY_URL = "https://{orion_server}:17778/SolarWinds/InformationService/v3/Json/Query".format(
        orion_server=orion_server
    )
    requests_mock.post(QUERY_URL, text=read_file("npm_topology_data.json", "samples"))
    solarwinds_check.run()
    npm_topology_data = solarwinds_check.get_npm_topology_data("", "")
    assert npm_topology_data == load_json_from_file("npm_topology_data.json", "samples")["results"]


def test_create_npm_topology(solarwinds_check):
    solarwinds_domain = "StackState_Domain"
    npm_topology_data = load_json_from_file("npm_topology_data.json", "samples")["results"]
    # Make sure we can re-use the topology
    global npm_topology
    solarwinds_check.base_url = 'https://solarwinds.procyonnetworks.nl'
    npm_topology = solarwinds_check.create_npm_topology(npm_topology_data, solarwinds_domain)
    # Compare serialized npm topology with saved version
    serialized_npm_topology = json.loads(json.dumps(npm_topology, indent=4, default=lambda o: o.__dict__))
    expected_npm_topology = json.loads(read_file("npm_topology_dumps.json", "samples"))
    assert serialized_npm_topology == expected_npm_topology


def test_check_udt_active(requests_mock, test_instance, solarwinds_check):
    orion_server = test_instance.get("url")
    QUERY_URL = "https://{orion_server}:17778/SolarWinds/InformationService/v3/Json/Query".format(
        orion_server=orion_server
    )
    requests_mock.post(QUERY_URL, text=read_file("udt_active.json", "samples"))
    solarwinds_check.run()
    udt_active = solarwinds_check.check_udt_active()
    assert udt_active is True


def test_get_udt_topology_data(requests_mock, test_instance, solarwinds_check):
    orion_server = test_instance.get("url")
    QUERY_URL = "https://{orion_server}:17778/SolarWinds/InformationService/v3/Json/Query".format(
        orion_server=orion_server
    )
    requests_mock.post(QUERY_URL, text=read_file("udt_topology_data.json", "samples"))
    solarwinds_check.run()
    # Make sure we can re-use the topology data later
    global udt_topology_data
    udt_topology_data = solarwinds_check.get_udt_topology_data()
    assert udt_topology_data == load_json_from_file("udt_topology_data.json", "samples")["results"]


def test_add_udt_topology(solarwinds_check):
    global npm_topology
    global udt_topology_data
    solarwinds_check.add_udt_topology(udt_topology_data, npm_topology)
    # Compare serialized npm + udt topology with saved version
    serialized_npm_topology = json.loads(json.dumps(npm_topology, indent=4, default=lambda o: o.__dict__))
    expected_npm_and_udt_topology = json.loads(read_file("npm_and_udt_topology_dumps.json", "samples"))
    assert serialized_npm_topology == expected_npm_and_udt_topology
