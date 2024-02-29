#!/bin/bash
CONDA_HOME=$( cd -- "$( dirname -- "$( dirname -- "$(which conda)" )" )" &> /dev/null && pwd )
conda_env=llm-on-ray
source $CONDA_HOME/bin/activate $conda_env
node_ip=$(ip addr show eno1 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)
export no_proxy="$node_ip, localhost, $no_proxy"

echo $no_proxy
user=root
cd /root/xinyao/finetune_rag/llm-on-ray/
export LOG_LEVEL=info


#        command = '/root/miniconda3/envs/llm-ray/bin/ray status'
#import logging
#logging.basicConfig(
#    level=os.environ.get('LOGLEVEL', 'INFO').upper()
#)
python -u ui/start_ui.py --node_user_name $user --conda_env_name $conda_env --master_ip_port "$node_ip:6379"

