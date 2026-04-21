#!/bin/bash

# Create a done flag to ensure it only runs once
touch /var/lib/firstboot.done

# Disable all firstboot services
systemctl disable firstboot-bcm-nic-setup.service
systemctl disable firstboot-finalize.service
systemctl disable firstboot.target
