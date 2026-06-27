import json


def literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
