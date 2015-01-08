#!/usr/bin/python -Werror

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
import os.path
import yaml

from fabric.api import *

from netaddr import IPNetwork as CIDR

import cuisine

from fabric.utils import puts
from fabric.colors import green, yellow, red

class Orizuru(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def orizuru(self):
        self.zonefile()
        self.hostsfile()
        self.sshconfig()
        self.pingcheck()
        self.connectcheck()

    def pingcheck(self):
        domain = self._metadata.config["domain"]
        for server in sorted(self._metadata.servers):
            ip = self._metadata.servers[server]["ip"]
            puts(yellow("pinging %s.%s (%s)" % (server,domain,ip)))

            local("ping -c1 -W20 %s" % ip)

    def connectcheck(self):
        run("echo OK OK OK OK")

    def zonefile(self):
        for server in sorted(self._metadata.servers):
            puts("%s IN A %s" % (server, self._metadata.servers[server]["ip"]))

            puts("%s.tinc IN A %s.%s" % (server,
                self._metadata.config["vpn_base"],
                self._metadata.config["idx"][server]))

            puts("%s.dockernet IN A %s" % (server,
                CIDR(self._metadata.servers[server]["dockernet"])[1]))

            for role in sorted(self._metadata.roles):
                if role <> 'all_servers':
                    if server in self._metadata.roles[role]:
                        container_ip = self._metadata.config["docker_ips"][server][role]
                        puts("%s.%s.dockernet IN A %s" % (role, server, container_ip))

        for container in sorted(self._metadata.containers):
            puts("%s IN A %s" % (container, self._metadata.containers[container]["ip"]))

    def hostsfile(self):
        for server in sorted(self._metadata.servers):
            puts("%s %s.%s" % (self._metadata.servers[server]["ip"],
                server, self._metadata.config["domain"]))

            for role in sorted(self._metadata.roles):
                if role <> 'all_servers':
                    if server in self._metadata.roles[role]:
                        container_ip = self._metadata.config["docker_ips"][server][role]

                        puts("%s %s_%s.%s %s_%s" % (
                            container_ip,
                            role,
                            server,
                            self._metadata.config["domain"],
                            role,
                            server
                            ))

                        puts("%s %s.%s" % (
                            container_ip,
                            role,
                            server
                            ))

            puts("%s.%s %s.tinc.%s %s" % (self._metadata.config["vpn_base"],
                self._metadata.config["idx"][server], server,
                self._metadata.config["domain"], server))

            puts("%s %s.dockernet.%s" % (CIDR(self._metadata.servers[server]["dockernet"])[1],
                server, self._metadata.config["domain"]))

            for role in sorted(self._metadata.roles):
                if role <> 'all_servers':
                    if server in self._metadata.roles[role]:
                        container_ip = self._metadata.config["docker_ips"][server][role]
                        puts("%s %s.%s.dockernet.%s" % (container_ip, role, server,
                            self._metadata.config["domain"]))

    def sshconfig(self):
        for server in sorted(self._metadata.servers):
            puts("""

Host %s
    User root
    ServerAliveInterval 2
    KeepAlive yes
    ConnectTimeout 30
    TCPKeepAlive yes
    Hostname %s

Host %s.%s
    User root
    ServerAliveInterval 2
    KeepAlive yes
    ConnectTimeout 30
    TCPKeepAlive yes
    Hostname %s

""" % ( server,
        self._metadata.servers[server]["ip"],
        server,
        self._metadata.config["domain"],
        self._metadata.servers[server]["ip"]))

            for role in sorted(self._metadata.roles):
                if role <> 'all_servers':
                    if server in self._metadata.roles[role]:
                        container_ip = self._metadata.config["docker_ips"][server][role]
                        puts("""

Host %s.%s
    User root
    ServerAliveInterval 2
    KeepAlive yes
    ConnectTimeout 30
    TCPKeepAlive yes
    ProxyCommand /usr/bin/ssh -F%s -W%s:22 root@%s

Host %s_%s
    User root
    ServerAliveInterval 2
    KeepAlive yes
    ConnectTimeout 30
    TCPKeepAlive yes
    ProxyCommand /usr/bin/ssh -F%s -W%s:22 root@%s

""" % (
        role,
        server,
        "%s/.ssh/config" % os.environ["TMPDIR"],
        container_ip,
        self._metadata.servers[server]["ip"],
        role,
        server,
        "%s/.ssh/config" % os.environ["TMPDIR"],
        container_ip,
        self._metadata.servers[server]["ip"]
    ))

