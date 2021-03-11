# StackState Agent Integrations v2 releases

## 1.10.1 / 2020-03-11

* [Fixed] Remove `stackstate-identifier`, `stackstate-environment`, `stackstate-layer`, `stackstate-domain` and `stackstate-identifiers` from the tags object if it has been mapped to the data object.

## 1.10.0 / 2020-03-09

* [Added] Added support to map user defined `stackstate-environment` tags or config to the `environments` object
* [Added] Added support to map user defined `stackstate-layer` tags or config to the `layer` object
* [Added] Added support to map user defined `stackstate-domain` tags or config to the `domain` object
* [Added] Added support to map user defined `stackstate-identifiers` tags or config to the `identifiers` array
* [Added] Added support to map user defined `stackstate-identifier` tag or config to the `identifiers` array
