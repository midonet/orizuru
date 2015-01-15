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
class midonet_repository {
  define install()
  {
    package{ "curl":
      ensure => "latest"
    }
  }

  define configure($username = "unknown", $password = "unknown", $midonet_flavor = 'MEM', $midonet_version = '1.7', $rhel_version = '7', $midonet_openstack_plugin_version = 'juno', $os_release = 'trusty')
  {
    if $midonet_flavor == "MEM"
    {
      if $::osfamily == "RedHat"
      {
        # MEM RHEL
        file {"/etc/yum.repos.d/midokura.repo":
          ensure => "file",
          path => "/etc/yum.repos.d/midokura.repo",
          content => template("midonet_repository/etc/yum.repos.d/midokura.repo.erb"),
          mode => "0644",
          owner => "root",
          group => "root",
        }
      }
      else
      {
        # MEM UBUNTU
        exec {"${module_name}__install_package_key_on_osfamily_Debian":
          command => "/usr/bin/curl -k http://$username:$password@apt.midokura.com/packages.midokura.key | /usr/bin/apt-key add -",
          unless => "/usr/bin/apt-key list | /bin/grep 'info@midokura.jp'"
        }
        ->
        file {"/etc/apt/sources.list.d/midokura.list":
          ensure => "file",
          path => "/etc/apt/sources.list.d/midokura.list",
          content => template("midonet_repository/etc/apt/sources.list.d/midokura.list.erb"),
          mode => "0644",
          owner => "root",
          group => "root",
        }
      }
    }
    else
    {
      if $::osfamily == "RedHat"
      {
        # MOSS RHEL
        file {"/etc/yum.repos.d/midonet.repo":
          ensure => "file",
          path => "/etc/yum.repos.d/midonet.repo",
          content => template("midonet_repository/etc/yum.repos.d/midonet.repo.erb"),
          mode => "0644",
          owner => "root",
          group => "root",
        }
      }
      else
      {
        # MOSS UBUNTU
        exec {"${module_name}__install_package_key_on_osfamily_Debian":
          command => "/usr/bin/curl -k http://repo.midonet.org/packages.midokura.key | /usr/bin/apt-key add -",
          unless => "/usr/bin/apt-key list | /bin/grep 'ops@midokura.com'"
        }
        ->
        file {"/etc/apt/sources.list.d/midonet.list":
          ensure => "file",
          path => "/etc/apt/sources.list.d/midonet.list",
          content => template("midonet_repository/etc/apt/sources.list.d/midonet.list.erb"),
          mode => "0644",
          owner => "root",
          group => "root",
        }
      }
    }
  }

}

