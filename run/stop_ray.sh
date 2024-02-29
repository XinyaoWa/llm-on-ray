#!/bin/bash
CONDA_HOME=$( cd -- "$( dirname -- "$( dirname -- "$(which conda)" )" )" &> /dev/null && pwd )

source $CONDA_HOME/bin/activate llm-on-ray
node_ip=$(ip addr show eno1 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)
#conda env list
ray stop

