"""Agent tool schema must stay valid for Gemini function calling.

Regression for the bug where a parameter named "type" was stringified by the
schema converter, making Gemini reject the entire tool list and silently fall
back to plain code replies (one scene per chat turn).
"""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

import serve


def walk_properties(schema, path="parameters"):
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for name, child in properties.items():
                assert isinstance(child, dict), f"{path}.properties.{name} is {type(child).__name__}, not a schema: {child!r}"
                walk_properties(child, f"{path}.properties.{name}")
        items = schema.get("items")
        if isinstance(items, dict):
            walk_properties(items, f"{path}.items")
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            walk_properties(item, f"{path}[{index}]")


declarations = serve._gemini_tool_declarations()
names = [tool["name"] for tool in declarations]
assert names == [tool["name"] for tool in serve.LLM_TOOL_DECLARATIONS]
assert len(names) == len(set(names)), names
for declaration in declarations:
    walk_properties(declaration.get("parameters") or {}, declaration["name"])

transition = next(tool for tool in declarations if tool["name"] == "add_transition")
type_param = transition["parameters"]["properties"]["type"]
assert type_param["type"] == "STRING", type_param
assert transition["parameters"]["type"] == "OBJECT", transition["parameters"]

mistral = serve._mistral_tool_declarations()
assert len(mistral) == len(names)
assert all(tool["type"] == "function" for tool in mistral)

print(f"PASS tool schema ({len(declarations)} tools, all property schemas valid)")
