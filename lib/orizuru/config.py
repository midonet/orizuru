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

from fabric.utils import puts

from netaddr import IPNetwork as CIDR

import sys

class Config(object):

    def __init__(self, configfile):
        self._config = self.__set_config(configfile)
        self._roles = self.__set_roles(configfile)
        self._servers = self.__set_servers(configfile)
        self._containers = self.__set_containers(configfile)
        self._services = self.__set_services()

        self.__prepare()
        self.__setup_fabric_env()

        #self.__dumpconfig()

    def __dumpconfig(self):
        for role in sorted(self._roles):
            sys.stderr.write("role: %s\n" % role)
        sys.stderr.write("\n")

        for server in sorted(self._servers):
            sys.stderr.write("server: %s\n" % server)
            for role in sorted(self._roles):
                if server in self._roles[role]:
                    sys.stderr.write("server role: %s\n" % role)
            sys.stderr.write("\n")

        for container in sorted(self._containers):
            sys.stderr.write("container: %s\n" % container)
            for role in sorted(self._roles):
                if container in self._roles[role]:
                    sys.stderr.write("container role: %s\n" % role)
            sys.stderr.write("\n")

    def __setup_fabric_env(self):
        env.use_ssh_config = True

        env.port = 22
        env.connection_attempts = 5
        env.timeout = 5

        env.parallel = self._config["parallel"]

        env.roledefs = self._roles

    @classmethod
    def __slurp(cls, yamlfile, section_name):
        with open(yamlfile, 'r') as yaml_file:
            yamldata = yaml.load(yaml_file.read())

        if yamldata and section_name in yamldata:
            return yamldata[section_name]
        else:
            return {}

    def __set_config(self, yamlfile):
        return self.__slurp(yamlfile, 'config')

    def __set_roles(self, yamlfile):
        return self.__slurp(yamlfile, 'roles')

    def __set_servers(self, yamlfile):
        return self.__slurp(yamlfile, 'servers')

    def __set_containers(self, yamlfile):
        return self.__slurp(yamlfile, 'containers')

    @classmethod
    def __set_services(cls):
        services = {}

        services["keystone"] = {}
        services["keystone"]["publicurl"] = "5000/v2.0"
        services["keystone"]["internalurl"] = "5000/v2.0"
        services["keystone"]["adminurl"] = "35357/v2.0"
        services["keystone"]["type"] = "identity"
        services["keystone"]["description"] = "OpenStack Identity"

        services["glance"] = {}
        services["glance"]["publicurl"] = "9292"
        services["glance"]["internalurl"] = "9292"
        services["glance"]["adminurl"] = "9292"
        services["glance"]["type"] = "image"
        services["glance"]["description"] = "OpenStack Image Service"

        services["nova"] = {}
        services["nova"]["publicurl"] = "8774/v2/%(tenant_id)s"
        services["nova"]["internalurl"] = "8774/v2/%(tenant_id)s"
        services["nova"]["adminurl"] = "8774/v2/%(tenant_id)s"
        services["nova"]["type"] = "compute"
        services["nova"]["description"] = "OpenStack Compute"

        services["neutron"] = {}
        services["neutron"]["publicurl"] = "9696"
        services["neutron"]["internalurl"] = "9696"
        services["neutron"]["adminurl"] = "9696"
        services["neutron"]["type"] = "network"
        services["neutron"]["description"] = "OpenStack Networking"

        services["midonet"] = {}
        services["midonet"]["publicurl"] = "8080"
        services["midonet"]["internalurl"] = "8080"
        services["midonet"]["adminurl"] = "8080"
        services["midonet"]["type"] = "midonet"
        services["midonet"]["description"] = "MidoNet API Service"

        return services

    def __prepare(self):
        self.__prepare_config()
        self.__prepare_roles()
        self.__prepare_servers()
        self.__prepare_config_idx()
        self.__prepare_config_docker_ips()
        self.__prepare_containers()

    def __prepare_containers(self):
        self._roles['all_containers'] = []

        for server in sorted(self._servers):
            for role in sorted(self._roles):
                if role <> 'all_servers':
                    if not role.startswith("physical_"):
                        if server in self._roles[role]:
                            container_ip = self._config["docker_ips"][server][role]
                            container_id = "%s_%s" % (role, server)
                            container_role = "container_%s" % role

                            self._containers[container_id] = {}

                            self._containers[container_id]["ip"] = container_ip
                            self._containers[container_id]["server"] = server
                            self._containers[container_id]["role"] = role

                            if container_id not in self._roles['all_containers']:
                                self._roles['all_containers'].append(container_id)

                            if container_role not in self._roles:
                                self._roles[container_role] = []

                            if container_id not in self._roles[container_role]:
                                self._roles[container_role].append(container_id)

    def __prepare_config_idx(self):
        idx = 1
        self._config["idx"] = {}
        for server in sorted(self._servers):
            self._config["idx"][server] = idx
            idx = idx + 1

    def __prepare_config_docker_ips(self):
        self._config["docker_ips"] = {}
        for server in sorted(self._servers):
            idx = 10
            dockernet = CIDR(self._servers[server]["dockernet"])
            self._config["docker_ips"][server] = {}
            for role in sorted(self._roles):
                if role <> 'all_servers':
                    if server in self._roles[role]:
                        self._config["docker_ips"][server][role] = dockernet[idx]
                        idx = idx + 1

    def __prepare_config(self):
        common1 = 'htop vim screen atop tcpdump nload make git dstat tinc bridge-utils openjdk-7-jre-headless'
        common2 = 'traceroute mosh python-mysqldb mysql-client-core-5.5 apparmor docker.io python git puppet minicom strace'

        common_packages = "%s %s" % (common1, common2)

        if 'additional_packages' in self._config:
            common_packages = "%s %s" % (common_packages, self._config['additional_packages'])

        defaults = {}

        #
        # if you change this you must make sure that this ip is reachable and routable also from the networks of the containers
        # that means you must provide routing to the container networks yourself.
        # if you leave this at 8.8.8.8 (or any other non RFC1918 IP) you have to do nothing because it will be SNATed from the hosts to the ip if it is a public one
        #
        defaults["nameserver"] = "8.8.8.8"

        defaults["parallel"] = True

        defaults["archive_country"] = "us"
        defaults["apt-cacher"] = "http:/"

        defaults["constrictor"] = "/usr/share/orizuru/bin/constrictor.py"

        defaults["common_packages"] = common_packages

        defaults["midonet_puppet_modules"] = "http://github.com/midonet/orizuru"
        defaults["midonet_puppet_modules_branch"] = "master"

        defaults["region"] = "regionOne" # RHEL uses RegionOne

        # these two values are used for launching the respective ubuntu base image in the Dockerfile for the containers
        defaults["container_os"] = "ubuntu"
        defaults["container_os_version"] = "14.04"

        # used for setting up sources.list on the containers
        defaults["container_os_release_codename"] = "trusty"

        # used for setting up sources.list on the host
        defaults["os_release_codename"] = "trusty"

        defaults["fip_base"] = "200.200.200"

        defaults["mtu_physical"] = 1500
        defaults["mtu_mezzanine"] = 1500
        defaults["mtu_container"] = 1500

        for overloading_key in defaults:
            if overloading_key not in self._config:
                overloading_value = defaults[overloading_key]
                self._config[overloading_key] = overloading_value

    def __prepare_roles(self):
        self._roles['all_servers'] = []

        for server in self._servers:
            if server not in self._roles['all_servers']:
                self._roles['all_servers'].append(server)

    def __prepare_servers(self):
        for role in self._roles:
            for server in self._roles[role]:
                if server not in self._servers:
                    self._servers[server] = {}
                if 'roles' not in self._servers[server]:
                    self._servers[server]['roles'] = []
                if role not in self._servers[server]['roles']:
                    self._servers[server]['roles'].append(role)

        for server in self._servers:
            for global_config_key in self._config:
                if global_config_key not in self._servers[server]:
                    value = self._config[global_config_key]
                    self._servers[server][global_config_key] = value

    @property
    def config(self):
        return self._config

    @property
    def roles(self):
        return self._roles

    @property
    def servers(self):
        return self._servers

    @property
    def containers(self):
        return self._containers

    @property
    def services(self):
        return self._services

