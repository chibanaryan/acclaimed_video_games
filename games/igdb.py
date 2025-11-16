import logging
from typing import Optional, Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Genre themes that match our curated genre list
genre_themes = [
    "4X (explore, expand, exploit, and exterminate)",
    "Action",
    "Horror",
    "Open world",
    "Party",
    "Sandbox",
    "Stealth",
    "Survival",
]


class IgbdApi:
    """
    Client for interacting with the IGDB (Internet Game Database) API.

    Handles authentication, caching, and data retrieval from IGDB API endpoints.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        """
        Initialize the IGDB API client.

        Args:
            client_id: IGDB API client ID
            client_secret: IGDB API client secret
        """
        self.client_id: str = client_id
        self.client_secret: str = client_secret

        self.headers: Dict[str, str] = {}
        self.company_cache: Dict[int, Dict[str, Any]] = {}
        self.game_cache: Dict[int, Dict[str, Any]] = {}
        self.genre_cache: Dict[int, str] = {}
        self.release_date_statuses: Dict[str, int] = {}
        self.release_dates: Dict[int, Any] = {}
        self.themes: Dict[int, str] = {}

        self._get_auth_token()
        self._get_release_statuses()
        self._get_themes()

    def _get_auth_token(self) -> bool:
        """
        Authenticate with IGDB API and store access token in headers.

        Returns:
            bool: True if authentication was successful, False otherwise
        """
        token_url = (
            "https://id.twitch.tv/oauth2/token?"
            f"client_id={self.client_id}&client_secret={self.client_secret}"
            "&grant_type=client_credentials"
        )
        data = requests.post(token_url).json()

        if data.get("access_token"):
            self.headers = {
                "Client-Id": settings.IGDB_CLIENT_ID,
                "Authorization": f'Bearer {data["access_token"]}',
            }
            return True
        else:
            return False

    def _get_themes(self) -> None:
        """
        Fetch and cache theme data from IGDB API.

        Themes are stored in self.themes as a dict mapping theme IDs to names.
        """
        try:
            res = requests.post(
                "https://api.igdb.com/v4/themes/",
                headers=self.headers,
                data="limit 500; fields name;",
            )
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB themes: %s", exc)
            self.themes = {}
            return

        self.themes = {x["id"]: x["name"] for x in results}

    def _get_release_statuses(self) -> None:
        """
        Fetch and cache release date status data from IGDB API.

        Release statuses are stored in self.release_date_statuses as a dict
        mapping status names to their IDs.
        """
        try:
            res = requests.post(
                "https://api.igdb.com/v4/release_date_statuses/",
                headers=self.headers,
                data="fields name;",
            )
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB release statuses: %s", exc)
            self.release_date_statuses = {}
            return

        self.release_date_statuses = {x["name"]: x["id"] for x in results}

    def _get_cover_by_id(self, cover_id: int) -> Optional[str]:
        """
        Fetch cover art filename from IGDB API by cover ID.

        Args:
            cover_id: IGDB cover ID to fetch

        Returns:
            Cover filename if successful, None otherwise
        """
        try:
            res = requests.post(
                "https://api.igdb.com/v4/covers/",
                headers=self.headers,
                data=f"where id={cover_id}; fields url;",
            )
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB cover %s: %s", cover_id, exc)
            return None

        if len(results) != 1:
            logger.warning("Unexpected cover response for %s: %s", cover_id, results)
            return None

        return results[0]["url"].split("/")[-1]

    def _get_company_by_id(
        self, company_id: int, cache_results: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch company (developer/publisher) data from IGDB API by company ID.

        Args:
            company_id: IGDB company ID to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Company data dict with id, name, slug, parent fields if successful,
            None otherwise
        """
        if cache_results and company_id in self.company_cache:
            return self.company_cache[company_id]

        try:
            res = requests.post(
                "https://api.igdb.com/v4/companies/",
                headers=self.headers,
                data=f"where id={company_id}; fields id,name,slug,parent;",
            )
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB company %s: %s", company_id, exc)
            return None

        if len(results) != 1:
            logger.warning(
                "Unexpected company response for %s: %s", company_id, results
            )
            return None

        self.company_cache[company_id] = results[0]
        return results[0]

    def _get_genre_by_id(
        self, genre_id: int, cache_results: bool = True
    ) -> Optional[str]:
        """
        Fetch genre name from IGDB API by genre ID.

        Args:
            genre_id: IGDB genre ID to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Genre name if successful, None otherwise
        """
        if cache_results and genre_id in self.genre_cache:
            return self.genre_cache[genre_id]

        try:
            res = requests.post(
                "https://api.igdb.com/v4/genres/",
                headers=self.headers,
                data=f"where id={genre_id}; fields name;",
            )
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB genre %s: %s", genre_id, exc)
            return None

        if len(results) != 1:
            logger.warning("Unexpected genre response for %s: %s", genre_id, results)
            return None

        genre_name = results[0]["name"]
        self.genre_cache[genre_id] = genre_name
        return genre_name

    def get_game_info_by_id(
        self, game_id: int, cache_results: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive game information from IGDB API by game ID.

        This method retrieves game data including cover art, developers,
        genres, and metadata. It intelligently selects developers from
        involved companies, preferring actual developers over supporters,
        publishers, and porters in that order.

        Args:
            game_id: IGDB game ID to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Dict containing game data with keys:
                - cover: Cover art filename
                - developers: List of developer dicts with id, name, slug, parent
                - genres: List of genre names (combination of genres and themes)
                - storyline: Game storyline text
                - summary: Game summary text
                - url: IGDB URL for the game
                - slug: IGDB slug for the game
            Returns None if the game cannot be fetched or authentication fails.
        """
        # Check cache first
        if cache_results and game_id in self.game_cache:
            return self.game_cache[game_id]

        # Get game data from API
        res = requests.post(
            "https://api.igdb.com/v4/games/",
            headers=self.headers,
            data=(
                "where id="
                f"{game_id}; fields slug,cover,genres,first_release_date,"
                "summary,storyline,url,themes,involved_companies.*;"
            ),
        )

        if res.status_code == 401:
            if self._get_auth_token():
                return self.get_game_info_by_id(game_id, cache_results)
            else:
                return

        results = res.json()
        assert len(results) == 1
        data = results[0]

        # Get developer information
        developers = []
        porters = []
        supporters = []
        publishers = []

        for involved_company_dict in data.get("involved_companies", []):
            company_id = involved_company_dict["company"]

            if involved_company_dict["developer"]:
                developers.append(company_id)

            if involved_company_dict["supporting"]:
                supporters.append(company_id)

            if involved_company_dict["publisher"]:
                publishers.append(company_id)

            if involved_company_dict["porting"]:
                porters.append(company_id)

        company_ids = []

        if developers:
            company_ids += developers
        else:
            if supporters:
                company_ids += supporters
            elif publishers:
                company_ids += publishers
            elif porters:
                company_ids += porters

        developer_objs = []
        for company_id in company_ids:
            company_obj = self._get_company_by_id(company_id, cache_results)
            if not company_obj:
                continue

            parent_id = company_obj.get("parent")
            if parent_id:
                parent_obj = self._get_company_by_id(parent_id, cache_results)
            else:
                parent_obj = None

            developer_objs.append(
                {
                    "id": company_id,
                    "name": company_obj["name"],
                    "slug": company_obj["slug"],
                    "parent": parent_obj,
                }
            )

        # Get genres
        theme_names = [
            self.themes.get(x)
            for x in data.get("themes", [])
            if self.themes.get(x) in genre_themes
        ]
        genre_names = [
            self._get_genre_by_id(x, cache_results) for x in data.get("genres", [])
        ]
        genres = list(set(theme_names + genre_names))

        game_data = {
            "cover": self._get_cover_by_id(data["cover"]),
            "developers": developer_objs,
            "genres": genres,
            "storyline": data.get("storyline"),
            "summary": data.get("summary"),
            "url": data.get("url"),
            "slug": data.get("slug"),
        }

        self.game_cache[game_id] = game_data

        return game_data


def get_api() -> Optional[IgbdApi]:
    """
    Create and return an IGDB API client instance.

    Returns:
        IgbdApi: Configured IGDB API client, or None if initialization fails
    """
    try:
        return IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
    except (ValueError, KeyError, AttributeError) as e:
        logger.error("Failed to initialize IGDB API: %s", e)
        return None
    except requests.RequestException as e:
        logger.error("Network error initializing IGDB API: %s", e)
        return None
