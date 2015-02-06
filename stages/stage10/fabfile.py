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

    if 'midonet_vtep_sandbox' in metadata.roles:
        execute(stage10_container_midonet_vtep_sandbox)
        execute(stage10_container_midonet_vtep)

@roles('container_midonet_vtep_sandbox')
def stage10_container_midonet_vtep_sandbox():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    # set up ovsdb-server in the vtep sandbox
    #
    cuisine.package_ensure(["openvswitch-switch", "openvswitch-vtep", "vlan"])

    run("""
ip netns | xargs -n1 --no-run-if-empty ip netns del

rm /etc/openvswitch/vtep.db
rm /etc/openvswitch/conf.db

/etc/init.d/openvswitch-switch restart
/etc/init.d/openvswitch-vtep restart

""")

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage10_container_midonet_vtep():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    #
    # set up the connection to the vtep in midonet-cli
    #

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

