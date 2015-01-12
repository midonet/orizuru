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
class midolman {
  define install($openstack_version = "icehouse")
  {
    if $::osfamily == 'RedHat' {
      $packages = ["midolman"]
    } else {
      $packages = ["openjdk-7-jre-headless", "midolman"]
    }

    if $::lsbdistid == 'Ubuntu' and $::lsbdistcodename == 'precise' {
      exec {"${module_name}__add_cloud_archive_on_Ubuntu_precise":
        command => "/bin/echo | /usr/bin/add-apt-repository cloud-archive:$openstack_version",
        unless => "/usr/bin/test -f /etc/apt/sources.list.d/cloudarchive-$openstack_version.list"
      }
      ->
      package {$packages:
        ensure => "latest"
      }
    }
    else
    {
      package {$packages:
        ensure => "latest"
      }
    }
  }

  define configure($zookeepers = "127.0.0.1",
    $cassandras = "127.0.0.1",
    $cluster_name = "midonet",
    $max_heap_size = "2400M",
    $heap_newsize = "1600M")
  {
    if $::osfamily == 'RedHat' {
      $bgpd_binary = '/usr/sbin/'
    } else {
      $bgpd_binary = '/usr/lib/quagga/'
    }

    file {"/etc/midolman/midolman.conf":
      ensure => "file",
      path => "/etc/midolman/midolman.conf",
      content => template("midolman/etc/midolman/midolman.conf.erb"),
      mode => "0644",
      owner => "root",
      group => "root",
    }

    file {"/etc/midolman/midolman-env.sh":
      ensure => "file",
      path => "/etc/midolman/midolman-env.sh",
      content => template("midolman/etc/midolman/midolman-env.sh.erb"),
      mode => "0644",
      owner => "root",
      group => "root",
    }
  }

  define start()
  {
    service {"midolman":
      ensure => "running",
        subscribe => File["/etc/midolman/midolman.conf",
                          "/etc/midolman/midolman-env.sh"]
    }
  }

}

