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

#
# all logic in this fabfile is directly taken from the
# OpenStack Installation Guide for Ubuntu 14.04 pdf
#
# the downloaded version we have used: November 21, 2014 juno
#
def stage6():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    execute(stage6_container_openstack_mysql)
    execute(stage6_container_openstack_mysql_create_databases)

    execute(stage6_container_openstack_rabbitmq)

    execute(stage6_container_openstack_keystone)
    execute(stage6_container_openstack_keystone_keystonerc)
    execute(stage6_container_openstack_keystone_create_tenants_users_roles)
    execute(stage6_container_openstack_keystone_create_service_entity_api_endpoints)

    execute(stage6_container_openstack_glance)

    execute(stage6_container_openstack_neutron)

    execute(stage6_container_openstack_nova_controller)

    if 'physical_openstack_compute' in metadata.roles:
        execute(stage6_physical_openstack_compute_nova_compute)

    if 'container_openstack_compute' in metadata.roles:
        execute(stage6_container_openstack_compute_nova_compute)

    execute(stage6_container_openstack_horizon)

@roles('container_openstack_horizon')
def stage6_container_openstack_horizon():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure(["openstack-dashboard", "apache2", "libapache2-mod-wsgi", "memcached", "python-memcache"])

    run("apt-get -y remove openstack-dashboard-ubuntu-theme")

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

OPENSTACK_KEYSTONE="%s"

CONFIGFILE="/etc/openstack-dashboard/local_settings.py"

test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

cat>"${CONFIGFILE}"<<EOF

import os
from django.utils.translation import ugettext_lazy as _
from openstack_dashboard import exceptions
DEBUG = False
TEMPLATE_DEBUG = DEBUG
HORIZON_CONFIG = {
    'dashboards': ('project', 'admin', 'settings',),
    'default_dashboard': 'project',
    'user_home': 'openstack_dashboard.views.get_user_home',
    'ajax_queue_limit': 10,
    'auto_fade_alerts': {
        'delay': 3000,
        'fade_duration': 1500,
        'types': ['alert-success', 'alert-info']
    },
    'help_url': "http://docs.openstack.org",
    'exceptions': {'recoverable': exceptions.RECOVERABLE,
                   'not_found': exceptions.NOT_FOUND,
                   'unauthorized': exceptions.UNAUTHORIZED},
    'angular_modules': [],
    'js_files': [],
}
LOCAL_PATH = os.path.dirname(os.path.abspath(__file__))
from horizon.utils import secret_key
SECRET_KEY = secret_key.generate_or_read_from_file('/var/lib/openstack-dashboard/secret_key')
CACHES = {
   'default': {
       'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
       'LOCATION': '127.0.0.1:11211',
   }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

OPENSTACK_HOST = "${OPENSTACK_KEYSTONE}"

OPENSTACK_KEYSTONE_URL = "http://%%s:5000/v2.0" %% OPENSTACK_HOST

OPENSTACK_KEYSTONE_DEFAULT_ROLE = "_member_"

OPENSTACK_KEYSTONE_BACKEND = {
    'name': 'native',
    'can_edit_user': True,
    'can_edit_group': True,
    'can_edit_project': True,
    'can_edit_domain': True,
    'can_edit_role': True
}

OPENSTACK_HYPERVISOR_FEATURES = {
    'can_set_mount_point': False,
    'can_set_password': False,
}

OPENSTACK_CINDER_FEATURES = {
    'enable_backup': False,
}

OPENSTACK_NEUTRON_NETWORK = {
    'enable_router': True,
    'enable_quotas': True,
    'enable_ipv6': True,
    'enable_distributed_router': False,
    'enable_ha_router': False,
    'enable_lb': True,
    'enable_firewall': True,
    'enable_vpn': True,
    # The profile_support option is used to detect if an external router can be
    # configured via the dashboard. When using specific plugins the
    # profile_support can be turned on if needed.
    'profile_support': None,
    #'profile_support': 'cisco',
    # Set which provider network types are supported. Only the network types
    # in this list will be available to choose from when creating a network.
    # Network types include local, flat, vlan, gre, and vxlan.
    'supported_provider_types': ['*'],
}

IMAGE_CUSTOM_PROPERTY_TITLES = {
    "architecture": _("Architecture"),
    "kernel_id": _("Kernel ID"),
    "ramdisk_id": _("Ramdisk ID"),
    "image_state": _("Euca2ools state"),
    "project_id": _("Project ID"),
    "image_type": _("Image Type")
}

IMAGE_RESERVED_CUSTOM_PROPERTIES = []

API_RESULT_LIMIT = 1000

API_RESULT_PAGE_SIZE = 20

TIME_ZONE = "UTC"

LOGGING = {

    'version': 1,

    # When set to True this will disable all logging except
    # for loggers specified in this configuration dictionary. Note that
    # if nothing is specified here and disable_existing_loggers is True,
    # django.db.backends will still log unless it is disabled explicitly.
    'disable_existing_loggers': False,

    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'django.utils.log.NullHandler',
        },
        'console': {
            # Set the level to "DEBUG" for verbose output logging.
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },

    'loggers': {
        # Logging from django.db.backends is VERY verbose, send to null
        # by default.
        'django.db.backends': {
            'handlers': ['null'],
            'propagate': False,
        },
        'requests': {
            'handlers': ['null'],
            'propagate': False,
        },
        'horizon': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'openstack_dashboard': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'novaclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'cinderclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'keystoneclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'glanceclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'neutronclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'heatclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'ceilometerclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'troveclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'swiftclient': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'openstack_auth': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },

        'nose.plugins.manager': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'iso8601': {
            'handlers': ['null'],
            'propagate': False,
        },
        'scss': {
            'handlers': ['null'],
            'propagate': False,
        },
    }
}

