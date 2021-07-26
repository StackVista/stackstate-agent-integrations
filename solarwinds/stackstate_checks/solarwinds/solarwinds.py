# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import pprint
import requests
from orionsdk import SwisClient
from schematics import Model
from schematics.types import StringType, ListType
from stackstate_checks.base import AgentCheck, Health, HealthStream, HealthStreamUrn, StackPackInstance
from stackstate_checks.base.utils.identifiers import Identifiers


class InstanceInfo(Model):
    url = StringType(required=True)
    username = StringType(required=True)
    password = StringType(required=True)
    solarwinds_domain = StringType()
    solarwinds_domain_values = ListType(StringType)
    instance_tags = ListType(StringType, default=[])


class SolarWindsCheck(AgentCheck):
    SERVICE_CHECK_NAME = "solarwinds_service_check"
    INSTANCE_TYPE = "solarwinds"
    INSTANCE_SCHEMA = InstanceInfo
    base_url = ""

    def get_instance_key(self, instance_info):
        return StackPackInstance(self.INSTANCE_TYPE, str(instance_info.url))

    def build_base_url(self, orion_server):
        self.log.debug("Build orion server base URL")
        # Build base url to reach the orion server for more data
        https_status = self.swis.query("SELECT SSLEnabled FROM Orion.Websites WHERE Port = 443")
        if len(https_status["results"]):
            url = "https://" + orion_server
        else:
            url = "http://" + orion_server
        self.log.debug("URL: %s" % url)
        return url

    def build_where_clause(self, solarwinds_domain_values, solarwinds_domain):
        self.log.debug("Build SWQL WHERE clause")
        # Build SWQL WHERE clause
        where_clause = ""
        for value in solarwinds_domain_values:
            if where_clause:
                where_clause += " OR N.CustomProperties.{domain} = ".format(domain=solarwinds_domain)
            else:
                where_clause = "WHERE (N.CustomProperties.{domain} = ".format(domain=solarwinds_domain)
            where_clause += "'{value}'".format(value=value)
        where_clause += ")"
        self.log.debug("SWQL WHERE clause: %s" % where_clause)
        return where_clause

    def get_npm_topology_data(self, solarwinds_domain, where_clause):
        self.log.info("Query SolarWinds Orion server - NPM topology data")
        # Get a list of all nodes, interfaces, L2 connections and health status for nodes and interfaces filtered by
        # solarwinds_domain.
        # NodeCategory shows the Orion classification of nodes (Server, Network, Other) DetailsUrl are direct links to
        # detail dashboards.
        # The LEFT JOIN only accepts connections that have an Orion.NPM.Interfaces type on both sides (meaning neither
        # side is 'unknown').
        # When DestInterfaceID is now NONE, that means either source or destination interface (or both) was
        # unknown -> None means there is no connection to anything.
        query_npm = self.swis.query(
            "SELECT N.NodeID, N.Caption, N.IPAddress, N.CustomProperties.{domain}, N.Interfaces.InterfaceID, "
            "N.Interfaces.IfName, "
            "CASE WHEN N.Interfaces.TypeDescription NOT LIKE '%Virtual%' THEN N.Interfaces.MAC END AS MAC, "
            "T.DestInterfaceID, I.MAC AS DestInterfaceMAC, "
            "(SELECT Description FROM Orion.NodeCategories WHERE N.Category = CategoryID) AS NodeCategory, "
            "(SELECT StatusName FROM Orion.StatusInfo WHERE N.Status = StatusId) AS NodeStatus, "
            "(SELECT StatusName FROM Orion.StatusInfo WHERE N.Interfaces.Status = StatusId) AS InterfaceStatus, "
            "N.DetailsUrl AS NodeDetailsUrl, N.Interfaces.DetailsUrl AS InterfaceDetailsUrl "
            "FROM Orion.Nodes N "
            "LEFT JOIN Orion.TopologyConnections T ON T.SrcInterfaceID = N.Interfaces.InterfaceID AND "
            "T.SrcType = 'Orion.NPM.Interfaces' "
            "AND T.DestType = 'Orion.NPM.Interfaces' AND T.LayerType = 'L2' "
            "LEFT JOIN Orion.NPM.Interfaces I ON I.InterfaceID = T.DestInterfaceID "
            "{where_clause}".format(domain=solarwinds_domain, where_clause=where_clause)
        )
        # Assign the query results to a variable
        npm_topology_data = query_npm.get("results")
        return npm_topology_data

    def create_npm_topology(self, npm_data, solarwinds_domain):
        self.log.info("Convert NPM topology data into list of Node objects")
        # Create a new list of Node objects containing all node information
        # This way, we eliminate duplicate entries coming from the query so we have a clean list
        # Add Interface objects to the Node objects where applicable
        # Also create a new list of connections (relations) between interfaces
        nodes = []
        for npm_node in npm_data:
            # Is this NodeID present in the list of nodes?
            found_node = next((sub for sub in nodes if sub.node_id == npm_node.get("NodeID")), None)
            if not found_node:
                # New node, create it and add it to the list
                nodes.append(
                    Node(
                        npm_node.get("NodeID"),
                        npm_node.get("Caption"),
                        npm_node.get("IPAddress"),
                        npm_node.get("NodeStatus"),
                        npm_node.get(solarwinds_domain),
                        npm_node.get("NodeCategory"),
                        self.base_url + npm_node.get("NodeDetailsUrl"),
                    )
                )
                found_node = nodes[-1]
            # Is there an interface for this node?
            interface_id = npm_node.get("InterfaceID")
            if interface_id:
                # Is this interface present in the list of interfaces on this node?
                # For new nodes, this would not be necessary
                found_interface = next((sub for sub in found_node.interfaces if sub.interface_id == interface_id), None)
                if not found_interface:
                    # New interface, create it and add it to the list
                    found_node.append_interface(
                        interface_id,
                        npm_node.get("IfName"),
                        npm_node.get("MAC"),
                        npm_node.get("InterfaceStatus"),
                        npm_node.get(solarwinds_domain),
                        self.base_url + npm_node.get("InterfaceDetailsUrl"),
                    )
                    found_interface = found_node.interfaces[-1]
                # Is there a connection to this interface?
                dest_interface_id = npm_node.get("DestInterfaceID")
                if dest_interface_id:
                    # Is the destination node (of this interface) present in the solarwinds data?
                    found_dest_node = next((sub for sub in npm_data if sub["InterfaceID"] == dest_interface_id), None)
                    if found_dest_node:
                        dest_node_name = found_dest_node.get("Caption")
                        dest_interface_name = found_dest_node.get("IfName")
                        dest_mac_address = npm_node.get("DestInterfaceMAC")
                        found_interface.append_connection(dest_node_name, dest_interface_name, dest_mac_address)
        return nodes

    def check_udt_active(self):
        self.log.debug("Check for installed UDT module")
        # Get a list of all installed Orion modules, check for (not expired) UDT
        query_udt = self.swis.query(
            "SELECT LicenseName, IsExpired FROM Orion.InstalledModule WHERE LicenseName = 'UDT' AND IsExpired = FALSE"
        )
        if query_udt.get("results"):
            self.log.debug("UDT module is active")
            return True
        else:
            self.log.debug("Licensed UDT module not detected")
            return False

    def get_udt_topology_data(self):
        self.log.info("Collect UDT connection information")
        # Get unique connections from UDT
        # This shows nodes connected to Switch ports (that may not be monitored inside Orion)
        query_udt_connections = self.swis.query(
            "SELECT DISTINCT ConnectedTo, ConnectionTypeName, HostName, IPAddress, MACAddress, PortNumber "
            "FROM Orion.UDT.AllEndpoints WHERE IPAddress IS NOT NULL"
        )
        # Assign the query results to a variable
        udt_connections = query_udt_connections["results"]
        return udt_connections

    def add_udt_topology(self, udt_topology_data, npm_topology):
        self.log.info("Add UDT topology information to NPM topology data")
        for udt_connection in udt_topology_data:
            src_node_name = OrionComponent.strip_domain(udt_connection.get("ConnectedTo"))
            src_interface_name = udt_connection.get("PortNumber")
            dest_mac_address = udt_connection.get("MACAddress").replace(":", "")
            dest_ip_address = udt_connection.get("IPAddress")
            dest_node_name = udt_connection.get("HostName")
            if not dest_node_name:
                dest_node_name = dest_ip_address

            # Find the source node to connect from
            found_src_node = next((sub for sub in npm_topology if sub.caption == src_node_name), None)
            if found_src_node:
                # Find the interface to connect from
                found_src_interface = next(
                    (sub for sub in found_src_node.interfaces if sub.interface_name == src_interface_name), None
                )
                if found_src_interface:
                    # If there already is a connection that came from NPM,
                    # there is a chance of creating a duplicate here
                    # StackState will ignore the duplicate
                    found_src_interface.append_connection(dest_node_name, "", dest_mac_address)

            # Are there matching destination nodes for this connection?
            found_dest_node = next((sub for sub in npm_topology if sub.ip_address == dest_ip_address), None)
            if found_dest_node:
                # Does this node have a matching interface to connect to?
                found_dest_interface = next(
                    (sub for sub in found_dest_node.interfaces if sub.mac_address == dest_mac_address), None
                )
                if not found_dest_interface:
                    # No matching interface on existing node, create one
                    found_dest_node.append_interface(
                        -1,
                        "Int",
                        dest_mac_address,
                        'Up',
                        found_dest_node.domain,
                        None
                    )
            else:
                # No matching node found, create one and add it to the list
                npm_topology.append(
                    Node(
                        -1,
                        dest_node_name,
                        dest_ip_address,
                        'Up',
                        found_src_node.domain,
                        "Machines",
                        None
                    )
                )
                # The new node needs an interface
                npm_topology[-1].append_interface(
                    -1,
                    "Int",
                    dest_mac_address,
                    'Up',
                    found_src_node.domain,
                    None
                )

    def register_components(self, npm_topology):
        self.log.info("Register SolarWinds Orion components (nodes & interfaces)")
        # Register all nodes and interfaces
        for node in npm_topology:
            # Register the node component
            node_component = {
                "name": node.caption,
                "domain": node.domain,
                "layer": node.layer,
                "environment": node.environment,
                "identifiers": node.identifiers,
                "details_url": node.details_url,
            }
            self.component(node.identifiers[0], node.component_type, node_component)

            # Register the interfaces (if any)
            for interface in node.interfaces:
                # Register the interface component
                interface_component = {
                    "name": interface.interface_name,
                    "domain": interface.domain,
                    "layer": node.layer,
                    "environment": node.environment,
                    "identifiers": interface.identifiers,
                    "details_url": interface.details_url,
                }
                # Register the interface component
                self.component(interface.identifiers[0], "Interface", interface_component)
                # Connect this interface to its node
                self.relation(node.identifiers[0], interface.identifiers[0], "has", {})

    def create_relations(self, npm_topology):
        self.log.info("Create all interface connections")
        # Connect the interfaces to each other
        for node in npm_topology:
            for interface in node.interfaces:
                for connection in interface.connections:
                    # For bi-directional connections we temporarily use 'puts message' as the type
                    # This will have to be changed later
                    self.relation(interface.identifiers[0], connection.dest_identifier, "puts message", {})
                    self.relation(connection.dest_identifier, interface.identifiers[0], "puts message", {})

    def get_health_stream(self, instance_info):
        return HealthStream(HealthStreamUrn(self.INSTANCE_TYPE, "solarwinds_health"), repeat_interval_seconds=150,
                            expiry_seconds=300)

    def send_component_health(self, npm_topology):
        self.log.info("Create component health state")
        # UNKNOWN state should not happen. That means something is wrong. A device cannot be polled usually.
        # The thing is… it doesnt have to mean the device is not working, but it does mean something needs to be done.
        # Hence… DEVIATING.
        # UNREACHABLE is a special state. Suppose you have this: Device ----- router ----- SolarWinds Server
        # If the router fails, the device might still be working just fine. But… we don’t know.
        # So in SolarWinds, you can set up what are called dependencies.
        # A dependency would say ’if the router fails, we don’t know about the device’s state, but we do know we cannot
        # reach it. So the device gets the special state UNREACHABLE. SolarWinds assumes the device is up and healthy.
        health_value_translations = {
            "Up": Health.CLEAR,
            "External": Health.CLEAR,
            "Unmanaged": Health.CLEAR,
            "Unreachable": Health.CLEAR,
            "Shutdown": Health.CLEAR,
            "Warning": Health.DEVIATING,
            "Unknown": Health.DEVIATING,
            "Down": Health.CRITICAL,
            "Critical": Health.CRITICAL,
        }

        for node in npm_topology:
            # Has to be unique per health state
            check_state_id = node.identifiers[0]
            name = "Node Status"
            # Unknown status we map to Deviating, check explanation above.
            health_value = health_value_translations.get(node.node_status, Health.DEVIATING)
            topology_element_identifier = node.identifiers[0]
            # Message supports markdown and could include a link to the SolarWinds Orion page for more info
            message = "Node Status includes up/down state and rollup status of 'child objects' like CPU, Memory, " \
                      "interfaces, etc. The child status is determined by 'NODE STATUS CALCULATION' in " \
                      "polling settings."
            self.health.check_state(check_state_id, name, health_value, topology_element_identifier, message)
            for interface in node.interfaces:
                # Has to be unique per health state
                check_state_id = interface.identifiers[0]
                name = "Interface Status"
                health_value = health_value_translations.get(interface.interface_status, Health.DEVIATING)
                topology_element_identifier = interface.identifiers[0]
                # Message supports markdown and could include a link to the SolarWinds Orion page for more info
                message = "Interface Status indicating up/down state, but also bandwidth usage and error thresholds."
                self.health.check_state(check_state_id, name, health_value, topology_element_identifier, message)

    def check(self, instance_info):
        try:
            self.log.info("Start SolarWinds Orion check")
            # Disable Orion SSL warnings
            requests.packages.urllib3.disable_warnings()
            # Connect to Orion server
            self.swis = SwisClient(instance_info.url, instance_info.username, instance_info.password)
            # Build base URL for primary SolarWinds website
            self.base_url = self.build_base_url(instance_info.url)
            # Create SWQL WHERE clause for node / interface query
            where_clause = self.build_where_clause(instance_info.solarwinds_domain_values,
                                                   instance_info.solarwinds_domain)
            npm_topology_data = self.get_npm_topology_data(instance_info.solarwinds_domain, where_clause)
            # Create list of Node objects containing optional Interface objects
            npm_topology = self.create_npm_topology(npm_topology_data, instance_info.solarwinds_domain)

            # Is UDT installed?
            if self.check_udt_active():
                udt_topology_data = self.get_udt_topology_data()
                # Add UDT topology data to nodes
                self.add_udt_topology(udt_topology_data, npm_topology)

            self.start_snapshot()
            self.register_components(npm_topology)
            self.create_relations(npm_topology)
            self.stop_snapshot()

            self.health.start_snapshot()
            self.send_component_health(npm_topology)
            self.health.stop_snapshot()

            message = "Orion check processed successfully"
            # Not sure how to use the tags !!
            self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK, tags=None, message=message)

        except Exception as e:
            self.log.exception(e)
            msg = '%s: %s' % (type(e).__name__, str(e))
            self.service_check(
                self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=msg, tags=instance_info.instance_tags
            )


