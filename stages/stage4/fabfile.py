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

from fabric.colors import green, yellow, red
from fabric.utils import puts

import cuisine

from netaddr import IPNetwork as CIDR

metadata = Config(os.environ["CONFIGFILE"])

@roles('all_servers')
def stage4():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""

cat >/etc/default/docker<<EOF
DOCKER_OPTS="--dns 8.8.8.8 --dns 8.8.4.4"
EOF

service docker restart

sleep 10

""")

    run("docker ps")

    run("docker images")

    for container in sorted(metadata.containers):
        server = metadata.containers[container]["server"]
        container_ip = metadata.containers[container]["ip"]
        role = metadata.containers[container]["role"]

        #
        # only create a container on this host if the container belongs on it
        #
        if server == env.host_string:
            puts(green("creating/configuring container on server %s with ip %s for role %s" % (server, container_ip, role)))

            dockerfile = "/tmp/Dockerfile_orizuru_%s" % server

            cuisine.file_write(dockerfile,
"""
#
# orizuru base image for all Midonet and Openstack services
#
# VERSION               0.1.0
#

FROM %s:%s

MAINTAINER Alexander Gabert <alexander@midokura.com>

RUN sed -i 's,deb http://archive.ubuntu.com,deb %s/%s.archive.ubuntu.com,g;' /etc/apt/sources.list
RUN sed -i 's,deb-src http://archive.ubuntu.com,deb-src %s/%s.archive.ubuntu.com,g;' /etc/apt/sources.list

RUN sync

RUN cat /etc/apt/sources.list

RUN rm -rf /var/lib/apt/lists
RUN mkdir -p /var/lib/apt/lists/partial
RUN apt-get clean
RUN apt-get autoclean
RUN apt-get update 1>/dev/null
RUN DEBIAN_FRONTEND=noninteractive apt-get -y -u dist-upgrade 1>/dev/null

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server screen
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y %s

RUN mkdir -pv /var/run/screen
RUN chmod 0777 /var/run/screen

RUN chmod 0755 /usr/bin/screen
RUN mkdir -pv /var/run/sshd

RUN echo 'LANG="en_US.UTF-8"' | tee /etc/default/locale
RUN locale-gen en_US.UTF-8

RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

RUN mkdir -pv /root/.ssh
RUN chmod 0755 /root/.ssh

COPY /root/.ssh/authorized_keys /root/.ssh/authorized_keys

ENV NOTVISIBLE "in users profile"

RUN echo "export VISIBLE=now" >> /etc/profile

RUN sync

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]

""" % (
        metadata.config["container_os"],
        metadata.config["container_os_version"],
        metadata.config["apt-cacher"],
        metadata.config["archive_country"],
        metadata.config["apt-cacher"],
        metadata.config["archive_country"],
        metadata.config["common_packages"]
        ))

            run("""

SERVER_NAME="%s"
CONTAINER_ROLE="%s"
DOCKERFILE="/tmp/Dockerfile_orizuru_${SERVER_NAME}"

cd "$(mktemp -d)"

cp "${DOCKERFILE}" Dockerfile

mkdir -pv root/.ssh

cat /root/.ssh/authorized_keys > root/.ssh/authorized_keys

echo nameserver 8.8.8.8 | tee /etc/resolv.conf

echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6

docker images | grep "template_${SERVER_NAME}" || docker build --no-cache=true -t "template_${SERVER_NAME}" .

mkdir -pv /etc/rc.local.d

""" % (
        server,
        role
     ))

            cuisine.file_write("/etc/rc.local.d/docker_%s_%s" % (role, server),
"""#!/bin/bash
#
# adapted from https://docs.docker.com/articles/networking/#building-your-own-bridge
#

DOCKER_BRIDGE="dockertinc"
SERVER_NAME="%s"
CONTAINER_IP="%s"
CONTAINER_ROLE="%s"
CONTAINER_DEFAULT_GW="%s"
CONTAINER_NETMASK="%s"
CONTAINER_NETWORK="%s"
DOMAIN_NAME="%s"
SERVER_IP="%s"
FIP_BASE="%s"

