bugs
====

if you are running with containers you should not set an MTU higher than 1500 (this will yield about 200-300mbits on a gigabit wire)

for real performance you should look into conf/physical.yaml and enable uncontainered gateways and hypervisors

their traffic will not go through the tinc mesh and therefore you can increase the MTU then there

