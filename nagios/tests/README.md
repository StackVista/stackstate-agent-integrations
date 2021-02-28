# Checksdev Nagios environment

There is a Nagios + MySQL environment that is useful for testing. 

```shell
checksdev env start nagios py27
```

## Simulation events

There is script that creates random events and append them to `nagios.log`.
Start `checksdev` Nagios environment as described before. 

```shell
docker exec -it compose_nagios_1 bash
watch -n 20 opt/simulate_events.py
```
