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
class midonet_manager18 {
  define install($package_name = "midonet-manager", $install_dir = "/var/www/html/midonet-manager")
  {
    package {"$package_name":
      ensure => "latest"
    }
    ->
    exec { "mv /var/www/midonet-manager $install_dir":
      path => "/bin:/usr/bin",
      onlyif => "test -d /var/www/midonet-manager && test ! -d $install_dir"
    }
  }

  define configure($rest_api_base = "http://localhost:8080", $install_dir = "/var/www/html/midonet-manager") {
    if $::osfamily == "RedHat" {
      $root_url = "/html/midonet-manager/"
    } else {
      $root_url = "/midonet-manager/"
    }

    file {"$install_dir/config/client.js":
      ensure => "file",
      path => "$install_dir/config/client.js",
      content => template("midonet_manager/var/www/html/midonet-manager/config/client.js.erb"),
      mode => "0644",
      owner => "root",
      group => "root",
    }
  }

  define start($install_dir = "/var/www/html/midonet-manager")
  {
    if $::osfamily == "RedHat" {
      $webserver = "httpd"
    } else {
      $webserver = "apache2"
    }

    service {"$webserver":
      ensure => "running",
      subscribe => File["$install_dir/config/client.js"]
    }
  }

}

