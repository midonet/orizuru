#!/bin/bash

#
# bgp routing example
#

for GW in $(seq 1 3); do

    /usr/bin/expect<<EOF 1>/dev/null 2>/dev/null
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }

expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 del port address 192.168.6.10${GW} net 192.168.6.0/24\r" }
expect "midonet> " { send "router router0 del port address 192.168.6.10${GW} net 192.168.6.0/24\r" }
expect "midonet> " { send "router router0 del port address 192.168.6.10${GW} net 192.168.6.0/24\r" }

expect "midonet> " { send "quit\r" }
EOF

    sleep 2

    /usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }

expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.10${GW} net 192.168.6.0/24\r" }

expect "midonet> " { send "port list device router0 address 192.168.6.10${GW}\r" }
expect "midonet> " { send "host list name gw00${GW}\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }

expect "midonet> " { send "router router0 add route dst 192.168.6.0/24 src 0.0.0.0/0 type normal port router0:port0\r" }

expect "midonet> " { send "router router0 port port0 add bgp local-AS 6510${GW} peer-AS 65254 peer 192.168.6.254\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 200.200.200.0/24\r" }

expect "midonet> " { send "quit\r" }
EOF

    sleep 2

done

exit 0

