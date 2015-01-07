
import os
import sys

from orizuru.config import Config

from fabric.api import *
from fabric.colors import red, green, yellow, white
from fabric.utils import puts

def info():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(red("""
    The current configuration will install a Midonet powered Openstack Cluster using the following information:"""))

    puts(green("""
    container operating system: Ubuntu %s (%s)

    Midonet variant (MEM or OSS): %s

    Midonet version: %s

    Midonet Openstack plugin version: %s

    Openstack version: %s
""" % (
        metadata.config["container_os_release_codename"],
        metadata.config["container_os_version"],
        metadata.config["midonet_repo"],
        metadata.config["midonet_%s_version" % metadata.config["midonet_repo"].lower()],
        metadata.config["midonet_%s_openstack_plugin_version" % metadata.config["midonet_repo"].lower()],
        metadata.config["openstack_release"]
    )))

    puts(white("""
    Containers:
"""))

    for server in sorted(metadata.servers):
        for role in sorted(metadata.config["docker_ips"][server]):
            puts(white("    host: %s physical ip: [%s] >> tinc vpn ip: [%s] >>>> %s >>>>>> docker container ip: [%s]" % (
                server,
                metadata.servers[server]["ip"],
                "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][server]),
                role,
                metadata.config["docker_ips"][server][role]
                )))
        puts("")

    puts("""
press CTRL-C to abort, you have 10 seconds.
""")

    sys.exit(0)
