import requests
from django.conf import settings
from datetime import datetime


class IgbdApi():

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {}
        self.company_cache = {}
        self.game_cache = {}
        self.genre_cache = {}
        self.get_auth_token()

    def get_auth_token(self):
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

    def get_cover_by_id(self, cover_id: int):
        results = requests.post(
            'https://api.igdb.com/v4/covers/',
            headers=self.headers,
            data=f'where id={cover_id}; fields url;'
        ).json()
        assert len(results) == 1
        return results[0]['url'].split('/')[-1]

    def get_company_by_id(self, company_id: int):
        if company_id in self.company_cache:
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
        
    def get_genre_by_id(self, genre_id: int):
        if genre_id in self.genre_cache:
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

    def get_game_info_by_id(self, game_id: int):
        if game_id in self.game_cache:
            return self.game_cache[game_id]

        res = requests.post(
            'https://api.igdb.com/v4/games/',
            headers=self.headers,
            data=f'where id={game_id}; fields cover,genres,first_release_date,summary,storyline,involved_companies.*;'
        )

        if res.status_code == 401:
            if self.get_auth_token():
                return self.game_info_by_id(game_id)
            else:
                return

        results = res.json()
        assert len(results) == 1
        data = results[0]

        developers = []
        porters = []
        supporters = []
        publishers = []

        for involved_company_dict in data['involved_companies']:
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
            company_obj = self.get_company_by_id(company_id)
            parent_id = company_obj.get('parent')
            if parent_id:
                parent_obj = self.get_company_by_id(parent_id)
            else:
                parent_obj = None

            developer_objs.append(
                {
                    'id': company_id,
                    'name': company_obj['name'],
                    'parent': parent_obj,
                }
            )

        game_data = {
            'cover': self.get_cover_by_id(data['cover']),
            'developers': developer_objs,
            'genres': [self.get_genre_by_id(x) for x in data.get('genres', [])],
            'storyline': data.get('storyline'),
            'summary': data.get('summary'),
            'year': datetime.fromtimestamp(data['first_release_date']).year,
        }

        self.game_cache[game_id] = game_data

        return game_data


api = IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
