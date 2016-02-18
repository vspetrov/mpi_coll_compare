#!/bin/bash
##SBATCH -N 4 --ntasks-per-node=24 --reservation=mlnx -J test --mail-user=valentinp@mellanox.com
#SBATCH -N 128 -p orion --ntasks-per-node=28 -J hcoll_barrier_scaling -t 360
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
set -x


#HPCX_PATH=/homeb/zam/valentin/workspace/hpcx
#source $HPCX_PATH/hpcx-init.sh
#hpcx_load
source /etc/profile.d/modules.sh
module load hpcx-gcc
which mpirun
export IMB_EXE=$HPCX_MPI_TESTS_DIR/imb/IMB-MPI1

export OSU_DIR=$HPCX_MPI_TESTS_DIR/osu-micro-benchmarks-5.2
osu_bench_list_full="barrier allreduce"
osu_bench_list_short="barrier allreduce"



nodes=$SLURM_NNODES
PPN=`echo $SLURM_TASKS_PER_NODE | cut --field=1  --delimiter=\(`
NP=$((nodes * PPN))

ulimit -s 10240
MPIRUN=$HPCX_MPI_DIR/bin/mpirun
args_ssh=" -mca plm_rsh_agent ssh -mca plm rsh"
args_noknem=" -x MXM_SHM_KCOPY_MODE=off"
#args_placement="--display-map --report-bindings"
args_placement=""
args="$args_placement --bind-to core -mca pml yalla"

device=mlx5_3:1
args_mxm="-x MXM_LOG_LEVEL=fatal -x MXM_IB_PORTS=$device"

args_hcoll="-x HCOLL_ML_DISABLE_REDUCE=1 -x HCOLL_MAIN_IB=$device"
mpi_args="$args_ssh $args_noknem $args_placement $args $args_mxm $args_hcoll"
single_run() {
###########################
	run_name=$1
        params=$3
        ppn=$2
        osu_bench_list=$4
	bench_p=$5
###########################
	if [ $ppn -eq 1 ]; then
		n_end=$nodes
		n_step=16
		n_start=16
	elif [ $ppn -eq $PPN ]; then
		n_end=$NP
		n_step=$((16*PPN))
		n_start=$((16*PPN))
	fi

###########################
	filename="rst/${run_name}_ppn${ppn}.txt"
	rm -rf $filename
	echo "Running setup $run_name..."
	for ((np=$n_start; $np <= $n_end; np=$((np+n_step)) )); do
        	echo "benchrun_NP: $np" | tee -a $filename
# cmd="mpirun -np $np --npernode $ppn -hostfile $hostfile -mca pml yalla -x MXM_LOG_LEVEL=FATAL $params $IMB_EXE -npmin $np  Allreduce Barrier Allgather"
		for bench in $osu_bench_list ; do
                        cmd="$MPIRUN -np $np --npernode $ppn $mpi_args $params $OSU_DIR/osu_$bench -m 4:8 -f $bench_p"
			echo $cmd >> $filename
			$cmd 2>&1 | tee -a $filename
		done
	done
}

# export I_MPI_ADJUST_ALLTOALL=1
# single_run "daplud" "-genv I_MPI_FABRICS=shm:dapl -genv I_MPI_DAPL_UD=1"
# single_run "mxm" "-genv I_MPI_FABRICS=shm:tmi"


MCAST_ON="-x HCOLL_MCAST_ENABLE_ALL=1 -x HCOLL_MCAST_NP=0"
MCAST_OFF="-x HCOLL_MCAST_ENABLE_ALL=0"
LBS_ON="-x HCOLL_ML_LARGE_BUFFER_SUPPORT=1  -x HCOLL_ML_LARGE_BUFFER_COUNT=$PPN"
LBS_OFF="-x HCOLL_ML_LARGE_BUFFER_SUPPORT=0"
ALLTOALLV="-x HCOLL_ML_DISABLE_ALLTOALLV=0"
IBOFFLOAD_FLAT="-x HCOLL_BCOL=iboffload,mlnx_p2p -x HCOLL_SBGP=ibnet,p2p $MCAST_OFF"
IBOFFLOAD_2LVL="-x HCOLL_BCOL=basesmuma,iboffload,mlnx_p2p -x HCOLL_SBGP=basesmuma,ibnet,p2p $MCAST_OFF"
IBOFFLOAD_3LVL="-x HCOLL_BCOL=basesmuma,basesmuma,iboffload,mlnx_p2p -x HCOLL_SBGP=basesmsocket,basesmuma,ibnet,p2p $MCAST_OFF"

run_default() {
    for run_ppn in 1 $PPN; do
        single_run "hcoll" $run_ppn "-mca coll_hcoll_enable 1" "$osu_bench_list_short" ""
        single_run "hcoll_ss" $run_ppn "-mca coll_hcoll_enable 1" "$osu_bench_list_short" "-x 10000 -i 10000"
    done
}

run_iboffload() {
    for run_ppn in 1 $PPN; do
        single_run "hcoll_iboffload_flat" $run_ppn "-mca coll_hcoll_enable 1 $IBOFFLOAD_FLAT" "$osu_bench_list_short"
        single_run "hcoll_iboffload_3lvl" $run_ppn "-mca coll_hcoll_enable 1 $IBOFFLOAD_3LVL" "$osu_bench_list_short"
    done
}

echo "Running default"
run_default

#echo "Running iboffload"
#run_iboffload

set +x
