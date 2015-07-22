#!/bin/bash

make distclean; echo

make clean; echo

touch tmp/.SUCCESS_pipinstall

make 2>&1 | tee /tmp/orizuru_CI_$(date +%s).txt

