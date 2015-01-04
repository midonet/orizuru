#!/bin/bash

for LOCAL_IP in $(ip a | grep 'inet ' | grep -v 'inet 127' | awk '{print $2;}' | awk -F'/' '{print $1;}'); do
    echo "${LOCAL_IP} $(hostname -f) $(hostname)"
done
