from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

COUNTRIES = {
    "": "全球",
    "US": "美国",
    "GB": "英国",
    "JP": "日本",
    "TW": "中国台湾",
    "HK": "中国香港",
    "SG": "新加坡",
    "CA": "加拿大",
    "AU": "澳大利亚",
    "DE": "德国",
    "FR": "法国",
    "IN": "印度",
    "BR": "巴西",
    "KR": "韩国",
}
Timeframe = Literal["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"]
Mode = Literal["demo", "live"]
ScheduleInterval = Literal[3, 7]


class ExploreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(min_length=1, max_length=5)
    geo: str = "US"
    timeframe: Timeframe = "today 12-m"
    gprop: Literal["", "youtube", "news", "images", "froogle"] = ""
    mode: Mode = "demo"

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values):
        clean = []
        for value in values:
            word = " ".join(value.split())
            if not word or len(word) > 100 or any(ord(c) < 32 for c in word):
                raise ValueError("关键词须为 1–100 个可见字符")
            if word.casefold() not in {w.casefold() for w in clean}:
                clean.append(word)
        return clean

    @field_validator("geo")
    @classmethod
    def valid_geo(cls, value):
        if value not in COUNTRIES:
            raise ValueError("请选择支持的地区")
        return value


class OpportunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: ExploreRequest
    series: list[dict] = Field(default_factory=list, max_length=1000)
    regions: list[dict] = Field(default_factory=list, max_length=1000)


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(min_length=1, max_length=5)
    geo: str = "US"
    timeframe: Timeframe = "today 12-m"
    gprop: Literal["", "youtube", "news", "images", "froogle"] = ""
    interval_days: ScheduleInterval = 7

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, values):
        return ExploreRequest.clean_keywords(values)

    @field_validator("geo")
    @classmethod
    def valid_geo(cls, value):
        if value not in COUNTRIES:
            raise ValueError("请选择支持的地区")
        return value
