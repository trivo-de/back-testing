"""Retired manifest runner kept only for the PostgreSQL acceptance script."""

from copy import deepcopy
from dataclasses import replace
from datetime import date

from ..domain.strategies import get_strategy_definition
from .result_mapper import result_to_dict


def run_legacy_manifest(repository, config):
    definition = get_strategy_definition(config.strategy_id, config.strategy_version)
    values = {} if config.strategy_params is None else config.strategy_params
    params = definition.parameter_model.model_validate(values)
    requirements = definition.data_requirements(params)
    if set(requirements) - {"primary", "market"}:
        raise ValueError("UNSUPPORTED_DATA_REQUIREMENTS")
    if "market" in requirements and requirements["market"].get("symbol") != "VNINDEX":
        raise ValueError("UNSUPPORTED_DATA_REQUIREMENTS: market symbol")
    config = replace(config, strategy_version=definition.version,
                     strategy_params=deepcopy(values))
    run_id, dataset = repository.start_run(config)
    try:
        market_arguments = {}
        if "market" in requirements:
            if dataset.market_bars:
                market_arguments["market_bars"] = dataset.market_bars
            elif any(bar.index_close is None for bar in dataset.bars):
                raise ValueError("MISSING_REQUIRED_DATA: market")
        if dataset.metadata.get("rollover_action") == "close_at_expiry_open":
            market_arguments["flat_dates"] = frozenset(
                date.fromisoformat(value) for value in dataset.metadata["expiry_dates"])
        result = definition.runner(
            dataset.bars, params=params, initial_cash=config.initial_cash,
            fee_rate=config.fee_rate, slippage_rate=config.slippage_rate,
            start_date=config.start_date, end_date=config.end_date, **market_arguments,
        )
        response = result_to_dict(run_id, dataset.metadata, config, result,
                                  strategy_parameters=params.model_dump(mode="json"))
        repository.complete_run(run_id, result, response)
        return response
    except Exception as error:
        repository.fail_run(run_id, error)
        raise
