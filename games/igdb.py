import logging
import threading
import time
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

    def __init__(
        self, client_id: str, client_secret: str, use_pro_tier: bool = False
    ) -> None:
        """
        Initialize the IGDB API client.

        Args:
            client_id: IGDB API client ID
            client_secret: IGDB API client secret
            use_pro_tier: Whether to use Pro tier endpoints and rate limits
        """
        self.client_id: str = client_id
        self.client_secret: str = client_secret
        self.use_pro_tier: bool = use_pro_tier

        self.headers: Dict[str, str] = {}
        self.company_cache: Dict[int, Dict[str, Any]] = {}
        self.game_cache: Dict[int, Dict[str, Any]] = {}
        self.genre_cache: Dict[int, str] = {}
        self.release_date_statuses: Dict[str, int] = {}
        self.release_dates: Dict[int, Any] = {}
        self.themes: Dict[int, str] = {}

        # Thread safety locks
        self.rate_limit_lock: threading.Lock = threading.Lock()
        self.cache_lock: threading.Lock = threading.Lock()

        # Rate limiting and batch size based on tier
        if use_pro_tier:
            # Pro tier: 3000 requests/second
            # Using 2500 req/sec to stay safely below the limit
            self.min_request_interval: float = 1.0 / 2500  # ~0.4ms
            self.max_batch_size: int = 500  # Pro tier batch limit
        else:
            # Free tier: 4 requests/second
            # Using 3.8 req/sec to stay safely below the limit
            self.min_request_interval: float = 1.0 / 3.8  # ~263ms
            self.max_batch_size: int = 50  # Free tier batch limit
        self.last_request_time: float = 0.0

        self._get_auth_token()
        self._get_release_statuses()
        self._get_themes()

    def _get_endpoint_url(self, endpoint: str) -> str:
        """
        Get the full URL for an IGDB API endpoint.

        Args:
            endpoint: Endpoint name (e.g., 'games', 'companies', 'genres')

        Returns:
            Full URL for the endpoint, using Pro tier path if enabled
        """
        if self.use_pro_tier:
            return f"https://api.igdb.com/pro/v4/{endpoint}/"
        else:
            return f"https://api.igdb.com/v4/{endpoint}/"

    def _wait_for_rate_limit(self) -> None:
        """
        Enforce rate limiting by sleeping if necessary.

        Thread-safe implementation that ensures requests are spaced at least
        min_request_interval apart, respecting the IGDB API's 4 requests/second
        limit (using 3.8 for safety).
        """
        with self.rate_limit_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                sleep_time = self.min_request_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()

    def _make_request_with_retry(
        self, url: str, data: str, max_retries: int = 3
    ) -> Optional[requests.Response]:
        """
        Make an API request with rate limiting and exponential backoff for retries.

        Args:
            url: The API endpoint URL
            data: The request body/data
            max_retries: Maximum number of retries on 429 errors (default: 3)

        Returns:
            The response object if successful, None if all retries fail
        """
        retry_count = 0
        while retry_count <= max_retries:
            self._wait_for_rate_limit()
            try:
                response = requests.post(url, headers=self.headers, data=data)

                # Handle rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    if retry_count < max_retries:
                        wait_time = (
                            2**retry_count
                        )  # Exponential backoff: 1s, 2s, 4s, etc.
                        logger.warning(
                            "Rate limited by IGDB API. Retrying in %d seconds... "
                            "(attempt %d/%d)",
                            wait_time,
                            retry_count + 1,
                            max_retries + 1,
                        )
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        logger.error(
                            "Rate limited by IGDB API. Max retries (%d) exceeded.",
                            max_retries,
                        )
                        return None

                return response

            except requests.RequestException as exc:
                logger.warning("Request failed: %s", exc)
                return None

        return None

    def _get_auth_token(self) -> bool:
        """
        Authenticate with IGDB API and store access token in headers.

        Returns:
            bool: True if authentication was successful, False otherwise
        """
        # Check if credentials are set (not default "XXX")
        if self.client_id == "XXX" or self.client_secret == "XXX":
            logger.warning(
                "IGDB credentials not configured. "
                "Set IGDB_CLIENT_ID and IGDB_CLIENT_SECRET environment variables."
            )
            return False

        token_url = (
            "https://id.twitch.tv/oauth2/token?"
            f"client_id={self.client_id}&client_secret={self.client_secret}"
            "&grant_type=client_credentials"
        )

        try:
            response = requests.post(token_url)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Failed to authenticate with IGDB API: %s", exc)
            return False
        except ValueError as exc:
            logger.warning("Invalid JSON response from IGDB auth: %s", exc)
            return False

        if data.get("access_token"):
            self.headers = {
                "Client-Id": self.client_id,
                "Authorization": f'Bearer {data["access_token"]}',
            }
            return True
        else:
            error_msg = data.get("message", "Unknown error")
            logger.warning("IGDB authentication failed: %s", error_msg)
            return False

    def _get_themes(self) -> None:
        """
        Fetch and cache theme data from IGDB API.

        Themes are stored in self.themes as a dict mapping theme IDs to names.
        """
        # Check if headers are properly set (not just empty dict)
        if not self.headers or "Authorization" not in self.headers:
            logger.debug("Skipping IGDB themes fetch: authentication not available")
            self.themes = {}
            return

        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("themes"),
                data="limit 500; fields name;",
            )
            if res is None:
                self.themes = {}
                return
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
        # Check if headers are properly set (not just empty dict)
        if not self.headers or "Authorization" not in self.headers:
            logger.debug(
                "Skipping IGDB release statuses fetch: " "authentication not available"
            )
            self.release_date_statuses = {}
            return

        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("release_date_statuses"),
                data="fields name;",
            )
            if res is None:
                self.release_date_statuses = {}
                return
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
            res = self._make_request_with_retry(
                self._get_endpoint_url("covers"),
                data=f"where id={cover_id}; fields url;",
            )
            if res is None:
                return None
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

        Thread-safe implementation with cache locking.

        Args:
            company_id: IGDB company ID to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Company data dict with id, name, slug, parent fields if successful,
            None otherwise
        """
        if cache_results:
            with self.cache_lock:
                if company_id in self.company_cache:
                    return self.company_cache[company_id]

        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("companies"),
                data=f"where id={company_id}; fields id,name,slug,parent;",
            )
            if res is None:
                return None
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

        if cache_results:
            with self.cache_lock:
                self.company_cache[company_id] = results[0]
        return results[0]

    def _get_genre_by_id(
        self, genre_id: int, cache_results: bool = True
    ) -> Optional[str]:
        """
        Fetch genre name from IGDB API by genre ID.

        Thread-safe implementation with cache locking.

        Args:
            genre_id: IGDB genre ID to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Genre name if successful, None otherwise
        """
        if cache_results:
            with self.cache_lock:
                if genre_id in self.genre_cache:
                    return self.genre_cache[genre_id]

        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("genres"),
                data=f"where id={genre_id}; fields name;",
            )
            if res is None:
                return None
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB genre %s: %s", genre_id, exc)
            return None

        if len(results) != 1:
            logger.warning("Unexpected genre response for %s: %s", genre_id, results)
            return None

        genre_name = results[0]["name"]
        if cache_results:
            with self.cache_lock:
                self.genre_cache[genre_id] = genre_name
        return genre_name

    def get_companies_by_ids(
        self, company_ids: list, cache_results: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """
        Batch fetch multiple companies from IGDB API by IDs.

        This method fetches company data for multiple IDs in a single request,
        significantly reducing the number of API calls needed.

        Args:
            company_ids: List of IGDB company IDs to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Dict mapping company IDs to company data dicts with id, name, slug,
            parent fields. Companies not found or with errors are omitted.
        """
        if not company_ids:
            return {}

        # Check cache for already-fetched companies
        companies_dict = {}
        ids_to_fetch = []

        for company_id in company_ids:
            if cache_results:
                with self.cache_lock:
                    if company_id in self.company_cache:
                        companies_dict[company_id] = self.company_cache[company_id]
                        continue
            ids_to_fetch.append(company_id)

        if not ids_to_fetch:
            return companies_dict

        # Batch fetch companies
        ids_str = ",".join(str(cid) for cid in ids_to_fetch)
        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("companies"),
                data=f"where id = ({ids_str}); fields id,name,slug,parent; limit 500;",
            )
            if res is None:
                return companies_dict
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB companies %s: %s", ids_to_fetch, exc)
            return companies_dict

        # Process results and update cache
        for company_data in results:
            company_id = company_data["id"]
            companies_dict[company_id] = company_data
            if cache_results:
                with self.cache_lock:
                    self.company_cache[company_id] = company_data

        return companies_dict

    def get_games_info_by_ids(
        self, game_ids: list, cache_results: bool = True
    ) -> Dict[int, Dict[str, Any]]:
        """
        Batch fetch multiple games from IGDB API by IDs.

        This method fetches game data for multiple IDs in a single request,
        with field expansion for covers, genres, and companies. This significantly
        reduces the number of API calls needed.

        Args:
            game_ids: List of IGDB game IDs to fetch
            cache_results: Whether to use/store results in cache (default: True)

        Returns:
            Dict mapping game IDs to game data dicts with keys:
                - cover: Cover art filename
                - developers: List of developer dicts with id, name, slug, parent
                - genres: List of genre names (combination of genres and themes)
                - storyline: Game storyline text
                - summary: Game summary text
                - url: IGDB URL for the game
                - slug: IGDB slug for the game
            Games not found or with errors are omitted.
        """
        if not game_ids:
            return {}

        # Check cache for already-fetched games
        games_dict = {}
        ids_to_fetch = []

        for game_id in game_ids:
            if cache_results:
                with self.cache_lock:
                    if game_id in self.game_cache:
                        games_dict[game_id] = self.game_cache[game_id]
                        continue
            ids_to_fetch.append(game_id)

        if not ids_to_fetch:
            return games_dict

        # Batch fetch games with field expansion
        ids_str = ",".join(str(gid) for gid in ids_to_fetch)
        try:
            res = self._make_request_with_retry(
                self._get_endpoint_url("games"),
                data=(
                    f"where id = ({ids_str}); "
                    "fields slug,cover.*,genres.*,first_release_date,"
                    "summary,storyline,url,themes,involved_companies.*; "
                    "limit 500;"
                ),
            )
            if res is None:
                logger.warning("Failed to fetch batch game data after retries")
                return games_dict
            res.raise_for_status()
            results = res.json()
        except Exception as exc:
            logger.warning("Unable to load IGDB games %s: %s", ids_to_fetch, exc)
            return games_dict

        # Collect all company IDs that need to be fetched
        all_company_ids = set()
        for data in results:
            for involved_company_dict in data.get("involved_companies", []):
                company_id = involved_company_dict.get("company")
                if company_id:
                    all_company_ids.add(company_id)
                parent_id = involved_company_dict.get("parent")
                if parent_id:
                    all_company_ids.add(parent_id)

        # Batch fetch all companies
        companies = self.get_companies_by_ids(list(all_company_ids), cache_results)

        # Process each game
        for data in results:
            game_id = data["id"]

            # Process developers
            developers = []
            porters = []
            supporters = []
            publishers = []

            for involved_company_dict in data.get("involved_companies", []):
                company_id = involved_company_dict.get("company")
                if not company_id:
                    continue

                if involved_company_dict.get("developer"):
                    developers.append(company_id)
                if involved_company_dict.get("supporting"):
                    supporters.append(company_id)
                if involved_company_dict.get("publisher"):
                    publishers.append(company_id)
                if involved_company_dict.get("porting"):
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
                company_obj = companies.get(company_id)
                if not company_obj:
                    continue

                parent_id = company_obj.get("parent")
                parent_obj = companies.get(parent_id) if parent_id else None

                developer_objs.append(
                    {
                        "id": company_id,
                        "name": company_obj["name"],
                        "slug": company_obj["slug"],
                        "parent": parent_obj,
                    }
                )

            # Process genres
            theme_names = [
                self.themes.get(x)
                for x in data.get("themes", [])
                if self.themes.get(x) in genre_themes
            ]
            genre_names = [
                genre_obj["name"]
                for genre_obj in data.get("genres", [])
                if isinstance(genre_obj, dict) and "name" in genre_obj
            ]
            genres = list(set(theme_names + genre_names))

            # Process cover
            cover_data = data.get("cover")
            if cover_data and isinstance(cover_data, dict) and "url" in cover_data:
                cover_filename = cover_data["url"].split("/")[-1]
            else:
                cover_filename = None

            game_data = {
                "cover": cover_filename,
                "developers": developer_objs,
                "genres": genres,
                "storyline": data.get("storyline"),
                "summary": data.get("summary"),
                "url": data.get("url"),
                "slug": data.get("slug"),
            }

            games_dict[game_id] = game_data
            if cache_results:
                with self.cache_lock:
                    self.game_cache[game_id] = game_data

        return games_dict

    def get_game_info_by_id(
        self, game_id: int, cache_results: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch comprehensive game information from IGDB API by game ID.

        Thread-safe implementation with cache locking. This method retrieves game
        data including cover art, developers, genres, and metadata. It intelligently
        selects developers from involved companies, preferring actual developers
        over supporters, publishers, and porters in that order.

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
        # Check cache first (thread-safe)
        if cache_results:
            with self.cache_lock:
                if game_id in self.game_cache:
                    return self.game_cache[game_id]

        # Get game data from API with field expansion for cover and genres
        res = self._make_request_with_retry(
            self._get_endpoint_url("games"),
            data=(
                "where id="
                f"{game_id}; fields slug,cover.*,genres.*,first_release_date,"
                "summary,storyline,url,themes,involved_companies.*;"
            ),
        )

        if res is None:
            logger.warning(
                "Failed to fetch game data for game ID %s after retries", game_id
            )
            return None

        if res.status_code == 401:
            if self._get_auth_token():
                return self.get_game_info_by_id(game_id, cache_results)
            else:
                return None

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

        # Get genres - now expanded in the query
        theme_names = [
            self.themes.get(x)
            for x in data.get("themes", [])
            if self.themes.get(x) in genre_themes
        ]
        # Parse expanded genre data directly (no extra API calls needed)
        genre_names = [
            genre_obj["name"]
            for genre_obj in data.get("genres", [])
            if isinstance(genre_obj, dict) and "name" in genre_obj
        ]
        genres = list(set(theme_names + genre_names))

        # Parse expanded cover data directly (no extra API call needed)
        cover_data = data.get("cover")
        if cover_data and isinstance(cover_data, dict) and "url" in cover_data:
            cover_filename = cover_data["url"].split("/")[-1]
        else:
            cover_filename = None

        game_data = {
            "cover": cover_filename,
            "developers": developer_objs,
            "genres": genres,
            "storyline": data.get("storyline"),
            "summary": data.get("summary"),
            "url": data.get("url"),
            "slug": data.get("slug"),
        }

        if cache_results:
            with self.cache_lock:
                self.game_cache[game_id] = game_data

        return game_data


def get_api(use_pro_tier: bool = None) -> Optional[IgbdApi]:
    """
    Create and return an IGDB API client instance.

    Args:
        use_pro_tier: Whether to use Pro tier. If None, reads from settings.

    Returns:
        IgbdApi: Configured IGDB API client, or None if initialization fails
    """
    try:
        if use_pro_tier is None:
            use_pro_tier = getattr(settings, "IGDB_USE_PRO_TIER", False)
        return IgbdApi(
            settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET, use_pro_tier
        )
    except (ValueError, KeyError, AttributeError) as e:
        log = logger.debug if getattr(settings, "DEBUG", False) else logger.error
        log("Failed to initialize IGDB API: %s", e)
        return None
    except requests.RequestException as e:
        log = logger.info if getattr(settings, "DEBUG", False) else logger.error
        log("Network error initializing IGDB API: %s", e)
        return None
