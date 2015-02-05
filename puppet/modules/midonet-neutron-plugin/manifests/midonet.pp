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
class neutron::plugins::midonet (
  $plugin_package             = 'python-neutron-plugin-midonet',
  $core_plugin                = 'midonet.neutron.plugin.MidonetPluginV2',
  $plugin_path                = '/etc/neutron/plugins/midonet/midonet.ini'
  $midonet_api_address        = '127.0.0.1',
  $midonet_api_port           = '8081',
  $midonet_keystone_username,
  $midonet_keystone_password,
  $keystone_admin_tenant_name = 'admin'
  ){
    include neutron::server

    Package { $plugin_package:
      name   => $plugin_package,
      ensure => present,
    }

    if $::osfamily == 'ubuntu' {
    file_line { '/etc/default/neutron-server:NEUTRON_PLUGIN_CONFIG':
      path    => '/etc/default/neutron-server',
      match   => '^NEUTRON_PLUGIN_CONFIG=(.*)$',
      line    => "NEUTRON_PLUGIN_CONFIG=${plugin_path}",
      require => [ Package['neutron-server'], Package[$plugin_package] ],
      notify  => Service['neutron-server']
      }
    }

    if $::osfamily == "redhat" {
      file { '/etc/neutron/plugin.ini':
        ensure => link,
        owner => 'root',
        group => 'neutron',
        mode => '0640',
        target => $plugin_path,
        require => [ Package['neutron-server'], Package[$plugin_package] ],
        notify  => Service['neutron-server']
      }
    }

    file_line { '/etc/neutron/neutron.conf:sql_connection':
      path    => '/etc/neutron/neutron.conf',
      match   => '^sql_connection=(.*)$',
      line    => "sql_connection=${::neutron::server::database_connection}",
      require => [ Package['neutron-server'], Package[$plugin_package] ],
      notify  => Service['neutron-server'],
      }
    }

    file_line { '/etc/neutron/neutron.conf:core_plugin':
      path    => '/etc/neutron/neutron.conf',
      match   => '^core_plugin=(.*)$',
      line    => "core_plugin=${core_plugin}",
      require => [ Package['neutron-server'], Package[$plugin_package] ],
      notify  => Service['neutron-server'],
      }
    }

    concat { '/etc/neutron/neutron.conf':
      ensure  => present,
      replace => true,
      path    => '/etc/neutron/neutron.conf'
      backup  => '/etc/neutron/neutron.conf.backup'
      }

    concat::fragment { 'original_neutron_conf':
      target => '/etc/neutron/neutron.conf',
      source => '/etc/neutron/neutron.conf',
      order  => '1'
      }

    concat::fragment { 'midokura_config_lines':
      target => '/etc/neutron/neutron.conf',
      source => template('/etc/neutron/midokura_config_lines.erb'),
      order  => '2'
      }

    file { '/etc/neutron/plugins/midonet':
      ensure => directory,
      owner  => 'root',
      group  => 'neutron',
      mode   => '0640'
      }

    file { '/etc/neutron/plugins/midonet/midonet.ini':
      ensure  => file,
      owner   => 'root',
      group   => 'neutron',
      mode    => '0640',
      content => template(/etc/neutron/plugins/midonet/midonet.ini.erb),
      notify  => Service[("midolman"), ("neutron")]
      }
    }

  }
