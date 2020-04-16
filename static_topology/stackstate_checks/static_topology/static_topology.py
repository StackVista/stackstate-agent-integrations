# (C) StackState 2020
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import csv
import codecs

from stackstate_checks.base import ConfigurationError, AgentCheck, TopologyInstance


class StaticTopologyCheck(AgentCheck):
    SERVICE_CHECK_NAME = "StaticTopology"
    INSTANCE_TYPE = "StaticTopology"

    def get_instance_key(self, instance):
        if "components_file" not in instance:
            raise ConfigurationError('Static topology instance missing "components_file" value.')

        return TopologyInstance(self.INSTANCE_TYPE, instance["components_file"])

    def check(self, instance):
        if 'components_file' not in instance:
            raise ConfigurationError('Static topology instance missing "components_file" value.')
        if 'relations_file' not in instance:
            raise ConfigurationError('Static topology instance missing "relations_file" value.')
        if 'type' not in instance:
            raise ConfigurationError('Static topology instance missing "type" value.')

        instance_tags = instance['tags'] if 'tags' in instance else []

        if instance['type'].lower() == "csv":
            component_file = instance['components_file']
            relation_file = instance['relations_file']
            delimiter = instance['delimiter']
            instance_tags.extend(["csv.component:%s" % component_file, "csv.relation:%s" % relation_file])
            try:
                self.start_snapshot()
                self.handle_component_csv(component_file, delimiter, instance_tags)
                if relation_file:
                    self.handle_relation_csv(relation_file, delimiter, instance_tags)
            except ConfigurationError as e:
                self.log.error(str(e))
                raise e
            except Exception as e:
                self.log.exception(str(e))
                self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.CRITICAL, message=str(e), tags=instance_tags)
            finally:
                self.stop_snapshot()
        else:
            raise ConfigurationError('Static topology instance only supports type CSV.')

    def handle_component_csv(self, filelocation, delimiter, instance_tags):
        self.log.debug("Processing component CSV file %s." % filelocation)

        COMPONENT_ID_FIELD = 'id'
        COMPONENT_TYPE_FIELD = 'type'
        COMPONENT_NAME_FIELD = 'name'

        with codecs.open(filelocation, mode='r', encoding="utf-8-sig") as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar='"')

            header_row = next(reader, None)
            if header_row is None:
                raise ConfigurationError("Component CSV file is empty.")
            self.log.debug("Detected component header: %s" % str(header_row))

            if len(header_row) == 1:
                self.log.warn("Detected one field in header, is the delimiter set properly?")
                self.log.warn("Detected component header: %s" % str(header_row))

            # mandatory fields
            for field in (COMPONENT_ID_FIELD, COMPONENT_NAME_FIELD, COMPONENT_TYPE_FIELD):
                if field not in header_row:
                    raise ConfigurationError('CSV header %s not found in component csv.' % field)
            id_idx = header_row.index(COMPONENT_ID_FIELD)
            type_idx = header_row.index(COMPONENT_TYPE_FIELD)
            header_row_number_of_fields = len(header_row)

            for row in reader:
                data = dict(zip(header_row, row))
                if len(data) != header_row_number_of_fields:
                    self.log.warn("Skipping row because number of fields do not match header row, got: %s" % row)
                    continue

                # label processing
                labels = data.get('labels', "")
                labels = labels.split(',') if labels else []
                labels.extend(instance_tags)
                data['labels'] = labels

                # environment processing
                environments = data.get('environments', "Production")
                # environments column may be in the row but may be empty/unspecified for that row,
                # defaulting to Production
                environments = environments.split(',') if environments else ["Production"]
                data['environments'] = environments

                # identifiers processing
                identifiers = data.get('identifiers', "")
                # identifiers column may be in the row but may be empty/unspecified for that row, defaulting
                identifiers = identifiers.split(',') if identifiers else []
                data['identifiers'] = identifiers

                self.component(row[id_idx], row[type_idx], data)

    def handle_relation_csv(self, filelocation, delimiter, instance_tags):
        self.log.debug("Processing relation CSV file %s." % filelocation)

        RELATION_SOURCE_ID_FIELD = 'sourceid'
        RELATION_TARGET_ID_FIELD = 'targetid'
        RELATION_TYPE_FIELD = 'type'

        with codecs.open(filelocation, mode='r', encoding="utf-8-sig") as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter, quotechar='|')

            header_row = next(reader, None)
            if header_row is None:
                raise ConfigurationError("Relation CSV file is empty.")
            self.log.debug("Detected relation header: %s" % str(header_row))

            # mandatory fields
            for field in (RELATION_SOURCE_ID_FIELD, RELATION_TARGET_ID_FIELD, RELATION_TYPE_FIELD):
                if field not in header_row:
                    raise ConfigurationError('CSV header %s not found in relation csv.' % field)
            source_id_idx = header_row.index(RELATION_SOURCE_ID_FIELD)
            target_id_idx = header_row.index(RELATION_TARGET_ID_FIELD)
            type_idx = header_row.index(RELATION_TYPE_FIELD)
            header_row_number_of_fields = len(header_row)

            for row in reader:
                data = dict(zip(header_row, row))
                if len(data) != header_row_number_of_fields:
                    self.log.warn("Skipping row because number of fields do not match header row, got: %s" % row)
                    continue

                self.relation(row[source_id_idx], row[target_id_idx], row[type_idx], data)