SECURITY_GROUP_RULES = {
    'all_tcp': {
        'name': _('All TCP'),
        'ip_protocol': 'tcp',
        'from_port': '1',
        'to_port': '65535',
    },
    'all_udp': {
        'name': _('All UDP'),
        'ip_protocol': 'udp',
        'from_port': '1',
        'to_port': '65535',
    },
    'all_icmp': {
        'name': _('All ICMP'),
        'ip_protocol': 'icmp',
        'from_port': '-1',
        'to_port': '-1',
    },
    'ssh': {
        'name': 'SSH',
        'ip_protocol': 'tcp',
        'from_port': '22',
        'to_port': '22',
    },
    'smtp': {
        'name': 'SMTP',
        'ip_protocol': 'tcp',
        'from_port': '25',
        'to_port': '25',
    },
    'dns': {
        'name': 'DNS',
        'ip_protocol': 'tcp',
        'from_port': '53',
        'to_port': '53',
    },
    'http': {
        'name': 'HTTP',
        'ip_protocol': 'tcp',
        'from_port': '80',
        'to_port': '80',
    },
    'pop3': {
        'name': 'POP3',
        'ip_protocol': 'tcp',
        'from_port': '110',
        'to_port': '110',
    },
    'imap': {
        'name': 'IMAP',
        'ip_protocol': 'tcp',
        'from_port': '143',
        'to_port': '143',
    },
    'ldap': {
        'name': 'LDAP',
        'ip_protocol': 'tcp',
        'from_port': '389',
        'to_port': '389',
    },
    'https': {
        'name': 'HTTPS',
        'ip_protocol': 'tcp',
        'from_port': '443',
        'to_port': '443',
    },
    'smtps': {
        'name': 'SMTPS',
        'ip_protocol': 'tcp',
        'from_port': '465',
        'to_port': '465',
    },
    'imaps': {
        'name': 'IMAPS',
        'ip_protocol': 'tcp',
        'from_port': '993',
        'to_port': '993',
    },
    'pop3s': {
        'name': 'POP3S',
        'ip_protocol': 'tcp',
        'from_port': '995',
        'to_port': '995',
    },
    'ms_sql': {
        'name': 'MS SQL',
        'ip_protocol': 'tcp',
        'from_port': '1433',
        'to_port': '1433',
    },
    'mysql': {
        'name': 'MYSQL',
        'ip_protocol': 'tcp',
        'from_port': '3306',
        'to_port': '3306',
    },
    'rdp': {
        'name': 'RDP',
        'ip_protocol': 'tcp',
        'from_port': '3389',
        'to_port': '3389',
    },
}

try:
  from ubuntu_theme import *
except ImportError:
  pass

LOGIN_URL='/horizon/auth/login/'

LOGOUT_URL='/horizon/auth/logout/'

LOGIN_REDIRECT_URL='/horizon'

ALLOWED_HOSTS = '*'

COMPRESS_OFFLINE = True

EOF

cd /usr/share/openstack-dashboard/static/dashboard/img

for PIC in favicon.ico logo.png logo-splash.png; do
    test -f "${PIC}.ORIG" || rsync -avpx "${PIC}" "${PIC}.ORIG"
done

service apache2 restart
service memcached restart

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"]
    ))

    cuisine.file_upload("/usr/share/openstack-dashboard/static/dashboard/img/favicon.ico", "%s/img/favicon.ico" % os.environ["TMPDIR"])

    for picture in ["logo", "logo-splash"]:
        cuisine.file_upload("/usr/share/openstack-dashboard/static/dashboard/img/%s.png" % picture, "%s/img/midokura.png" % os.environ["TMPDIR"])

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_neutron')
def stage6_container_openstack_neutron():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure([
        "python-neutron-plugin-midonet",
        "neutron-server",
        "python-neutronclient",
        "python-keystoneclient",
        "neutron-l3-agent",
        "neutron-dhcp-agent"])

    # from kilo onward you can use the lbaas in horizon
    if metadata.config["midonet_mem_openstack_plugin_version"] not in ['havana', 'icehouse', 'juno']:
        cuisine.package_ensure("neutron-lbaas")

    service = "neutron"

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

CONFIGHELPER="%s"

SERVICE="%s"

DATABASE_SERVER_IP="%s"

KEYSTONE_IP="%s"

RABBIT_IP="%s"

CONTROLLER_IP="%s"

REGION="%s"

MIDONET_API="%s"

MIDONET_API_URL="%s"

PLUGIN_VERSION="%s"

source /etc/keystone/KEYSTONERC_ADMIN || source /etc/keystone/admin-openrc.sh

SERVICE_TENANT_ID="$(keystone tenant-list | grep 'service' | awk -F'|' '{print $2;}' | xargs -n1 echo)"