MIDONET_API_IP="%s"
MIDONET_API_OUTER_IP="%s"

MTU_CONTAINER="%s"

CONTAINER_VETH="${RANDOM}"

NETNS_NAME="docker_${CONTAINER_VETH}_${CONTAINER_ROLE}_${SERVER_NAME}"

CONTAINER_VETH_A="${CONTAINER_VETH}A"
CONTAINER_VETH_B="${CONTAINER_VETH}B"

CONTAINER_ETC_HOSTS="/etc/hosts"

DEFAULT_GW_IFACE="$(ip route show | grep 'default via' | awk -Fdev '{print $2;}' | xargs -n1 echo)"

if [[ "${DEFAULT_GW_IFACE}" == "" ]]; then
    exit 1
fi

if [[ "$(ps axufwwwwwwwwwwwwwww | grep -v grep | grep -v SCREEN | grep -- "docker run -h ${CONTAINER_ROLE}_${SERVER_NAME}")" == "" ]]; then
    #
    # start the container in a screen session
    #
    screen -d -m -- docker run -h "${CONTAINER_ROLE}_${SERVER_NAME}" --privileged=true -i -t --rm --net="none" --name "${CONTAINER_VETH}_${CONTAINER_ROLE}_${SERVER_NAME}" "template_${SERVER_NAME}"

    for i in $(seq 1 120); do
        CONTAINER_ID="$(docker ps | grep "${CONTAINER_VETH}_${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}')"

        if [[ "" == "${CONTAINER_ID}" ]]; then
            sleep 1
        else
            break
        fi
    done

    if [[ "" == "${CONTAINER_ID}" ]]; then
        echo "container failed to spawn."
        exit 1
    fi

    CONTAINER_PID="$(docker inspect -f '{{.State.Pid}}' "${CONTAINER_ID}")"

    if [[ "${CONTAINER_PID}" == "" ]]; then
        echo "container failed to spawn."
        exit 1
    fi

    #
    # link the network namespace of the spawned container to make it a non-anonymous ip namespace
    #
    mkdir -p "/var/run/netns"
    ln -s "/proc/${CONTAINER_PID}/ns/net" "/var/run/netns/${NETNS_NAME}"

    #
    # add the veth pair for this container
    #
    ip link add "${CONTAINER_VETH_A}" type veth peer name "${CONTAINER_VETH_B}"

    #
    # add one side of the pair to our master bridge for the container network on this host (routed by tinc)
    #
    brctl addif "${DOCKER_BRIDGE}" "${CONTAINER_VETH_A}"

    #
    # set up networking for the container in our main namespace
    #
    ip link set "${CONTAINER_VETH_A}" up
    ip link set dev "${CONTAINER_VETH_A}" mtu "${MTU_CONTAINER}"

    #
    # set up networking in the container namespace
    #
    ip link set "${CONTAINER_VETH_B}" netns "${NETNS_NAME}"
    ip netns exec "${NETNS_NAME}" ip link set dev "${CONTAINER_VETH_B}" name eth0
    ip netns exec "${NETNS_NAME}" ip link set eth0 up
    ip netns exec "${NETNS_NAME}" ip addr add "${CONTAINER_IP}/${CONTAINER_NETMASK}" dev eth0
    ip netns exec "${NETNS_NAME}" ip route add default via "${CONTAINER_DEFAULT_GW}"
    ip netns exec "${NETNS_NAME}" ip link set dev eth0 mtu "${MTU_CONTAINER}"

else
    CONTAINER_ID="$(docker ps | grep -v '^CONTAINER' | grep -- "${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}' | head -n1)"
fi

#
# the /etc/hosts could have been updated in the meantime, add it to the container even when its already running
#
CONTAINER_HOSTS_PATH="$(docker ps | grep -v ^CONTAINER | grep "^${CONTAINER_ID}" | awk '{print $1;}' | xargs -n1 --no-run-if-empty docker inspect --format "{{ .HostsPath }}")"
cat "${CONTAINER_ETC_HOSTS}" >"${CONTAINER_HOSTS_PATH}"

