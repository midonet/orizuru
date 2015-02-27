#!/bin/bash

#
# this is the configuration from the other side:
#
#Address:   192.168.6.21         11000000.10101000.00000110.000101 01
#Netmask:   255.255.255.252 = 30 11111111.11111111.11111111.111111 00
#Wildcard:  0.0.0.3              00000000.00000000.00000000.000000 11
#=>
#Network:   192.168.6.20/30      11000000.10101000.00000110.000101 00
#HostMin:   192.168.6.21         11000000.10101000.00000110.000101 01
#HostMax:   192.168.6.22         11000000.10101000.00000110.000101 10
#Broadcast: 192.168.6.23         11000000.10101000.00000110.000101 11
#Hosts/Net: 2                     Class C, Private Internet
#
#auto eth2
#iface eth2 inet static
#        network 192.168.7.20
#        netmask 255.255.255.252
#        address 192.168.7.21
#        broadcast 192.168.7.23
#
#auto eth3
#iface eth3 inet static
#        network 192.168.7.24
#        netmask 255.255.255.252
#        address 192.168.7.25
#        broadcast 192.168.7.27
#
#auto eth4
#iface eth4 inet static
#        network 192.168.7.28
#        netmask 255.255.255.252
#        address 192.168.7.29
#        broadcast 192.168.7.31
#
#hostname edge001
#password zebra
#enable password zebra
#
#log file /var/log/quagga/bgpd.log
#log stdout
#
#router bgp 65424
# bgp router-id 192.168.4.24
# bgp cluster-id 192.168.4.24
#
# neighbor 192.168.7.22 remote-as 65722
# neighbor 192.168.7.22 next-hop-self
# neighbor 192.168.7.22 update-source 192.168.7.21
#
# neighbor 192.168.7.26 remote-as 65726
# neighbor 192.168.7.26 next-hop-self
# neighbor 192.168.7.26 update-source 192.168.7.25
#
# neighbor 192.168.7.30 remote-as 65730
# neighbor 192.168.7.30 next-hop-self
# neighbor 192.168.7.30 update-source 192.168.7.29
#

#
# bgp routing example
#

/usr/bin/expect<<EOF 1>/dev/null 2>/dev/null
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }

expect "midonet> " { send "router router0 del port address 192.168.7.22 net 192.168.7.20/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.22 net 192.168.7.20/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.22 net 192.168.7.20/30\r" }

expect "midonet> " { send "router router0 del port address 192.168.7.26 net 192.168.7.24/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.26 net 192.168.7.24/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.26 net 192.168.7.24/30\r" }

expect "midonet> " { send "router router0 del port address 192.168.7.30 net 192.168.7.28/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.30 net 192.168.7.28/30\r" }
expect "midonet> " { send "router router0 del port address 192.168.7.30 net 192.168.7.28/30\r" }

expect "midonet> " { send "quit\r" }
EOF

echo

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 add port address 192.168.7.22 net 192.168.7.20/30\r" }
expect "midonet> " { send "router router0 add port address 192.168.7.26 net 192.168.7.24/30\r" }
expect "midonet> " { send "router router0 add port address 192.168.7.30 net 192.168.7.28/30\r" }
expect "midonet> " { send "quit\r" }
EOF

echo

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.7.22\r" }
expect "midonet> " { send "host list name gw001\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "router router0 add route dst 192.168.7.20/30 src 0.0.0.0/0 type normal port router0:port0\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65722 peer-AS 65424 peer 192.168.7.21\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 10.0.0.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF

echo

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.7.26\r" }
expect "midonet> " { send "host list name gw002\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "router router0 add route dst 192.168.7.24/30 src 0.0.0.0/0 type normal port router0:port0\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65726 peer-AS 65424 peer 192.168.7.25\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 10.0.0.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF

echo

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli
expect "midonet> " { send "cleart\r" }
expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }
expect "midonet> " { send "router router0 port list address 192.168.7.30\r" }
expect "midonet> " { send "host list name gw003\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface p3p1\r" }
expect "midonet> " { send "router router0 add route dst 192.168.7.28/30 src 0.0.0.0/0 type normal port router0:port0\r" }
expect "midonet> " { send "router router0 port port0 add bgp local-AS 65730 peer-AS 65424 peer 192.168.7.29\r" }
expect "midonet> " { send "router router0 port port0 bgp bgp0 add route net 10.0.0.0/24\r" }
expect "midonet> " { send "quit\r" }
EOF

echo

exit 0

