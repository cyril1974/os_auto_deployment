#!/bin/bash
echo "Setting up MI3XX Server policy routing..."

sudo ip route add default via 192.168.21.7 metric 99

