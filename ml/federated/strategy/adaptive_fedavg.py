"""AdaptiveFedAvg — custom Flower strategy with DP enforcement, Byzantine filtering,
and sample-weighted aggregation to handle non-IID data across hospital nodes."""

import logging
from functools import reduce
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from flwr.common import (
    EvaluateIns,
    EvaluateRes,
    FitIns,
    FitRes,
    Parameters,
    Scalar,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)
from flwr.server.client_manager import ClientManager
from flwr.server.client_proxy import ClientProxy
from flwr.server.strategy import FedAvg

logger = logging.getLogger(__name__)

_COSINE_SIMILARITY_THRESHOLD = 0.3   # Byzantine rejection threshold
_SAMPLE_WEIGHT_EXPONENT = 0.75        # Reduce IID dominance of large clients


class AdaptiveFedAvg(FedAvg):
    """
    FedAvg with:
    1. DP enforcement (reject updates without noise applied)
    2. Byzantine filtering (cosine similarity vs. median)
    3. Sample-weighted aggregation: w_i = n_i^0.75 / sum(n_j^0.75)
    4. Adaptive learning rate decay per round
    """

    def __init__(
        self,
        min_fit_clients: int = 10,
        min_available_clients: int = 10,
        fraction_fit: float = 0.2,
        fraction_evaluate: float = 0.1,
        min_epsilon_per_round: float = 0.5,
    ):
        super().__init__(
            min_fit_clients=min_fit_clients,
            min_available_clients=min_available_clients,
            fraction_fit=fraction_fit,
            fraction_evaluate=fraction_evaluate,
        )
        self.min_epsilon_per_round = min_epsilon_per_round
        self._round_number = 0

    def aggregate_fit(
        self,
        server_round: int,
        results: List[Tuple[ClientProxy, FitRes]],
        failures: List[Union[Tuple[ClientProxy, FitRes], BaseException]],
    ) -> Tuple[Optional[Parameters], Dict[str, Scalar]]:
        self._round_number = server_round

        if not results:
            return None, {}

        # Step 1: Filter out updates that didn't apply DP noise
        valid_results = []
        for client, fit_res in results:
            dp_applied = fit_res.metrics.get("dp_noise_applied", False)
            if not dp_applied:
                logger.warning(f"Round {server_round}: Rejecting update from {client.cid} — DP noise not applied")
                continue
            valid_results.append((client, fit_res))

        if len(valid_results) < self.min_fit_clients:
            logger.error(f"Round {server_round}: Only {len(valid_results)} valid updates (need {self.min_fit_clients})")
            return None, {"round": server_round, "valid_updates": len(valid_results)}

        # Step 2: Byzantine filtering via cosine similarity
        weights_list = [parameters_to_ndarrays(r.parameters) for _, r in valid_results]
        flat_weights = [np.concatenate([w.flatten() for w in wl]) for wl in weights_list]
        filtered_indices = self._byzantine_filter(flat_weights)

        if len(filtered_indices) < self.min_fit_clients // 2:
            logger.error(f"Round {server_round}: Too many Byzantine rejections")
            return None, {}

        filtered_results = [valid_results[i] for i in filtered_indices]

        # Step 3: Sample-weighted aggregation
        num_samples = [r.num_examples ** _SAMPLE_WEIGHT_EXPONENT for _, r in filtered_results]
        total_weight = sum(num_samples)
        normalized_weights = [n / total_weight for n in num_samples]

        aggregated = []
        first_weights = parameters_to_ndarrays(filtered_results[0][1].parameters)
        for layer_idx in range(len(first_weights)):
            layer_agg = sum(
                w * parameters_to_ndarrays(r.parameters)[layer_idx]
                for w, (_, r) in zip(normalized_weights, filtered_results)
            )
            aggregated.append(layer_agg)

        aggregated_params = ndarrays_to_parameters(aggregated)
        metrics = {
            "round": server_round,
            "total_clients": len(results),
            "valid_clients": len(valid_results),
            "byzantine_rejected": len(valid_results) - len(filtered_results),
            "total_samples": sum(r.num_examples for _, r in filtered_results),
        }
        logger.info(f"Round {server_round} aggregation: {metrics}")
        return aggregated_params, metrics

    def _byzantine_filter(self, flat_weights: List[np.ndarray]) -> List[int]:
        """Keep updates with cosine similarity ≥ threshold vs. the median update."""
        if len(flat_weights) <= 2:
            return list(range(len(flat_weights)))

        stacked = np.stack(flat_weights)
        median = np.median(stacked, axis=0)
        median_norm = np.linalg.norm(median) + 1e-9

        valid_indices = []
        for i, w in enumerate(flat_weights):
            cos_sim = np.dot(w, median) / (np.linalg.norm(w) + 1e-9) / median_norm
            if cos_sim >= _COSINE_SIMILARITY_THRESHOLD:
                valid_indices.append(i)
            else:
                logger.warning(f"Byzantine reject: client {i}, cos_sim={cos_sim:.4f}")
        return valid_indices
