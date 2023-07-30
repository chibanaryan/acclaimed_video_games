import requests
from django.conf import settings


class IgbdApi():

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.get_auth_token()

    def get_auth_token(self):
        data = requests.post(
            f'https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={self.client_secret}&grant_type=client_credentials'
        ).json()

        self.headers = {
            'Client-Id': settings.IGDB_CLIENT_ID,
            'Authorization': f'Bearer {data["access_token"]}'
        }

    def get_game_info(self, game):

        res = requests.post(
            'https://api.igdb.com/v4/games/',
            headers=self.headers,
            data=f'search "{game.name}"; fields id,artworks;'
        )

        if res.status_code == 401:
            self.get_auth_token()
            return self.get_game_info(game)

        results = res.json()

        game_id = None
        artwork_id = None

        for result in results:
            if result.get('artworks'):
                game_id = result['id']
                artwork_id = result['artworks'][0]
                break

        if not game_id or not artwork_id:
            return 

        results = requests.post(
            'https://api.igdb.com/v4/artworks/',
            headers=self.headers,
            data=f'where id={artwork_id}; fields url;'
        ).json()
        url = results[0]['url']

        artwork_name = url.split('/')[-1]

        return {
            'game_id': game_id,
            'artwork_id': artwork_name,
        }


api = IgbdApi(settings.IGDB_CLIENT_ID, settings.IGDB_CLIENT_SECRET)
