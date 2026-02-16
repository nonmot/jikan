import tomllib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from jikan.lib.print import warn


class JikanSetting(BaseSettings):
    timezone: str = Field(default="Asia/Tokyo")


CONFIG_PATH = Path.home() / ".jikan" / "config.toml"


def load_config() -> JikanSetting:
    if not CONFIG_PATH.exists():
        return JikanSetting()
    with CONFIG_PATH.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            warn(f"Invalid syntax in {CONFIG_PATH}")
            return JikanSetting()
    return JikanSetting.model_validate(data)
