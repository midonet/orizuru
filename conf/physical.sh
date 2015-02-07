#!/bin/bash

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.6.103 net 192.168.6.0/24\r" }
expect "midonet> " { send "port list device router0 address 192.168.6.103\r" }
expect "midonet> " { send "host list name gw001\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "router router0 add route dst 192.168.6.0/24 src 0.0.0.0/0 type normal port router0:port0\r" }
expect "midonet> " { send "router router0 add route dst 0.0.0.0/0 src 0.0.0.0/0 type normal port router0:port0 weight 100 gw 192.168.6.1\r" }
expect "midonet> " { send "quit\r" }
EOF

