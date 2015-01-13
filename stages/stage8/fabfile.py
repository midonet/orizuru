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

    execute(stage8_tempest)

@roles('container_midonet_cli')
def stage8_tempest():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    # TODO install all the packages needed for tempest runs

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

SERVICE_TENANT_ID="$(keystone tenant-list | grep '| service |' | awk -F'|' '{print $2;}' | xargs -n1)"

KEYSTONE_IP="%s"
COMPUTE_IP="%s"
MYSQL_IP="%s"
MIDONET_API_IP="%s"

mkdir -pv /var/log/nova
mkdir -pv /etc/tempest

pip install --upgrade -r /usr/share/doc/tempest/requirements.txt

cat>/etc/tempest/tempest.conf<<EOF
[DEFAULT]
notification_driver = ceilometer.compute.nova_notifier
notification_driver = nova.openstack.common.notifier.rpc_notifier
amqp_durable_queues = False
rabbit_host = ${RABBIT_HOST}
rabbit_port = 5672
rabbit_hosts = ${RABBIT_HOST}:5672
rabbit_use_ssl = False
rabbit_userid = ${RABBIT_USER}
rabbit_password = ${RABBIT_PASS}
rabbit_virtual_host = /
rabbit_ha_queues = False
notification_topics = notifications
rpc_backend = nova.openstack.common.rpc.impl_kombu
notify_api_faults = False
state_path = /var/lib/nova
report_interval = 10
enabled_apis = ec2,osapi_compute,metadata
ec2_listen = 0.0.0.0
osapi_compute_listen = 0.0.0.0
osapi_compute_workers = 4
metadata_listen = 0.0.0.0
metadata_workers = 4
service_down_time = 60
rootwrap_config = /etc/nova/rootwrap.conf
auth_strategy = keystone
use_forwarded_for = False
service_neutron_metadata_proxy = True
neutron_metadata_proxy_shared_secret = ${NEUTRON_METADATA_SHARED_SECRET}
neutron_default_tenant_id = ${SERVICE_TENANT_ID}
novncproxy_host = ${CONTROLLER_IP}
novncproxy_port = 6080
glance_api_servers = ${GLANCE_IP}:9292
network_api_class = nova.network.neutronv2.api.API
metadata_host = ${CONTROLLER_IP}
neutron_url = http://${NEUTRON_IP}:9696
neutron_url_timeout = 30
neutron_admin_username = neutron
neutron_admin_password = ${NEUTRON_PASS}
neutron_admin_tenant_name = service
neutron_region_name = regionOne
neutron_admin_auth_url = http://${KEYSTONE_IP}:35357/v2.0
neutron_auth_strategy = keystone
neutron_ovs_bridge = br-int
neutron_extension_sync_interval = 600
security_group_api = neutron
lock_path = /var/lib/nova/tmp
debug = False
verbose = True
log_dir = /var/log/nova
use_syslog = False
cpu_allocation_ratio = 16.0
ram_allocation_ratio = 1.5
scheduler_default_filters = RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,CoreFilter
compute_driver = nova.virt.libvirt.LibvirtDriver
vif_plugging_is_fatal = True
vif_plugging_timeout = 300
firewall_driver = nova.virt.firewall.NoopFirewallDriver
novncproxy_base_url = http://${CONTROLLER_IP}:6080/vnc_auto.html
vncserver_listen = ${CONTROLLER_IP}
vncserver_proxyclient_address = ${COMPUTE_IP}
vnc_enabled = True
volume_api_class = nova.volume.cinder.API
sql_connection = mysql://nova:${NOVA_DBPASS}@${MYSQL_IP}/nova
image_service = nova.image.glance.GlanceImageService
osapi_volume_listen = 0.0.0.0
libvirt_inject_partition = -1
libvirt_cpu_mode = none
username = admin
auth_url = http://${KEYSTONE_IP}:5000/v2.0
password = ${ADMIN_PASS}
libvirt_vif_driver = midonet.nova.virt.libvirt.vif.MidonetVifDriver
midonet_uri = http://${MIDONET_API_IP}:8080/midonet-api
project_id = admin

[baremetal]

[cells]

[conductor]
workers = 4

[database]

[hyperv]

[image_file_url]

[keymgr]

[keystone_authtoken]
auth_host = ${KEYSTONE_IP}
auth_port = 35357
auth_protocol = http
auth_uri = http://${KEYSTONE_IP}:5000/
admin_user = admin
admin_password = ${ADMIN_PASS}
admin_tenant_name = admin

[libvirt]
virt_type = qemu
live_migration_uri = qemu+ssh://nova@${CONTROLLER_IP}/system?keyfile=/etc/nova/ssh/nova_migration_key
vif_driver = nova.virt.libvirt.vif.LibvirtGenericVIFDriver
cpu_mode = host-model
[matchmaker_ring]

[metrics]

[osapi_v3]

[rdp]

[spice]

[ssl]

[trusted_computing]

[upgrade_levels]

[vmware]

[xenserver]

[zookeeper]

[MIDONET]
midonet_uri = http://${MIDONET_API_IP}:8080/midonet-api
username = midonet
password = ${MIDONET_PASS}
project_id = service
auth_url = http://${MIDONET_API_IP}:5000/v2.0

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
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"]
    ))

    # TODO do the tempest run against the freshly installed cloud

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

