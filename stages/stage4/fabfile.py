
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

@parallel
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

                cuisine.file_write("/tmp/Dockerfile_%s_%s" % (role, env.host_string),
"""
#
# sshd
#
# VERSION               0.0.2
#

FROM ubuntu:14.04

#
# this is the original maintainer from the dockerfile we used as a basis for the logic below: Sven Dowideit <SvenDowideit@docker.com>

#
# the whole concept of running and maintaining ubuntu in a container is not the true docker spirit of doing things.  i know.
# we simply abuse docker as a hipsteresque replacement for good old chroots.
# in the future, when OpenStack provides docker images for their stuff we will rely on to those
#

MAINTAINER Alexander Gabert <alexander.gabert@gmail.com>

RUN apt-get update && apt-get install -y openssh-server
RUN mkdir /var/run/sshd
RUN echo "root:%s" | chpasswd
RUN sed -i 's/PermitRootLogin without-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN echo 'LANG="en_US.UTF-8"' | tee /etc/default/locale
RUN locale-gen en_US.UTF-8

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

RUN mkdir -p /root/.ssh
RUN chmod 0755 /root/.ssh

COPY /root/.ssh/authorized_keys /root/.ssh/authorized_keys

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]

""" % os.environ["OS_MIDOKURA_ROOT_PASSWORD"])

                run("""

SERVER_NAME="%s"
CONTAINER_ROLE="%s"
DOCKERFILE="/tmp/Dockerfile_${CONTAINER_ROLE}_${SERVER_NAME}"

cd "$(mktemp -d)"

cp "${DOCKERFILE}" Dockerfile

mkdir -pv root/.ssh

cat /root/.ssh/authorized_keys > root/.ssh/authorized_keys

docker images | grep "template_${CONTAINER_ROLE}_${SERVER_NAME}" || docker build -t "template_${CONTAINER_ROLE}_${SERVER_NAME}" .

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
    iptables -t nat -A POSTROUTING -o "${DEFAULT_GW_IFACE}" -s "${CONTAINER_IP}/32" ! -d "${CONTAINER_NETWORK}/${CONTAINER_NETMASK}" -j MASQUERADE

    screen -d -m -- docker run -h "${CONTAINER_ROLE}_${SERVER_NAME}" --privileged=true -i -t --rm --net="none" --name "${CONTAINER_VETH}_${CONTAINER_ROLE}_${SERVER_NAME}" "template_${CONTAINER_ROLE}_${SERVER_NAME}"

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

    # link the network namespace of the spawned container to ip namespaces
    mkdir -p "/var/run/netns"
    ln -s "/proc/${CONTAINER_PID}/ns/net" "/var/run/netns/${NETNS_NAME}"

    # add the veth pair
    ip link add "${CONTAINER_VETH_A}" type veth peer name "${CONTAINER_VETH_B}"

    # add one side of the pair to our master bridge connected to the tinc overlay
    brctl addif "${DOCKER_BRIDGE}" "${CONTAINER_VETH_A}"

    # up the interface on our side
    ip link set "${CONTAINER_VETH_A}" up

    # punch the other side of the pair into the namespace of the container
    ip link set "${CONTAINER_VETH_B}" netns "${NETNS_NAME}"
    ip netns exec "${NETNS_NAME}" ip link set dev "${CONTAINER_VETH_B}" name eth0
    ip netns exec "${NETNS_NAME}" ip link set eth0 up
    ip netns exec "${NETNS_NAME}" ip addr add "${CONTAINER_IP}/${CONTAINER_NETMASK}" dev eth0
    ip netns exec "${NETNS_NAME}" ip route add default via "${CONTAINER_DEFAULT_GW}"

    # if this is a midonet gateway, add a route to the fip range via this ip
    if [[ "midonet_gateway" == "${CONTAINER_ROLE}" ]]; then
        ip route add 200.200.200.0/24 via "${CONTAINER_IP}"
    fi

    sleep 2
else
    CONTAINER_ID="$(docker ps | grep -v '^CONTAINER' | grep -- "${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}' | head -n1)"
fi

#
# hard-wire the /etc/hosts to the container
#

CONTAINER_HOSTS_PATH="$(docker ps | grep -v ^CONTAINER | grep "^${CONTAINER_ID}" | awk '{print $1;}' | xargs -n1 --no-run-if-empty docker inspect --format "{{ .HostsPath }}")"

cat "${CONTAINER_ETC_HOSTS}" >"${CONTAINER_HOSTS_PATH}"

sync

exit 0

""" % (
        env.host_string,
        container_ip,
        role,
        CIDR(metadata.servers[env.host_string]["dockernet"])[1],
        CIDR(metadata.servers[env.host_string]["dockernet"]).netmask,
        CIDR(metadata.servers[env.host_string]["dockernet"])[0],
        metadata.config["domain"]
    ))

                run("""
set -x

SERVER_NAME="%s"
CONTAINER_ROLE="%s"
chmod 0755 /etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}

/etc/rc.local.d/docker_${CONTAINER_ROLE}_${SERVER_NAME}

""" % (env.host_string, role))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

