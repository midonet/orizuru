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

from fabric.api import *

class Daemon(object):
    def __init__(self, configfile):
        pass

    def start(self, command, daemon_string, timeout=15):
        run("""

echo screen session for command

""")

        self.poll(daemon_string, timeout)

    @classmethod
    def poll(cls, daemon_string, timeout=15):
        run("""
DAEMON_STRING="%s"
TIMEOUT="%i"

RETURNCODE=1

for i in $(seq 1 "${TIMEOUT}"); do
    ALIVE="$(ps axufwwwwwwwwwwwwwwwwwwwwww | grep -v grep | grep "${DAEMON_STRING}")"

    if [[ "" == "${ALIVE}" ]]; then
        RETURNCODE=1
    else
        RETURNCODE=0
        continue
    fi

    sleep 2
done

exit "${RETURNCODE}"

""" % (daemon_string, timeout))

class Puppet(object):

    def __init__(self, configfile):
        pass

    @classmethod
    def apply(cls, module_name, args_vector, metadata):

        args_array = []
        for key in args_vector:
            args_array.append("%s => %s" % (key, args_vector[key]))

        args_string = ", ".join(args_array)

        if metadata.config['debug'] == True:
            debug_flag = '--debug'
        else:
            debug_flag = ''

        if metadata.config['verbose'] == True:
            verbose_flag = '--verbose'
        else:
            verbose_flag = ''

        if module_name == 'midonet::repository':
            pass
        else:
            xargs = {}

            if "OS_MIDOKURA_REPOSITORY_USER" in os.environ:
                xapt = 'http://%s:%s@apt.midokura.com' % (os.environ["OS_MIDOKURA_REPOSITORY_USER"], os.environ["OS_MIDOKURA_REPOSITORY_PASS"])
                xargs['midonet_stage'] = "'trusty'"
                xargs['openstack_release'] = "'%s'" % metadata.config["openstack_release"]
                xargs['midonet_repo'] = "'%s/midonet/v%s/stable'" % (xapt, metadata.config["midonet_mem_version"])
                xargs['midonet_openstack_repo'] = "'%s/openstack/%s/stable'" % (xapt, metadata.config["midonet_mem_openstack_plugin_version"])
                xargs['midonet_key'] = "'054314CD'"
                xargs['midonet_key_url'] = "'%s/packages.midokura.key'" % xapt
            else:
                xapt = 'http://repo.midonet.org'
                xargs['midonet_stage'] = "'stable'"
                xargs['openstack_release'] = "'%s'" % metadata.config["openstack_release"]
                xargs['midonet_repo'] = "'%s/midonet/v%s'" % (xapt, metadata.config["midonet_oss_version"])
                xargs['midonet_openstack_repo'] = "'%s/openstack'" % xapt
                xargs['midonet_thirdparty_repo'] = "'%s/misc'" % xapt
                xargs['midonet_key'] = "'50F18FCF'"
                xargs['midonet_key_url'] = "'%s/packages.midokura.key'" % xapt

            repo_args = []

            for key in xargs:
                repo_args.append("%s => %s" % (key, xargs[key]))

            run("""
DEBUG="%s"
VERBOSE="%s"

cat >/tmp/node.pp<<EOF
node $(hostname) {
    class { 'midonet::repository':
        %s
    }
    ->
    class { '%s':
        %s
    }
}
EOF

puppet apply ${DEBUG} ${VERBOSE} -- /tmp/node.pp 2>&1

""" % (
        debug_flag,
        verbose_flag,
        ",".join(repo_args),
        module_name,
        args_string
    ))

