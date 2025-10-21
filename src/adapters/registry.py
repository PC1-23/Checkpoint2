from typing import Callable, Dict

AdapterFn = Callable[[bytes, str], list]

registry: Dict[str, AdapterFn] = {}

def register_adapter(name: str, fn: AdapterFn) -> None:
    registry[name] = fn

def get_adapter(name: str):
    return registry.get(name)