#
# neutron controller
#
for XSERVICE in "${SERVICE}"; do
    CONFIGFILE="/etc/${SERVICE}/${XSERVICE}.conf"

    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "database" "connection" "mysql://${SERVICE}:${NEUTRON_DBPASS}@${DATABASE_SERVER_IP}/${SERVICE}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rpc_backend" "rabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_host" "${RABBIT_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_user" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_username" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_userid" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_password" "${RABBIT_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "core_plugin" "midonet.neutron.plugin.MidonetPluginV2"

    #
    # use the horizon lbaas plugin for juno upwards.
    #
    # all older releases should configure L4LB in midonet manager or use neutron cli.
    #
    if [[ ! "havana" == "${PLUGIN_VERSION}" ]]; then
        if [[ ! "icehouse" == "${PLUGIN_VERSION}" ]]; then
            if [[ ! "juno" == "${PLUGIN_VERSION}" ]]; then
                "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_plugins" "lbaas"
                "${CONFIGHELPER}" set "${CONFIGFILE}" "service_providers" "service_provider" \
                    "LOADBALANCER:Midonet:midonet.neutron.services.loadbalancer.driver.MidonetLoadbalancerDriver:default"
            else
                "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_plugins" ""
            fi
        else
            "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_plugins" ""
        fi
    else
        "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_plugins" ""
    fi

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "allow_overlapping_ips" "True"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "notify_nova_on_port_status_changes" "True"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "notify_nova_on_port_data_changes" "True"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_url" "http://${CONTROLLER_IP}:8774/v2"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_admin_auth_url" "http://${KEYSTONE_IP}:35357/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_region_name" "${REGION}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_admin_username" "nova"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_admin_tenant_id" "${SERVICE_TENANT_ID}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_admin_password" "${NOVA_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "auth_strategy" "keystone"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "auth_uri" "http://${KEYSTONE_IP}:5000/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "identity_uri" "http://${KEYSTONE_IP}:35357"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_user" "${SERVICE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_password" "${NEUTRON_PASS}"
done

MIDONET_PLUGIN="/etc/neutron/plugins/midonet/midonet.ini"
mkdir -pv "$(dirname ${MIDONET_PLUGIN})"
touch "${MIDONET_PLUGIN}"

for CONFIGFILE in "${MIDONET_PLUGIN}" "/etc/neutron/dhcp_agent.ini" "/etc/neutron/metadata_agent.ini"; do
    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true
done

#
# Neutron dhcp agent
#
CONFIGFILE="/etc/neutron/dhcp_agent.ini"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "interface_driver" "neutron.agent.linux.interface.MidonetInterfaceDriver"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "dhcp_driver" "midonet.neutron.agent.midonet_driver.DhcpNoOpDriver"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "use_namespaces" "True"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "enable_isolated_metadata" "True"

#
# Neutron metadata agent
#
CONFIGFILE="/etc/neutron/metadata_agent.ini"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "auth_url" "http://${KEYSTONE_IP}:35357/v2.0"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "auth_region" "${REGION}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "admin_tenant_name" "service"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "admin_user" "neutron"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "admin_password" "${NEUTRON_PASS}"

"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_metadata_ip" "${CONTROLLER_IP}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_metadata_port" "8775"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "nova_metadata_protocol" "http"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_proxy_shared_secret" "${NEUTRON_METADATA_SHARED_SECRET}"

#
# Add the midonet section to the midonet plugin and the dhcp agent ini
#
for CONFIGFILE in "${MIDONET_PLUGIN}" "/etc/neutron/dhcp_agent.ini"; do
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "midonet_uri" "http://${MIDONET_API}:${MIDONET_API_URL}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "username" "midonet"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "password" "${MIDONET_PASS}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "project_id" "service"
done

CONFIGFILE="${MIDONET_PLUGIN}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "database" "sql_connection" "mysql://${SERVICE}:${NEUTRON_DBPASS}@${DATABASE_SERVER_IP}/${SERVICE}"

cat>/etc/default/neutron-server<<EOF
NEUTRON_PLUGIN_CONFIG="/etc/neutron/plugins/midonet/midonet.ini"
EOF

chown -R neutron: /etc/neutron

sync

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        service,
        metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_rabbitmq"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_controller"][0]]["ip"],
        metadata.config["region"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.services["midonet"]["internalurl"],
        metadata.config["midonet_mem_openstack_plugin_version"]
    ))

    puts(green("running neutron-db-manage"))

    run("""

set -e

source /etc/keystone/KEYSTONERC_ADMIN || source /etc/keystone/admin-openrc.sh

neutron-db-manage --config-file /etc/neutron/neutron.conf upgrade %s

""" % metadata.config["openstack_release"])

    run("""

source /etc/keystone/KEYSTONERC_ADMIN || source /etc/keystone/admin-openrc.sh

SERVICE="neutron"

set -e

rm -fv "/var/lib/${SERVICE}/${SERVICE}.sqlite"

cd /var/run

mkdir -p /var/run/neutron
chown -R neutron:root /var/run/neutron

mkdir -p /var/log/neutron
chown -R neutron:root /var/log/neutron

[ -r /etc/default/neutron-server ] && . /etc/default/neutron-server
[ -r "$NEUTRON_PLUGIN_CONFIG" ] && CONF_ARG="--config-file $NEUTRON_PLUGIN_CONFIG"

chmod 0777 /var/run/screen

for DAEMON in dhcp-agent metadata-agent; do
    ps axufwwwww | grep -v grep | grep "neutron-${DAEMON}" || \
        screen -S "neutron-${DAEMON}" -d -m -- \
            start-stop-daemon --start --chuid neutron \
                --exec "/usr/bin/neutron-${DAEMON}" -- \
                    --config-file=/etc/neutron/neutron.conf \
                    --config-file="/etc/neutron/$(echo "${DAEMON}" | sed 's,-,_,g;').ini" \
                    --log-file="/var/log/neutron/${DAEMON}.log"

    for i in $(seq 1 12); do
        ps axufwwwww | grep -v grep | grep "neutron-${DAEMON}" && break || true
        sleep 1
    done

    ps axufwwwww | grep -v grep | grep "neutron-${DAEMON}"
done

ps axufwwwww | grep -v grep | grep neutron-server || \
    screen -S "neutron-server" -d -m -- \
        start-stop-daemon --start --chuid neutron \
            --exec /usr/bin/neutron-server -- \
            --config-file /etc/neutron/neutron.conf \
            --log-file /var/log/neutron/server.log $CONF_ARG

DAEMON="server"

for i in $(seq 1 12); do
    ps axufwwwww | grep -v grep | grep "neutron-${DAEMON}" && break || true
    sleep 1
done

ps axufwwwww | grep -v grep | grep "neutron-${DAEMON}"

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_controller')
def stage6_container_openstack_nova_controller():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure([
        "nova-api",
        "nova-cert",
        "nova-conductor",
        "nova-consoleauth",
        "nova-novncproxy",
        "nova-scheduler",
        "python-novaclient"])

    service = "nova"

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

CONFIGHELPER="%s"

SERVICE="%s"

DATABASE_SERVER_IP="%s"

KEYSTONE_IP="%s"

RABBIT_IP="%s"

GLANCE_IP="%s"

CONTROLLER_IP="%s"

NEUTRON_IP="%s"

#
# nova controller
#
for XSERVICE in "${SERVICE}"; do
    CONFIGFILE="/etc/${SERVICE}/${XSERVICE}.conf"

    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_listen" "0.0.0.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_listen_port" "8775"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_workers" "2"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_neutron_metadata_proxy" "True"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_host" "${CONTROLLER_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "neutron_metadata_proxy_shared_secret" "${NEUTRON_METADATA_SHARED_SECRET}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "database" "connection" "mysql://${SERVICE}:${%s_DBPASS}@${DATABASE_SERVER_IP}/${SERVICE}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "neutron_url_timeout" "240"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rpc_backend" "rabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_host" "${RABBIT_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_user" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_username" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_userid" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_password" "${RABBIT_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "my_ip" "${CONTROLLER_IP}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "novncproxy_host" "0.0.0.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "novncproxy_port" "6080"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "auth_strategy" "keystone"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "auth_uri" "http://${KEYSTONE_IP}:5000/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "identity_uri" "http://${KEYSTONE_IP}:35357"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_user" "${SERVICE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_password" "${%s_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "glance" "host" "${GLANCE_IP}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "network_api_class" "nova.network.neutronv2.api.API"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "security_group_api" "neutron"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "linuxnet_interface_driver" "nova.network.linux_net.LinuxOVSInterfaceDriver"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "firewall_driver" "nova.virt.firewall.NoopFirewallDriver"

    # TODO find out which one is correct (this or the above one in DEFAULT)
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "neutron_metadata_proxy_shared_secret" "${NEUTRON_METADATA_SHARED_SECRET}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "url" "http://${NEUTRON_IP}:9696"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "auth_strategy" "keystone"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_auth_url" "http://${KEYSTONE_IP}:35357/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_username" "neutron"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_password" "${NEUTRON_PASS}"

done

nova-manage db sync

cd /var/run

mkdir -p /var/run/nova
chown -R nova:root /var/run/nova/

mkdir -p /var/lock/nova
chown -R nova:root /var/lock/nova/

chmod 0777 /var/run/screen

rm -fv "/var/lib/${SERVICE}/${SERVICE}.sqlite"

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        service,
        metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_rabbitmq"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_glance"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_controller"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_neutron"][0]]["ip"],
        service.upper(),
        service.upper()
    ))

    for service in ['nova']:
        for subservice in ['api', 'cert', 'consoleauth', 'scheduler', 'conductor', 'novncproxy']:
            run("""
SERVICE="%s"
SUBSERVICE="%s"

if [[ "${SUBSERVICE}" == "novncproxy" ]]; then
    SUBSERVICE_PARAMS="--web /usr/share/novnc/"
fi

mkdir -pv /etc/rc.local.d

cat >/etc/rc.local.d/orizuru-${SERVICE}-${SUBSERVICE}.sh<<EOF
#!/bin/bash

while(true); do
    ps axufwwwwwwww | grep -v grep | grep -v "orizuru-${SERVICE}-${SUBSERVICE}.sh" | grep -- "${SERVICE}-${SUBSERVICE}" || \
        start-stop-daemon --start --chuid ${SERVICE} \
            --exec "/usr/bin/${SERVICE}-${SUBSERVICE}" -- --config-file=/etc/${SERVICE}/${SERVICE}.conf ${SUBSERVICE_PARAMS}
    sleep 2
done

EOF

chmod 0755 /etc/rc.local.d/orizuru-${SERVICE}-${SUBSERVICE}.sh

screen -S "${SERVICE}-${SUBSERVICE}" -d -m -- /etc/rc.local.d/orizuru-${SERVICE}-${SUBSERVICE}.sh

for i in $(seq 1 24); do
    ps axufwwwww | grep -v grep | grep -v "orizuru-${SERVICE}-${SUBSERVICE}.sh" | grep "${SERVICE}-${SUBSERVICE}" && break || true
    sleep 1
done

sleep 10

ps axufwwwwww | grep -v grep | grep -v "orizuru-${SERVICE}-${SUBSERVICE}.sh" | grep -- "${SERVICE}-${SUBSERVICE}"

""" % (service, subservice))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('physical_openstack_compute')
def stage6_physical_openstack_compute_nova_compute():
    metadata = Config(os.environ["CONFIGFILE"])

    compute_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][env.host_string])

    stage6_openstack_compute_nova_compute(compute_ip, compute_ip)

    run("""

service nova-compute restart

for i in $(seq 1 12); do
    ps axufwwwww | grep -v grep | grep "nova-compute" && break || true
    sleep 1
done

sleep 10

ps axufwwwww | grep -v grep | grep nova-compute

""")

@roles('container_openstack_compute')
def stage6_container_openstack_compute_nova_compute():
    metadata = Config(os.environ["CONFIGFILE"])

    compute_ip = metadata.containers[env.host_string]["ip"]

    stage6_openstack_compute_nova_compute(compute_ip, compute_ip)

    run("""

chmod 0777 /var/run/screen

ps axufwwwww | grep -v grep | grep nova-compute || \
    screen -S nova-compute -d -m -- start-stop-daemon --start --chuid nova --exec /usr/bin/nova-compute -- --config-file=/etc/nova/nova.conf --config-file=/etc/nova/nova-compute.conf

for i in $(seq 1 12); do
    ps axufwwwww | grep -v grep | grep "nova-compute" && break || true
    sleep 1
done

sleep 10

ps axufwwwww | grep -v grep | grep nova-compute

""")

def stage6_openstack_compute_nova_compute(compute_ip, compute_vpn_ip):
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure(["nova-compute", "sysfsutils", "nova-network", "neutron-common", "python-neutron-plugin-midonet"])

    service = "nova"

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

CONFIGHELPER="%s"

SERVICE="%s"

KEYSTONE_IP="%s"

RABBIT_IP="%s"

GLANCE_IP="%s"

COMPUTE_IP="%s"

CONTROLLER_IP="%s"

CONTROLLER_OUTER_IP="%s"

MIDONET_API="%s"

NEUTRON_IP="%s"

COMPUTE_VPN_IP="%s"

MIDONET_API_URL="%s"

#
# nova compute
#
for XSERVICE in "${SERVICE}"; do
    CONFIGFILE="/etc/${SERVICE}/${XSERVICE}.conf"

    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_listen" "0.0.0.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_listen_port" "8775"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_workers" "2"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "service_neutron_metadata_proxy" "True"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "metadata_host" "${CONTROLLER_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "neutron_metadata_proxy_shared_secret" "${NEUTRON_METADATA_SHARED_SECRET}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rpc_backend" "rabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_host" "${RABBIT_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_user" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_username" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_userid" "osrabbit"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "rabbit_password" "${RABBIT_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "my_ip" "${COMPUTE_IP}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "novncproxy_base_url" "http://${CONTROLLER_OUTER_IP}:6080/vnc_auto.html"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "vncserver_listen" "${COMPUTE_VPN_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "vncserver_proxyclient_address" "${COMPUTE_VPN_IP}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "vnc_enabled" "True"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "auth_strategy" "keystone"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "auth_uri" "http://${KEYSTONE_IP}:5000/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "identity_uri" "http://${KEYSTONE_IP}:35357"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_user" "${SERVICE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_password" "${%s_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "glance" "host" "${GLANCE_IP}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "network_api_class" "nova.network.neutronv2.api.API"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "security_group_api" "neutron"
    # "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "linuxnet_interface_driver" "nova.network.linux_net.LinuxOVSInterfaceDriver"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "firewall_driver" "nova.virt.firewall.NoopFirewallDriver"

    # used for midonet
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "libvirt_vif_driver" "nova.virt.libvirt.vif.LibvirtGenericVIFDriver"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "midonet_uri" "http://${MIDONET_API}:${MIDONET_API_URL}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "username" "midonet"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "password" "${MIDONET_PASS}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "MIDONET" "project_id" "service"

    # TODO find out which one is correct (this or the above one in DEFAULT)
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "neutron_metadata_proxy_shared_secret" "${NEUTRON_METADATA_SHARED_SECRET}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "url" "http://${NEUTRON_IP}:9696"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "auth_strategy" "keystone"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_auth_url" "http://${KEYSTONE_IP}:35357/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_username" "neutron"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "neutron" "admin_password" "${NEUTRON_PASS}"

done

CONFIGFILE="/etc/${SERVICE}/${SERVICE}-compute.conf"
if [[ "$(egrep -c 'vmx|svm' /proc/cpuinfo)" == "0" || "$(grep kvm /proc/misc)" == "" ]]; then
    "${CONFIGHELPER}" set "${CONFIGFILE}" "libvirt" "virt_type" "qemu"
else
    "${CONFIGHELPER}" set "${CONFIGFILE}" "libvirt" "virt_type" "kvm"

    if [ ! -e /dev/kvm ]; then
        KVM_NODE="$(grep 'kvm' /proc/misc | awk '{print $2;}')"
        mknod /dev/kvm c 10 "${KVM_NODE}"
    fi

    if [ ! -e /dev/net/tun ]; then
        TUN_NODE="$(grep 'tun' /proc/misc | awk '{print $2;}')"

        if [[ ! "${TUN_NODE}" == "" ]]; then
            mkdir -pv /dev/net
            mknod /dev/net/tun c 10 "${TUN_NODE}"
        fi
    fi
fi

cat>/etc/libvirt/qemu.conf<<EOF

user = "root"
group = "root"

cgroup_device_acl = [
    "/dev/null", "/dev/full", "/dev/zero", "/dev/random", "/dev/urandom", "/dev/ptmx", "/dev/kvm", "/dev/kqemu", "/dev/rtc","/dev/hpet", "/dev/vfio/vfio", "/dev/net/tun"
]

EOF

rm -fv "/var/lib/${SERVICE}/${SERVICE}.sqlite"

cd /var/run

mkdir -p /var/run/nova
chown -R nova:root /var/run/nova/

mkdir -p /var/lock/nova
chown -R nova:root /var/lock/nova/

modprobe nbd

service libvirt-bin restart

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        service,
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_rabbitmq"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_glance"][0]]["ip"],
        compute_ip,
        metadata.containers[metadata.roles["container_openstack_controller"][0]]["ip"],
        metadata.servers[metadata.roles["openstack_controller"][0]]["ip"],
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_neutron"][0]]["ip"],
        compute_vpn_ip,
        metadata.services["midonet"]["internalurl"],
        service.upper()
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_glance')
def stage6_container_openstack_glance():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure(["glance", "python-glanceclient"])

    service = "glance"

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

CONFIGHELPER="%s"

SERVICE="%s"

DATABASE_SERVER_IP="%s"

KEYSTONE_IP="%s"

for SUBSERVICE in "api" "registry"; do

    CONFIGFILE="/etc/${SERVICE}/${SERVICE}-${SUBSERVICE}.conf"

    test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "True"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "database" "connection" "mysql://${SERVICE}:${%s_DBPASS}@${DATABASE_SERVER_IP}/${SERVICE}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "auth_uri" "http://${KEYSTONE_IP}:5000/v2.0"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "identity_uri" "http://${KEYSTONE_IP}:35357"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_tenant_name" "service"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_user" "${SERVICE}"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "keystone_authtoken" "admin_password" "${%s_PASS}"

    "${CONFIGHELPER}" set "${CONFIGFILE}" "paste_deploy" "flavor" "keystone"
done

SUBSERVICE="api"
CONFIGFILE="/etc/${SERVICE}/${SERVICE}-${SUBSERVICE}.conf"

"${CONFIGHELPER}" set "${CONFIGFILE}" "glance_store" "default_store" "file"
"${CONFIGHELPER}" set "${CONFIGFILE}" "glance_store" "filesystem_store_datadir" "/var/lib/glance/images/"

glance-manage db_sync

chmod 0777 /var/run/screen

chown -R glance:adm /var/log/glance

chown -R glance:glance /var/lib/glance

rm -rfv /tmp/keystone-signing*

for SUBSERVICE in "registry" "api"; do
    ps axufwwwwww | grep -v grep | grep -- "/usr/bin/glance-${SUBSERVICE}" || \
        screen -S glance-${SUBSERVICE} -d -m -- start-stop-daemon --start --chuid glance --chdir /var/lib/glance --name glance-${SUBSERVICE} --exec /usr/bin/glance-${SUBSERVICE}

    for i in $(seq 1 12); do
        ps axufwwwww | grep -v grep | grep "glance-${SUBSERVICE}" && break || true
        sleep 1
    done

    ps axufwwwwww | grep -v grep | grep -- "/usr/bin/glance-${SUBSERVICE}"
done

rm -fv "/var/lib/${SERVICE}/${SERVICE}.sqlite"

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        service,
        metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"],
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        service.upper(),
        service.upper()
    ))

    run("""

source /etc/keystone/KEYSTONERC_ADMIN || source /etc/keystone/admin-openrc.sh

set -e

cd /tmp

# wget --continue http://cdn.download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img

wget --continue http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img

glance image-list | grep cirros || \
    glance image-create \
        --name "cirros-0.3.3-x86_64" \
        --file "cirros-0.3.3-x86_64-disk.img" \
        --disk-format qcow2 \
        --container-format bare \
        --is-public True

""")

    run("""

source /etc/keystone/KEYSTONERC_ADMIN || source /etc/keystone/admin-openrc.sh

set -e

cd /tmp

wget --continue http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img

glance image-list | grep 'trusty' || \
    glance image-create \
        --name "Ubuntu 14.04 trusty-server-cloudimg-amd64-disk1.img" \
        --file "trusty-server-cloudimg-amd64-disk1.img" \
        --disk-format qcow2 \
        --container-format bare \
        --is-public True

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('all_containers')
def stage6_container_openstack_keystone_keystonerc():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

KEYSTONE_IP="%s"

OPENSTACK_RELEASE="%s"

mkdir -pv /etc/keystone

if [[ "kilo" == "${OPENSTACK_RELEASE}" || \
      "liberty" == "${OPENSTACK_RELEASE}" ]]; then

    cat>/etc/keystone/admin-openrc.sh<<EOF
export OS_PROJECT_DOMAIN_ID=default
export OS_USER_DOMAIN_ID=default
export OS_PROJECT_NAME=admin
export OS_TENANT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD=${ADMIN_PASS}
export OS_AUTH_URL=http://${KEYSTONE_IP}:35357/v3
EOF

    chmod 0700 /etc/keystone/admin-openrc.sh
    chown root:root /etc/keystone/admin-openrc.sh

    exit 0
fi

cat>/etc/keystone/KEYSTONERC<<EOF
export OS_TENANT_NAME=admin
export OS_USERNAME=admin
export OS_PASSWORD=${ADMIN_PASS}
export OS_AUTH_URL=http://${KEYSTONE_IP}:35357/v2.0
EOF

cp /etc/keystone/KEYSTONERC /etc/keystone/KEYSTONERC_ADMIN

cat>/etc/keystone/KEYSTONERC_DEMO<<EOF
export OS_TENANT_NAME=demo
export OS_USERNAME=demo
export OS_PASSWORD=${DEMO_PASS}
export OS_AUTH_URL=http://${KEYSTONE_IP}:5000/v2.0
EOF

chmod 0700 /etc/keystone/KEYSTONERC*
chown root:root /etc/keystone/KEYSTONERC*

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
        metadata.config["openstack_release"]
    ))

    if metadata.config["openstack_release"] in ["liberty", "kilo"]:
        # install this everywhere because we might need to get tenant ids with it
        cuisine.package_ensure("python-openstackclient")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_keystone')
