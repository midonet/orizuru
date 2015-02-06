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

def cleanup():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(fabric_docker_rm_role_containers_and_cleanup)

    for server in sorted(metadata.servers):
        for role in sorted(metadata.roles):
            if role <> 'all_servers':
                if server in metadata.roles[role]:
                    local("ssh-keygen -f ${HOME}/.ssh/known_hosts -R %s_%s; true" % (server, role))
                    local("ssh-keygen -f ${HOME}/.ssh/known_hosts -R %s.%s; true" % (server, role))

    for role in sorted(metadata.roles):
        if role <> 'all_servers':
            local("ssh-keygen -f ${HOME}/.ssh/known_hosts -R %s; true" % role)

@parallel
@roles('all_servers')
def fabric_docker_rm_role_containers_and_cleanup():
    metadata = Config(os.environ["CONFIGFILE"])

    for container in sorted(metadata.containers):
        if env.host_string == metadata.containers[container]["server"]:
            puts(yellow("destroying container %s on %s" % (container, env.host_string)))
            run("""
SERVER_NAME="%s"
CONTAINER_ROLE="%s"
TEMPLATE_NAME="template_${SERVER_NAME}"

for CONTAINER in $(docker ps | grep "${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}' | grep -v CONTAINER); do
    docker kill $CONTAINER || true;
    docker rm -f $CONTAINER || true;
done

docker images | grep "${TEMPLATE_NAME}" && docker rmi -f "${TEMPLATE_NAME}" || true;

rm -fv /var/run/netns/docker_*_"${SERVER_NAME}"

""" %(env.host_string, container))

    run("""

rm -fv /etc/newrelic/nrsysmond.cfg
rm -fv /etc/apt/sources.list.d/cloudarchive*
rm -fv /etc/apt/sources.list.d/newrelic*
rm -fv /etc/apt/sources.list.d/mido*

# apt-get update 1>/dev/null

""")

    puts(red("destroying all containers"))
    run("""

DOMAIN="%s"

rm -rfv /etc/rc.local.d
mkdir -pv /etc/rc.local.d

rm -rf "/etc/tinc/${DOMAIN}"
mkdir -pv "/etc/tinc/${DOMAIN}/hosts"

pidof tincd | xargs -n1 --no-run-if-empty kill -9

ifconfig dockertinc down || true
brctl delbr dockertinc || true

iptables -t nat --flush

iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

iptables --flush

docker ps --no-trunc -aq | xargs -n1 --no-run-if-empty docker rm -f

docker images | grep '^<none>' | awk '{print $3}' | xargs -n1 --no-run-if-empty docker rmi -f

#
# this will restore the iptables NAT rules for docker build
#
service docker.io restart

rm -fv /etc/newrelic/nrsysmond.cfg

sync

exit 0

""" % metadata.config["domain"])

