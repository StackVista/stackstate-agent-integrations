# (C) Datadog, Inc. 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.capital_one import CapitalOneCheck
from stackstate_checks.base.stubs import topology


def test_check(file_instance):
    capital_check = CapitalOneCheck('capital_one', {}, {}, instances=[file_instance])
    capital_check.check(file_instance)
    snapshot = topology.get_snapshot(capital_check.check_id)
    components = snapshot.get("components")
    relations = snapshot.get("relations")
    instance_key = snapshot.get("instance_key")
    expected_instance_key = {'type': 'capital-one', 'url': './tests/data/sample_data.txt'}
    # since url file contains a single line with ec2, VPC and Subnet each which creates 3 components
    assert len(components) == 3
    assert instance_key == expected_instance_key
    # since url file contains a single line with relations making ec2 with subnet and VPC with Subnet each which
    # creates 2 relations
    assert len(relations) == 2
