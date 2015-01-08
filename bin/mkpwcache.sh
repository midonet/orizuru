#!/bin/bash

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

for PASS in MYSQL_DATABASE_PASSWORD \
  RABBIT_PASS \
  KEYSTONE_DBPASS \
  DEMO_PASS \
  ADMIN_PASS \
  ADMIN_TOKEN \
  GLANCE_DBPASS \
  GLANCE_PASS \
  NOVA_DBPASS \
  NOVA_PASS \
  DASH_DBPASS \
  CINDER_DBPASS \
  CINDER_PASS \
  NEUTRON_DBPASS \
  NEUTRON_PASS \
  HEAT_DBPASS \
  HEAT_PASS \
  CEILOMETER_DBPASS \
  CEILOMETER_PASS \
  TROVE_DBPASS \
  TROVE_PASS \
  MIDONET_PASS \
  NEUTRON_METADATA_SHARED_SECRET
do
  echo "export ${PASS}=$(openssl rand -hex 10)"
done

exit 0

