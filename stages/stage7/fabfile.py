#
# Copyright (c) 2015 Midokura SARL, All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import re

import os
import sys

from orizuru.config import Config

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

def stage7():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(stage7_container_zookeeper)
    execute(stage7_container_cassandra)
    execute(stage7_container_midonet_agent)
    execute(stage7_container_midonet_gateway)
    execute(stage7_container_midonet_api)

    # only install midonet manager if the user and password was set
    # a user who does not have the user/password must be able to install midonet.org without it
    if "OS_MIDOKURA_REPOSITORY_USER" in os.environ:
        if "OS_MIDOKURA_REPOSITORY_PASS" in os.environ:
            execute(stage7_container_midonet_manager)

    execute(stage7_container_midonet_cli)
    execute(stage7_container_midonet_tunnelzone)

    execute(stage7_container_test_connectivity)

@roles('container_zookeeper')
def stage7_container_zookeeper():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    zkhosts = []

    # the first cluster node myst have my_id 1
    zkid = 1

    # construct the ensemble string
    for container in sorted(metadata.roles["container_zookeeper"]):
        zkhosts.append('"%s:2888:3888"' % metadata.containers[container]["ip"])

        if container == env.host_string:
            my_id = zkid

        zkid = zkid + 1

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

#
# initialize the puppet module for setting up zookeeper
#
REPO="%s"
BRANCH="%s"
MY_ID="%s"

PUPPET_NODE_DEFINITION="$(mktemp)"

cd "$(mktemp -d)"; git clone "${REPO}" --branch "${BRANCH}"

PUPPET_MODULES="$(pwd)/$(basename ${REPO})/puppet/modules"

#
# set up the node definition
#
cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
    hadoop-zookeeper::install {"$(hostname)":
    }
    ->
    hadoop-zookeeper::configure {"$(hostname)":
        myid => "${MY_ID}",
        ensemble => [%s]
    }
    ->
    hadoop-zookeeper::start {"$(hostname)":
    }
}
EOF

#
# do the puppet run
#
puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"

