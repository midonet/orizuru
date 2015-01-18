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

def stage4():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(docker_containers_for_roles_stage4)

@roles('all_servers')
def docker_containers_for_roles_stage4():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    for role in sorted(metadata.roles):
        if role <> 'all_servers':
            if env.host_string in metadata.roles[role]:
                container_ip = metadata.config["docker_ips"][env.host_string][role]

                puts(green("creating/configuring container on server %s with ip %s for role %s" % (
                    env.host_string, container_ip, role)))

                dockerfile = "/tmp/Dockerfile_orizuru_%s" % env.host_string

                cuisine.file_write(dockerfile,
"""
#
# orizuru base image for all Midonet and Openstack services
#
# VERSION               0.1.0
#

FROM %s:%s

MAINTAINER Alexander Gabert <alexander@midokura.com>

RUN echo "root:%s" | chpasswd

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

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server puppet screen %s 1>/dev/null
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config

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
        os.environ["OS_MIDOKURA_ROOT_PASSWORD"],
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

docker images | grep "template_${SERVER_NAME}" || docker build --no-cache=true -t "template_${SERVER_NAME}" .

mkdir -pv /etc/rc.local.d

""" % (
        env.host_string,
        role
     ))

                cuisine.file_write("/etc/rc.local.d/docker_%s_%s" % (role, env.host_string),
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

if [[ "$(docker ps | grep -v '^CONTAINER' | grep -- "${CONTAINER_ROLE}_${SERVER_NAME}")" == "" ]]; then
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

    #
    # set up networking in the container namespace
    #
    ip link set "${CONTAINER_VETH_B}" netns "${NETNS_NAME}"
    ip netns exec "${NETNS_NAME}" ip link set dev "${CONTAINER_VETH_B}" name eth0
    ip netns exec "${NETNS_NAME}" ip link set eth0 up
    ip netns exec "${NETNS_NAME}" ip addr add "${CONTAINER_IP}/${CONTAINER_NETMASK}" dev eth0
    ip netns exec "${NETNS_NAME}" ip route add default via "${CONTAINER_DEFAULT_GW}"

else
    CONTAINER_ID="$(docker ps | grep -v '^CONTAINER' | grep -- "${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}' | head -n1)"
fi

#
# the /etc/hosts could have been updated in the meantime, add it to the container even when its already running
#
CONTAINER_HOSTS_PATH="$(docker ps | grep -v ^CONTAINER | grep "^${CONTAINER_ID}" | awk '{print $1;}' | xargs -n1 --no-run-if-empty docker inspect --format "{{ .HostsPath }}")"
cat "${CONTAINER_ETC_HOSTS}" >"${CONTAINER_HOSTS_PATH}"

""" % (
        env.host_string,
        container_ip,
        role,
        CIDR(metadata.servers[env.host_string]["dockernet"])[1],
        CIDR(metadata.servers[env.host_string]["dockernet"]).netmask,
        CIDR(metadata.servers[env.host_string]["dockernet"])[0],
        metadata.config["domain"],
        metadata.servers[env.host_string]["ip"],
        metadata.config["fip_base"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.servers[metadata.roles["midonet_api"][0]]["ip"]
    ))

                cuisine.file_write("/etc/rc.local.d/docker_%s_%s_NAT" % (role, env.host_string),
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
# SNAT the container talking to the outside world
#
iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -j MASQUERADE

iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -d "10.0.0.0/8" -j ACCEPT
iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -d "172.16.0.0/12" -j ACCEPT
iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" -d "192.168.0.0/16" -j ACCEPT

#
# midonet gateway
#
if [[ "midonet_gateway" == "${CONTAINER_ROLE}" ]]; then

    #
    # SNAT the dummy FIP range traffic that is going to the internet
    #
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -j MASQUERADE

    #
    # but do not SNAT for RFC1918 networks
    #
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -d "10.0.0.0/8" -j ACCEPT
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -d "172.16.0.0/12" -j ACCEPT
    iptables -t nat -I POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${FIP_BASE}.0/24" -d "192.168.0.0/16" -j ACCEPT

    #
    # route incoming packets to the FIP network through the midonet container ip, it will know what to do
    #
    ip route add "${FIP_BASE}.0/24" via "${CONTAINER_IP}" || true

fi

#
# openstack controller VNC proxy
#
if [[ "openstack_controller" == "${CONTAINER_ROLE}" ]]; then
    for IP in "${SERVER_IP}" "${DEFAULT_GW_IFACE_IP}"; do
        iptables -t nat -I PREROUTING -i "${DEFAULT_GW_IFACE}" -p tcp -d "${IP}" --dport 6080 -j DNAT --to "${CONTAINER_IP}:6080"
        iptables -I FORWARD -p tcp -d "${IP}" --dport 6080 -j ACCEPT
    done
fi

#
# horizon dashboard
#
if [[ "openstack_horizon" == "${CONTAINER_ROLE}" ]]; then
    for IP in "${SERVER_IP}" "${DEFAULT_GW_IFACE_IP}"; do
        iptables -t nat -I PREROUTING -i "${DEFAULT_GW_IFACE}" -p tcp -d "${IP}" --dport 80 -j DNAT --to "${CONTAINER_IP}:80"
        iptables -I FORWARD -p tcp -d "${IP}" --dport 80 -j ACCEPT
    done
fi

#
# midonet manager
#
if [[ "midonet_manager" == "${CONTAINER_ROLE}" ]]; then
    for IP in "${SERVER_IP}" "${DEFAULT_GW_IFACE_IP}"; do
        iptables -t nat -I PREROUTING -i "${DEFAULT_GW_IFACE}" -p tcp -d "${IP}" --dport 81 -j DNAT --to "${CONTAINER_IP}:80"
        iptables -I FORWARD -p tcp -d "${IP}" --dport 80 -j ACCEPT
    done
fi

#
# midonet api
#
if [[ "midonet_api" == "${CONTAINER_ROLE}" ]]; then
    for IP in "${MIDONET_API_OUTER_IP}" "${DEFAULT_GW_IFACE_IP}"; do
        iptables -t nat -I PREROUTING -i "${DEFAULT_GW_IFACE}" -p tcp -d "${IP}" --dport 8080 -j DNAT --to "${CONTAINER_IP}:8080"
        iptables -I FORWARD -p tcp -d "${IP}" --dport 8080 -j ACCEPT
    done
else
    iptables -t nat -I PREROUTING -i dockertinc -p tcp -d "${MIDONET_API_OUTER_IP}" --dport 8080 -j DNAT --to "${MIDONET_API_IP}:8080"
    iptables -I FORWARD -p tcp -d "${MIDONET_API_IP}" --dport 8080 -j ACCEPT
fi

""" % (
        env.host_string,
        container_ip,
        role,
        CIDR(metadata.servers[env.host_string]["dockernet"])[1],
        CIDR(metadata.servers[env.host_string]["dockernet"]).netmask,
        CIDR(metadata.servers[env.host_string]["dockernet"])[0],
        metadata.config["domain"],
        metadata.servers[env.host_string]["ip"],
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

""" % (metadata.config["debug"], env.host_string, role))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

