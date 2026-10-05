"""Registry for selecting supported strategy runners by stable identifier."""

from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel
from ...config import CANSLIM_BREAKOUT_V0
from . import canslim_breakout_v0


ENGINE_CAPABILITIES = frozenset({"long", "single_position", "full_exit", "next_open", "normalized_accounting"})


@dataclass(frozen=True)
class StrategyDefinition:
    version: str
    parameter_model: type[BaseModel]
    runner: Callable
    data_requirements: Callable[[BaseModel], dict]
    required_capabilities: frozenset[str]


strategies = {
    CANSLIM_BREAKOUT_V0.strategy_id: StrategyDefinition(
        version="1", parameter_model=canslim_breakout_v0.Parameters,
        runner=canslim_breakout_v0.run, data_requirements=canslim_breakout_v0.data_requirements,
        required_capabilities=ENGINE_CAPABILITIES,
    ),
}


def get_strategy_definition(strategy_id: str, version: str | None = None) -> StrategyDefinition:
    try:
        definition = strategies[strategy_id]
    except KeyError as error:
        raise ValueError(f"unsupported strategy_id: {strategy_id}") from error
    if version is not None and version != definition.version:
        raise ValueError(f"unsupported strategy_version: {strategy_id}/{version}")
    unsupported = definition.required_capabilities - ENGINE_CAPABILITIES
    if unsupported:
        raise ValueError(f"UNSUPPORTED_ENGINE_CAPABILITIES: {', '.join(sorted(unsupported))}")
    return definition


def get_strategy_parameters(strategy_id: str, values: dict | None = None, version: str | None = None) -> dict:
    """Lấy đúng tham số đã kiểm tra, không dùng cấu hình của chiến lược khác."""

    definition = get_strategy_definition(strategy_id, version)
    return definition.parameter_model.model_validate({} if values is None else values).model_dump(mode="json")


def describe_strategy(strategy_id: str, version: str | None = None) -> dict:
    definition = get_strategy_definition(strategy_id, version)
    # Trường bắt buộc có thể không có mặc định; không tạo một yêu cầu giả để mô tả schema.
    schema = definition.parameter_model.model_json_schema()
    defaults = {name: field["default"] for name, field in schema["properties"].items() if "default" in field}
    return {"strategy_id": strategy_id, "strategy_version": definition.version,
            "parameter_schema": schema,
            "default_params": defaults,
            "data_requirements": (None if schema.get("required") else
                                  definition.data_requirements(definition.parameter_model.model_validate(defaults))),
            "required_capabilities": sorted(definition.required_capabilities)}