""" % (
        server,
        container_ip,
        role,
        CIDR(metadata.servers[server]["dockernet"])[1],
        CIDR(metadata.servers[server]["dockernet"]).netmask,
        CIDR(metadata.servers[server]["dockernet"])[0],
        metadata.config["domain"],
        metadata.servers[server]["ip"],
        metadata.config["fip_base"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.servers[metadata.roles["midonet_api"][0]]["ip"],
        metadata.config["mtu_container"]
    ))

            cuisine.file_write("/etc/rc.local.d/docker_%s_%s_NAT" % (role, server),
"""#!/bin/bash
#
# adapted from https://docs.docker.com/articles/networking/#building-your-own-bridge
#

DOCKER_BRIDGE="dockertinc"
SERVER_NAME="%s"
CONTAINER_IP="%s"
CONTAINER_ROLE="%s"
CONTAINER_DEFAULT_GW="%s"
CONTAINER_NETMASK="%s"
CONTAINER_NETWORK="%s"
DOMAIN_NAME="%s"
SERVER_IP="%s"
FIP_BASE="%s"

MIDONET_API_IP="%s"
MIDONET_API_OUTER_IP="%s"

CONTAINER_VETH="${RANDOM}"

NETNS_NAME="docker_${CONTAINER_VETH}_${CONTAINER_ROLE}_${SERVER_NAME}"

CONTAINER_VETH_A="${CONTAINER_VETH}A"
CONTAINER_VETH_B="${CONTAINER_VETH}B"

CONTAINER_ETC_HOSTS="/etc/hosts"

DEFAULT_GW_IFACE="$(ip route show | grep 'default via' | awk -Fdev '{print $2;}' | xargs -n1 echo)"

if [[ "${DEFAULT_GW_IFACE}" == "" ]]; then
    exit 1
fi

DEFAULT_GW_IFACE_IP="$(ip addr show dev ${DEFAULT_GW_IFACE} | grep 'inet ' | awk '{print $2;}' | awk -F'/' '{print $1;}' | xargs -n1 echo | head -n1)"

#
# SNAT the private ips talking to the outside world via this box (we need this for fakeuplink)
#
iptables -t nat --list -n -v | grep -A999999 'Chain POSTROUTING' | grep 'MASQUERADE' | grep "${DEFAULT_GW_IFACE}" | grep "${CONTAINER_IP}" | grep "0.0.0.0" || \
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -j MASQUERADE

#
# do not SNAT if we talk to private networks
# we achieve this by inserting the rule before the masquerade rule that came above
#
for RFC1918 in "10.0.0.0/8" "172.16.0.0/12" "192.168.0.0/16"; do
    iptables -t nat --list -n -v | grep -A999999 'Chain POSTROUTING' | grep 'ACCEPT' | grep "${DEFAULT_GW_IFACE}" | grep "${CONTAINER_IP}" | grep "${RFC1918}" || \
        iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -d "${RFC1918}" -j ACCEPT
done

""" % (
        server,
        container_ip,
        role,
        CIDR(metadata.servers[server]["dockernet"])[1],
        CIDR(metadata.servers[server]["dockernet"]).netmask,
        CIDR(metadata.servers[server]["dockernet"])[0],
        metadata.config["domain"],
        metadata.servers[server]["ip"],
        metadata.config["fip_base"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.servers[metadata.roles["midonet_api"][0]]["ip"]
    ))

            run("""
if [[ "%s" == "True" ]] ; then set -x; fi

SERVER_NAME="%s"
CONTAINER_ROLE="%s"

chmod 0755 /etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}
chmod 0755 /etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}_NAT

"/etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}"
"/etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}_NAT"

""" % (metadata.config["debug"], server, role))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

    puts(green("waiting for other servers to finish their container bootstrapping"))

