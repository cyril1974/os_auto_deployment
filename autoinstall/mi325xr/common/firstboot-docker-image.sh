#!/bin/bash

# Docker image name and tag
IMAGE="rocm/device-metrics-exporter:v1.4.1"

# Path to the docker image tar file
IMAGE_TAR="/opt/firstboot/rocm-device-metrics-exporter.tar"

# Wait until Docker daemon is fully ready
until /usr/bin/docker info >/dev/null 2>&1; do
    sleep 1
done

# Exit if the image already exists
if /usr/bin/docker image inspect "$IMAGE" >/dev/null 2>&1; then
    exit 0
fi

# Exit if the image tar file does not exist
if [ ! -f "$IMAGE_TAR" ]; then
    exit 1
fi

# Load the Docker image from tar file
/usr/bin/docker load -i "$IMAGE_TAR"

# Delete the tar file
#rm -rf $IMAGE_TAR

# Start container
cd /home/mctadmin/ai-cluster-test/scripts/install
./install_device_metrics_exporter.sh
