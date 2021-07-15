# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import csv
import codecs
from schematics import Model
from stackstate_checks.base.utils.schemas import StrictStringType
from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance,\
    HealthStream, HealthStreamUrn, HealthType


class InstanceInfo(Model):
    type = StrictStringType(required=True, choices=["csv"])
    health_file = StrictStringType(required=True)
    delimiter = StrictStringType(required=True)


class StaticHealthCheck(AgentCheck):
    SERVICE_CHECK_NAME = "StaticHealth"
    INSTANCE_TYPE = "StaticHealth"
    INSTANCE_SCHEMA = InstanceInfo

    def get_health_stream(self, instance_info):
        return HealthStream(HealthStreamUrn(self.INSTANCE_TYPE, str(instance_info.health_file)))

    def get_instance_key(self, instance_info):
        return TopologyInstance(self.INSTANCE_TYPE, str(instance_info.health_file))

    def check(self, instance_info):
        self.health.start_snapshot()
        self.handle_health_csv(str(instance_info.health_file), str(instance_info.delimiter))
        self.health.stop_snapshot()

    def handle_health_csv(self, filelocation, delimiter):
        self.log.debug("Processing health CSV file %s." % filelocation)

        CHECK_STATE_ID_FIELD = 'check_state_id'
        NAME_FIELD = 'name'
        HEALTH_FIELD = 'health'
        TOPOLOGY_ELEMENT_IDENTIFIER_FIELD = 'topology_element_identifier'
        MESSAGE_FIELD = 'message'

        with codecs.open(filelocation, mode='r', encoding="utf-8-sig") as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar='"')

            header_row = next(reader, None)
            if header_row is None:
                raise ConfigurationError("Health CSV file is empty.")
            self.log.debug("Detected health header: %s" % str(header_row))

            if len(header_row) == 1:
                self.log.warn("Detected one field in header, is the delimiter set properly?")
                self.log.warn("Detected health header: %s" % str(header_row))

            # mandatory fields
            for field in (CHECK_STATE_ID_FIELD, NAME_FIELD, HEALTH_FIELD, TOPOLOGY_ELEMENT_IDENTIFIER_FIELD):
                if field not in header_row:
                    raise ConfigurationError('CSV header %s not found in health csv.' % field)

            header_row_number_of_fields = len(header_row)

            for row in reader:
                data = dict(zip(header_row, row))
                if len(data) != header_row_number_of_fields:
                    self.log.warn("Skipping row because number of fields do not match header row, got: %s" % row)
                    continue

                check_state_id = data.get(CHECK_STATE_ID_FIELD)
                name = data.get(NAME_FIELD)
                health = HealthType().convert(data.get(HEALTH_FIELD), None)
                topology_element_identifier = data.get(TOPOLOGY_ELEMENT_IDENTIFIER_FIELD)
                message = data.get(MESSAGE_FIELD, None)

                self.health.check_state(check_state_id, name, health, topology_element_identifier,
                                        message if message != "" else None)