def stage6_container_openstack_keystone_create_service_entity_api_endpoints():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    keystone_ip = metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"]

    for service in metadata.services:
        if not service == 'keystone':
            if service == 'nova':
                service_alias = 'controller'
            else:
                service_alias = service

            if service == 'midonet':
                service_ip = metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"]
            else:
                if service == 'swift':
                    service_ip = metadata.containers[metadata.roles["container_openstack_controller"][0]]["ip"]
                else:
                    service_ip = metadata.containers[metadata.roles["container_openstack_%s" % service_alias][0]]["ip"]

            run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

KEYSTONE_IP="%s"

SERVICE="%s"

SERVICE_TYPE="%s"
SERVICE_DESCRIPTION="%s"
PUBLICURL="%s"
INTERNALURL="%s"
ADMINURL="%s"

REGION="%s"

SERVICE_IP="%s"

OPENSTACK_RELEASE="%s"

touch /usr/lib/python2.7/dist-packages/babel/localedata/__init__.py

if [[ "kilo" == "${OPENSTACK_RELEASE}" || \
      "liberty" == "${OPENSTACK_RELEASE}" ]]; then
    export OS_TOKEN="${ADMIN_TOKEN}"
    export OS_URL="http://${KEYSTONE_IP}:35357/v2.0"

    openstack service list -c Type | grep "${SERVICE_TYPE}" || \
        openstack service create --name "${SERVICE}" --description "${SERVICE_DESCRIPTION}" "${SERVICE_TYPE}"

    PUBLIC="http://${SERVICE_IP}:${PUBLICURL}"
    ADMIN="http://${SERVICE_IP}:${ADMINURL}"
    INTERNAL="http://${SERVICE_IP}:${INTERNALURL}"

    openstack endpoint list -c 'Service Type' | grep "${SERVICE_TYPE}" || \
        openstack endpoint create \
            --publicurl "${PUBLIC}" \
            --internalurl "${INTERNAL}" \
            --adminurl "${ADMIN}" \
            --region "${REGION}" \
            "${SERVICE_TYPE}"

    exit 0
