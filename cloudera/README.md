# Cloudera Check


## Overview

#### Installation of CLoudera Manager Single Node Cluster:

    Choose a Centos 7 AMI and create an instance with minimum capacity t2.medium.

#### Prerequisite Steps:

Execute the following commands on the newly provisioned VM.

```bash
echo "echo never > /sys/kernel/mm/redhat_transparent_hugepage/enabled" >> /etc/rc.local
echo "echo never >  /sys/kernel/mm/redhat_transparent_hugepage/defrag" >> /etc/rc.local
echo "vm.swappines = 10" >> /etc/sysctl.conf
chkconfig iptables off
chkconfig iptables off
sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
yum -y install ntp
chkconfig ntpd on
```

#### Install Cloudera Manager:

Download from archive.cloudera.com the installer binary and execute the installer and select the default options on the screen prompt.

```bash
$ yum install -y wget
$ wget http://archive.cloudera.com/cm5/installer/5.11.1/cloudera-manager-installer.bin
$ chmod u+x cloudera-manager-installer.bin
$ sudo ./cloudera-manager-installer.bin
```

After installation above start the manager service.
```bash
sudo service cloudera-scm-server start
```

In your browser navigate to  http://{instance_fqdn}:7180 and logon with the credentials displayed in the popup to continue the installation . 



