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

def stage8():
    metadata = Config(os.environ["CONFIGFILE"])

    if "openstack_tempest" in metadata.roles:
        execute(stage8_tempest)

@roles('container_openstack_tempest')
def stage8_tempest():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    #cuisine.package_ensure("python-tempest")
    #cuisine.package_ensure("python-nose-testconfig")

    cuisine.package_ensure("python-keystoneclient")
    cuisine.package_ensure("python-neutronclient")
    cuisine.package_ensure("python-novaclient")
    cuisine.package_ensure("python-glanceclient")

    run("""

if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

source /etc/keystone/KEYSTONERC_ADMIN

RABBIT_HOST="%s"
RABBIT_USER="osrabbit"

CONTROLLER_IP="%s"
GLANCE_IP="%s"
NEUTRON_IP="%s"

KEYSTONE_IP="%s"
COMPUTE_IP="%s"
MYSQL_IP="%s"
MIDONET_API_IP="%s"
HORIZON_IP="%s"

SERVICE_TENANT_ID="$(keystone tenant-list | grep service | awk -F'|' '{print $2;}' | xargs -n1 echo)"
ADMIN_TENANT_ID="$(keystone tenant-list | grep admin | awk -F'|' '{print $2;}' | xargs -n1 echo)"
PUBLIC_NETWORK_ID="$(neutron net-list | grep public | awk -F'|' '{print $2;}' | xargs -n1 echo)"
FLAVOR_ID="$(nova flavor-list | grep m1.tiny | awk -F'|' '{print $2;}' | xargs -n1 echo)"
IMAGE_ID="$(glance image-list | grep cirros | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)"

for CHECK_EMPTY in "${SERVICE_TENANT_ID}" \
    "${ADMIN_TENANT_ID}" \
    "${PUBLIC_NETWORK_ID}" \
    "${FLAVOR_ID}" \
    "${IMAGE_ID}"; do

    if [[ "${CHECK_EMPTY}" == "" ]]; then
        echo "at least one variable could not be loaded"
        exit 1
    fi

done

cat>/root/accounts.yaml<<EOF
- username: admin
  tenant_name: admin
  password: ${ADMIN_PASS}

EOF

cat>/root/tempest.conf<<EOF

[DEFAULT]
debug = ${DEBUG}
verbose = ${VERBOSE}

log_file = /root/tempest.log
use_stderr = False
lock_path = /root

[auth]
allow_tenant_isolation = True

[compute]
ssh_connect_method = floating
flavor_ref_alt = ${FLAVOR_ID}
flavor_ref = ${FLAVOR_ID}
image_alt_ssh_user = cirros
image_ref_alt = ${IMAGE_ID}
image_ssh_user = cirros
image_ref = ${IMAGE_ID}
ssh_timeout = 196
ip_version_for_ssh = 4
network_for_ssh = private
ssh_user = cirros
allow_tenant_isolation = True
build_timeout = 196

[compute-admin]
tenant_name = admin
password = ${ADMIN_PASS}
username = admin

[compute-feature-enabled]
api_extensions = all
block_migration_for_live_migration = False
change_password = False
live_migration = False
resize = True

[dashboard]
login_url = http://${HORIZON_IP}/auth/login/
dashboard_url = http://${HORIZON_IP}/

[identity]
auth_version = v2
admin_domain_name = Default
admin_tenant_id = ${ADMIN_TENANT_ID}
admin_tenant_name = admin
admin_password = ${ADMIN_PASS}
admin_username = admin
alt_tenant_name = admin
alt_password = ${ADMIN_PASS}
alt_username = admin
tenant_name = admin
password = ${ADMIN_PASS}
username = admin
uri_v3 = http://${KEYSTONE_IP}:5000/v3/
uri = http://${KEYSTONE_IP}:5000/v2.0/

[network]
default_network = 10.0.0.0/24
public_router_id =
public_network_id = ${PUBLIC_NETWORK_ID}
tenant_networks_reachable = false
api_version = 2.0

[network-feature-enabled]
api_extensions = Neutron Extra DHCP opts,Neutron Extra Route,Allowed Address Pairs,Neutron L3 Router,Neutron external network,Multi Provider Network,HA Router extension,DHCP Agent Scheduler,Quota management support,agent,Provider Network,Port Binding,Neutron L3 Configurable external gateway mode,L3 Agent Scheduler,security-group,Distributed Virtual Router
ipv6_subnet_attributes = True
ipv6 = True

[object-storage-feature-enabled]
discoverable_apis = all

[service_available]
tuskar = False
heat = False
ceilometer = False
swift = False
cinder = False
nova = True
glance = False
horizon = False
neutron = True

[volume]
build_timeout = 196

[volume-feature-enabled]
backup = False
api_extensions = all

[compute-feature-disabled]
api_extensions =

[network-feature-disabled]
api_extensions =

[object-storage-feature-disabled]
discoverable_apis =

[volume-feature-disabled]
api_extensions =

EOF

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.containers[metadata.roles["container_openstack_rabbitmq"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_controller"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_glance"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_neutron"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_compute"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_horizon"][0]]["ip"]
    ))


    run("service docker.io start || true")

#    run("""
#docker run -v /root/tempest.conf:/etc/tempest/tempest.conf \
#           -v /root/accounts.yaml:/etc/tempest/accounts.yaml \
#           julienvey/tempest-in-docker tempest.api.compute
#""")

    run("""
docker run -v /root/tempest.conf:/etc/tempest/tempest.conf \
           -v /root/accounts.yaml:/etc/tempest/accounts.yaml \
           julienvey/tempest-in-docker tempest.api.network 1>/tmp/test_stdout 2>/tmp/test_stderr
""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

