"""Flower federated learning server.

Run: python -m ml.federated.server --rounds 200 --min_clients 10
"""

import argparse
import logging

import flwr as fl
import torch

from ..models.neuroguard_model import NeuroGuardModel
from .strategy.adaptive_fedavg import AdaptiveFedAvg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def get_initial_parameters() -> fl.common.Parameters:
    model = NeuroGuardModel()
    weights = [val.cpu().numpy() for val in model.state_dict().values()]
    return fl.common.ndarrays_to_parameters(weights)


def run_server(args) -> None:
    strategy = AdaptiveFedAvg(
        min_fit_clients=args.min_clients,
        min_available_clients=args.min_clients,
        fraction_fit=0.2,
        fraction_evaluate=0.1,
        min_epsilon_per_round=0.5,
    )
    strategy.initial_parameters = get_initial_parameters()

    fl.server.start_server(
        server_address=f"0.0.0.0:{args.port}",
        config=fl.server.ServerConfig(num_rounds=args.rounds),
        strategy=strategy,
        grpc_max_message_length=1024 * 1024 * 512,  # 512 MB
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--min_clients", type=int, default=10)
    parser.add_argument("--port", type=int, default=8080)
    run_server(parser.parse_args())
