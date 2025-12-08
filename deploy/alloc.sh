
set -x

WORKERS=${WORKERS:-4}
CPUS_PER_WORKER=${CPUS_PER_WORKER:-2}
MEM_PER_CPU=${MEM_PER_CPU:-100M}
TIME=${TIME:-1:30:00}
PARTITION=${PARTITION:-hopper-cpu}

salloc --time "$TIME" \
  --partition="$PARTITION" --nodes="$WORKERS" --cpus-per-task="$CPUS_PER_WORKER" --mem-per-cpu="$MEM_PER_CPU" : \
  --partition="$PARTITION" --nodes=1 --cpus-per-task=4 --mem-per-cpu=200M \
  bash

