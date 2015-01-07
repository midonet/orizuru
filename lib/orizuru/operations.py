#!/usr/bin/python -Werror

import sys

import os
import os.path
import yaml

from fabric.api import *

from netaddr import IPNetwork as CIDR

from fabric.colors import yellow
from fabric.utils import puts

import cuisine

class Configure(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def configure(self):
        self.name_resolution()
        self.os_release()
        self.newrelic()
        self.datastax()
        self.midonet()

    def name_resolution(self):
        if env.host_string not in self._metadata.roles["all_containers"]:
            run("hostname %s" % env.host_string.split(".")[0])
            cuisine.file_write("/etc/hostname", env.host_string.split(".")[0])

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
        cuisine.file_write("/etc/apt/sources.list.d/datastax.list", """
deb [arch=amd64] http://debian.datastax.com/community stable main
""")
        self.repokey("http://debian.datastax.com/debian/repo_key")

    def midonet(self):

        Install(self._metadata).apt_get_update()

        cuisine.package_ensure("puppet")
        cuisine.package_ensure("git")

        if "OS_MIDOKURA_REPOSITORY_USER" in os.environ:
            username = os.environ["OS_MIDOKURA_REPOSITORY_USER"]
        else:
            username = ""

        if "OS_MIDOKURA_REPOSITORY_PASS" in os.environ:
            password = os.environ["OS_MIDOKURA_REPOSITORY_PASS"]
        else:
            password = ""

        # midonet manager can only be installed when using MEM
        if str(env.host_string).startswith("midonet_manager"):
            repo_flavor = "MEM"
        else:
            repo_flavor = self._metadata.config["midonet_repo"]

        run("""
set -x

#
# initialize the password cache
#
%s

#
# initialize the puppet modules
#
REPO="%s"

USERNAME="%s"
PASSWORD="%s"

MIDONET_VERSION="%s"
OPENSTACK_RELEASE="%s"

REPO_FLAVOR="%s"

PUPPET_NODE_DEFINITION="$(mktemp)"

cd "$(mktemp -d)"; git clone "${REPO}"

PUPPET_MODULES="$(pwd)/$(basename ${REPO})/puppet/modules"

if [[ "${REPO_FLAVOR}" == "OSS" ]]; then
    cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
  midonet_repository::ubuntu_${REPO_FLAVOR} {"$(hostname)":
    midonet_version => "${MIDONET_VERSION}",
    midonet_openstack_plugin_version => "${OPENSTACK_RELEASE}"
  }
}
EOF

    puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"
fi

if [[ "${REPO_FLAVOR}" == "MEM" ]]; then
    if [[ "${USERNAME}" == "" || "${PASSWORD}" == "" ]]; then
        echo "MEM can only be installed by providing repo credentials"
        echo "set the environment variables OS_MIDOKURA_REPOSITORY_USER and OS_MIDOKURA_REPOSITORY_PASS"
    else
        cat>"${PUPPET_NODE_DEFINITION}"<<EOF
node $(hostname) {
  midonet_repository::ubuntu_${REPO_FLAVOR} {"$(hostname)":
    username => "${USERNAME}",
    password => "${PASSWORD}",
    midonet_version => "${MIDONET_VERSION}",
    midonet_openstack_plugin_version => "${OPENSTACK_RELEASE}"
  }
}
EOF

        puppet apply --verbose --show_diff --modulepath="${PUPPET_MODULES}" "${PUPPET_NODE_DEFINITION}"
    fi
fi

""" % (
        open(os.environ["PASSWORDCACHE"]).read(),
        self._metadata.config["midonet_puppet_modules"],
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

    @classmethod
    def __lib_orizuru_operations_ubuntu_repo(cls, codename, archive_country="us"):
        run("""
set -x

XC="%s" # ubuntu release
XD="%s" # country code

cat>/etc/apt/sources.list<<EOF
#
# autogenerated file - do not modify - modify %s instead
#
EOF

for TYPE in 'deb' 'deb-src'; do
    for realm in "main restricted" "universe" "multiverse"; do
        echo "${TYPE} http://${XD}.archive.ubuntu.com/ubuntu/ ${XC} ${realm}"
        echo "${TYPE} http://${XD}.archive.ubuntu.com/ubuntu/ ${XC}-updates ${realm}"
        echo "${TYPE} http://security.archive.ubuntu.com/ubuntu/ ${XC}-security ${realm}"
    done

    echo "${TYPE} http://${XD}.archive.ubuntu.com/ubuntu/ ${XC}-backports main restricted universe multiverse"

done | tee -a /etc/apt/sources.list

""" % (codename, archive_country, sys._getframe().f_code.co_name))

class Install(object):

    def __init__(self, metadata):
        self._metadata = metadata

    def install(self):
        self.screen()
        self.login_stuff()
        self.apt_get_update()
        self.common_packages()
        self.newrelic()
        self.cloud_repository()
        self.apt_get_update()
        self.ntp()
        self.dist_upgrade()
        self.constrictor()
        self.openvswitchdkms()

    def openvswitchdkms(self):
        if env.host_string not in self._metadata.roles["all_containers"]:
            run("modprobe openvswitch")

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

        run("mkdir -pv /var/run/screen; chmod 0775 /var/run/screen")

        cuisine.file_write("/root/.screenrc", """
hardstatus alwayslastline

hardstatus string '%%{= kG} %s [%%= %%{= kw}%%?%%-Lw%%?%%{r}[%%{W}%%n*%%f %%t%%?{%%u}%%?%%{r}]%%{w}%%?%%+Lw%%?%%?%%= %%{g}] %%{W}%%{g}%%{.w} screen %%{.c} [%%H]'

""" % screenrc_string)

    @classmethod
    def login_stuff(cls):
        run("echo 'root:%s' | chpasswd" % os.environ["OS_MIDOKURA_ROOT_PASSWORD"])

    @classmethod
    def apt_get_update(cls):
        puts(yellow("updating repositories, this may take a long time."))

        run("""
#
# Round 1: try to apt-get update without purging the cache
#
apt-get update 1>/dev/null

#
# Round 2: something went wrong
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

    def newrelic(self):
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

sleep 10

ps axufwwwwwwwww | grep -v grep | grep nrsysmond

""" % (
        env.host_string,
        self._metadata.config["domain"],
        self._metadata.config["newrelic_license_key"]
    ))

    def cloud_repository(self):
        cuisine.package_ensure(["python-software-properties", "software-properties-common"])

        # prevent the error about juno cloud archive not available
        self.dist_upgrade()

        if env.host_string in self._metadata.containers:
            if self._metadata.config["openstack_release"] == "juno":
                if self._metadata.config["container_os_release_codename"] == "trusty":
                    run("add-apt-repository --yes cloud-archive:%s" % self._metadata.config["openstack_release"])

            if self._metadata.config["openstack_release"] == "icehouse":
                if self._metadata.config["container_os_release_codename"] == "precise":
                    run("add-apt-repository --yes cloud-archive:%s" % self._metadata.config["openstack_release"])

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

apt-get -y -u --force-yes dist-upgrade

""")

        run("apt-get clean")

        run("""

export DEBIAN_FRONTEND=noninteractive

apt-get -y autoremove

""")

    def ntp(self):
        run("""
/etc/init.d/ntp stop || true

ln -sfv "/usr/share/zoneinfo/%s" /etc/localtime

ntpdate zeit.fu-berlin.de || true

/etc/init.d/ntp start || true
""" % self._metadata.config["timezone"])

