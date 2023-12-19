import ray
from inference_config import ModelDescription, InferenceConfig, all_models
import sys
from utils import get_deployment_actor_options
from pydantic_yaml import parse_yaml_raw_as
from api_server import serve_run
from api_server_openai import openai_serve_run
from predictor_deployment import PredictorDeployment

# make it unittest friendly
def main(argv=None):
    # args
    import argparse
    parser = argparse.ArgumentParser("Model Serve Script", add_help=False)
    parser.add_argument("--config_file", type=str, help="inference configuration file in YAML. If specified, all other arguments are ignored")
    parser.add_argument("--model", default=None, type=str, help="model name or path")
    parser.add_argument("--tokenizer", default=None, type=str, help="tokenizer name or path")
    parser.add_argument("--port", default=8000, type=int, help="the port of deployment address")
    parser.add_argument("--route_prefix", default="custom_model", type=str, help="the route prefix for HTTP requests.")
    parser.add_argument("--cpus_per_worker", default="24", type=int, help="cpus per worker")
    parser.add_argument("--gpus_per_worker", default=0, type=float, help="gpus per worker, used when --device is cuda")
    parser.add_argument("--hpus_per_worker", default=0, type=float, help="hpus per worker, used when --device is hpu")
    parser.add_argument("--deepspeed", action='store_true', help="enable deepspeed inference")
    parser.add_argument("--workers_per_group", default="2", type=int, help="workers per group, used with --deepspeed")
    parser.add_argument("--ipex", action='store_true', help="enable ipex optimization")
    parser.add_argument("--device", default="cpu", type=str, help="cpu, xpu, hpu or cuda")
    parser.add_argument("--serve_local_only", action="store_true", help="only support local access to url")
    parser.add_argument("--openai_api", action="store_true", help="whether to serve OpenAI-compatible API")

    args = parser.parse_args(argv)

    # serve all pre-defined models, or model from MODEL_TO_SERVE env, if no model argument specified
    if args.model is None and args.config_file is None:
        model_list = all_models
    else:
        # config_file has precedence over others
        if args.config_file:
            print("reading from config file, " + args.config_file)
            with open(args.config_file, "r") as f:
                infer_conf = parse_yaml_raw_as(InferenceConfig, f)
        else: # args.model should be set
            print("reading from command line, " + args.model)
            model_desc = ModelDescription()
            model_desc.model_id_or_path = args.model
            model_desc.tokenizer_name_or_path = args.tokenizer if args.tokenizer is not None else args.model
            infer_conf = InferenceConfig(model_description=model_desc)
            infer_conf.host = "127.0.0.1" if args.serve_local_only else "0.0.0.0"
            infer_conf.port = args.port
            rp = args.route_prefix if args.route_prefix else "custom_model"
            infer_conf.route_prefix = "/{}".format(rp)
            infer_conf.name = rp
            infer_conf.ipex.enabled = args.ipex
        model_list = {}
        model_list[infer_conf.name] = infer_conf

    ray.init(address="auto")

    deployment_map = {}
    for model_id, infer_conf in model_list.items():
        ray_actor_options = get_deployment_actor_options(infer_conf)
        deployment_map[model_id] = PredictorDeployment.options(ray_actor_options=ray_actor_options).bind(infer_conf)

    if args.openai_api:
        # all models are served under the same URL and then accessed through model_id, so it needs to pass in a unified URL.
        host = "127.0.0.1" if args.serve_local_only else "0.0.0.0"
        rp = args.route_prefix if args.route_prefix else "custom_model"
        route_prefix = "/{}".format(rp)
        openai_serve_run(deployment_map, host, route_prefix, args.port)
    else:
        # models can be served to custom URLs according to the configuration.
        serve_run(deployment_map, model_list)

if __name__ == "__main__":
    main(sys.argv[1:])
