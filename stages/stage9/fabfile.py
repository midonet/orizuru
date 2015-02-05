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

import os
import sys

from orizuru.config import Config

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

#
# all logic in this fabfile is directly taken from the
# OpenStack Installation Guide for Ubuntu 14.04 pdf
#
# the downloaded version we have used: November 21, 2014 juno
#
def stage9():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    if 'physical_openstack_compute' in metadata.roles:
        execute(stage9_container_openstack_swift)
        execute(stage9_container_openstack_swift_seed_rings)
        execute(stage9_container_openstack_swift_automate_all_the_startups)
        execute(stage9_container_openstack_swift_check)

@roles('container_openstack_controller')
def stage9_container_openstack_swift_seed_rings():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    rings = {}
    rings["account"] = 6002
    rings["container"] = 6001
    rings["object"] = 6000

    #
    # create the rings
    #
    for ring in rings:
        run("""
RING="%s"

mkdir -p /etc/swift
cd /etc/swift

swift-ring-builder ${RING}.builder create 10 3 1

""" % ring)

    #
    # add all compute nodes to these rings
    #
    for compute_node in metadata.roles["physical_openstack_compute"]:
        compute_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][compute_node])
        for ring in rings:
            run("""
COMPUTE_IP="%s"
COMPUTE_NODE="%s"
PORT="%s"
RING="%s"

mkdir -p /etc/swift
cd /etc/swift

swift-ring-builder ${RING}.builder add r1z1-${COMPUTE_IP}:${PORT}/sdx1 100
swift-ring-builder ${RING}.builder add r1z1-${COMPUTE_IP}:${PORT}/sdx2 100

""" % (compute_ip, compute_node, rings[ring], ring))

    #
    # create the .gz files
    #
    for ring in rings:
        run("""
RING="%s"

cd /etc/swift

swift-ring-builder ${RING}.builder rebalance

sync

swift-ring-builder ${RING}.builder

""" % ring)

    #
    # fan-out the .gz files to the compute nodes
    #
    local("""
TMPDIR="%s"
CONTROLLER="%s"

cd "${TMPDIR}"

mkdir -pv ${CONTROLLER}/etc/swift

rsync -avpx -e 'ssh -F .ssh/config -o StrictHostKeyChecking=no' root@${CONTROLLER}:/etc/swift/. ./${CONTROLLER}/etc/swift/.

""" % (os.environ["TMPDIR"], env.host_string))

    for compute_node in metadata.roles["physical_openstack_compute"]:
        local("""
TMPDIR="%s"
COMPUTE_NODE="%s"
CONTROLLER="%s"

cd "${TMPDIR}"

ssh -F .ssh/config root@${COMPUTE_NODE} -- mkdir -p /etc/swift

rsync -avpx -e 'ssh -F .ssh/config -o StrictHostKeyChecking=no' ./${CONTROLLER}/etc/swift/*.gz root@${COMPUTE_NODE}:/etc/swift/.

""" % (os.environ["TMPDIR"], compute_node, env.host_string))

    # TODO enable this once things have stabilized cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_controller', 'physical_openstack_compute')
def stage9_container_openstack_swift_automate_all_the_startups():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""

chown -R swift:swift /srv/node
chown -R swift:swift /etc/swift
chown -R swift:swift /var/cache/swift
chown -R swift:swift /var/run/swift

""")

    run("""

service memcached restart

""")

    run("""

swift-init all stop || true

service memcached restart

echo stats | nc localhost 11211 | grep 'STAT uptime'

swift-init all start

""")

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_controller')
def stage9_container_openstack_swift_check():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""

source /etc/keystone/KEYSTONERC

swift list

""")

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_controller', 'physical_openstack_compute')
def stage9_container_openstack_swift():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure([
        "curl",
        "swift",
        "swift-proxy",
        "python-swiftclient",
        "python-keystoneclient",
        "python-keystonemiddleware",
        "memcached",
        "swift-account",
        "swift-container",
        "swift-object",
        "xfsprogs",
        "rsync"])

    if env.host_string in metadata.roles["physical_openstack_compute"]:
        rsync_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][env.host_string])
    else:
        rsync_ip = metadata.containers[env.host_string]["ip"]

    run("""

RSYNC_BIND_IP="%s"

swift-init all stop || true

rm -rf /etc/swift
rm -rf /var/cache/swift
rm -rf /var/run/swift
rm -rf /var/log/swift

mkdir -p /etc/swift
mkdir -p /var/cache/swift
mkdir -p /var/run/swift
mkdir -p /var/log/swift

cat>/etc/rsyncd.conf<<EOF
uid = swift
gid = swift
log file = /var/log/rsyncd.log
pid file = /var/run/rsyncd.pid
address = ${RSYNC_BIND_IP}

[account]
max connections = 2
path = /srv/node/
read only = false
lock file = /var/lock/account.lock

[container]
max connections = 2
path = /srv/node/
read only = false
lock file = /var/lock/container.lock

[object]
max connections = 2
path = /srv/node/
read only = false
lock file = /var/lock/object.lock

EOF

cat>/etc/default/rsync<<EOF
RSYNC_ENABLE=true
EOF

service rsync restart

""" % rsync_ip)

    if env.host_string in metadata.roles["physical_openstack_compute"]:
        run("""
for NODE in 1 2; do
    mkdir -p /srv/node/sdx${NODE}

    umount /srv/node/sdx${NODE} || true
    test -f /tmp/sdx${NODE}.dd || dd if=/dev/zero of=/tmp/sdx${NODE}.dd bs=4096 count=100000

    losetup /dev/loop${NODE} /tmp/sdx${NODE}.dd || true

    mkfs.ext4 /dev/loop${NODE} || true
    mount -o noatime,nodiratime,nobarrier,data=ordered -t ext4 /dev/loop${NODE} /srv/node/sdx${NODE}
done

""")

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

