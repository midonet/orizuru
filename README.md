折鶴
====
Test drive MidoNet.org or MEM (with MidoNet Manager) together with Openstack on Ubuntu.

A video of the installer running (30 minutes) is available here: http://midonet.github.io/orizuru .

To get started all you have to do is to provide a list of (virtual or physical) servers which you define in a simple yaml file.

MidoNet and Openstack will then install inside Docker containers on these servers and use a tinc vpn for secure communication between all containers and hosts.

Localhost Quickstart
====================
If you do not want to change anything and install on your localhost right away, make sure that you have at least 4 cores (8 HT cores) and 16 GB memory on your single machine.

Also ssh root@localhost must work and the ssh fingerprint of the server should be saved in .ssh/known_hosts. If the environment variable CONFIGFILE is not set the installer will use conf/localhost.yaml.
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
make
```

Writing your own config file
============================
To set up the installation on another server you should cd into the project directory, create a yaml file in the ./conf directory and export two environment variables, one for the config, one for the root password of the containers and the hosts:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export CONFIGFILE="$(pwd)/conf/alex.yaml"
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
make
```

The server should have at least 8GB memory and 2 cores (4 HT cores).

Please make sure you also use an ssh-agent for your ssh key passphrase so that fabric can login as root to the ips of the servers you defined without asking you for the passphrase each time.

Also you should make sure that all the host fingerprints for the ips are in your .ssh/known_hosts file before you start the installer with multiple hosts.

MidoNet Manager
===============
If you want to look at MidoNet Manager you will need a MEM repo account (you can get one from Midokura) and enable the following environment vars:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export OS_MIDOKURA_REPOSITORY_USER="your username"
export OS_MIDOKURA_REPOSITORY_PASS="your password"
export CONFIGFILE="$(pwd)/conf/alex.yaml"
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
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

Please do not use this software to set up production clouds.  Running the services inside Docker containers is ok but the startup of all the services is (intentionally) not automated.

This installer should serve as a bootstrapper for a complete OpenStack cloud running MidoNet and for example testing it against newer Operating System releases and different MEM and OSS versions.

