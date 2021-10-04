# StackState Agent Integrations v2 releases

## 1.16.0 / 2021-??-??

* [Fixed] SolarWinds Create interface components with MAC address and no IP address [(STAC-14057)](https://stackstate.atlassian.net/browse/STAC-14057) 
* [Added] ServiceNow send Topology Event to StackState before the scheduled Planned Start Date of the Change Request. [(STAC-13256)](https://stackstate.atlassian.net/browse/STAC-13256)

## 1.15.0 / 2021-08-02
* [Fixed] SolarWinds Component has multiple health statuses. [(STAC-13796)](https://stackstate.atlassian.net/browse/STAC-13796)
* [Improvement] AWS x-ray integration performance improvements when fetching historic data, as well as schema validation using Schematics.  [(STAC-13551)](https://stackstate.atlassian.net/browse/STAC-13551)
* [Fixed] Unable to load Splunk Topology on Stackstate UI. [(STAC-13564)](https://stackstate.atlassian.net/browse/STAC-13564)
* [Added] Splunk http helper base library. [(STAC-13089)](https://stackstate.atlassian.net/browse/STAC-13089)
* [Added] Health synchronization splunk check to synchronize health states from Splunk into StackState. [(STAC-13174)](https://stackstate.atlassian.net/browse/STAC-13174)
* [Added] SolarWinds integrations that monitors your network landscape and reports it to StackState. [(STAC-13240)](https://stackstate.atlassian.net/browse/STAC-13240)
* [Fixed] AWS Topology ResourceMethodIntegration validation for API Gateway resources.  [(STAC-13604)](https://stackstate.atlassian.net/browse/STAC-13604)
* [Added] Add instance url as an identifier for zabbix integration. [(STAC-13621)](https://stackstate.atlassian.net/browse/STAC-13621)
* [Added] Validation to ensure all lists produced by integrations are homogeneous and all dictionaries contain only string keys.

## 1.14.0 / 2021-07-09

* [Fixed] AWS x-ray check error when `role_arn` is not defined in `conf.yaml`.
* [Fixed] AWS x-ray check memory leak caused by `trace_ids` and `arns`.
* [Fixed] AWS x-ray integration spans produce a span kind to allow StackState to correctly calculate metrics.
* [Added] AWS x-ray integration spans are interpreted to get http response codes.
* [Added] Hostname identifiers for Zabbix hosts.
* [Added] `get_hostname` to AgentCheck base class.
* [Fixed] `event_type` is used as the Event Type in StackState for normal events.
* [Added] SCOM check now support two operation modes, api-based or powershell-based. 
  The operation mode can be switched using `integration_mode` in `conf.yaml`.
* [Fixed] Removed `lastSeenTimestamp` from DynaTrace components to avoid sporadic updates in StackState.
* [Added] AWS Topology integration that monitors your AWS landscape and reports it to StackState.

## 1.13.2 / 2021-04-19

* [Fixed] Fixed out-of-box AWS x-ray check instance error.

## 1.13.1 / 2021-04-14

* [Fixed] Fix out-of-box VSphere check settings to support the Vsphere StackPack.

## 1.13.0 / 2021-03-30

* [Added] Dynatrace - Gathers Dynatrace events for determining health state of Dynatrace components is StackState. 

## 1.12.0 / 2021-03-30

* [Added] Make the check state location configurable in the `conf.d` of the check. See [#123](https://github.com/StackVista/stackstate-agent-integrations/pull/123).

## 1.11.0 / 2021-03-24

* [Added] ServiceNow - Implement query param change for retrieving tags from ServiceNow.

## 1.10.1 / 2021-03-11

* [Fixed] Remove `stackstate-identifier`, `stackstate-environment`, `stackstate-layer`, `stackstate-domain` and `stackstate-identifiers` from the tags object if it has been mapped to the data object.

## 1.10.0 / 2021-03-09

* [Added] Added support to map user defined `stackstate-environment` tags or config to the `environments` object
* [Added] Added support to map user defined `stackstate-layer` tags or config to the `layer` object
* [Added] Added support to map user defined `stackstate-domain` tags or config to the `domain` object
* [Added] Added support to map user defined `stackstate-identifiers` tags or config to the `identifiers` array
* [Added] Added support to map user defined `stackstate-identifier` tag or config to the `identifiers` array