/etc/init.d/zookeeper restart

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["midonet_puppet_modules"],
        metadata.config["midonet_puppet_modules_branch"],
        my_id,
        ",".join(zkhosts)
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_cassandra')
def stage7_container_cassandra():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cshosts = []

    for container in sorted(metadata.roles["container_cassandra"]):
        cshosts.append("%s" % metadata.containers[container]["ip"])

    cuisine.package_ensure("cassandra=2.0.10")
    cuisine.package_ensure("dsc20=2.0.10-1")

    # cuisine.package_ensure("dsc21")

    ip_address = metadata.containers[env.host_string]["ip"]

    # dsc20: org.apache.cassandra.exceptions.ConfigurationException: Invalid yaml. Please remove properties [counter_write_request_timeout_in_ms, sstable_preemptive_open_interval_in_mb, index_summary_capacity_in_mb, counter_cache_size_in_mb, memtable_allocation_type, concurrent_counter_writes, index_summary_resize_interval_in_minutes, counter_cache_save_period] from your cassandra.yaml

    cuisine.file_write("/etc/cassandra/cassandra.yaml", """

cluster_name: 'midonet'
seed_provider:
    - class_name: org.apache.cassandra.locator.SimpleSeedProvider
      parameters:
          - seeds: "%s"
listen_address: %s
rpc_address: %s

num_tokens: 256
hinted_handoff_enabled: true
max_hint_window_in_ms: 10800000 # 3 hours
hinted_handoff_throttle_in_kb: 1024
max_hints_delivery_threads: 2
batchlog_replay_throttle_in_kb: 1024
authenticator: AllowAllAuthenticator
authorizer: AllowAllAuthorizer
permissions_validity_in_ms: 2000

partitioner: org.apache.cassandra.dht.Murmur3Partitioner

data_file_directories:
    - /var/lib/cassandra/data

commitlog_directory: /var/lib/cassandra/commitlog
disk_failure_policy: stop
commit_failure_policy: stop
key_cache_size_in_mb:
key_cache_save_period: 14400
row_cache_size_in_mb: 0
row_cache_save_period: 0
# counter_cache_size_in_mb:
# counter_cache_save_period: 7200
saved_caches_directory: /var/lib/cassandra/saved_caches
commitlog_sync: periodic
commitlog_sync_period_in_ms: 10000
commitlog_segment_size_in_mb: 32

concurrent_reads: 32
concurrent_writes: 32
# concurrent_counter_writes: 32
# memtable_allocation_type: heap_buffers
# index_summary_capacity_in_mb:
# index_summary_resize_interval_in_minutes: 60
trickle_fsync: false
trickle_fsync_interval_in_kb: 10240
storage_port: 7000
ssl_storage_port: 7001
start_native_transport: true
native_transport_port: 9042

start_rpc: true
rpc_port: 9160
rpc_keepalive: true
rpc_server_type: sync

thrift_framed_transport_size_in_mb: 15

incremental_backups: false
snapshot_before_compaction: false
auto_snapshot: true
tombstone_warn_threshold: 1000
tombstone_failure_threshold: 100000
column_index_size_in_kb: 64
batch_size_warn_threshold_in_kb: 5
compaction_throughput_mb_per_sec: 16
# sstable_preemptive_open_interval_in_mb: 50
read_request_timeout_in_ms: 5000
range_request_timeout_in_ms: 10000
write_request_timeout_in_ms: 2000
# counter_write_request_timeout_in_ms: 5000
cas_contention_timeout_in_ms: 1000
truncate_request_timeout_in_ms: 60000
request_timeout_in_ms: 10000
cross_node_timeout: false

endpoint_snitch: SimpleSnitch

dynamic_snitch_update_interval_in_ms: 100
dynamic_snitch_reset_interval_in_ms: 600000
dynamic_snitch_badness_threshold: 0.1

request_scheduler: org.apache.cassandra.scheduler.NoScheduler

server_encryption_options:
    internode_encryption: none
    keystore: conf/.keystore
    keystore_password: cassandra
    truststore: conf/.truststore
    truststore_password: cassandra

client_encryption_options:
    enabled: false
    keystore: conf/.keystore
    keystore_password: cassandra

internode_compression: all
inter_dc_tcp_nodelay: false

""" % (
        ",".join(cshosts),
        ip_address,
        ip_address
    ))

    cuisine.package_ensure("openjdk-7-jre-headless")

    run("""
service cassandra start || service cassandra restart

sleep 10

if [[ ! "$(grep 'Saved cluster name Test Cluster' /var/log/cassandra/system.log)" == "" ]]; then
    service cassandra stop
    rm -rfv /var/lib/cassandra/*
    rm -v /var/log/cassandra/system.log
    service cassandra start
fi

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

#
# midolman must be on the neutron controller to work with dhcp and metadata service
#
@roles('container_midonet_gateway', 'container_openstack_neutron', 'container_openstack_compute')
def stage7_container_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

#
# initialize the puppet module for installing the midonet agent (midolman)
#
REPO="%s"
BRANCH="%s"

ZOOKEEPERS="%s"
CASSANDRAS="%s"

XMS="%s"
XMX="%s"
XMN="%s"

OPENSTACK_RELEASE="%s"

PUPPET_NODE_DEFINITION="$(mktemp)"

cd "$(mktemp -d)"; git clone "${REPO}" --branch "${BRANCH}"

PUPPET_MODULES="$(pwd)/$(basename ${REPO})/puppet/modules"

#
# set up the node definition
#
cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
    midolman::install {$(hostname):
        openstack_version => "${OPENSTACK_RELEASE}"
    }
    ->
    midolman::configure {"$(hostname)":
        zookeepers => "${ZOOKEEPERS}",
        cassandras => "${CASSANDRAS}",
        max_heap_size => "${XMX}",
        heap_newsize => "${XMN}"
    }
    ->
    midolman::start {$(hostname):
    }
}
EOF

#
# do the puppet run
#
puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"

for i in $(seq 1 12); do
    ps axufwwwww | grep -v grep | grep "midolman" && break || true
    sleep 1
done

ps axufwwwwwwwwwwwww | grep -v grep | grep midolman && exit 0

/usr/share/midolman/midolman-prepare

chmod 0777 /var/run/screen

screen -S midolman -d -m -- /usr/share/midolman/midolman-start

for i in $(seq 1 24); do
    ps axufwwwww | grep -v grep | grep "midolman" && break || true
    sleep 1
done

ps axufwwwwwwwwwwwww | grep -v grep | grep midolman

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["midonet_puppet_modules"],
        metadata.config["midonet_puppet_modules_branch"],
        ",".join(sorted(metadata.roles["container_zookeeper"])),
        ",".join(sorted(metadata.roles["container_cassandra"])),
        metadata.config["HEAP_INITIAL"],
        metadata.config["MAX_HEAPSIZE"],
        metadata.config["HEAP_NEWSIZE"],
        metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_gateway')
def stage7_container_midonet_gateway():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    server_idx = int(re.sub(r"\D", "", env.host_string))

    overlay_ip_idx = 255 - server_idx

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# fakeuplink logic for midonet gateways without binding a dedicated virtual edge NIC
#
# this is recommended for silly toy installations only - do not do this in production!
#
# The idea with the veth-pairs was originally introduced and explained to me from Daniel Mellado.
#
# Thanks a lot, Daniel!
#

# this will go into the host-side of the veth pair
PHYSICAL_IP="%s"

# this will be bound to the provider router
OVERLAY_BINDING_IP="%s"

FIP_BASE="%s"

ip a | grep veth1 || \
    ip link add type veth

# these two interfaces are basically acting as a virtual RJ45 cross-over patch cable
ifconfig veth0 up
ifconfig veth1 up

# this bridge brings us to the linux kernel routing
brctl addbr fakeuplink

# this is the physical ip we use for routing (SNATing inside linux)
ifconfig fakeuplink "${PHYSICAL_IP}/24" up

# this is the physical plug of the veth-pair
brctl addif fakeuplink veth0 # veth1 will be used by midonet

# change this to the ext range for more authentic testing
ip route add ${FIP_BASE}.0/24 via "${OVERLAY_BINDING_IP}"

# enable routing
echo 1 > /proc/sys/net/ipv4/ip_forward

""" % (
        metadata.config["debug"],
        "%s.%s" % (metadata.config["fake_transfer_net"], str(server_idx)),
        "%s.%s" % (metadata.config["fake_transfer_net"], str(overlay_ip_idx)),
        metadata.config["fip_base"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_api')
def stage7_container_midonet_api():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

#
# initialize the puppet module for midonet api
#
REPO="%s"
BRANCH="%s"
KEYSTONE_IP="%s"
MIDONET_API_IP="%s"
MIDONET_API_OUTER_IP="%s"
ZOOKEEPER_HOSTS="%s"

PUPPET_NODE_DEFINITION="$(mktemp)"

cd "$(mktemp -d)"; git clone "${REPO}" --branch "${BRANCH}"

PUPPET_MODULES="$(pwd)/$(basename ${REPO})/puppet/modules"

#
# init script is starting the daemon multiple times? might as well hit it with the sledge hammer.
#
ps axufww | grep -v grep | grep ^tomcat | awk '{print $2;}' | xargs -n1 kill -9

#
# set up the node definition
#
cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
    midonet_api::install {"$(hostname)":
    }
    ->
    midonet_api::configure {"$(hostname)":
        keystone_admin_token => "${ADMIN_TOKEN}",
        keystone_service_host => "${KEYSTONE_IP}",
        rest_api_base_url => "http://${MIDONET_API_OUTER_IP}:8080/midonet-api",
        zookeeper_hosts => "${ZOOKEEPER_HOSTS}"
    }
    ->
    midonet_api::start {"$(hostname)":
    }
}
EOF

#
# do the puppet run
#
puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["midonet_puppet_modules"],
        metadata.config["midonet_puppet_modules_branch"],
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.containers[env.host_string]["ip"],
        metadata.servers[metadata.roles["midonet_api"][0]]["ip"],
        ",".join(map(lambda zk: str(metadata.containers[zk]["ip"]), sorted(metadata.roles["container_zookeeper"])))
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_manager')
def stage7_container_midonet_manager():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

#
# initialize the puppet module for the midonet manager
#
REPO="%s"
BRANCH="%s"
API_IP="%s"
API_OUTER_IP="%s"

PUPPET_NODE_DEFINITION="$(mktemp)"

cd "$(mktemp -d)"; git clone "${REPO}" --branch "${BRANCH}"

PUPPET_MODULES="$(pwd)/$(basename ${REPO})/puppet/modules"

#
# set up the node definition
#
cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
    midonet_manager::install {"$(hostname)":
    }
    ->
    midonet_manager::configure {"$(hostname)":
        rest_api_base => "http://${API_OUTER_IP}:8080",
    }
    ->
    midonet_manager::start {"$(hostname)":
    }
}
EOF

#
# do the puppet run
#
puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["midonet_puppet_modules"],
        metadata.config["midonet_puppet_modules_branch"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.servers[metadata.roles["midonet_api"][0]]["ip"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_container_midonet_cli():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure([
        "python-midonetclient",
        "python-keystoneclient",
        "python-glanceclient",
        "python-novaclient",
        "python-neutronclient"
        ])

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

source /etc/keystone/KEYSTONERC_ADMIN

ADMIN_TENANT_ID="$(keystone tenant-list | grep admin | awk -F'|' '{print $2;}' | xargs -n1 echo)"

cat >/root/.midonetrc<<EOF
[cli]
api_url = http://%s:8080/midonet-api
username = admin
password = ${ADMIN_PASS}
tenant = ${ADMIN_TENANT_ID}
project_id = admin
EOF

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_container_midonet_tunnelzone():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure("expect")

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# create tunnel-zone
#
midonet-cli -e 'tunnel-zone list name gre' | \
    grep '^tzone' | grep 'name gre type gre' || \
        midonet-cli -e 'tunnel-zone create name gre type gre'

""" % metadata.config["debug"])

    for role in ['container_midonet_gateway', 'container_openstack_neutron', 'container_openstack_controller', 'container_openstack_compute']:
        for container in metadata.containers:
            if container in metadata.roles[role]:
                puts(green("enrolling container %s in tunnel-zone gre" % container))
                run("""
if [[ "%s" == "True" ]] ; then set -x; fi

CONTAINER_NAME="%s"
CONTAINER_IP="%s"
/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "tunnel-zone list name gre\r" }
expect "midonet> " { send "host list name ${CONTAINER_NAME}\r" }
expect "midonet> " { send "tunnel-zone tzone0 add member host host0 address ${CONTAINER_IP}\r" }
expect "midonet> " { send "quit\r" }

EOF

""" %(
        metadata.config["debug"],
        container,
        metadata.containers[container]["ip"]
    ))

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

FIP_BASE="%s"

source /etc/keystone/KEYSTONERC_ADMIN

neutron net-list | grep public || \
    neutron net-create public --shared --router:external=true

# this is the pseudo FIP subnet
neutron subnet-list | grep extsubnet || \
    neutron subnet-create public "${FIP_BASE}.0/24" --name extsubnet --enable_dhcp False

# create one example tenant router for the admin tenant
neutron router-list | grep ext-to-int || \
    neutron router-create ext-to-int

# make the Midonet provider router the virtual next-hop router for the tenant router
neutron router-gateway-set "ext-to-int" public

# create the first admin tenant internal openstack vm network
neutron net-list | grep internal || \
    neutron net-create internal --shared

# create the subnet for the vms
neutron subnet-list | grep internalsubnet || \
    neutron subnet-create internal \
        --allocation-pool start=192.168.77.100,end=192.168.77.200 \
        --name internalsubnet \
        --enable_dhcp=True \
        --gateway=192.168.77.1 \
        --dns-nameserver=8.8.8.8 \
        --dns-nameserver=8.8.4.4 \
        192.168.77.0/24

# attach the internal network to the tenant router to allow outgoing traffic for the vms
neutron router-interface-add "ext-to-int" "internalsubnet"

SECURITY_GROUP_NAME="testing"

# delete existing security groups with the same name
for ID in $(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }'); do
    nova secgroup-delete "${ID}" || true # may be already in use
done

# try to find the survivor
for ID in $(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }'); do
    EXISTING="${ID}"
done

# if not found, create
if [[ "${EXISTING}" == "" ]]; then
    nova secgroup-create "${SECURITY_GROUP_NAME}" "created by a script"
    EXISTING="$(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }')"
fi

nova secgroup-add-rule "${EXISTING}" tcp 22 22 0.0.0.0/0 || true # ssh
nova secgroup-add-rule "${EXISTING}" tcp 80 80 0.0.0.0/0 || true # http
nova secgroup-add-rule "${EXISTING}" udp 53 53 0.0.0.0/0 || true # dns
nova secgroup-add-rule "${EXISTING}" icmp -1 -1 0.0.0.0/0 || true # icmp

SSHKEY="/root/.ssh/id_rsa_nova"

if [[ ! -f "${SSHKEY}" ]]; then
  ssh-keygen -b 8192 -t rsa -N "" -C "nova" -f "${SSHKEY}"
fi

nova keypair-list | grep "$(hostname)_root_ssh_id_rsa_nova" || \
    nova keypair-add --pub_key "${SSHKEY}.pub" "$(hostname)_root_ssh_id_rsa_nova"

nova boot \
    --flavor "$(nova flavor-list | grep m1.tiny | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --image "$(nova image-list | grep cirros | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --key-name "$(nova keypair-list | grep "$(hostname)_root_ssh_id_rsa_nova" | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --security-groups "$(neutron security-group-list | grep testing | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --nic net-id="$(neutron net-list | grep internal | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    "test$(date +%%s)"

""" % (
        metadata.config["debug"],
        metadata.config["fip_base"]
    ))

    # provider router has been created now. we can set up the static routing logic.
    # note that we might also change this role loop to include compute nodes
    # (for simulating a similar approach like the HP DVR off-ramping directly from the compute nodes)
    for role in ['container_midonet_gateway']:
        for container in metadata.containers:
            if container in metadata.roles[role]:
                puts(green("setting up fakeuplink provider router leg for container %s" % container))

                physical_ip_idx = int(re.sub(r"\D", "", container))

                overlay_ip_idx = 255 - physical_ip_idx

                #
                # This logic is the complimentary logic to what happens on the midonet gateways when the veth pair, the fakeuplink bridge and the eth0 SNAT is set up.
                # We might some day change this to proper BGP peer (which will be in another container or on a different host of course).
                #
                run("""
if [[ "%s" == "True" ]] ; then set -x; fi

CONTAINER_NAME="%s"
FAKEUPLINK_VETH1_IP="%s"
FAKEUPLINK_NETWORK="%s.0/24"
FAKEUPLINK_VETH0_IP="%s"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "cleart\r" }

expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }

expect "midonet> " { send "router router0 add port address ${FAKEUPLINK_VETH1_IP} net ${FAKEUPLINK_NETWORK}\r" }
expect "midonet> " { send "port list device router0 address ${FAKEUPLINK_VETH1_IP}\r" }

expect "midonet> " { send "host list name ${CONTAINER_NAME}\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface veth1\r" }

expect "midonet> " { send "router router0 add route type normal weight 0 src 0.0.0.0/0 dst 0.0.0.0/0 gw ${FAKEUPLINK_VETH0_IP} port port0\r" }
expect "midonet> " { send "quit\r" }

EOF

""" % (
        metadata.config["debug"],
        container,
        "%s.%s" % (metadata.config["fake_transfer_net"], str(overlay_ip_idx)),
        metadata.config["fake_transfer_net"],
        "%s.%s" % (metadata.config["fake_transfer_net"], str(physical_ip_idx))
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_container_test_connectivity():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

FIP_BASE="%s"

source /etc/keystone/KEYSTONERC_ADMIN

neutron floatingip-list | grep "${FIP_BASE}" || neutron floatingip-create public

FIP_ID="$(neutron floatingip-list | grep "${FIP_BASE}" | awk -F'|' '{print $2;}' | xargs -n1 echo)"

INSTANCE_IP=""

for i in $(seq 1 100); do
    INSTANCE_ALIVE="$(nova list | grep test | grep ACTIVE)"

    if [[ "" == "${INSTANCE_ALIVE}" ]]; then
        sleep 1
    else
        break
    fi
done

if [[ "" == "${INSTANCE_ALIVE}" ]]; then
    echo "instance not alive after 100 seconds, this is not good."
    exit 1
fi

INSTANCE_IP="$(nova list --field name | grep test | awk -F'|' '{print $2;}' | xargs -n1 echo | xargs -n1 nova show | grep 'internal network' | awk -F'|' '{print $3;}' | xargs -n1 echo)"

NOVA_PORT_ID="$(neutron port-list --field id --field fixed_ips | grep "${INSTANCE_IP}" | awk -F'|' '{print $2;}' | xargs -n1 echo)"

neutron floatingip-list --field fixed_ip_address | grep "${INSTANCE_IP}" || neutron floatingip-associate "${FIP_ID}" "${NOVA_PORT_ID}"

neutron floatingip-list

""" % (
        metadata.config["debug"],
        metadata.config["fip_base"]
    ))

    run("""

source /etc/keystone/KEYSTONERC_ADMIN

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address)"

for i in $(seq 1 30); do
    ping -c1 "${FIP}" && break || true
    sleep 1
done

ping -c3 "${FIP}"

""")

    run("""

source /etc/keystone/KEYSTONERC_ADMIN

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address)"

for i in $(seq 1 30); do
    ssh -q -o StrictHostKeyChecking=no -o ConnectTimeout=2 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" uptime && break || true
    sleep 1
done

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" -- wget -O/dev/null http://www.midokura.com

""")

    run("""

source /etc/keystone/KEYSTONERC_ADMIN

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address)"

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" -- ping -c3 www.midokura.com

""")

    run("""

source /etc/keystone/KEYSTONERC_ADMIN

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address)"

ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" -- ping -c3 www.google.com

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

