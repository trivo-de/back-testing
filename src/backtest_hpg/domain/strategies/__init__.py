"""Registry for selecting supported strategy runners by stable identifier."""

from ...config import CANSLIM_BREAKOUT_V0
from . import canslim_breakout_v0


strategy_runners = {CANSLIM_BREAKOUT_V0.strategy_id: canslim_breakout_v0.run}
strategy_settings = {CANSLIM_BREAKOUT_V0.strategy_id: CANSLIM_BREAKOUT_V0}


def get_strategy(strategy_id: str):
    """Return the runner registered for ``strategy_id`` or fail explicitly."""

    try:
        return strategy_runners[strategy_id]
    except KeyError as error:
        raise ValueError(f"unsupported strategy_id: {strategy_id}") from error


def get_strategy_parameters(strategy_id: str) -> dict:
    """Return the immutable strategy settings as serializable audit metadata."""

    get_strategy(strategy_id)
    return strategy_settings[strategy_id].parameters()
