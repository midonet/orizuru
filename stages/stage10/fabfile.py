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
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

def stage10():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    if 'vtep' in metadata.roles:
        execute(stage10_vtep)
        execute(stage10_container_midonet_cli_vtep)

@roles('vtep')
def stage10_vtep():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    puts(yellow("bumping to utopic"))
    run("""
sed -i 's,%s,utopic,g;' /etc/apt/sources.list
dpkg -l | grep openvswitch-vtep || apt-get update
""" % metadata.config["os_release_codename"])

    # set up ovsdb-server in the vtep sandbox
    #
    cuisine.package_ensure(["openvswitch-switch", "openvswitch-vtep", "vlan"])

    compute_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][env.host_string])

    run("""
IP="%s"
PORT="%s"

#
# do we need to patch the init script?
#
INITSCRIPT="/etc/init.d/openvswitch-vtep"
if [[ "$(grep -- '--remote=ptcp:6262' ${INITSCRIPT})" == "" ]]; then
    TEMPFILE="$(mktemp)"

    grep -B9999 -- '--remote=db:hardware_vtep,Global,managers' ${INITSCRIPT} > ${TEMPFILE}
    echo '        --remote=ptcp:6262 \\' >> ${TEMPFILE}
    grep -A9999 -- '--private-key=/etc/openvswitch/ovsclient-privkey.pem' ${INITSCRIPT} >> ${TEMPFILE}

    mv ${TEMPFILE} ${INITSCRIPT}
fi

chmod 0755 ${INITSCRIPT}

rm /etc/openvswitch/vtep.db
rm /etc/openvswitch/conf.db

cat >/etc/default/openvswitch-vtep<<EOF
ENABLE_OVS_VTEP="true"
EOF

/etc/init.d/openvswitch-switch stop
/etc/init.d/openvswitch-vtep stop

sleep 2

ps axufwwwwwwww | grep -v grep | grep ovs | awk '{print $2;}' | xargs -n1 --no-run-if-empty kill -9

/etc/init.d/openvswitch-switch start
/etc/init.d/openvswitch-vtep start

ovs-vsctl add-br vtep
vtep-ctl add-ps vtep

vtep-ctl set Physical_Switch vtep tunnel_ips=${IP}
vtep-ctl set Physical_Switch vtep management_ips=${IP}

ovs-vsctl add-port vtep ${PORT}
vtep-ctl add-port vtep ${PORT}

ifconfig ${PORT} up

for P in 1 3 5 7 9; do
    ip a | grep veth${P} || ip link add type veth

    ifconfig veth${P} 192.168.77.20${P}/24
    ifconfig veth$(( ${P} - 1 )) up
    ifconfig veth${P} up

    ovs-vsctl add-port vtep veth$(( ${P} - 1 ))
    vtep-ctl add-port vtep veth$(( ${P} - 1 ))
done

screen -d -m -- /usr/share/openvswitch/scripts/ovs-vtep --log-file=/var/log/openvswitch/ovs-vtep.log --pidfile=/var/run/openvswitch/ovs-vtep.pid vtep

exit 0

""" % (compute_ip, metadata.config["vtep_port"]))

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage10_container_midonet_cli_vtep():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure("expect")

    compute_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][metadata.roles["vtep"][0]])

    #
    # set up the connection to the vtep and set up the binding inside midonet-cli
    #
    run("""
IP="%s"
PORT="%s"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "tunnel-zone list name vtep\r" }
expect "midonet> " { send "vtep add management-ip ${IP} management-port 6262 tunnel-zone tzone0\r" }
expect "midonet> " { send "quit\r" }

EOF

sleep 10

ID="$(midonet-cli -e 'list bridge name internal' | awk '{print $2;}')"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "vtep management-ip ${IP} binding add network-id ${ID} physical-port ${PORT} vlan 0\r" }
expect "midonet> " { send "quit\r" }

EOF

""" % (
    compute_ip,
    metadata.config["vtep_port"]
    ))


    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