CONFIGHELPER="%s"

SERVICE="%s"

KEYSTONE_IP="%s"

BIND_IP="%s"

for TYPE in "proxy" "account" "container" "object"; do
    CONFIGFILE="/etc/swift/${TYPE}-server.conf"

    test -f ${CONFIGFILE} || curl -o ${CONFIGFILE} https://raw.githubusercontent.com/openstack/swift/stable/juno/etc/${TYPE}-server.conf-sample
    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "True"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "True"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "bind_ip" "${BIND_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "user" "swift"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "swift_dir" "/etc/swift"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "expose_info" "true"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_name" "swift"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_facility" "LOG_LOCAL2"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_level" "INFO"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_headers" "true"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_requests" "true"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_address" "/dev/log"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "log_max_line_length" "0"

    if [[ ! "proxy" == "${TYPE}" ]]; then
        "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "devices" "/srv/node"
        "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "mount_check" "false"
    fi

    "${CONFIGHELPER}" set "${CONFIGFILE}" "filter:recon" "use" "egg:swift#recon"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "filter:recon" "recon_cache_path" "/var/cache/swift"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "filter:healthcheck" "use" "egg:swift#healthcheck"
done

touch "/etc/swift/container-sync-realms.conf"

CONFIGFILE="/etc/swift/proxy-server.conf"

"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "bind_port" "8080"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "workers" "8"

"${CONFIGHELPER}" set "${CONFIGFILE}" "pipeline:main" "pipeline" "tempauth authtoken cache healthcheck keystoneauth proxy-logging proxy-server"

"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:cache" "memcache_servers" "127.0.0.1:11211"

"${CONFIGHELPER}" set "${CONFIGFILE}" "app:proxy-server" "allow_account_management" "true"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:proxy-server" "account_autocreate" "true"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:proxy-server" "use" "egg:swift#proxy"

"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:keystoneauth" "use" "egg:swift#keystoneauth"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:keystoneauth" "operator_roles" "admin,_member_"

"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "paste.filter_factory" "keystonemiddleware.auth_token:filter_factory"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "auth_uri" "http://${KEYSTONE_IP}:5000/v2.0"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "identity_uri" "http://${KEYSTONE_IP}:35357"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "admin_tenant_name" "service"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "admin_user" "swift"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "admin_password" "${SWIFT_PASS}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:authtoken" "delay_auth_decision"  "true"

CONFIGFILE="/etc/swift/account-server.conf"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "bind_port" "6002"
"${CONFIGHELPER}" set "${CONFIGFILE}" "pipeline:main" "pipeline" "healthcheck recon account-server"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:account-server" "use" "egg:swift#account"
"${CONFIGHELPER}" set "${CONFIGFILE}" "account-replicator" "concurrency" "8"

CONFIGFILE="/etc/swift/container-server.conf"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "bind_port" "6001"
"${CONFIGHELPER}" set "${CONFIGFILE}" "pipeline:main" "pipeline" "healthcheck recon container-server"
"${CONFIGHELPER}" set "${CONFIGFILE}" "filter:recon" "container_recon" "true"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:container-server" "use" "egg:swift#container"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:container-server" "allow_versions" "true"
"${CONFIGHELPER}" set "${CONFIGFILE}" "container-replicator" "concurrency" "8"
"${CONFIGHELPER}" set "${CONFIGFILE}" "container-updater" "concurrency" "8"

CONFIGFILE="/etc/swift/object-server.conf"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "bind_port" "6000"
"${CONFIGHELPER}" set "${CONFIGFILE}" "pipeline:main" "pipeline" "healthcheck recon object-server"
"${CONFIGHELPER}" set "${CONFIGFILE}" "app:object-server" "use" "egg:swift#object"
"${CONFIGHELPER}" set "${CONFIGFILE}" "object-replicator" "concurrency" "8"
"${CONFIGHELPER}" set "${CONFIGFILE}" "object-updater" "concurrency" "8"

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        "swift",
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        rsync_ip
    ))

    run("""

CONFIGHELPER="%s"

CONFIGFILE="/etc/swift/swift.conf"

curl -o ${CONFIGFILE} https://raw.githubusercontent.com/openstack/swift/stable/juno/etc/swift.conf-sample
test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION"

"${CONFIGHELPER}" set "${CONFIGFILE}" "swift-hash" "swift_hash_path_prefix" "12345678"
"${CONFIGHELPER}" set "${CONFIGFILE}" "swift-hash" "swift_hash_path_suffix" "12345678"

"${CONFIGHELPER}" set "${CONFIGFILE}" "storage-policy:0" "name" "Policy-0"
"${CONFIGHELPER}" set "${CONFIGFILE}" "storage-policy:0" "default" "yes"

""" % metadata.config["constrictor"])

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

