#!/usr/bin/env bash

set -x

#SLURM_NODELIST_HET_GROUP_0=ip-10-53-94-255,ip-10-53-87-163
echo $SLURM_NODELIST_HET_GROUP_0

# Extract the list of nodes from the SLURM_NODELIST_HET_GROUP_0 environment variable
nodes=$(scontrol show hostname $SLURM_NODELIST_HET_GROUP_0)

# Loop through each node and launch the HTTP server using srun and Pyxis
echo "Launching HTTP servers on nodes: $nodes"
for node in $nodes; do
    echo "Launching on node: $node port 8080"
    srun --het-group=0 -N1 -w $node --container-image=nginxdemos/hello:0.4-plain-text \
      --container-mounts=$(pwd)/hello-plain-text.conf:/etc/nginx/conf.d/hello-plain-text.conf \
      nginx -g 'daemon off;' &
done

# Prepare the Envoy configuration file with the backend list
# Use Python to process the template and generate the config
echo "$nodes" | python3 -c "
import sys
backend_endpoints = '\\n'.join(
    f'              - endpoint: {{ address: {{ socket_address: {{ address: \"{node}\", port_value: 8080 }} }} }}'
    for node in sys.stdin.read().strip().splitlines()
)
with open('envoy-config-template.yaml') as template_file:
    sys.stdout.write(template_file.read().replace('{{BACKEND_ENDPOINTS}}', backend_endpoints))
" > envoy-config.yaml


# Launch Envoy on the node in SLURM_NODELIST_HET_GROUP_1
envoy_node=$(scontrol show hostname $SLURM_NODELIST_HET_GROUP_1)
echo "Launching Envoy on node: $envoy_node"
srun --het-group=1 -N1 -w $envoy_node --container-image=envoyproxy/envoy:v1.26.0 \
  --container-mounts=$(pwd)/envoy-config.yaml:/etc/envoy/envoy-config.yaml \
  /usr/local/bin/envoy -c /etc/envoy/envoy-config.yaml
wait
