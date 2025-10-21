from .registry import get_adapter, register_adapter
from .json_adapter import parse_json  # registers itself
from .csv_adapter import parse_csv    # registers itself

__all__ = ["get_adapter", "register_adapter", "parse_json", "parse_csv"]
