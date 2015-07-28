折鶴
====

This program can be used to test drive MEM OpenStack and midonet.org OpenStack inside containers on Ubuntu Linux.

For MEM credentials you can always get your MEM trial key here today: http://www.midokura.com/midonet-enterprise/

A demo video of the installer running (30 minutes) is available here: http://midonet.github.io/orizuru .

To get started with this all you need to provide is a list of (virtual or physical) servers.

At the end of the installation you can do the following to log into midonet-cli and use keystone:
```
ssh -F tmp/.ssh/config midonet_cli
root@midonet_cli # source /etc/keystone/KEYSTONERC
root@midonet_cli # keystone tenant-list
root@midonet_cli # midonet-cli
```
The file /etc/keystone/KEYSTONERC is available in every container (so when you log into openstack_controller you will be able to source it also).

Note that for kilo you should source /etc/keystone/admin-openrc.sh (the KEYSTONERC will not exist there).

Localhost Quickstart
====================
This is useful if you do not want to install to other servers and install everything on your localhost right away.

Please make sure that you have at least 4 cores (8 HT cores) and 16 GB memory on the machine where the installer runs and the demo is installed.

Also ssh root@localhost must work and the ssh fingerprint of the server should be saved in .ssh/known_hosts.

The file that is used for this installation is called conf/localhost.yaml

You need to replace the ip 127.0.0.1 in this file with the ip for your host before starting the installation:
```
servers:
  os001:
    ip: 146.185.187.4
```

Now you can set the root password, set the configfile and start
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export CONFIGFILE=${PWD}/conf/localhost.yaml
make
```

If you experience a lot of spurious ssh errors that could be a bug in paramiko ssh session handling (we see it alot during testing).
What helps is running the installer from a second machine, not on the same host you are installing to.

Also make sure your ~/.ssh/known_hosts is clean and does not contain fingerprints from logging into containers created during earlier runs (may also lead to ssh connect errors in paramiko).

Writing your own config file
============================
To set up the installation on several servers you should cd into the project directory and create a yaml file in the ./conf directory.

Also you should export two environment variables, one for the config, one for the root password of the containers and the hosts you are installing to:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export CONFIGFILE="$(pwd)/conf/alex.yaml"
make
```

You can take a look at conf/alex.yaml for an example.

If you are installing to one server and are running the installer on a different machine the server you are installing the demo on should have at least 8GB memory and 2 cores (4 HT cores).

Please make sure you also use an ssh-agent for your ssh key passphrase so that fabric can login as root to the ips of the servers you defined without asking you for the passphrase each time.

Also you should make sure that all the host fingerprints for the ips are in your .ssh/known_hosts file before you start the installer with multiple hosts (this is because of a bug in paramiko handling ProxyCommand).

MidoNet Manager
===============
If you want to look at MidoNet Manager we encourage you to get a MEM repo account (you can get a free 30 day trial key from Midokura at no cost!) and enable the following environment vars:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export OS_MIDOKURA_REPOSITORY_USER="your MEM username"
export OS_MIDOKURA_REPOSITORY_PASS="your MEM password"
export CONFIGFILE="$(pwd)/conf/alex.yaml"
make
```

After enabling these env vars the MidoNet Manager will automatically be installed (even when you pick OSS as the midonet repo) and you can use it for managing your NVO solution.

Restrictions on server names
============================
All names in the servers section (and therefore also in the role section) must end with XXX where XXX is a number between 001 and 999.
Please do not use names like 'server' or 'test' as server names.

What works best is naming the servers like this:
```
servers:
    zk001:
        ip: 192.168.4.203
        dockernet: 192.168.21.0/24

    zk002:
        ip: 192.168.4.207
        dockernet: 192.168.22.0/24

    zk003:
        ip: 192.168.4.208
        dockernet: 192.168.23.0/24

    os001:
        ip: 192.168.4.206
        dockernet: 192.168.31.0/24

    os002:
        ip: 192.168.4.202
        dockernet: 192.168.32.0/24

    os003:
        ip: 192.168.4.209
        dockernet: 192.168.33.0/24

```

When you only have one server things become easy: just name it server001 or os001.

The reason for this is that we construct some id fields from the digits of the server names.

Not for production
==================

Please do not use this software to set up production clouds.

Running the services inside Docker containers is perfectly acceptable (and will be the future of OpenStack running services anyway) but the startup of all the services is (intentionally) not automated because we want to be able to prune machines with 'make distclean' without leaving any startup scripts around on the physical servers.

The installer should serve as a fully automated bootstrapper to give you a fast and elegant way of buidling and looking at the inner workings of an OpenStack cloud running the MidoNet reference architecture.

Nested cloud installations
==========================

If you are installing into a cloud, please write down the MTU from the virtual machines and set the parameter "mtu_container" in your config file to the same value as the vms are having.

For example, when installing to MidoCloud, the vm mtu is 1450. The containers inside those vms should run with 1450 also.

If you do not set up this value, the containers will come up with a default MTU of 1500, which will then lead to very detrimental network performance inside the containers (around 30kbits, purely nostalgic modem speed).

