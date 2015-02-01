#!/bin/bash

nova boot \
  --flavor "$(nova flavor-list | grep m1.medium | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
  --image "$(nova image-list | grep trusty | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
  --key-name "$(nova keypair-list | grep "$(hostname)_root_ssh_id_rsa_nova" | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
  --security-groups "$(neutron security-group-list | grep testing | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
  --nic net-id="$(neutron net-list | grep internal | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    "test$(date +%%s)"

