BGP
===

Implementing a BGP mock testbed in containers is hard.

We therefore recommend you do the following (manual steps):

For each network card in the gateways, add them to the namespace of the gateway midonet agent:

```
ip link set p3p1 netns docker_22065_midonet_gateway_gw001
```
(Your number for the namespace may vary)

Do this for all gateways you have with two NICs.

If you dont have a second nic in the gateway: bad luck, no BGP testbed.

Now we need to set up the bgpd on the gateway

```
root@trgbe:/etc/quagga# cat daemons
zebra=yes
bgpd=yes
ospfd=no
ospf6d=no
ripd=no
ripngd=no
isisd=no
babeld=no
root@trgbe:/etc/quagga# cat zebra.conf
hostname trgbe
password zebra
enable password zebra

root@trgbe:/etc/quagga# cat bgpd.conf
#
# bgpd.conf
#

hostname trgbe
password zebra
enable password zebra

log file /var/log/quagga/bgpd.log
log stdout

debug bgp events
debug bgp fsm
debug bgp as4
debug bgp filters
debug bgp keepalives
debug bgp updates
debug bgp zebra

router bgp 65000
 bgp router-id 192.168.6.1
 bgp cluster-id 192.168.6.1

 network 0.0.0.0/0

 neighbor 192.168.6.103 remote-as 65103
 neighbor 192.168.6.103 next-hop-self
 neighbor 192.168.6.103 update-source 192.168.6.1

 neighbor 192.168.6.104 remote-as 65104
 neighbor 192.168.6.104 next-hop-self
 neighbor 192.168.6.104 update-source 192.168.6.1

 neighbor 192.168.6.106 remote-as 65106
 neighbor 192.168.6.106 next-hop-self
 neighbor 192.168.6.106 update-source 192.168.6.1

 # only enable this on demand
 # neighbor ${MIDONET_BGP_IP} timers 1 3
 # neighbor ${MIDONET_BGP_IP} timers connect 1
```

The next thing you will do is set up ports and bgp sessions on the gateways.

Note that you cannot do this AFTER the installer has been finishing creating networks.
```
midonet> cleart
midonet> router list name 'MidoNet Provider Router'
midonet> router router0 add port address 192.168.6.103 net 192.168.6.0/24
midonet> port list device router0 address 192.168.6.103
midonet> host list name midonet_gateway_gw001
midonet> host host0 add binding port router router0 port port0 interface p3p1
midonet> quit
```
Do this port binding for every midonet gateway that has a second network card.

Now we create the actual BGP session to each bgp router you have:
```
midonet> cleart
midonet> router list name 'MidoNet Provider Router'
midonet> router router0 port list address 192.168.6.103
midonet> router router0 port port0 add bgp local-AS 65103 peer-AS 65000 peer 192.168.6.1
midonet> router router0 port port0 bgp bgp0 add route net 200.200.200.0/24
midonet> quit
```
Again, do this for every port you have, one session per port.

As usual this config is appropriate for conf/alex.yaml. Your settings may differ.

Finally, do not forget to remove the default route going through the fake uplink ports (which is the default option of this installer).

