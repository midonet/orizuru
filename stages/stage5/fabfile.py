
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

@parallel
@roles('all_containers')
def configure_stage5():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Configure(metadata).configure()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@parallel
@roles('all_containers')
def install_stage5():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Install(metadata).install()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@parallel
@roles('all_servers')
def stage5_ping_containers():
    metadata = Config(os.environ["CONFIGFILE"])

    for role in sorted(metadata.roles):
        if role <> 'all_servers':
            if env.host_string in metadata.roles[role]:

                container_ip = metadata.config["docker_ips"][env.host_string][role]

                puts(yellow("pinging %s.%s.%s (%s)" % (role, env.host_string, metadata.config["domain"], container_ip)))
                run("ping -c1 %s" % container_ip)

