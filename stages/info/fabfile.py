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
from fabric.colors import red, green, yellow, white
from fabric.utils import puts

def info(admin_password="test"):
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("""
    This is the current configuration for your MidoNet powered OpenStack Demo Cluster:"""))

    puts(green("""
    container operating system: Ubuntu %s (%s)

    Midonet variant (MEM or OSS): %s

    Midonet version: %s

    Midonet Openstack plugin version: %s

    Openstack version: %s

    Admin password: %s

    Horizon url: http://%s/horizon/""" % (
        metadata.config["container_os_release_codename"],
        metadata.config["container_os_version"],
        metadata.config["midonet_repo"],
        metadata.config["midonet_%s_version" % metadata.config["midonet_repo"].lower()],
        metadata.config["midonet_%s_openstack_plugin_version" % metadata.config["midonet_repo"].lower()],
        metadata.config["openstack_release"],
        admin_password,
        metadata.servers[metadata.roles["openstack_horizon"][0]]["ip"]
    )))

    if "OS_MIDOKURA_REPOSITORY_PASS" in os.environ:
        puts(green("""
    MidoNet Manager url: http://%s:81/midonet-manager/ (or /midonet-cp2 for systems older than 1.8)
""" % metadata.servers[metadata.roles["midonet_manager"][0]]["ip"]))

    puts(white("""    Containers (and fakeuplink configuration):
"""))

    for server in sorted(metadata.servers):
        for role in sorted(metadata.config["docker_ips"][server]):
            if role == "midonet_gateway":
                server_idx = int(re.sub(r"\D", "", server))
                overlay_ip_idx = 255 - server_idx

                fakeuplink = ">> >> >> >> veth_A: %s ++ veth_B: %s" % (
                    "%s.%s" % (metadata.config["fake_transfer_net"], str(server_idx)),
                    "%s.%s" % (metadata.config["fake_transfer_net"], str(overlay_ip_idx))
                    )
            else:
                fakeuplink = ""
            puts(white("    host: %s physical ip: [%s] >> tinc vpn ip: [%s] >> >> %s >> >> >> docker container ip: [%s] %s" % (
                server,
                metadata.servers[server]["ip"],
                "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][server]),
                role,
                metadata.config["docker_ips"][server][role],
                fakeuplink
                )))
        puts("")

    puts("log in to %s (%s) and tail /var/log/syslog to see syslog of all hosts and containers" % (
        metadata.roles["openstack_controller"][0],
        metadata.servers[metadata.roles["openstack_controller"][0]]["ip"]
        ))

    puts("")

    sys.exit(0)
