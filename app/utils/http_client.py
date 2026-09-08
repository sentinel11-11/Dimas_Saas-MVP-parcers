import time
import random
import requests
from dataclasses import dataclass
from loguru import logger


@dataclass
class ResponseWrapper:
    status_code: int
    text: str
    url: str


class HTTPClient:

    def __init__(self):

        self.session = requests.Session()

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml",
            "Connection": "keep-alive",
        }

        self.min_delay = 1.5
        self.max_delay = 4.5

        self.last_request_time = 0

        self.retry_count = 3


    def _smart_sleep(self):

        elapsed = time.time() - self.last_request_time

        base_delay = random.uniform(self.min_delay, self.max_delay)

        if elapsed < base_delay:
            sleep_time = base_delay - elapsed
        else:
            sleep_time = random.uniform(0.5, 1.5)

        logger.info(f"Sleep: {sleep_time:.2f} sec")

        time.sleep(sleep_time)


    def get(self, url: str, params=None):

        for attempt in range(self.retry_count):

            try:

                self._smart_sleep()

                response = self.session.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=15
                )

                self.last_request_time = time.time()

                # rate limit handling
                if response.status_code == 429:

                    logger.warning(f"429 RATE LIMIT: {url}")

                    time.sleep(5 + attempt * 3)
                    continue

                if response.status_code >= 500:

                    logger.warning(f"SERVER ERROR {response.status_code}: {url}")

                    time.sleep(2 + attempt * 2)
                    continue

                logger.info(f"STATUS {response.status_code}: {url}")

                return ResponseWrapper(
                    status_code=response.status_code,
                    text=response.text,
                    url=url
                )

            except Exception as e:

                logger.error(f"HTTP ERROR: {url} -> {e}")

                time.sleep(2 + attempt * 2)

        return None