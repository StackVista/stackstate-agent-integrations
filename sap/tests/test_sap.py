# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from stackstate_checks.sap import SapCheck
from stackstate_checks.base.stubs import topology


def test_check(aggregator, instance):
    check = SapCheck("test-sap", {}, {}, instances=[instance])
    check.check(instance)

    print(topology.get_snapshot(''))
