#!/usr/bin/env python3

import datetime
from random import choice

log_file = '/opt/nagios/var/log/nagios.log'

simulated_log_entries = [
    '[%s] CURRENT HOST STATE: nagios4;UP;HARD;1;Simulated current host state\n',
    '[%s] CURRENT HOST STATE: nagios4;UNREACHABLE;HARD;1;Simulated current host state\n',
    '[%s] CURRENT HOST STATE: nagios4;DOWN;HARD;1;Simulated current host state\n',
    '[%s] CURRENT HOST STATE: mysql;UP;HARD;1;Simulated current host state\n',
    '[%s] CURRENT HOST STATE: mysql;UNREACHABLE;HARD;1;Simulated current host state\n',
    '[%s] CURRENT HOST STATE: mysql;DOWN;HARD;1;Simulated current host state\n',
    '[%s] CURRENT SERVICE STATE: nagios4;Simulate;OK;HARD;1;Simulated current service state\n',
    '[%s] CURRENT SERVICE STATE: nagios4;Simulate;WARNING;HARD;1;Simulated current service state\n',
    '[%s] CURRENT SERVICE STATE: nagios4;Simulate;CRITICAL;HARD;1;Simulated current service state\n',
    '[%s] CURRENT SERVICE STATE: mysql;Simulate;OK;HARD;1;Simulated current service state\n',
    '[%s] CURRENT SERVICE STATE: mysql;Simulate;WARNING;HARD;1;Simulated current service state\n',
    '[%s] CURRENT SERVICE STATE: mysql;Simulate;CRITICAL;HARD;1;Simulated current service state\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;CRITICAL;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;WARNING;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;OK;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;CRITICAL;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;WARNING;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: nagios4;Simulate;OK;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;OK;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;WARNING;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;CRITICAL;HARD;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;OK;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;WARNING;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE ALERT: mysql;Simulate;CRITICAL;SOFT;4;Simulated service alert\n',
    '[%s] SERVICE NOTIFICATION: pagerduty;nagios4;Simulate;OK;notify-service-by-pagerduty;Simulated notification\n',
    '[%s] SERVICE NOTIFICATION: pagerduty;nagios4;Simulate;CRITICAL;notify-service-by-pagerduty;Simulated notif.\n',
    '[%s] SERVICE NOTIFICATION: pagerduty;mysql;Simulate;OK;notify-service-by-pagerduty;Simulated notification\n',
    '[%s] SERVICE NOTIFICATION: pagerduty;mysql;Simulate;CRITICAL;notify-service-by-pagerduty;Simulated notification\n',
    '[%s] HOST ALERT: nagios4;DOWN;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: nagios4;UNREACHABLE;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: nagios4;UP;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: nagios4;DOWN;HARD;1;Simulated host alert',
    '[%s] HOST ALERT: nagios4;UNREACHABLE;HARD;1;Simulated host alert',
    '[%s] HOST ALERT: nagios4;UP;HARD;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;DOWN;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;UNREACHABLE;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;UP;SOFT;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;DOWN;HARD;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;UNREACHABLE;HARD;1;Simulated host alert',
    '[%s] HOST ALERT: mysql;UP;HARD;1;Simulated host alert',
    '[%s] HOST FLAPPING ALERT: nagios4;STARTED;Simulated host flapping alert\n',
    '[%s] HOST FLAPPING ALERT: nagios4;STOPPED;Simulated host flapping alert\n',
    '[%s] HOST FLAPPING ALERT: mysql;STARTED;Simulated host flapping alert\n',
    '[%s] HOST FLAPPING ALERT: mysql;STOPPED;Simulated host flapping alert\n',
    '[%s] SERVICE FLAPPING ALERT: nagios4;Simulated;STARTED; Simulated service flapping alert\n',
    '[%s] SERVICE FLAPPING ALERT: nagios4;Simulated;STOPPED; Simulated service flapping alert\n',
    '[%s] SERVICE FLAPPING ALERT: mysql;Simulated;STARTED; Simulated service flapping alert\n',
    '[%s] SERVICE FLAPPING ALERT: mysql;Simulated;STOPPED; Simulated service flapping alert\n',
]

event_template = choice(simulated_log_entries)
ts = int(datetime.datetime.timestamp(datetime.datetime.now()))
new_log_line = event_template % ts
print('Appending to nagios.log:\n %s' % new_log_line)

with open(log_file, 'a') as file:
    file.write(new_log_line)
