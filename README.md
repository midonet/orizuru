折鶴
====
Test drive Midonet.org or MEM (with Midonet Manager) together with Openstack on Ubuntu.

The installation of the services will take place on top of Docker Ubuntu images.

You only have to provide a list of (virtual or physical) servers which you define in a simple yaml file.

Please note that you need at least one server with 8 GB for a single-host installation when you decide that all services should go into containers on one machine.

To set up the installation you should cd into the project directory, create a yaml file in the ./conf directory and export two environment variables, one for the config, one for the root password of the containers and the hosts:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export CONFIGFILE="$(pwd)/conf/alex.yaml"
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
make
```

The conf directory in the project contains a lot of files we created for testing this installer, you can look at them to see how they work.

Please make sure you use an ssh-agent for your ssh key passphrase so that fabric can login as root to the ips of the servers you defined without asking you for the passphrase.

Also you should make sure that all the host fingerprints for the ips are in your .ssh/known_hosts file before you start the script.

If you want to look at Midonet Manager you will need a MEM repo account (you can get one from Midokura) and enable the following environment vars:
```
git clone https://github.com/midonet/orizuru.git
cd orizuru
export OS_MIDOKURA_REPOSITORY_USER="your username"
export OS_MIDOKURA_REPOSITORY_PASS="your password"
export CONFIGFILE="$(pwd)/conf/alex.yaml"
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
make
```

After enabling these env vars the Midonet Manager will automatically be installed (even when you pick OSS as the midonet repo) and you can use it for managing your Midonet solution.

