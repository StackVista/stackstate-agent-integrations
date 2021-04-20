# StackState Agent Integrations v2 releases

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
