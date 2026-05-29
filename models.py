from dataclasses import dataclass


@dataclass
class Post:
    post_id: str
    text: str
    url: str


@dataclass
class Notification:
    title: str
    body: str
