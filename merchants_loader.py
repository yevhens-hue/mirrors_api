# merchants_loader.py

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

# merchants_config.json лежит в корне проекта рядом с этим файлом
CONFIG_PATH = Path(__file__).parent / "merchants_config.json"


def load_merchants() -> List[Dict[str, Any]]:
    """
    Загружает конфиг мерчантов из merchants_config.json.
    Формат файла:
    [
      {
        "merchant": "1xbet",
        "country": "in",
        "keywords": ["cricket betting"],
        "brand_pattern": "1xbet"
      },
      ...
    ]
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("merchants_config.json должен содержать список объектов")

    return data