class OrionComponent:
    environment = "Production"
    component_registered = False

    # Strip FQDN names of anything including and after '.'
    @staticmethod
    def strip_domain(fqdn):
        if fqdn:
            return fqdn.split(".")[0]
        else:
            return None


class Node(OrionComponent):

    def __init__(self, node_id, caption, ip_address, node_status, domain, layer, node_details_url):
        self.node_id = node_id
        self.caption = caption
        self.ip_address = ip_address
        self.node_status = node_status
        self.domain = domain
        if layer == "Network":
            self.layer = "Networking"
            self.component_type = "network_host"
        else:
            self.layer = "Machines"
            self.component_type = "host"
        self.details_url = node_details_url
        # Create node identifiers: With and without domain extension,
        # All upper and all lower case
        self.identifiers = []
        if caption == ip_address:
            # Nodes with just an IP address in the name never have a domain part
            self._node_identifier = Identifiers.create_host_identifier(self.caption)
            self.identifiers.append(self._node_identifier)
        else:
            self._node_identifier_no_caps = Identifiers.create_host_identifier(self.caption.lower())
            self._node_identifier_all_caps = Identifiers.create_host_identifier(self.caption.upper())
            self._node_identifier_no_caps_no_domain = OrionComponent.strip_domain(self._node_identifier_no_caps)
            self._node_identifier_all_caps_no_domain = OrionComponent.strip_domain(self._node_identifier_all_caps)
            self.identifiers.append(self._node_identifier_no_caps)
            self.identifiers.append(self._node_identifier_all_caps)
            if self._node_identifier_no_caps_no_domain not in self.identifiers:
                self.identifiers.append(self._node_identifier_no_caps_no_domain)
            if self._node_identifier_all_caps_no_domain not in self.identifiers:
                self.identifiers.append(self._node_identifier_all_caps_no_domain)
        self.interfaces = []

    def __repr__(self):
        properties = pprint.pformat(vars(self), width=120, sort_dicts=False)
        return properties

    def append_interface(self, interface_id, interface_caption, mac_address, interface_status, domain,
                         interface_details_url):
        self.interfaces.append(
            Interface(interface_id, interface_caption, mac_address, interface_status, domain, interface_details_url))


