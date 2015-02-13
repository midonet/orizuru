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
from fabric.operations import reboot
from fabric.colors import red
from fabric.utils import puts

Config(os.environ["CONFIGFILE"])

@parallel
@roles('all_servers')
def disks():
    run("""

cat>/etc/init/ttyS0.conf<<EOX
#
# ttyS0 - getty
#

start on stopped rc or RUNLEVEL=[12345]
stop on runlevel [!12345]

respawn
exec /sbin/getty -L 115200 ttyS0 vt102

EOX

start ttyS0

mkdir -pv /var/lib/docker
mkdir -pv /var/lib/nova

if [[ ! "$(ls -ali /dev/sdc)" == "" ]]; then
  mdadm --stop /dev/md0
  mdadm --stop /dev/md127
  dd if=/dev/zero of=/dev/sdb count=1000 bs=4096
  dd if=/dev/zero of=/dev/sdc count=1000 bs=4096
  yes | mdadm --create --verbose /dev/md127 --level=stripe --raid-devices=2 /dev/sdb /dev/sdc
  sync
  mkfs.ext4 /dev/md127

  cat>/etc/mdadm/mdadm.conf<<EOX
CREATE owner=root group=disk mode=0660 auto=yes
HOMEHOST <system>
MAILADDR root
EOX

  mdadm --detail --scan >> /etc/mdadm/mdadm.conf
  grep '/var/lib/docker' /etc/fstab || echo '/dev/md127 /var/lib/docker ext4 errors=remount-ro 0 1' >> /etc/fstab
  grep '/var/lib/nova' /etc/fstab || echo '/var/lib/docker /var/lib/nova none defaults,bind 0 0' >> /etc/fstab

  mount /var/lib/docker
  mount /var/lib/nova

else
  if [[ ! "$(ls -ali /dev/sdb1)" == "" ]]; then
    grep '/var/lib/docker' /etc/fstab || echo '/dev/sdb1 /var/lib/docker ext4 errors=remount-ro 0 1' >> /etc/fstab
    grep '/var/lib/nova' /etc/fstab || echo '/var/lib/docker /var/lib/nova none defaults,bind 0 0' >> /etc/fstab

    mount /var/lib/docker
    mount /var/lib/nova

  fi
fi

service docker.io restart
service nova-compute restart

exit 0

""")

