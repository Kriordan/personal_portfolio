import os
from pathlib import Path
import json

import requests

def get_yt_playlist_data():
    print('Requesting youtube playlist data...')
    playlist_ids_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "youtube-ids.json"
    playlist_data_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "youtube-playlist-data.json"
    clean_playlist_data_path = Path(__file__).resolve().parent.parent / 'data' / 'jsonfiles' / "clean-youtube-playlist-data.json"
    
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
        
    clean_playlist_data = clean_yt_data(playlist_data)
        
    with open(clean_playlist_data_path, mode='w') as json_file:
        json.dump(clean_playlist_data, json_file)

    print('Finished gathering youtube playlist data')

def clean_yt_data(playlist_data):
    template_data = {}
    template_data['playlists'] = []
    print(playlist_data)
    for playlist in playlist_data['playlists']:
        temp_dict = dict(
            id=playlist['items'][0]['id'],
            title=playlist['items'][0]['snippet']['title'],
            channelTitle=playlist['items'][0]['snippet']['channelTitle']
        )
        if 'standard' in playlist['items'][0]['snippet']['thumbnails'].keys():
            temp_dict['thumbnail'] = playlist['items'][0]['snippet']['thumbnails']['standard']['url']
        elif 'high' in playlist['items'][0]['snippet']['thumbnails'].keys():
            temp_dict['thumbnail'] = playlist['items'][0]['snippet']['thumbnails']['high']['url']
        else:
            temp_dict['thumbnail'] = 'http://placecorgi.com/640/480'
        template_data['playlists'].append(temp_dict)
    
    return template_data
    