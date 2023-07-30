import requests
from django.conf import settings


class IgbdApi():

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {}
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

    def get_game_info(self, game):

        res = requests.post(
            'https://api.igdb.com/v4/games/',
            headers=self.headers,
            data=f'search "{game.name}"; fields id,cover;'
        )

        if res.status_code == 401:
            if self.get_auth_token():
                return self.get_game_info(game)
            else:
                return

        results = res.json()

        game_id = None
        cover_id = None

        for result in results:
            if result.get('cover'):
                game_id = result['id']
                cover_id = result['cover']
                break

        if not game_id or not cover_id:
            return

        results = requests.post(
            'https://api.igdb.com/v4/covers/',
            headers=self.headers,
            data=f'where id={cover_id}; fields url;'
        ).json()
        url = results[0]['url']

        artwork_name = url.split('/')[-1]

        return {
            'game_id': game_id,
            'artwork_id': artwork_name,
        }


api = IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
