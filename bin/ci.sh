#!/bin/bash

make distclean; echo

make clean; echo

make 2>&1 | tee /tmp/$(date +%s).log

