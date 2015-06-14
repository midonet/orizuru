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

import sys

import os
import os.path
import yaml

from fabric.api import *

from netaddr import IPNetwork as CIDR

from fabric.colors import yellow
from fabric.utils import puts

import cuisine

class Check(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def check_broken_cuisine(self):
        run("rm -f /tmp/check_broken_cuisine.txt")
        cuisine.file_write("/tmp/check_broken_cuisine.txt", "WORKING")
        run("grep WORKING /tmp/check_broken_cuisine.txt")

class Configure(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def configure(self):
        self.localegen()
        self.name_resolution()
        self.os_release()
        self.newrelic()
        self.datastax()
        self.midonet()

    def localegen(self):
        if env.host_string in self._metadata.roles["all_containers"]:
            run("locale-gen de_DE.UTF-8")

    def name_resolution(self):
        if env.host_string not in self._metadata.roles["all_containers"]:
            run("hostname %s" % env.host_string.split(".")[0])
            cuisine.file_write("/etc/hostname", env.host_string.split(".")[0])

            cuisine.file_write("/etc/resolv.conf", """
nameserver %s
options single-request
""" % self._metadata.config["nameserver"])

            if "local_ip_behind_nat" in self._metadata.servers[env.host_string]:
                local_ip = self._metadata.servers[env.host_string]["local_ip_behind_nat"]
            else:
                local_ip = self._metadata.servers[env.host_string]["ip"]

            cuisine.file_write("/etc/hosts", """
127.0.0.1 localhost.localdomain localhost

::1     ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts

%s %s.%s # %s

%s

""" % (
        local_ip,
        env.host_string,
        self._metadata.config["domain"],
        env.host_string.split(".")[0],
        open("%s/etc/hosts" % os.environ["TMPDIR"]).read()
    ))

    @classmethod
    def repokey(cls, url):
        run("""
URL="%s"

wget -SO- "${URL}" | apt-key add -
""" % url)

    def newrelic(self):
        cuisine.file_write("/etc/apt/sources.list.d/newrelic.list", """
deb [arch=amd64] http://apt.newrelic.com/debian/ newrelic non-free
""")
        self.repokey("https://download.newrelic.com/548C16BF.gpg")

    def datastax(self):
        if env.host_string in self._metadata.containers:
            cuisine.file_write("/etc/apt/sources.list.d/datastax.list", """
deb [arch=amd64] http://debian.datastax.com/community stable main
""")
            self.repokey("http://debian.datastax.com/debian/repo_key")

    def midonet(self):
        # Install(self._metadata).apt_get_update()

        if "OS_MIDOKURA_REPOSITORY_USER" in os.environ:
            username = os.environ["OS_MIDOKURA_REPOSITORY_USER"]
        else:
            username = ""

        if "OS_MIDOKURA_REPOSITORY_PASS" in os.environ:
            password = os.environ["OS_MIDOKURA_REPOSITORY_PASS"]
        else:
            password = ""

        if "midonet_repo" in self._metadata.config:
            repo_flavor = self._metadata.config["midonet_repo"]
        else:
            repo_flavor = "OSS"

        if "midonet_manager" in self._metadata.roles:
            if env.host_string in self._metadata.roles["container_midonet_manager"]:
                if username <> "":
                    if password <> "":
                        repo_flavor = "MEM"

        run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

USERNAME="%s"
PASSWORD="%s"

MIDONET_VERSION="%s"
OPENSTACK_PLUGIN_VERSION="%s"

REPO_FLAVOR="%s"

rm -fv -- /etc/apt/sources.list.d/midonet*
rm -fv -- /etc/apt/sources.list.d/midokura*

if [[ "${REPO_FLAVOR}" == "MEM" ]]; then
    FILENAME="/etc/apt/sources.list.d/midokura.list"

    wget -SO- "http://${USERNAME}:${PASSWORD}@apt.midokura.com/packages.midokura.key" | apt-key add -

    cat>"${FILENAME}"<<EOF
#
# MEM midolman
#

deb [arch=amd64] http://${USERNAME}:${PASSWORD}@apt.midokura.com/midonet/v${MIDONET_VERSION}/stable precise main non-free

#
# MEM midonet neutron plugin
#

deb [arch=amd64] http://${USERNAME}:${PASSWORD}@apt.midokura.com/openstack/${OPENSTACK_PLUGIN_VERSION}/stable precise main

EOF
fi

if [[ "${REPO_FLAVOR}" == "OSS" ]]; then
    FILENAME="/etc/apt/sources.list.d/midonet.list"

    wget -SO- http://repo.midonet.org/packages.midokura.key | apt-key add -

    cat>"${FILENAME}"<<EOF

# OSS MidoNet
deb http://repo.midonet.org/midonet/v${MIDONET_VERSION} stable main

# OSS MidoNet OpenStack Integration
deb http://repo.midonet.org/openstack-${OPENSTACK_PLUGIN_VERSION} stable main

# OSS MidoNet 3rd Party Tools and Libraries
deb http://repo.midonet.org/misc stable main

EOF
fi

""" % (
        self._metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        username,
        password,
        self._metadata.config["midonet_%s_version" % repo_flavor.lower()],
        self._metadata.config["midonet_%s_openstack_plugin_version" % repo_flavor.lower()],
        repo_flavor.upper()
    ))

    def os_release(self):
        if env.host_string in self._metadata.containers:
            self.__lib_orizuru_operations_ubuntu_repo(self._metadata.config["container_os_release_codename"])
        else:
            self.__lib_orizuru_operations_ubuntu_repo(self._metadata.config["os_release_codename"])

    def __lib_orizuru_operations_ubuntu_repo(self, codename):

        archive_country = self._metadata.config["archive_country"]

        apt_cacher = self._metadata.config["apt-cacher"]

        run("""
if [[ "%s" == "True" ]] ; then set -x; fi

XC="%s" # ubuntu release
XD="%s" # country code
XX="%s" # apt-cacher

cat>/etc/apt/sources.list<<EOF
#
# autogenerated file - do not modify - modify %s instead
#
EOF

for TYPE in 'deb' 'deb-src'; do
    for realm in "main restricted" "universe" "multiverse"; do
        echo "${TYPE} ${XX}/${XD}.archive.ubuntu.com/ubuntu/ ${XC} ${realm}"
        echo "${TYPE} ${XX}/${XD}.archive.ubuntu.com/ubuntu/ ${XC}-updates ${realm}"
        echo "${TYPE} ${XX}/security.archive.ubuntu.com/ubuntu/ ${XC}-security ${realm}"
    done

    echo "${TYPE} ${XX}/${XD}.archive.ubuntu.com/ubuntu/ ${XC}-backports main restricted universe multiverse"

done | tee -a /etc/apt/sources.list

""" % (self._metadata.config["debug"], codename, archive_country, apt_cacher, sys._getframe().f_code.co_name))

class Install(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def install(self):
        self.rsyslog()
        self.screen()
        self.login_stuff()
        self.apt_get_update()
        self.common_packages()
        self.newrelic()
        self.rp_filter()
        self.cloud_repository()
        self.apt_get_update()
        self.ntp()
        self.dist_upgrade()
        self.constrictor()
        self.kmod("openvswitch")
        self.kmod("nbd")
        self.kmod("kvm")
        self.kmod("vhost_net")
        self.lldpd()

    def lldpd(self):
        cuisine.package_ensure("lldpd")

    def kmod(self, module_name):
        if env.host_string not in self._metadata.roles["all_containers"]:
            run("modprobe %s || true" % module_name)

    def constrictor(self):
        constrictor_bin = self._metadata.config["constrictor"]

        run("mkdir -pv $(dirname %s)" % constrictor_bin)

        cuisine.file_write(constrictor_bin, """#!/usr/bin/python -Werror
import sys
import ConfigParser

def add_section(configuration, section):
    if not(section == 'DEFAULT' or configuration.has_section(section)):
        configuration.add_section(section)

def set_option(configfile, configuration, section, option, value):
    configuration.set(section, option, value)

    cfgfile = open(configfile, "w")
    configuration.write(cfgfile)
    cfgfile.close()

def get_option(configuration, section, option):
    print configuration.get(section, option)

def handle_command(args):
    command = args[1]
    configfile = args[2]
    section = args[3]
    option = args[4]

    configuration = ConfigParser.RawConfigParser()
    configuration.read(configfile)

    if command == 'set':
        value = args[5]
        add_section(configuration, section)
        set_option(configfile, configuration, section, option, value)

    if command == 'get':
        get_option(configuration, section, option)

    return 0

if __name__ == "__main__":
    sys.exit(handle_command(sys.argv))

""")

        run("chmod 0755 %s" % constrictor_bin)

    def screen(self):
        screenrc_string = "%s.%s" % (env.host_string, self._metadata.config["domain"])

        cuisine.package_ensure("screen")

        run("""
mkdir -pv /var/run/screen
chmod 0755 /usr/bin/screen
chmod 0777 /var/run/screen
""")

        cuisine.file_write("/root/.screenrc", """
hardstatus alwayslastline

hardstatus string '%%{= kG} %s [%%= %%{= kw}%%?%%-Lw%%?%%{r}[%%{W}%%n*%%f %%t%%?{%%u}%%?%%{r}]%%{w}%%?%%+Lw%%?%%?%%= %%{g}] %%{W}%%{g}%%{.w} screen %%{.c} [%%H]'

""" % screenrc_string)

    @classmethod
    def login_stuff(cls):
        run("""
chmod 0755 /usr/bin/sudo
chmod u+s /usr/bin/sudo
""")

    @classmethod
    def apt_get_update(cls):
        puts(yellow("updating repositories, this may take a long time."))

        run("""
#
# Round 1: try to apt-get update without purging the cache
#
apt-get update 1>/dev/null

#
# Round 2: clean cache and update again
#
if [[ ! "${?}" == "0" ]]; then
    rm -rf /var/lib/apt/lists/*
    rm -f /etc/apt/apt.conf
    sync
    apt-get update 2>&1
fi

""")

    def common_packages(self):
        cuisine.package_ensure(self._metadata.config["common_packages"])

    def rsyslog(self):

        cuisine.package_ensure("rsyslog")

        controller_name = self._metadata.roles["openstack_controller"][0]
        controller_ip_suffix = self._metadata.config["idx"][controller_name]
        controller_ip = "%s.%s" % (self._metadata.config["vpn_base"], controller_ip_suffix)

        if env.host_string <> controller_name:
            cuisine.file_write("/etc/rsyslog.conf", """

$KLogPermitNonKernelFacility on
$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat
$RepeatedMsgReduction on
$FileOwner syslog
$FileGroup adm
$FileCreateMode 0640
$DirCreateMode 0755
$Umask 0022
$PrivDropToUser syslog
$PrivDropToGroup syslog
$WorkDirectory /var/spool/rsyslog
$IncludeConfig /etc/rsyslog.d/*.conf
$ModLoad imuxsock
$ModLoad imklog

*.* @%s:514
*.* @@%s:514
""" % (controller_ip, controller_ip))

        else:
            cuisine.file_write("/etc/rsyslog.conf", """

$ModLoad imuxsock # provides support for local system logging
$ModLoad imklog   # provides kernel logging support

$KLogPermitNonKernelFacility on

$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat

$RepeatedMsgReduction on

$FileOwner syslog
$FileGroup adm
$FileCreateMode 0640
$DirCreateMode 0755
$Umask 0022
$PrivDropToUser syslog
$PrivDropToGroup syslog

$WorkDirectory /var/spool/rsyslog

$IncludeConfig /etc/rsyslog.d/*.conf

$ModLoad imudp

$UDPServerRun 514

$template FILENAME,"/var/log/%fromhost-ip%/syslog.log"

*.* ?FILENAME

""")

        run("service rsyslog restart")

        run("logger ping")

    def rp_filter(self):
        #
        # async routing traffic floating from neutron metadata/dhcp midonet agent to hypervisors and gateways
        #
        if 'physical_midonet_gateway' in self._metadata.roles or 'physical_openstack_compute' in self._metadata.roles:
            if env.host_string not in self._metadata.containers:
                run("""

for RP in /proc/sys/net/ipv4/conf/*/rp_filter; do
    echo 0 > "${RP}"
done

""")

    def newrelic(self):
        if env.host_string not in self._metadata.containers:
            run("rm -fv /etc/newrelic/nrsysmond.cfg* || true")

            cuisine.package_ensure("newrelic-sysmond")

            run("""

SERVER_NAME="%s"
DOMAIN_NAME="%s"
LICENSE_KEY="%s"

cat>/etc/newrelic/nrsysmond.cfg<<EOF
license_key=${LICENSE_KEY}
loglevel=info
logfile=/var/log/newrelic/nrsysmond.log
hostname=${SERVER_NAME}.${DOMAIN_NAME}
EOF

nrsysmond-config --set license_key="${LICENSE_KEY}"

update-rc.d newrelic-sysmond defaults

/etc/init.d/newrelic-sysmond start || true
/etc/init.d/newrelic-sysmond restart || true

for i in $(seq 1 12); do
    ps axufwwwww | grep -v grep | grep "nrsysmond" && break || true
    sleep 1
done

ps axufwwwwwwwww | grep -v grep | grep nrsysmond

""" % (
        env.host_string,
        self._metadata.config["domain"],
        self._metadata.config["newrelic_license_key"]
    ))

    def cloud_repository(self):
        run("rm -rf /etc/apt/sources.list.d/cloudarchive-*")

        cuisine.package_ensure(["python-software-properties", "software-properties-common", "ubuntu-cloud-keyring"])

        self.dist_upgrade()

        if self._metadata.config["container_os_release_codename"] == "precise":
            if self._metadata.config["openstack_release"] in ["icehouse", "juno"]:
                run("add-apt-repository --yes cloud-archive:%s" % self._metadata.config["openstack_release"])

        if self._metadata.config["container_os_release_codename"] == "trusty":
            if self._metadata.config["openstack_release"] == "juno":
                run("add-apt-repository --yes cloud-archive:%s" % self._metadata.config["openstack_release"])

        run("""
OPENSTACK_RELEASE="%s"
APT_CACHER="%s"

SOURCES_LIST="/etc/apt/sources.list.d/cloudarchive-${OPENSTACK_RELEASE}.list"

test -f "${SOURCES_LIST}" && \
    sed -i 's,http://ubuntu-cloud.archive.canonical.com,'"${APT_CACHER}"'/ubuntu-cloud.archive.canonical.com,g;' "${SOURCES_LIST}"

exit 0

""" % (
        self._metadata.config["openstack_release"],
        self._metadata.config["apt-cacher"]
    ))

        self.dist_upgrade()

    @classmethod
    def dist_upgrade(cls):
        run("""

export DEBIAN_FRONTEND=noninteractive

debconf-set-selections <<EOF
grub grub/update_grub_changeprompt_threeway select install_new
grub-legacy-ec2 grub/update_grub_changeprompt_threeway select install_new
EOF

yes | dpkg --configure -a

apt-get -y -u --force-yes install

apt-get -y -u --force-yes dist-upgrade 1>/dev/null

""")

        run("apt-get clean")

        run("""

export DEBIAN_FRONTEND=noninteractive

apt-get -y autoremove

""")

    def ntp(self):
        if env.host_string not in self._metadata.containers:
            cuisine.package_ensure("ntpdate")
            cuisine.package_ensure("ntp")
            run("""
/etc/init.d/ntp stop || true

ln -sfv "/usr/share/zoneinfo/%s" /etc/localtime

ntpdate zeit.fu-berlin.de || true

/etc/init.d/ntp start || true
""" % self._metadata.config["timezone"])

