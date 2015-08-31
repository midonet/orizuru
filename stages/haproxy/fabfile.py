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
def haproxy():

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    haproxy_default_config()

    restart = 0

    if env.host_string in metadata.roles['openstack_keystone']:
        restart = 1
        for port in [5000, 35357]:
            haproxy_into_container(port, port, 'container_openstack_keystone')

    if env.host_string in metadata.roles['openstack_controller']:
        restart = 1
        for port in [6080, 8774]:
            haproxy_into_container(port, port, 'container_openstack_controller')

    if env.host_string in metadata.roles['openstack_glance']:
        restart = 1
        haproxy_into_container(9292, 9292, 'container_openstack_glance')

    if env.host_string in metadata.roles['openstack_neutron']:
        restart = 1
        haproxy_into_container(9696, 9696, 'container_openstack_neutron')

    if env.host_string in metadata.roles['midonet_api']:
        restart = 1
        for port in [8081, 8459, 8460, 8088]:
            haproxy_into_container(port, port, 'container_midonet_api')

    if env.host_string in metadata.roles['openstack_horizon']:
        restart = 1
        haproxy_into_container(80, 80, 'container_openstack_horizon')

    if env.host_string in metadata.roles['midonet_manager']:
        restart = 1
        haproxy_into_container(81, 80, 'container_midonet_manager')

    if restart == 1:
        run("""
service haproxy restart

ps axufwwwwwwww | grep -v grep | grep haproxy

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

def haproxy_into_container(src_port, dst_port, container_type):
    #
    # create the frontend and backend config for this src port
    #
    run("""
TYPE="%s"
PORT="%s"

cat >>/etc/haproxy/haproxy.cfg<<EOF
#
# begin of configuration for ${TYPE}:${PORT}
#
frontend ${TYPE}_${PORT}_frontend
    bind *:${PORT}
    mode http
    default_backend ${TYPE}_${PORT}_backend
    timeout http-keep-alive 500
    timeout http-request 50000

backend ${TYPE}_${PORT}_backend
    mode http
    balance roundrobin
EOF
""" % (container_type, src_port))

    #
    # set the backend servers for this port
    #
    idx = 0

    for container_name in metadata.roles[container_type]:
        container = metadata.containers[container_name]
        container_ip =  metadata.containers[container_name]["ip"]

        run("""
CONTAINER_IP="%s"
TYPE="%s"
PORT="%s"
IDX="%s"

cat >>/etc/haproxy/haproxy.cfg<<EOF
    server ${TYPE}_${PORT}_server${IDX} ${CONTAINER_IP}:${PORT} check
EOF

""" % (container_ip, container_type, dst_port, idx))

        idx = idx + 1

    #
    # end of config for this port
    #
    run("""
TYPE="%s"
PORT="%s"

cat >>/etc/haproxy/haproxy.cfg<<EOF

#
# end of configuration for ${TYPE}:${PORT}
#

EOF
""" % (container_type, src_port))

def haproxy_default_config():
    cuisine.package_ensure("haproxy")

    run("""

cat >/etc/default/haproxy<<EOF
ENABLED=1
#EXTRAOPTS="-de -m 16"
EOF

cat >/etc/haproxy/haproxy.cfg<<EOF
global
        log /dev/log    local0
        log /dev/log    local1 notice
        chroot /var/lib/haproxy
        user haproxy
        group haproxy
        daemon

defaults
        retries 3
        maxconn 5000
        log     global
        mode    http
        option  httplog
        option  dontlognull
        contimeout 50000
        clitimeout 500000
        srvtimeout 500000
        errorfile 400 /etc/haproxy/errors/400.http
        errorfile 403 /etc/haproxy/errors/403.http
        errorfile 408 /etc/haproxy/errors/408.http
        errorfile 500 /etc/haproxy/errors/500.http
        errorfile 502 /etc/haproxy/errors/502.http
        errorfile 503 /etc/haproxy/errors/503.http
        errorfile 504 /etc/haproxy/errors/504.http

EOF
""")

