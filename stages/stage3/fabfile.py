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

import cuisine

from netaddr import IPNetwork as CIDR

def stage3():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(prepare_tinc_stage3)

    execute(tinc_stage3)

@roles('all_servers')
def prepare_tinc_stage3():
    metadata = Config(os.environ["CONFIGFILE"])

    local("""
TMPDIR="%s"
SERVER="%s"

PRIVKEY="${TMPDIR}/${SERVER}/rsa_key.priv"

mkdir -pv "$(dirname "${PRIVKEY}")"

test -f "${PRIVKEY}" || openssl genrsa -out "${PRIVKEY}" 4096

test -f "${PRIVKEY}.pub" || openssl rsa -in "${PRIVKEY}" -pubout 2>/dev/null >"${PRIVKEY}.pub"

""" % (
        os.environ["TMPDIR"],
        env.host_string
    ))

@roles('all_servers')
def tinc_stage3():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.file_write("/etc/tinc/nets.boot", metadata.config["domain"])

    run("""
CONFIG="%s"

mkdir -pv "/etc/tinc/${CONFIG}/hosts"

for CMD in up down; do
    touch "/etc/tinc/${CONFIG}/tinc-${CMD}"
    chmod 0755 "/etc/tinc/${CONFIG}/tinc-${CMD}"
done

PRIVKEY="/etc/tinc/${CONFIG}/rsa_key.priv"

# chmod 0600 "${PRIVKEY}"

""" % metadata.config["domain"])

    cuisine.file_upload(
        "/etc/tinc/%s/rsa_key.priv" % metadata.config["domain"],
        "%s/%s/rsa_key.priv" % (os.environ["TMPDIR"], env.host_string))

    run("""
chmod 0600 /etc/tinc/%s/rsa_key.priv
""" % metadata.config["domain"])

    for server in metadata.servers:
        if server <> env.host_string:
            cuisine.file_write("/etc/tinc/%s/hosts/%s" % (
                metadata.config["domain"],
                server), """
Address = %s
Compression = 9

%s

""" % (
        metadata.servers[server]["ip"],
        open('%s/%s/rsa_key.priv.pub' % (os.environ["TMPDIR"], server), 'r').read()
    ))

    cuisine.file_write("/etc/tinc/%s/tinc.conf" % metadata.config["domain"], """
Name = %s

Mode = switch
AddressFamily = ipv4

""" % env.host_string)

    cuisine.file_write("/etc/tinc/%s/tinc-up" % metadata.config["domain"], """#!/bin/bash

VPN_BASE="%s"
LOCAL_IP="${VPN_BASE}.%s"
BROADCAST="${VPN_BASE}.255"
NETMASK="255.255.255.0"

TINC_INTERFACE="dockertinc"

LOCAL_TINC_IP="%s"
TINC_NETWORK="%s"
TINC_BROADCAST="%s"
TINC_NETMASK="%s"

if [[ "$(uname -o 2>/dev/null)" == "GNU/Linux" ]]; then
    /sbin/ifconfig "${INTERFACE}" "${LOCAL_IP}" netmask "${NETMASK}"
    echo 1 >/proc/sys/net/ipv4/ip_forward

    brctl show | grep "${TINC_INTERFACE}" || brctl addbr "${TINC_INTERFACE}"

    /sbin/ifconfig "${TINC_INTERFACE}" "${LOCAL_TINC_IP}" netmask "${TINC_NETMASK}"

    /sbin/ifconfig "${TINC_INTERFACE}" up
else
    /sbin/ifconfig "${INTERFACE}" "${LOCAL_IP}" "${BROADCAST}" netmask "${NETMASK}"
fi

""" % (
        metadata.config["vpn_base"],
        metadata.config["idx"][env.host_string],
        CIDR(metadata.servers[env.host_string]["dockernet"])[1],
        CIDR(metadata.servers[env.host_string]["dockernet"])[0],
        CIDR(metadata.servers[env.host_string]["dockernet"]).broadcast,
        CIDR(metadata.servers[env.host_string]["dockernet"]).netmask
    ))

    cuisine.file_write("/etc/tinc/%s/tinc-down" % metadata.config["domain"], """#!/bin/bash
/sbin/ifconfig "${INTERFACE}" down

exit 0
""")

    for server in sorted(metadata.servers):
        if server <> env.host_string:
            cuisine.file_append("/etc/tinc/%s/tinc.conf" % metadata.config["domain"], """
ConnectTo = %s
""" % server)

            # if you are not host with a midonet gateway on yourself
            if env.host_string not in metadata.roles["midonet_gateway"]:
                # and if the current server we want to route to is a midonet gateway (we can have multiple of them)
                if server in metadata.roles["midonet_gateway"]:
                    # route the fip network traffic to this midonet gateway
                    cuisine.file_append("/etc/tinc/%s/tinc-up" % metadata.config["domain"], """
#
# tinc routing configuration: forward floating ip range packets to %s
# where they will be further forwarded to the midonet_gateway docker container
#
VPN_BASE="%s"
GW="${VPN_BASE}.%s"

NET="%s.0"
NETMASK="255.255.255.0"

if [[ "$(uname -o 2>/dev/null)" == "GNU/Linux" ]]; then
    /sbin/route add -net "${NET}" netmask "${NETMASK}" gw "${GW}"
else
    /sbin/route add -net "${NET}" "${GW}" "${NETMASK}"
fi

""" % (
    server,
    metadata.config["vpn_base"],
    metadata.config["idx"][server],
    metadata.config["fip_base"]
    ))

            cuisine.file_append("/etc/tinc/%s/tinc-up" % metadata.config["domain"], """
#
# tinc routing configuration: forward packets for the docker network ips on server %s
#
VPN_BASE="%s"
NET="%s"
GW="${VPN_BASE}.%s"
NETMASK="%s"

if [[ "$(uname -o 2>/dev/null)" == "GNU/Linux" ]]; then
    /sbin/route add -net "${NET}" netmask "${NETMASK}" gw "${GW}"
else
    /sbin/route add -net "${NET}" "${GW}" "${NETMASK}"
fi
""" % (
        server,
        metadata.config["vpn_base"],
        CIDR(metadata.servers[server]["dockernet"])[0],
        metadata.config["idx"][server],
        CIDR(metadata.servers[server]["dockernet"]).netmask
    ))

    run("""

update-rc.d tinc defaults

/etc/init.d/tinc restart || /etc/init.d/tinc start

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

