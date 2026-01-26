import json
from datetime import timedelta
from pathlib import Path

MINUTE = 60
DAY = 60 * 60 * 24

SCHEDULER_VERSION = "sm2_v2_steps"

LEARNING_STEPS = [timedelta(minutes=10), timedelta(days=1)]
RELEARNING_STEPS = [timedelta(minutes=10), timedelta(days=1)]

GRADUATING_INTERVAL_DAYS = 3
POST_LAPSE_INTERVAL_DAYS = 1
MIN_EASINESS = 1.3

# HLR config
HLR_SCHEDULER_VERSION = "hlr_v1"
HLR_INITIAL_HALF_LIFE = 0.5
HLR_MIN_HALF_LIFE = 0.01
HLR_MAX_HALF_LIFE = 365.0
HLR_MIN_INTERVAL_HOURS = 1
HLR_DEFAULT_TARGET_RECALL = 0.9
HLR_HALF_LIFE_MULTIPLIERS = {3: 1.4, 4: 1.8, 5: 2.2}
HLR_LAPSE_MULTIPLIER = 0.5
HLR_GRADUATION_HALF_LIFE_DAYS = 180
HLR_CONFIDENCE_CHECK_INTERVAL_DAYS = 90

_RECALL_CONFIG_CACHE = None


def load_recall_config():
    global _RECALL_CONFIG_CACHE
    if _RECALL_CONFIG_CACHE is not None:
        return _RECALL_CONFIG_CACHE

    config_path = Path(__file__).with_name("recall_config.json")
    if not config_path.exists():
        _RECALL_CONFIG_CACHE = {}
        return _RECALL_CONFIG_CACHE

    try:
        _RECALL_CONFIG_CACHE = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _RECALL_CONFIG_CACHE = {}
    return _RECALL_CONFIG_CACHE


def get_effective_target_recall(tags):
    config = load_recall_config()
    default = config.get("default", HLR_DEFAULT_TARGET_RECALL)
    tag_overrides = config.get("tags", {}) or {}
    if not tags:
        return default
    matched = [tag_overrides.get(tag) for tag in tags if tag in tag_overrides]
    matched = [value for value in matched if value is not None]
    if not matched:
        return default
    return max(matched)
