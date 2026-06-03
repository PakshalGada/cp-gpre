"""Fetch CSES account progress by logging in and scraping the problem set page."""

import json
import os
import re
import time
from datetime import datetime, timezone

import requests

from core.practice.paths import CSES_PROGRESS_CACHE

CSES_BASE = "https://cses.fi"
LOGIN_URL = f"{CSES_BASE}/login"
PROBLEMSET_URL = f"{CSES_BASE}/problemset/"
CACHE_MAX_AGE_SECONDS = 6 * 60 * 60

TASK_SCORE_CLASS_PATTERN = re.compile(r'<span class="(task-score[^"]*)"')
CSRF_PATTERN = re.compile(
    r'name="csrf_token"\s+value="([^"]+)"',
)
LOGIN_LINK_MARKERS = (
    'class="account" href="/login">Login</a>',
    'href="/login">Login</a>',
)


class CsesLoginError(RuntimeError):
    pass


class CsesProfile:
    def __init__(self, username: str, password: str | None = None):
        self.username = username.strip()
        self.password = password
        self.solved_ids: set[int] = set()
        self.updated_at: str | None = None
        self.from_cache = False

    def fetch(self, force_refresh: bool = False) -> set[int]:
        if not self.username:
            return set()

        if not force_refresh and not self.password:
            cached = self._load_cache()
            if cached is not None:
                self.solved_ids = cached
                self.from_cache = True
                return self.solved_ids

        if not self.password:
            raise CsesLoginError(
                "CSES password required to refresh progress (or use a recent cached session)."
            )

        self.solved_ids = self._scrape_solved_ids()
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_cache()
        self.from_cache = False
        return self.solved_ids

    def _cache_path(self) -> str:
        safe_name = re.sub(r"[^\w.-]", "_", self.username)
        return CSES_PROGRESS_CACHE.format(safe_name)

    def _load_cache(self) -> set[int] | None:
        path = self._cache_path()
        if not os.path.exists(path):
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        updated = data.get("updated_at")
        if updated:
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
                if time.time() - ts > CACHE_MAX_AGE_SECONDS:
                    return None
            except ValueError:
                pass

        return set(data.get("solved_ids", []))

    def _save_cache(self) -> None:
        path = self._cache_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "username": self.username,
                    "updated_at": self.updated_at,
                    "solved_ids": sorted(self.solved_ids),
                    "solved_count": len(self.solved_ids),
                },
                f,
                indent=2,
            )

    def _login(self, session: requests.Session) -> None:
        login_page = session.get(LOGIN_URL, timeout=30)
        login_page.raise_for_status()

        csrf_match = CSRF_PATTERN.search(login_page.text)
        if not csrf_match:
            raise CsesLoginError("Could not find CSES login CSRF token.")

        response = session.post(
            LOGIN_URL,
            data={
                "csrf_token": csrf_match.group(1),
                "nick": self.username,
                "pass": self.password,
            },
            timeout=30,
            allow_redirects=True,
        )
        response.raise_for_status()

        if self._page_is_logged_out(response.text):
            raise CsesLoginError("Invalid CSES username or password.")

    @staticmethod
    def _is_solved_score_class(class_attr: str) -> bool:
        """AC on CSES is rendered as task-score with a 'full' class."""
        return bool(re.search(r"\bfull\b", class_attr))

    @classmethod
    def _parse_solved_ids(cls, html: str) -> set[int]:
        # CSES omits </li> between tasks; split on task items instead.
        solved: set[int] = set()
        chunks = html.split('<li class="task">')
        if len(chunks) <= 1:
            return solved

        for chunk in chunks[1:]:
            id_match = re.match(r'<a href="/problemset/task/(\d+)">', chunk)
            if not id_match:
                continue
            score_match = TASK_SCORE_CLASS_PATTERN.search(chunk)
            if score_match and cls._is_solved_score_class(score_match.group(1)):
                solved.add(int(id_match.group(1)))

        return solved

    @staticmethod
    def _page_is_logged_out(html: str) -> bool:
        return any(marker in html for marker in LOGIN_LINK_MARKERS)

    def _scrape_solved_ids(self) -> set[int]:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "cp-gpre/1.0 (CSES progress sync)",
            }
        )
        self._login(session)

        page = session.get(PROBLEMSET_URL, timeout=30)
        page.raise_for_status()

        if self._page_is_logged_out(page.text):
            raise CsesLoginError("CSES session expired or login failed.")

        solved = self._parse_solved_ids(page.text)
        task_count = page.text.count('<li class="task">')
        if task_count == 0:
            raise CsesLoginError("Unexpected CSES problem set page; cannot read progress.")

        return solved
