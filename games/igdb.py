import requests
from django.conf import settings
from datetime import datetime

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
        self._get_release_statuses()

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

    def _get_release_statuses(self):
        results = requests.post(
            'https://api.igdb.com/v4/release_date_statuses/',
            headers=self.headers,
            data=f'fields name;'
        ).json()

        self.release_date_statuses = {x['name']: x['id'] for x in results}

    def _get_cover_by_id(self, cover_id: int):
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

        res = requests.post(
            'https://api.igdb.com/v4/companies/',
            headers=self.headers,
            data=f'where id={company_id}; fields id,name,parent;'
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
            data=f'where game={game_id}; fields date, status;'
        )
        dates = res.json()

        self.release_dates[game_id] = dates
        return dates

    def get_game_info_by_id(self, game_id: int, cache_results: True):

        # Check cache first
        if cache_results and game_id in self.game_cache:
            return self.game_cache[game_id]

        # Get game data from API
        res = requests.post(
            'https://api.igdb.com/v4/games/',
            headers=self.headers,
            data=f'where id={game_id}; fields cover,genres,first_release_date,summary,storyline,url,involved_companies.*;'
        )

        if res.status_code == 401:
            if self._get_auth_token():
                return self.game_info_by_id(game_id, cache_results)
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
            company_obj = self._get_company_by_id(company_id, cache_results)
            if not company_obj:
                continue

            parent_id = company_obj.get('parent')
            if parent_id:
                parent_obj = self._get_company_by_id(parent_id, cache_results)
            else:
                parent_obj = None

            developer_objs.append(
                {
                    'id': company_id,
                    'name': company_obj['name'],
                    'parent': parent_obj,
                }
            )

        # Get the full release dates
        full_release_status = self.release_date_statuses['Full Release']
        full_release_dates = []
        for obj in self._get_release_dates_by_id(game_id, cache_results):
            if not obj.get('status') or obj.get('status') == full_release_status:
                if obj.get('date'):
                    full_release_dates.append(
                        datetime.fromtimestamp(obj['date']))

        # Choose the earliest release date
        full_release_dates.sort()
        release_date = full_release_dates[0]

        game_data = {
            'cover': self._get_cover_by_id(data['cover']),
            'developers': developer_objs,
            'genres': [self._get_genre_by_id(x, cache_results) for x in data.get('genres', [])],
            'storyline': data.get('storyline'),
            'summary': data.get('summary'),
            'url': data.get('url'),
            'year': release_date.year,
        }

        self.game_cache[game_id] = game_data

        return game_data


def get_api():
    return IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