fi

python 2>&1 <<EOF
from keystoneclient.v2_0 import client

keystone = client.Client(username="service", password="${SERVICE_PASS}", tenant_name="admin", auth_url="http://${KEYSTONE_IP}:5000/v2.0")

if not [x for x in keystone.services.list() if x.name == "${SERVICE}"]:
    publicurl = "http://${SERVICE_IP}:${PUBLICURL}"
    adminurl = "http://${SERVICE_IP}:${ADMINURL}"
    internalurl = "http://${SERVICE_IP}:${INTERNALURL}"

    service = keystone.services.create(name="${SERVICE}", service_type="${SERVICE_TYPE}", description="${SERVICE_DESCRIPTION}")

    keystone.endpoints.create(region="${REGION}", service_id=service.id, publicurl=publicurl, adminurl=adminurl, internalurl=internalurl)

EOF

""" % (
    metadata.config["debug"],
    open(os.environ["PASSWORDCACHE"]).read(),
    keystone_ip,
    service,
    metadata.services[service]["type"],
    metadata.services[service]["description"],
    metadata.services[service]["publicurl"],
    metadata.services[service]["internalurl"],
    metadata.services[service]["adminurl"],
    metadata.config["region"],
    service_ip,
    metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_keystone')
def stage6_container_openstack_keystone_create_tenants_users_roles():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    keystone_ip = metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"]

    service = 'keystone'

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

KEYSTONE_IP="%s"

REGION="%s"

SERVICE_DESCRIPTION="%s"
SERVICE_TYPE="%s"

PUBLICURL="%s"
INTERNALURL="%s"
ADMINURL="%s"

OPENSTACK_RELEASE="%s"

touch /usr/lib/python2.7/dist-packages/babel/localedata/__init__.py

if [[ "kilo" == "${OPENSTACK_RELEASE}" || \
      "liberty" == "${OPENSTACK_RELEASE}" ]]; then
    export OS_TOKEN="${ADMIN_TOKEN}"
    export OS_URL="http://${KEYSTONE_IP}:35357/v2.0"

    openstack service list | grep keystone || openstack service create --name keystone --description "OpenStack Identity" identity

    openstack endpoint list | grep "${KEYSTONE_IP}" || openstack endpoint create \
        --publicurl "http://${KEYSTONE_IP}:${PUBLICURL}" \
        --internalurl "http://${KEYSTONE_IP}:${INTERNALURL}" \
        --adminurl "http://${KEYSTONE_IP}:${ADMINURL}" \
        --region "${REGION}" \
            identity

    for TENANT in 'admin' 'service' 'demo'; do
        openstack project list | grep "${TENANT}" || openstack project create "${TENANT}"
    done

    for ROLE in 'admin' 'Member'; do
        openstack role list | grep "${ROLE}" || openstack role create "${ROLE}"
    done

    #
    # demo tenant
    #
    openstack user list --project demo --format csv -c Name | sed 's,",,g' | grep -v "^Name" | grep "^demo" && \
        openstack user set --project demo --password "${DEMO_PASS}" "demo" || \
        openstack user create --project demo --password "${DEMO_PASS}" "demo"

    #
    # admin tenant
    #
    openstack user list --project admin --format csv -c Name | sed 's,",,g' | grep -v "^Name" | grep "^admin" && \
        openstack user set --project admin --password "${ADMIN_PASS}" "admin" || \
        openstack user create --project admin --password "${ADMIN_PASS}" "admin"

    openstack role add --project admin --user admin admin || true

    #
    # service tenant
    #
    openstack user list --project service --format csv -c Name | sed 's,",,g' | grep -v "^Name" | grep "^service" && \
        openstack user set --project service --password "${SERVICE_PASS}" "service" || \
        openstack user create --project service --password "${SERVICE_PASS}" "service"

    openstack role add --project service --user service admin || true

    exit 0
fi

#
# logic for juno
#

python 2>&1 <<EOF
from keystoneclient.v2_0 import client

token = "${ADMIN_TOKEN}"
endpoint = "http://${KEYSTONE_IP}:35357/v2.0"
keystone = client.Client(token=token, endpoint=endpoint)

for create_role in ['admin', 'Member']:
    if not [x for x in keystone.roles.list() if x.name == create_role]:
        keystone.roles.create(create_role)

for create_service in ['keystone']:
    if not [x for x in keystone.services.list() if x.name == create_service]:
        publicurl = "http://${KEYSTONE_IP}:${PUBLICURL}"
        adminurl = "http://${KEYSTONE_IP}:${ADMINURL}"
        internalurl = "http://${KEYSTONE_IP}:${INTERNALURL}"

        service = keystone.services.create(name=create_service, service_type='${SERVICE_TYPE}', description='${SERVICE_DESCRIPTION}')

        keystone.endpoints.create(region="${REGION}", service_id=service.id, publicurl=publicurl, adminurl=adminurl, internalurl=internalurl)

for create_tenant in ['admin', 'service', 'demo']:
    if not [x for x in keystone.tenants.list() if x.name == create_tenant]:
        keystone.tenants.create(tenant_name=create_tenant, description="%%s tenant" %% create_tenant, enabled=True)

passwords = {}
passwords["admin"] = "${ADMIN_PASS}"
passwords["demo"] = "${DEMO_PASS}"
passwords["service"] = "${SERVICE_PASS}"

admin_tenant = [x for x in keystone.tenants.list() if x.name == 'admin'][0]
admin_tenant_id = admin_tenant.id

service_tenant = [x for x in keystone.tenants.list() if x.name == 'service'][0]
service_tenant_id = service_tenant.id

for create_user in passwords:
    user_password = passwords[create_user]

    if not [x for x in keystone.users.list() if x.name == create_user]:
        admin_tenant_user = keystone.users.create(name=create_user, password=user_password, email=None, tenant_id=admin_tenant_id, enabled=True)

        for create_role in ['admin', 'Member']:
            for role in [x for x in keystone.roles.list() if x.name == create_role]:
                if create_user <> 'demo':
                    keystone.roles.add_user_role(admin_tenant_user, role, tenant=admin_tenant)

                if create_user <> 'demo':
                    if create_user <> 'admin':
                        keystone.roles.add_user_role(admin_tenant_user, role, tenant=service_tenant)

EOF

""" % (
    metadata.config["debug"],
    open(os.environ["PASSWORDCACHE"]).read(),
    keystone_ip,
    metadata.config["region"],
    metadata.services[service]["description"],
    metadata.services[service]["type"],
    metadata.services[service]["publicurl"],
    metadata.services[service]["internalurl"],
    metadata.services[service]["adminurl"],
    metadata.config["openstack_release"]
    ))

    for service in metadata.services:
        if not service == 'keystone':
            puts(green("configuring keystone for service %s" % service))
            run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

