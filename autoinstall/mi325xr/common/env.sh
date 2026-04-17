#!/bin/bash
# Environment Variables Configuration

# Set HIP environment variables
export HIP_FORCE_DEV_KERNARG=1
export HIP_VISIBLE_DEVICES=1,3,2,0,5,7,6,4

# Set HSA environment variables
export HSA_OVERRIDE_CPU_AFFINITY_DEBUG=0

# RCCL Settings for CPX Mode (commented out by default)
# export TORCH_NCCL_USE_TENSOR_REGISTER_ALLOCATOR_HOOK=1
# export RCCL_MSCCLPP_THRESHOLD=$((2*1024*1024*1024))
# export MSCCLPP_READ_ALLRED=1

# Restrict GPU visibility (commented out by default)
# export ROCR_VISIBLE_DEVICES=0,1,2,3,4,5,6,7

export LD_LIBRARY_PATH=/opt/rocm-7.2.0/lib
export PATH=$PATH:/opt/rocm-7.2.0/bin
export MPI_HOME=$HOME/works/rocHPL/tpl/openmpi
export LD_LIBRARY_PATH=$MPI_HOME/lib:$LD_LIBRARY_PATH
export PATH=$MPI_HOME/bin:$PATH

echo "MI3XX environment variables loaded successfully"
