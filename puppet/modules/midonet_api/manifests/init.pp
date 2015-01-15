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
class midonet_api {
  define install()
  {
    if $::osfamily == "RedHat" {
      $jre_package = "java-1.7.0-openjdk"
    } else {
      $jre_package = "openjdk-7-jre-headless"
    }

    package {"$jre_package":
      ensure => "latest"
    }
    ->
    package {"tomcat6":
      ensure => "latest"
    }
    ->
    package {"midonet-api":
      ensure => "latest"
    }
    ->
    exec {"/bin/mkdir -pv /var/lib/tomcat7/webapps": }
    ->
    exec {"/bin/chown -Rv tomcat6:tomcat6 /var/lib/tomcat7": }
  }

  define configure($keystone_admin_token,
    $rest_api_base_url = "http://localhost:8080/midonet-api",
    $keystone_service_host = "127.0.0.1",
    $keystone_tenant_name = "admin",
    $zookeeper_hosts = "127.0.0.1",
    $midobrain_vxgw_enabled = "true")
  {
    file {"/usr/share/midonet-api/WEB-INF/web.xml":
      ensure => "file",
      path => "/usr/share/midonet-api/WEB-INF/web.xml",
      content => template("midonet_api/usr/share/midonet-api/WEB-INF/web.xml.erb"),
      mode => "0644",
      owner => "root",
      group => "root",
    }

    file {"/etc/tomcat6/Catalina/localhost/midonet-api.xml":
      ensure => "file",
      path => "/etc/tomcat6/Catalina/localhost/midonet-api.xml",
      source => "puppet:///modules/midonet_api/etc/tomcat6/Catalina/localhost/midonet-api.xml",
      mode => "0644",
      owner => "root",
      group => "root",
    }

    file {"/etc/default/tomcat6":
      ensure => "file",
      path => "/etc/default/tomcat6",
      source => "puppet:///modules/midonet_api/etc/default/tomcat6",
      mode => "0644",
      owner => "root",
      group => "root",
    }
  }

  define start()
  {
    service {"tomcat6":
      ensure => "running",
      subscribe => File["/usr/share/midonet-api/WEB-INF/web.xml",
                          "/etc/tomcat6/Catalina/localhost/midonet-api.xml",
                          "/etc/default/tomcat6"]
    }
  }

}

