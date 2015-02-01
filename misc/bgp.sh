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

#
# copy this to midonet_cli machine, adapt to your network and run it
#

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.103 net 192.168.6.0/24\r" }
expect "midonet> " { send "port list device router0 address 192.168.6.103\r" }
expect "midonet> " { send "host list name gw001\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "quit\r" }
EOF

for REMOTE in 12 13 14; do
  /usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.6.103\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65103 peer-AS 650${REMOTE} peer 192.168.6.${REMOTE}\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 200.200.200.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF
done

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.104 net 192.168.6.0/24\r" }
expect "midonet> " { send "port list device router0 address 192.168.6.104\r" }
expect "midonet> " { send "host list name gw002\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "quit\r" }
EOF

for REMOTE in 12 13 14; do
  /usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.6.104\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65104 peer-AS 650${REMOTE} peer 192.168.6.${REMOTE}\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 200.200.200.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF
done

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.106 net 192.168.6.0/24\r" }
expect "midonet> " { send "port list device router0 address 192.168.6.106\r" }
expect "midonet> " { send "host list name gw003\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "quit\r" }
EOF

for REMOTE in 12 13 14; do
  /usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.6.106\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65106 peer-AS 650${REMOTE} peer 192.168.6.${REMOTE}\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 200.200.200.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF
done