KEYSTONE_IP="%s"

SERVICE="%s"
X_PASSWORD="${%s_PASS}"

OPENSTACK_RELEASE="%s"

touch /usr/lib/python2.7/dist-packages/babel/localedata/__init__.py

if [[ "kilo" == "${OPENSTACK_RELEASE}" || \
      "liberty" == "${OPENSTACK_RELEASE}" ]]; then
    export OS_TOKEN="${ADMIN_TOKEN}"
    export OS_URL="http://${KEYSTONE_IP}:35357/v2.0"

    openstack user list --project service --format csv -c Name | sed 's,",,g' | grep -v "^Name" | grep "^${SERVICE}" && \
        openstack user set --project service --password "${X_PASSWORD}" "${SERVICE}" || \
        openstack user create --project service --password "${X_PASSWORD}" "${SERVICE}"

    openstack role add --project service --user "${SERVICE}" admin || true

    exit 0
fi

#
# logic for juno
#

python 2>&1 <<EOF
from keystoneclient.v2_0 import client

keystone = client.Client(username="service", password="${SERVICE_PASS}", tenant_name="service", auth_url="http://${KEYSTONE_IP}:5000/v2.0")

passwords = {}
passwords["${SERVICE}"] = "${X_PASSWORD}"

service_tenant = [x for x in keystone.tenants.list() if x.name == 'service'][0]
service_tenant_id = service_tenant.id

