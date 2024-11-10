import requests
from django.conf import settings

game_status_map = {
    0: 'released',
    2: 'alpha',
    3: 'beta',
    4: 'early_access',
    5: 'offline',
    6: 'cancelled',
    7: 'rumored',
    8: 'delisted',
}

genre_themes = [
    '4X (explore, expand, exploit, and exterminate)',
    'Action',
    'Horror',
    'Open world',
    'Party',
    'Sandbox',
    'Stealth',
    'Survival',
]


class IgbdApi():

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

        self.headers = {}
        self.company_cache = {}
        self.game_cache = {}
        self.genre_cache = {}
        self.release_date_statuses = {}
        self.release_dates = {}

        self._get_auth_token()
        self._get_themes()

    def _get_auth_token(self):
        data = requests.post(
            f'https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials'
        ).json()

        if data.get('access_token'):
            self.headers = {
                'Client-Id': settings.IGDB_CLIENT_ID,
                'Authorization': f'Bearer {data["access_token"]}'
            }
            return True
        else:
            return False

    def _get_themes(self):
        results = requests.post(
            'https://api.igdb.com/v4/themes/',
            headers=self.headers,
            data='limit 500; fields name;'
        ).json()
        self.themes = {x['id']: x['name'] for x in results}

    def _get_cover_by_id(self, cover_id: int):
        print(f'Getting data for cover {cover_id}')
        results = requests.post(
            'https://api.igdb.com/v4/covers/',
            headers=self.headers,
            data=f'where id={cover_id}; fields url;'
        ).json()
        assert len(results) == 1
        return results[0]['url'].split('/')[-1]

    def _get_company_by_id(self, company_id: int, cache_results: True):
        if cache_results and company_id in self.company_cache:
            return self.company_cache[company_id]

        print(f'Getting data for company {company_id}')
        res = requests.post(
            'https://api.igdb.com/v4/companies/',
            headers=self.headers,
            data=f'where id={company_id}; fields id,name,slug,parent;'
        )

        try:
            results = res.json()
            assert len(results) == 1
            self.company_cache[company_id] = results[0]
            return results[0]
        except:
            return

    def _get_genre_by_id(self, genre_id: int, cache_results: True):
        if cache_results and genre_id in self.genre_cache:
            return self.genre_cache[genre_id]

        print(f'Getting data for genre {genre_id}')
        res = requests.post(
            'https://api.igdb.com/v4/genres/',
            headers=self.headers,
            data=f'where id={genre_id}; fields name;'
        )

        try:
            results = res.json()
            assert len(results) == 1
            genre_name = results[0]['name']
            self.genre_cache[genre_id] = genre_name
            return genre_name
        except:
            return

    def _get_release_dates_by_id(self, game_id: int, cache_results: True):
        if cache_results and game_id in self.release_dates:
            return self.release_dates[game_id]

        res = requests.post(
            'https://api.igdb.com/v4/release_dates/',
            headers=self.headers,
            data=f'limit 500; where game={game_id}; fields date, status;'
        )
        dates = res.json()

        self.release_dates[game_id] = dates
        return dates

    def _get_chunks(self, lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def _get_games_chunk(self, game_ids):

        # Get game data from API
        res = requests.post(
            'https://api.igdb.com/v4/games/',
            headers=self.headers,
            data=f'where id={game_ids}; limit {len(game_ids)}; fields id,slug,cover,genres,first_release_date,summary,storyline,url,themes,involved_companies.*;'
        )

        results = res.json()
        for data in results:
            game_id = data['id']

            # Get developer information
            developers = []
            porters = []
            supporters = []
            publishers = []

            for involved_company_dict in data.get('involved_companies', []):
                company_id = involved_company_dict['company']

                if involved_company_dict['developer']:
                    developers.append(company_id)

                if involved_company_dict['supporting']:
                    supporters.append(company_id)

                if involved_company_dict['publisher']:
                    publishers.append(company_id)

                if involved_company_dict['porting']:
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
                company_obj = self._get_company_by_id(company_id, True)
                if not company_obj:
                    continue

                parent_id = company_obj.get('parent')
                if parent_id:
                    parent_obj = self._get_company_by_id(parent_id, True)
                else:
                    parent_obj = None

                developer_objs.append(
                    {
                        'id': company_id,
                        'name': company_obj['name'],
                        'slug': company_obj['slug'],
                        'parent': parent_obj,
                    }
                )

            # Get genres
            theme_names = [self.themes.get(x) for x in data.get(
                'themes', []) if self.themes.get(x) in genre_themes]
            genre_names = [self._get_genre_by_id(
                x, True) for x in data.get('genres', [])]
            genres = list(set(theme_names + genre_names))

            game_data = {
                'cover': self._get_cover_by_id(data['cover']),
                'developers': developer_objs,
                'genres': genres,
                'storyline': data.get('storyline'),
                'summary': data.get('summary'),
                'url': data.get('url'),
                'slug': data.get('slug'),
            }

            print(f'Game {game_id} data downloaded')
            self.game_cache[game_id] = game_data

        return game_data

    def get_game_info_by_id(self, game_id: int):
        # Build cache first
        if game_id not in self.game_cache:
            self.get_all_games()

        return self.game_cache.get(game_id)

    def get_all_games(self):
        from .models import Game
        game_ids = tuple(Game.objects.values_list('id', flat=True))
        for chunk in self._get_chunks(game_ids, 100):
            print(f'Fetching games {chunk[0]} to {chunk[-1]}')
            self._get_games_chunk(chunk)


def get_api():
    return IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
