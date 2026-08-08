from dataclasses import dataclass


@dataclass
class Event:
    external_id: str
    date: str
    quad_class: int
    num_mentions: int
    goldsteinscale: float
    isrootevent: int
    summary: str


@dataclass
class Actor:
    name: str
    type: str
    country_code: str


@dataclass
class Location:
    name: str
    long: str
    lat: str
    type: str


@dataclass
class NewsArticle:
    url: str


@dataclass
class Publisher:
    name: str


@dataclass
class Year:
    value: int
