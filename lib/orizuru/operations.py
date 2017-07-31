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

from fabric.colors import yellow, blue, green
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
        self.datastax()
        self.midonet()

    def localegen(self):
        if env.host_string in self._metadata.roles["all_containers"]:
            run("locale-gen de_DE.UTF-8")

    def name_resolution(self):
        if env.host_string not in self._metadata.roles["all_containers"]:
            run("hostname %s" % env.host_string.split(".")[0])

            run("ip address add %s/32 dev lo || echo" % self._metadata.servers[env.host_string]["ip"])

            cuisine.file_write("/etc/hostname", env.host_string.split(".")[0])

            cuisine.file_write("/etc/resolv.conf", """
nameserver %s
options single-request
""" % self._metadata.config["nameserver"])

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

    def datastax(self):
        if env.host_string in self._metadata.containers:
            run("""
apt-key add - <<EOF
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1

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
XO5tB2KhE3A=
=YO7C
-----END PGP PUBLIC KEY BLOCK-----
EOF
""")

            cuisine.file_write("/etc/apt/sources.list.d/datastax.list", """
deb [arch=amd64] http://debian.datastax.com/community 2.0 main
""")
            #self.repokey("https://debian.datastax.com/debian/repo_key")

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

        if "OS_MIDOKURA_URL_OVERRIDE" in os.environ:
            url_override = os.environ["OS_MIDOKURA_URL_OVERRIDE"]
        else:
            url_override = ""

        if "OS_MIDOKURA_PLUGIN_URL_OVERRIDE" in os.environ:
            plugin_url_override = os.environ["OS_MIDOKURA_PLUGIN_URL_OVERRIDE"]
        else:
            plugin_url_override = ""

        puts(blue("setting up Midokura repos"))
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

URL_OVERRIDE="%s"
PLUGIN_URL_OVERRIDE="%s"

rm -fv -- /etc/apt/sources.list.d/midonet*
rm -fv -- /etc/apt/sources.list.d/midokura*

if [[ "${REPO_FLAVOR}" == "MEM" ]]; then
    FILENAME="/etc/apt/sources.list.d/midokura.list"

    wget -SO- "http://${USERNAME}:${PASSWORD}@apt.midokura.com/packages.midokura.key" | apt-key add -

    if [[ "${URL_OVERRIDE}" == "" && "${PLUGIN_URL_OVERRIDE}" == "" ]]; then
        cat>"${FILENAME}"<<EOF
#
# MEM midolman
#

deb [arch=amd64] http://${USERNAME}:${PASSWORD}@apt.midokura.com/midonet/v${MIDONET_VERSION}/stable trusty main non-free

#
# MEM midonet neutron plugin
#

deb [arch=amd64] http://${USERNAME}:${PASSWORD}@apt.midokura.com/openstack/${OPENSTACK_PLUGIN_VERSION}/stable trusty main

EOF
    else
        cat>"${FILENAME}"<<EOF
#
# MEM midolman (url override)
#

${URL_OVERRIDE}

#
# MEM midonet neutron plugin (plugin url override)
#

${PLUGIN_URL_OVERRIDE}

EOF
    fi
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
        repo_flavor.upper(),
        url_override,
        plugin_url_override
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

    def cloud_repository(self):
        run("rm -rf /etc/apt/sources.list.d/cloudarchive-*")

        cuisine.package_ensure(["python-software-properties", "software-properties-common", "ubuntu-cloud-keyring"])

        self.dist_upgrade()

        if self._metadata.config["container_os_release_codename"] == "precise":
            if self._metadata.config["openstack_release"] in ["icehouse", "juno"]:
                run("add-apt-repository --yes cloud-archive:%s" % self._metadata.config["openstack_release"])

        if self._metadata.config["container_os_release_codename"] == "trusty":
            if self._metadata.config["openstack_release"] in ["juno", "kilo"]:
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

