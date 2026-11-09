import inspect
import json
from typing import get_type_hints, Callable

TOOLS: dict[str, Callable] = {}
SCHEMAS: list[dict] = []

def tool(fn: Callable):
    name = fn.__name__
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)

    props = {}
    required = []

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    for param_name, param in sig.parameters.items():
        py_type = hints.get(param_name, str)
        props[param_name] = {"type": type_map.get(py_type, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    SCHEMAS.append({
        "type": "function",
        "function": {
            "name": name,
            "description": (fn.__doc__ or "").strip(),
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    })
    TOOLS[name] = fn
    return fn
