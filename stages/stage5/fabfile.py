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

from orizuru.operations import Configure
from orizuru.operations import Install

from orizuru.config import Config

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

from netaddr import IPNetwork as CIDR

def stage5pingcheck():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(stage5_ping_containers)

def stage5():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    puts(yellow("executing stage5 configure"))
    execute(configure_stage5)

    puts(yellow("executing stage5 install"))
    execute(install_stage5)

@parallel(pool_size=5)
@roles('all_containers')
def configure_stage5():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Configure(metadata).configure()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@parallel(pool_size=5)
@roles('all_containers')
def install_stage5():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Install(metadata).install()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@parallel(pool_size=5)
@roles('all_servers')
def stage5_ping_containers():
    metadata = Config(os.environ["CONFIGFILE"])

    for container in sorted(metadata.containers):
        container_ip = metadata.containers[container]["ip"]

        run("""
IP="%s"

for i in $(seq 1 120); do
    ping -c1 "${IP}" && break
    sleep 1
done

ping -c1 "${IP}"

""" % container_ip)

