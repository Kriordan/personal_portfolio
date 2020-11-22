import os
from pathlib import Path
import json

import requests

def get_yt_playlist_data():
    print('Requesting youtube playlist data...')
    playlist_ids_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "youtube-ids.json"
    playlist_data_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "youtube-playlist-data.json"
    # clean_playlist_data_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "clean-youtube-playlist-data.json"
    
    playlist_data = {}
    playlist_data['playlists'] = []

    with open(playlist_ids_path) as json_file:
        playlist_ids = json.loads(json_file.read())['playlistIds']

    for id in playlist_ids:
        yt_playlist_url = 'https://youtube.googleapis.com/youtube/v3/playlists'
        payload = {
            'part': 'snippet',
            'id': id,
            'key': os.getenv('YT_API_KEY')
        }
        res = requests.get(yt_playlist_url, params=payload)
        playlist_data['playlists'].append(res.json())

    with open(playlist_data_path, mode='w') as json_file:
        json.dump(playlist_data, json_file)
        
    # clean_playlist_data = clean_yt_data(playlist_data)
        
    # with open(clean_playlist_data_path, mode='w') as json_file:
    #     json.dump(clean_playlist_data, json_file)

    print('Finished gathering youtube playlist data')

# def clean_yt_data(data):
#     some_fucking_dict = {}
#     some_fucking_dict['playlists'] = []
    
#     for playlist in data['playlists']:
#         other_fucking_dict = {}
#         other_fucking_dict['id'] = playlist['items'][0]['id']
#         other_fucking_dict['thumbnailUrl'] = playlist['items'][0]['snippet']['thumbnails']['standard']['url']
        
#         some_fucking_dict['playlists'].append(some_fucking_dict)
        
#     return some_fucking_dict
    