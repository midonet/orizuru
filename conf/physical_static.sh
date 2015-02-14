#!/bin/bash

#
# static routing example
#

# for E in $(seq 1 3); do
for E in $(seq 1 1); do

        /usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 del port address 192.168.6.10${E} net 192.168.6.0/24\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.10${E} net 192.168.6.0/24\r" }
expect "midonet> " { send "port list device router0 address 192.168.6.10${E}\r" }
expect "midonet> " { send "host list name gw00${E}\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "router router0 add route dst 0.0.0.0/0 src 0.0.0.0/0 type normal port router0:port0\r" }
expect "midonet> " { send "quit\r" }

EOF

done

exit 0

