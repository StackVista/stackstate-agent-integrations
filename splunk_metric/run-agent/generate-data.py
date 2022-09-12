import requests

USER = "admin"
PASSWORD = "admin12345"
URL = "https://sour-terms-lead-31-201-26-106.loca.lt"
SOURCE_TYPE = "sts_test_data"


def make_components():
    search_name = 'components'
    search = {'name': search_name,
              'search': '* topo_type=component '
                        '| dedup id '
                        '| sort - id '
                        '| fields id, type, description, running'}

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (URL, search_name), auth=(USER, PASSWORD))

    requests.post("%s/services/saved/searches" % URL, data=search, auth=(USER, PASSWORD)).raise_for_status()
    json_data = {"topo_type": "component", "id": "server_1", "type": "server", "description": "My important server 1"}
    requests.post("%s/services/receivers/simple" % URL, json=json_data, auth=(USER, PASSWORD)).raise_for_status()
    json_data = {"topo_type": "component", "id": "server_2", "type": "server", "description": "My important server 2"}
    requests.post("%s/services/receivers/simple" % URL, json=json_data, auth=(USER, PASSWORD)).raise_for_status()


def make_relations():
    search_name = 'relations'
    search = {'name': search_name,
              'search': '* topo_type=relation '
                        '| dedup type, sourceId, targetId '
                        '| fields type, sourceId, targetId, description'}

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (URL, search_name), auth=(USER, PASSWORD))

    requests.post("%s/services/saved/searches" % URL, data=search, auth=(USER, PASSWORD)).raise_for_status()
    json_data = {"topo_type": "relation", "type": "CONNECTED", "sourceId": "server_1", "targetId": "server_2",
                 "description": "Some relation"}
    requests.post("%s/services/receivers/simple" % URL, json=json_data, auth=(USER, PASSWORD)).raise_for_status()


def make_health():
    search_name = 'health'
    search = {'name': search_name,
              'search': '* '
                        '| dedup check_state_id '
                        '| sort - check_state_id '
                        '| fields check_state_id, name, health, topology_element_identifier, message'}

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (URL, search_name), auth=(USER, PASSWORD))

    requests.post("%s/services/saved/searches" % URL, data=search, auth=(USER, PASSWORD)).raise_for_status()
    json_data = {"check_state_id": "disk_sda",
                 "name": "Disk sda",
                 "health": "clear",
                 "topology_element_identifier": "server_1",
                 "message": "sda message"}
    requests.post("%s/services/receivers/simple" % URL, json=json_data, auth=(USER, PASSWORD)).raise_for_status()
    json_data = {"check_state_id": "disk_sdb",
                 "name": "Disk sdb",
                 "health": "critical",
                 "topology_element_identifier": "server_2"}
    requests.post("%s/services/receivers/simple" % URL, json=json_data, auth=(USER, PASSWORD)).raise_for_status()


def make_event():
    saved_search = "events"

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (URL, saved_search), auth=(USER, PASSWORD))

    requests.post("%s/services/saved/searches" % URL,
                  data={"name": saved_search,
                        "search": 'sourcetype="{}" '
                                  '| eval status = upper(status) '
                                  '| search status=critical OR status=error OR status=warning OR status=ok '
                                  '| table _time _bkt _cd host status description'.format(SOURCE_TYPE)},
                  auth=(USER, PASSWORD)).raise_for_status()
    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host01", "sourcetype": SOURCE_TYPE},
                  json={"status": "OK", "description": "host01 test ok event"},
                  auth=(USER, PASSWORD)).raise_for_status()
    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host02", "sourcetype": SOURCE_TYPE},
                  json={"status": "CRITICAL", "description": "host02 test critical event"},
                  auth=(USER, PASSWORD)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host03", "sourcetype": SOURCE_TYPE},
                  json={"status": "error", "description": "host03 test error event"},
                  auth=(USER, PASSWORD)).raise_for_status(),
    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host04", "sourcetype": SOURCE_TYPE},
                  json={"status": "warning", "description": "host04 test warning event"},
                  auth=(USER, PASSWORD)).raise_for_status()


def make_metrics():
    saved_search = "metrics"

    # Delete first to avoid 409 in case of tearing down the `checksdev env stop`
    requests.delete("%s/services/saved/searches/%s" % (URL, saved_search), auth=(USER, PASSWORD))

    requests.post("%s/services/saved/searches" % URL,
                  data={"name": saved_search,
                        "search": 'sourcetype="{}" '
                                  'AND topo_type="{}" '
                                  'AND value!="" '
                                  'AND metric!="" '
                                  '| table _bkt _cd _time metric value'.format(SOURCE_TYPE, saved_search)},
                  auth=(USER, PASSWORD)).raise_for_status()

    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host01", "sourcetype": SOURCE_TYPE},
                  json={"topo_type": saved_search, "metric": "raw.metrics", "value": 1},
                  auth=(USER, PASSWORD)).raise_for_status()

    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host02", "sourcetype": SOURCE_TYPE},
                  json={"topo_type": saved_search, "metric": "raw.metrics", "value": 21},
                  auth=(USER, PASSWORD)).raise_for_status()

    requests.post("%s/services/receivers/simple" % URL,
                  params={"host": "host03", "sourcetype": SOURCE_TYPE},
                  json={"topo_type": saved_search, "metric": "raw.metrics", "value": 5},
                  auth=(USER, PASSWORD)).raise_for_status()


if __name__ == '__main__':
    make_components()
    make_relations()
    make_health()
    make_event()
    make_metrics()
