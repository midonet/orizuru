折鶴
====

Test drive Midonet.org or MEM (with Midonet Manager) together with Openstack on Ubuntu.

The installation of the services will take place on top of Docker Ubuntu images.

You only have to provide a list of (virtual or physical) servers which you define in a simple yaml file.

To do this you can cd into the project directory, create a yaml file and export two environment variables, one for the config, one for the root password of the containers and the hosts:
```
export CONFIGFILE="$(pwd)/conf/alex.yaml"
export OS_MIDOKURA_ROOT_PASSWORD="new root password"
```

The installer will now create the containers on these servers and install Openstack with Midonet as part of a demo installation:
```
make
```

If you want to look at Midonet Manager you will need a MEM repo account (you can get one from Midokura) and enable the following environment vars:
```
export OS_MIDOKURA_REPOSITORY_USER="your username"
export OS_MIDOKURA_REPOSITORY_PASS="your password"
```

After enabling these the Midonet Manager will automatically be installed and you can use it for managing your Midonet solution.

