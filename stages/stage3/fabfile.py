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

from fabric.colors import green

from fabric.utils import puts

metadata = Config(os.environ["CONFIGFILE"])

def stage3():

    execute(prepare_tinc_stage3)

    execute(tinc_stage3)

    execute(check_tinc_stage3)

@roles('all_servers')
def prepare_tinc_stage3():

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

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    tinc_stage3_private_key()

    tinc_stage3_public_keys()

    tinc_stage3_networking()

    tinc_stage3_networking_shutdown()

    tinc_stage3_routing()

    tinc_stage3_fip_routing()

    tinc_stage3_daemon()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('all_servers')
def check_tinc_stage3():

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    puts(green("checking if the local tinc is up"))

    run("""
VPN_BASE="%s"
LOCAL_IP="${VPN_BASE}.%s"

ping -c3 "${LOCAL_IP}"

""" % (
        metadata.config["vpn_base"],
        metadata.config["idx"][env.host_string]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

#
# this is the fakeuplink routing logic. in a production setup it will not be used this way. because there the router is fully distributed.
#
def tinc_stage3_fip_routing():
    #
    # do not run this code if you are working with physical midonet gateways for a demo
    #
    if "midonet_gateway" not in metadata.roles:
        return

    #
    # on all machines that do not host a midonet_gateway container: send the traffic to a machine hosting a midonet gw container
    #
    if env.host_string not in metadata.roles["midonet_gateway"]:
        for server in metadata.servers:
            if server in metadata.roles["midonet_gateway"]:
                fip_router_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][server])
                continue

    #
    # on all machines that host a midonet gateway container: send the traffic to the midonet_gateway container on this box
    #
    else:

        #
        # SNAT the fip network
        #
        run("""
FIP_BASE="%s"

DEFAULT_GW_IFACE="$(ip route show | grep 'default via' | awk -Fdev '{print $2;}' | xargs -n1 echo)"

iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -j MASQUERADE

for RFC1918 in "10.0.0.0/8" "172.16.0.0/12" "192.168.0.0/16"; do
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -d "${RFC1918}" -j ACCEPT
done

""" % metadata.config["fip_base"])

        for container in metadata.containers:
            if metadata.containers[container]["server"] == env.host_string:
                if metadata.containers[container]["role"] == "midonet_gateway":
                    fip_router_ip = metadata.containers[container]["ip"]
                    continue

    cuisine.file_append("/etc/tinc/%s/tinc-up" % metadata.config["domain"], """

#
# route FIP traffic to this local container
#

NET="%s"
NETMASK="255.255.255.0"
GW="%s"

if [[ "$(uname -o 2>/dev/null)" == "GNU/Linux" ]]; then
    /sbin/route add -net "${NET}" netmask "${NETMASK}" gw "${GW}"
else
    /sbin/route add -net "${NET}" "${GW}" "${NETMASK}"
fi

""" % (metadata.config["fip_base"], fip_router_ip))

def tinc_stage3_private_key():
    run("mkdir -pv /etc/tinc")
    cuisine.file_write("/etc/tinc/nets.boot", metadata.config["domain"])

    run("""
DOMAIN="%s"

mkdir -pv "/etc/tinc/${DOMAIN}/hosts"

for CMD in up down; do
    touch "/etc/tinc/${DOMAIN}/tinc-${CMD}"
    chmod 0755 "/etc/tinc/${DOMAIN}/tinc-${CMD}"
done

PRIVKEY="/etc/tinc/${DOMAIN}/rsa_key.priv"

""" % metadata.config["domain"])

    cuisine.file_upload(
        "/etc/tinc/%s/rsa_key.priv" % metadata.config["domain"],
        "%s/%s/rsa_key.priv" % (os.environ["TMPDIR"], env.host_string))

    run("""
chmod 0600 /etc/tinc/%s/rsa_key.priv
""" % metadata.config["domain"])

def tinc_stage3_public_keys():
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

def tinc_stage3_networking():
    cuisine.file_write("/etc/tinc/%s/tinc.conf" % metadata.config["domain"], """
Name = %s

Mode = switch
AddressFamily = ipv4

""" % env.host_string)

    #
    # local routing
    #
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

ifconfig "${INTERFACE}" "${LOCAL_IP}" netmask "${NETMASK}"

echo 1 >/proc/sys/net/ipv4/ip_forward

brctl show | grep "${TINC_INTERFACE}" || brctl addbr "${TINC_INTERFACE}"

ifconfig "${TINC_INTERFACE}" "${LOCAL_TINC_IP}" netmask "${TINC_NETMASK}"
ifconfig "${TINC_INTERFACE}" up

""" % (
        metadata.config["vpn_base"],
        metadata.config["idx"][env.host_string],
        CIDR(metadata.servers[env.host_string]["dockernet"])[1],
        CIDR(metadata.servers[env.host_string]["dockernet"])[0],
        CIDR(metadata.servers[env.host_string]["dockernet"]).broadcast,
        CIDR(metadata.servers[env.host_string]["dockernet"]).netmask
    ))

def tinc_stage3_networking_shutdown():
    cuisine.file_write("/etc/tinc/%s/tinc-down" % metadata.config["domain"], """#!/bin/bash
/sbin/ifconfig "${INTERFACE}" down
""")

def tinc_stage3_routing():
    for server in sorted(metadata.servers):
        if server <> env.host_string:
            cuisine.file_append("/etc/tinc/%s/tinc.conf" % metadata.config["domain"], """
ConnectTo = %s
""" % server)

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

def tinc_stage3_daemon():
    run("""

update-rc.d tinc defaults

/etc/init.d/tinc stop || true

pidof tincd | xargs -n1 --no-run-if-empty -- kill -9

sleep 2

/etc/init.d/tinc start

sleep 10

ps axufwwwwwwwwwwwwwwwwwww | grep -v grep | grep tincd

""")