class Interface(OrionComponent):
    component_type = "Interface"

    def __init__(self, interface_id, interface_caption, mac_address, interface_status, domain, interface_details_url):
        self.interface_id = interface_id
        self.interface_name = interface_caption
        self.mac_address = mac_address
        # If interface has no MAC address, set it to 0
        if mac_address:
            self.mac_address = mac_address
        else:
            self.mac_address = "000000000000"
        self.interface_status = interface_status
        self.domain = domain
        self.details_url = interface_details_url
        self.identifiers = []
        # Make sure the MAC address is the first identifier
        # It seems, relations to secondary identifiers do not work
        if self.mac_address:
            self.identifiers.append(
                Identifiers.create_custom_identifier("interface", "{mac_address}".format(mac_address=self.mac_address))
            )
        self.connections = []

    def __repr__(self):
        properties = pprint.pformat(vars(self), width=120, sort_dicts=False)
        return properties

    def append_connection(self, dest_node_name, dest_interface_name, dest_mac_address):
        self.connections.append(ConnectionL2(dest_node_name, dest_interface_name, dest_mac_address))


class OrionConnection:
    # Strip FQDN names of anything including and after '.'
    def strip_domain(self, fqdn):
        if fqdn:
            return fqdn.split(".")[0]
        else:
            return None


class ConnectionL2(OrionConnection):
    def __init__(self, dest_node_name, dest_interface_name, dest_mac_address=None):
        self.dest_node_name = self.strip_domain(dest_node_name)
        self.dest_interface_name = dest_interface_name
        if dest_mac_address:
            self.dest_mac_address = dest_mac_address.replace(":", "")
        else:
            self.dest_mac_address = None
        # Use the destination MAC address for the destination identifier if known
        if self.dest_mac_address:
            self.dest_identifier = Identifiers.create_custom_identifier(
                "interface", "{mac_address}".format(mac_address=self.dest_mac_address)
            )
        else:
            self.dest_identifier = Identifiers.create_custom_identifier(
                "interface",
                "{dest_node_name}.{dest_interface_name}".format(
                    dest_node_name=self.dest_node_name, dest_interface_name=self.dest_interface_name
                )
            )

    def __repr__(self):
        properties = pprint.pformat(vars(self), width=120, sort_dicts=False)
        return properties
