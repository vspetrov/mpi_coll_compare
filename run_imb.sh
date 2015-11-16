#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
set -x

module load hpcx-gcc
export IMB_EXE=$HPCX_MPI_TESTS_DIR/IMB-4.0/IMB-MPI1
hostfile=$1
NODE_NUM=`cat $hostfile | wc -l`


single_run() {
run_name=$1
params=$3
ppn=$2
filename="rst/${run_name}_ppn${ppn}.txt"
rm -rf $filename
echo "Running setup $run_name..."
for ((n=2; $n <= $NODE_NUM; n=$((n+2)) )); do
    np=$((ppn*n))
    echo "NP: $np"
    cmd="mpirun -np $np --npernode $ppn -hostfile $hostfile -mca pml yalla -x MXM_LOG_LEVEL=FATAL $params $IMB_EXE -npmin $np  Allreduce Alltoallv"
    echo $cmd >> $filename
    $cmd 2>&1 | tail -n +40 | tee -a $filename
done
}

# export I_MPI_ADJUST_ALLTOALL=1
# single_run "daplud" "-genv I_MPI_FABRICS=shm:dapl -genv I_MPI_DAPL_UD=1"
# single_run "mxm" "-genv I_MPI_FABRICS=shm:tmi"

PPN=8

MCAST_ON="-x HCOLL_MCAST_ENABLE_ALL=1 -x HCOLL_MCAST_NP=0"
MCAST_OFF="-x HCOLL_MCAST_ENABLE_ALL=0"
LBS_ON="-x HCOLL_ML_LARGE_BUFFER_SUPPORT=1  -x HCOLL_ML_LARGE_BUFFER_COUNT=$PPN"
LBS_OFF="-x HCOLL_ML_LARGE_BUFFER_SUPPORT=0"


single_run "ompi_tuned" $PPN "-mca coll_hcoll_enable 0"
single_run "hcoll_mcast_on_lbs_off"  $PPN "-mca coll_hcoll_enable 1 $MCAST_ON $LBS_OFF"
single_run "hcoll_mcast_on_lbs_on" $PPN "-mca coll_hcoll_enable 1 $MCAST_ON $LBS_ON"



rm $hostfile

set +x
