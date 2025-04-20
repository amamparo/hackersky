import math
import re
import time
from dataclasses import dataclass
from email.utils import parsedate
from typing import List, Optional
from io import BytesIO

from atproto_client import Client
from atproto_client.models.app.bsky.embed.external import Main as Embed, External
from atproto_client.models.app.bsky.richtext.facet import Link, Main as Facet
from fake_useragent import UserAgent
from rss_parser import RSSParser
from tqdm import tqdm

import requests
from bs4 import BeautifulSoup
from PIL import Image

from injector import inject, Injector

from src.environment import Environment

user_agent = UserAgent().random


@dataclass
class HackerNewsPost:
    title: str
    url: str
    discussion_url: str
    points: int
    timestamp: float
    hotness: float

    def __init__(self, title: str, url: str, discussion_url: str, points: int, timestamp: float):
        self.title = title
        self.url = url
        self.discussion_url = discussion_url
        self.points = points
        self.timestamp = timestamp
        self.hotness = self.__hotness(points, timestamp)

    @staticmethod
    def __hotness(points: int, post_timestamp: float) -> float:
        hours_since_post = (time.time() - post_timestamp) / 3600
        return math.log(points + 1, 10) - (hours_since_post / 24)


@inject
def main(environment: Environment) -> None:
    bsky_handle = environment.get('BSKY_HANDLE')
    bsky = Client()
    bsky.login(bsky_handle, environment.get('BSKY_PASSWORD'))

    latest_bsky_posts = bsky.get_author_feed(actor=bsky_handle, limit=100)['feed']
    already_posted_urls = [post.post.embed.external.uri for post in latest_bsky_posts]

    for hn_post in tqdm(__get_hacker_news_posts(5)):
        if hn_post.url in already_posted_urls:
            continue

        thumb = __get_thumbnail(hn_post.url)
        thumb_blob = bsky.upload_blob(thumb).blob if thumb else None

        discussion = '[Discussion]'
        title = re.sub(r'[\u2010-\u2015\u2212]', '-', hn_post.title)
        text = f'{title} {discussion}'

        end = len(text)
        start = end - len(discussion)

        bsky.send_post(
            text=text,
            facets=[
                Facet(
                    index={
                        'byteStart': start,
                        'byteEnd': end
                    },
                    features=[
                        Link(uri=hn_post.discussion_url)
                    ]
                )
            ],
            embed=Embed(
                external=External(
                    title=hn_post.title,
                    description=hn_post.title,
                    uri=hn_post.url,
                    thumb=thumb_blob
                )
            )
        )


def __get_thumbnail(url: str) -> Optional[bytes]:
    page = requests.get(url, verify=False, headers={
        'User-Agent': user_agent
    })
    soup = BeautifulSoup(page.text, 'html.parser')
    meta = soup.find('meta', property='og:image')
    if not meta:
        return None

    img_url = meta['content']
    r = requests.get(img_url, verify=False, headers={
        'User-Agent': user_agent
    })
    if r.status_code != 200:
        return None

    data = r.content
    if len(data) <= 1_000_000:
        return data

    img = Image.open(BytesIO(data)).convert('RGB')
    width, height = img.size
    scale = 0.9
    while True:
        buf = BytesIO()
        img.save(buf, format='JPEG', optimize=False)
        buf_value = buf.getvalue()
        if len(buf_value) <= 1_000_000:
            return buf_value
        width = int(width * scale)
        height = int(height * scale)
        if width < 10 or height < 10:
            return buf_value
        img = img.resize((width, height))


def __get_hacker_news_posts(n: int) -> List[HackerNewsPost]:
    rss = RSSParser.parse(requests.get('https://hnrss.org/frontpage', params={'count': 30}).text)
    return sorted([
        HackerNewsPost(
            title=item.title.content,
            url=item.links[0].content,
            discussion_url=item.content.comments.content,
            timestamp=time.mktime(parsedate(item.content.pub_date)),
            points=int(item.description.content.lower().split('points:')[-1].split('<')[0].strip())
        )
        for item in rss.channel.items
    ], key=lambda post: post.hotness, reverse=True)[:n]


# pylint: disable=unused-argument
def lambda_handler(event: Optional[dict] = None, context: Optional[dict] = None) -> None:
    Injector().call_with_injection(main)


if __name__ == '__main__':
    lambda_handler()
