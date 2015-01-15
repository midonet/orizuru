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
class hadoop-zookeeper {
  define install()
  {
    if $::osfamily == "RedHat" {
      $packages = ["zookeeper"]
    } else {
      $packages = ["zookeeper", "zookeeperd"]
    }

    package { $packages:
      ensure => "latest"
    }
  }

  define configure($myid, $ensemble = ["localhost:2888:3888"])
  {
    if $::osfamily == "RedHat" {
      $zkconfdir = "/etc/zookeeper"
      $zkmyiddir = "/var/lib/zookeeper"
    } else {
      $zkconfdir = "/etc/zookeeper/conf"
      $zkmyiddir = $zkconfdir
    }

    file { "$zkconfdir/zoo.cfg":
      content => template("hadoop-zookeeper/etc/zookeeper/zoo.cfg.erb"),
      require => Package["zookeeper"],
    }
    ->
    file { "$zkmyiddir/myid":
      content => inline_template("<%= @myid %>"),
      require => Package["zookeeper"],
    }
  }

  define start()
  {
    if $::osfamily == "RedHat" {
      $zkconfdir = "/etc/zookeeper"
      $zkmyiddir = "/var/lib/zookeeper"
    } else {
      $zkconfdir = "/etc/zookeeper/conf"
      $zkmyiddir = $zkconfdir
    }

    service { "zookeeper":
      ensure => running,
      require => Package["zookeeper"],
      subscribe => [ File["$zkconfdir/zoo.cfg"],
                     File["$zkmyiddir/myid"] ],
      hasrestart => true,
      hasstatus => true,
    }
  }

}

