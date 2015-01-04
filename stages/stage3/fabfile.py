
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

@parallel
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

@parallel
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

            cuisine.file_append("/etc/tinc/%s/tinc-up" % metadata.config["domain"], """

#
# tinc routing configuration for reaching out to networks on %s
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

