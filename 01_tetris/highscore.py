"""Persist the high score to a local JSON file alongside the game."""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.json")


def load() -> int:
    try:
        with open(_PATH) as f:
            return int(json.load(f).get("high", 0))
    except Exception:
        return 0


def save(score: int) -> None:
    if score > load():
        with open(_PATH, "w") as f:
            json.dump({"high": score}, f)
