#!/bin/bash
# For K8s Conf
swapoff -a
sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
modprobe overlay
modprobe br_netfilter
sysctl --system

# Create a done flag to ensure it only runs once
touch /var/lib/firstboot.done

# Disable all firstboot services
systemctl disable firstboot-bcm-nic-setup.service
systemctl disable firstboot-finalize.service
systemctl disable firstboot.target

