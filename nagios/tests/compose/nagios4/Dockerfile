FROM jasonrivers/nagios:latest
COPY --chown=nagios:nagios nagios.cfg /opt/nagios/etc/nagios.cfg
COPY --chown=nagios:nagios conf.d/mysql.cfg /opt/nagios/etc/conf.d/mysql.cfg
COPY --chown=nagios:nagios localhost.cfg /opt/nagios/etc/objects/localhost.cfg
RUN  chown -R nagios:nagios /opt/nagios/var/