for create_user in passwords:
    user_password = passwords[create_user]

    if [x for x in keystone.users.list() if x.name == create_user]:
        print ("update user %%s with password %%s in tenant %%s (%%s)" %% (create_user, user_password, service_tenant.name, service_tenant_id))

        for user in [x for x in keystone.users.list() if x.name == create_user]:
            keystone.users.update_password(user, user_password)
    else:
        print ("create user %%s with password %%s in tenant %%s (%%s)" %% (create_user, user_password, service_tenant.name, service_tenant_id))

        user = keystone.users.create(name=create_user, password=user_password, email=None, tenant_id=service_tenant_id, enabled=True)

        for create_role in ['admin']:
            for role in [x for x in keystone.roles.list() if x.name == create_role]:
                keystone.roles.add_user_role(user, role, tenant=service_tenant)

EOF

""" % (
    metadata.config["debug"],
    open(os.environ["PASSWORDCACHE"]).read(),
    keystone_ip,
    service,
    service.upper(),
    metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_keystone')
def stage6_container_openstack_keystone():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    if metadata.config['openstack_release'] == 'kilo':
        cuisine.package_ensure(["keystone", "python-openstackclient", "apache2", "libapache2-mod-wsgi", "memcached", "python-memcache"])
    else:
        cuisine.package_ensure(["keystone", "python-keystoneclient"])

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

VERBOSE="%s"
DEBUG="%s"

#
# initialize the password cache
#
%s

#
# initialize the config helper script
#
CONFIGHELPER="%s"

DATABASE_SERVER_IP="%s"

OPENSTACK_RELEASE="%s"

CONFIGFILE="/etc/keystone/keystone.conf"

test -f "${CONFIGFILE}.DISTRIBUTION" || cp "${CONFIGFILE}" "${CONFIGFILE}.DISTRIBUTION" || true

#
# set the admin token for direct keystone access
#
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "admin_token" "${ADMIN_TOKEN}"

#
# set up logging
#
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "verbose" "${VERBOSE}"
"${CONFIGHELPER}" set "${CONFIGFILE}" "DEFAULT" "debug" "${DEBUG}"

#
# configure sql database settings for keystone
#
"${CONFIGHELPER}" set "${CONFIGFILE}" "database" "connection" "mysql://keystone:${KEYSTONE_DBPASS}@${DATABASE_SERVER_IP}/keystone"
# experimental feature "${CONFIGHELPER}" set "${CONFIGFILE}" "database" "use_db_reconnect" "True"

"${CONFIGHELPER}" set "${CONFIGFILE}" "token" "provider" "keystone.token.providers.uuid.Provider"

if [[ "${OPENSTACK_RELEASE}" == "icehouse" ]]; then
    "${CONFIGHELPER}" set "${CONFIGFILE}" "token" "driver" "keystone.token.backends.sql.Token"
fi

if [[ "${OPENSTACK_RELEASE}" == "juno" ]]; then
    "${CONFIGHELPER}" set "${CONFIGFILE}" "token" "driver" "keystone.token.persistence.backends.sql.Token"
fi

if [[ "${OPENSTACK_RELEASE}" == "kilo" ]]; then
    "${CONFIGHELPER}" set "${CONFIGFILE}" "memcache" "servers" "localhost:11211"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "token" "provider" "keystone.token.providers.uuid.Provider"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "token" "driver" "keystone.token.persistence.backends.memcache.Token"
    "${CONFIGHELPER}" set "${CONFIGFILE}" "revoke" "driver" "keystone.contrib.revoke.backends.sql.Revoke"
fi

keystone-manage db_sync

rm -fv /var/lib/keystone/keystone.db

if [[ "kilo" == "${OPENSTACK_RELEASE}" ]]; then
    cat> /etc/apache2/sites-available/wsgi-keystone.conf<<EOF
Listen 5000
Listen 35357

<VirtualHost *:5000>
    WSGIDaemonProcess keystone-public processes=5 threads=1 user=keystone display-name=%%{GROUP}
    WSGIProcessGroup keystone-public
    WSGIScriptAlias / /var/www/cgi-bin/keystone/main
    WSGIApplicationGroup %%{GLOBAL}
    WSGIPassAuthorization On
    <IfVersion >= 2.4>
      ErrorLogFormat "%%{cu}t %%M"
    </IfVersion>
    LogLevel info
    ErrorLog /var/log/apache2/keystone-error.log
    CustomLog /var/log/apache2/keystone-access.log combined
</VirtualHost>

<VirtualHost *:35357>
    WSGIDaemonProcess keystone-admin processes=5 threads=1 user=keystone display-name=%%{GROUP}
    WSGIProcessGroup keystone-admin
    WSGIScriptAlias / /var/www/cgi-bin/keystone/admin
    WSGIApplicationGroup %%{GLOBAL}
    WSGIPassAuthorization On
    <IfVersion >= 2.4>
      ErrorLogFormat "%%{cu}t %%M"
    </IfVersion>
    LogLevel info
    ErrorLog /var/log/apache2/keystone-error.log
    CustomLog /var/log/apache2/keystone-access.log combined
</VirtualHost>
EOF

    ln -fs /etc/apache2/sites-available/wsgi-keystone.conf /etc/apache2/sites-enabled

    mkdir -pv /var/www/cgi-bin/keystone

    for FILE in /var/www/cgi-bin/keystone/main /var/www/cgi-bin/keystone/admin; do

        cat >"${FILE}" <<EOF
import os
from keystone.server import wsgi as wsgi_server
name = os.path.basename(__file__)
application = wsgi_server.initialize_application(name)
EOF
    done

    chown -R keystone:keystone /var/www/cgi-bin/keystone
    chmod 0755 /var/www/cgi-bin/keystone/*

    service apache2 restart
else
    chmod 0777 /var/run/screen

    sync

    ps axufwwwwwwwwwww | grep -v grep | grep keystone | awk '{print $2;}' | xargs -n1 --no-run-if-empty kill -9 || true

    chown -R keystone:keystone /var/lib/keystone

    sleep 2

    ps axufwwwwwwwwwww | grep -v grep | grep keystone || screen -S keystone -d -m -- start-stop-daemon --start --chuid keystone --chdir /var/lib/keystone --name keystone --exec /usr/bin/keystone-all

    sleep 2

    ps axufwwwwwwwwwww | grep -v grep | grep keystone
fi

""" % (
        metadata.config["debug"],
        metadata.config["verbose"],
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.config["constrictor"],
        metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"],
        metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_rabbitmq')
def stage6_container_openstack_rabbitmq():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure(["rabbitmq-server"])

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

RABBIT_USER="osrabbit"

/etc/init.d/rabbitmq-server stop || true

/etc/init.d/rabbitmq-server start

rabbitmqctl change_password guest "${RABBIT_PASS}"

rabbitmqctl set_permissions -p / "guest" ".*" ".*" ".*"

rabbitmqctl change_password "${RABBIT_USER}" "${RABBIT_PASS}" || \
    rabbitmqctl add_user "${RABBIT_USER}" "${RABBIT_PASS}"

rabbitmqctl set_permissions -p / "${RABBIT_USER}" ".*" ".*" ".*"

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read()
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_mysql')
def stage6_container_openstack_mysql_create_databases():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    for service in metadata.services:
        puts(green("creating database for service %s" % service))

        run("""
if [[ "%s" == "True" ]] ; then set -x; fi

set -e

#
# initialize the password cache
#
%s

SERVICE_ACCOUNT="%s"
SERVICE_PASSWORD="${%s_DBPASS}"

# TODO test and enable this
#if [[ "" == "${SERVICE_PASSWORD}" ]]; then
#    exit 0
#fi

mysql -uroot <<EOF

CREATE DATABASE IF NOT EXISTS ${SERVICE_ACCOUNT};

GRANT ALL PRIVILEGES ON ${SERVICE_ACCOUNT}.* TO '${SERVICE_ACCOUNT}'@'localhost' IDENTIFIED BY '${SERVICE_PASSWORD}';

GRANT ALL PRIVILEGES ON ${SERVICE_ACCOUNT}.* TO '${SERVICE_ACCOUNT}'@'%%' IDENTIFIED BY '${SERVICE_PASSWORD}';

EOF

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        service,
        service.upper()
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_mysql')
def stage6_container_openstack_mysql():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

export MYSQL_PASSWORD="${MYSQL_DATABASE_PASSWORD}"

export DEBIAN_FRONTEND=noninteractive

debconf-set-selections<<EOF

mariadb-server-5.5 mysql-server/root_password password ${MYSQL_PASSWORD}
mariadb-server-5.5 mysql-server/root_password_again password ${MYSQL_PASSWORD}

mariadb-server-5.6 mysql-server/root_password password ${MYSQL_PASSWORD}
mariadb-server-5.6 mysql-server/root_password_again password ${MYSQL_PASSWORD}

mysql-server-5.5 mysql-server/root_password password ${MYSQL_PASSWORD}
mysql-server-5.5 mysql-server/root_password_again password ${MYSQL_PASSWORD}

mysql-server-5.6 mysql-server/root_password password ${MYSQL_PASSWORD}
mysql-server-5.6 mysql-server/root_password_again password ${MYSQL_PASSWORD}

EOF

DEBIAN_FRONTEND=noninteractive apt-get -q --yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install mariadb-server || true

mkdir -pv /var/lib/mysql
touch /var/lib/mysql/debian-x.flag

dpkg --configure -a

apt-get -f install

DEBIAN_FRONTEND=noninteractive apt-get -q --yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install mariadb-server

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read()
    ))

    cuisine.package_ensure("python-mysqldb")

    configfile = "/etc/mysql/my.cnf"

    cuisine.file_write(configfile, """
[client]
port = 3306
socket = /var/run/mysqld/mysqld.sock

[mysqld_safe]
socket = /var/run/mysqld/mysqld.sock
nice = 0

[mysqld]
max_connections = 10000
open-files-limit = 100000

user = mysql
pid-file = /var/run/mysqld/mysqld.pid
socket = /var/run/mysqld/mysqld.sock
port = 3306
basedir = /usr
datadir = /var/lib/mysql
tmpdir = /tmp
lc-messages-dir = /usr/share/mysql
skip-external-locking
bind-address = %s
key_buffer = 16M
max_allowed_packet = 16M
thread_stack = 192K
thread_cache_size = 8
myisam-recover = BACKUP
query_cache_limit = 1M
query_cache_size = 16M
log_error = /var/log/mysql/error.log
expire_logs_days = 10
max_binlog_size = 100M

default-storage-engine = innodb

innodb_file_per_table

collation-server = utf8_general_ci

init-connect = 'SET NAMES utf8'

character-set-server = utf8

[mysqldump]
quick
quote-names
max_allowed_packet = 16M

[mysql]

[isamchk]
key_buffer = 16M
!includedir /etc/mysql/conf.d/

""" % metadata.containers[metadata.roles["container_openstack_mysql"][0]]["ip"])

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

export MYSQL_PASSWORD="${MYSQL_DATABASE_PASSWORD}"

if [[ ! -f "/root/.my.cnf" ]]; then
    cat >"/root/.my.cnf"<<EOF
[client]
  user = root
  password = ${MYSQL_PASSWORD}
EOF
fi

service mysql restart

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read()
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

