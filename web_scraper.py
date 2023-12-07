'''
Database Application For Tunes - Metadata Scraper Script

Author(s): Melesio Albavera <ma6hv@mst.edu>
Created: 25 Novemeber 2023
Updated: 6 December 2023
Version: 0.0
Description:
    A script that utilizes the Invidious and Spotify Application Programming 
    Interfaces in order to compile and submit musical metadata to the Database
    Application For Tunes.
Notes:
    Still squashing request timeout bugs.
    Additionally, still noticing missing tracks from large albums (The Beatle's
    discography.)
'''
from alive_progress import alive_bar, alive_it
from dotenv import dotenv_values, find_dotenv
import hashlib
import json
from more_itertools import chunked
from multiprocessing import Pool
from mutagen.easyid3 import EasyID3
from os import mkdir, remove
from os.path import isdir, isfile, getsize
import requests
import sys
from time import sleep
from typing import Final
from yt_dlp import YoutubeDL


def create_submission(
    artist: str,
    genres: list[str],
    album: str,
    total_tracks: int,
    image_link: str,
    release_year: str,
    song_name: str,
    track_number: int,
    filename: int
) -> None:
    '''
    TO-DO: Numpy-Style Docstring
    '''
    # Check if the file already exists.
    if isfile(f'output/{filename:016}.json'):
        return

    submission: dict = {
        'song' : {
            'title' : song_name,
            'track number' : track_number,
            'year' : release_year, 
        },
        'album' : {
            'title' : album,
            'total_tracks' : total_tracks,
            'genre' : genres,
            'image_link' : image_link
        },
        'artist' : {
            'name' : artist
        },
    }

    encoded_characters: dict = str.maketrans({
        ' ' : '%20',
        '$' : '%24',
        '#' : '%23',
        '&' : '%26',
        '?' : '%3F',
        ':' : '%3A'
    })
    invidious_search_result: requests.Response = requests.Response()
    invidious_search_result.status_code = 100
    while invidious_search_result.status_code != 200:
        try:
            invidious_search_result = requests.get(
                'https://vid.puffyan.us/api/v1/search/'
                f'?q={song_name.translate(encoded_characters)}'
                f'%20{artist.translate(encoded_characters)}&type=video'
            )
        except:
            print('Waiting out Invidious (for a minute.)')
            sleep(60)

    audio_source_url: str = (
        'https://vid.puffyan.us/watch?v='
        f'{invidious_search_result.json()[0]["videoId"]}'
    )

    # Yt-dlp configuration options.
    options = {
        'outtmpl' : f'temp/{song_name}',
        'quiet' : True,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    # Hopefully this hacky try-catch can be dropped soon.
    with YoutubeDL(options) as youtube_downloader:
        download_return_code: int = 1
        while download_return_code:
            try:
                download_return_code = youtube_downloader.download(
                    audio_source_url
                )
            except:
                print('Waiting out Google (for a minute.)')
                sleep(60)

    # Clear any tags the download may have so that hash is consistent.
    audio_tags = EasyID3(f'temp/{song_name}.mp3')
    audio_tags.delete()
    audio_tags.save()

    # Hash mp3.
    with open(f'temp/{song_name}.mp3', 'rb') as mp3:
        mp3_hash: str = hashlib.md5(mp3.read()).hexdigest()

    remove(f'temp/{song_name}.mp3')

    # Put metadata into dictionary and write to J.S.O.N. file.
    with open(f'output/{filename:016}.json', 'x') as file:
        submission['hash'] = mp3_hash
        file.write(json.dumps(submission, indent=4))


if __name__ == '__main__':
    # Set up folders if they do not exist already.
    if not isdir('./output/'):
        mkdir('./output/')
    if not isdir('./temp/'):
        mkdir('./temp/')

    # Grab the first command line argument.
    seed_genre_path: Final[str] = sys.argv[1]

    # Verify that 'seed_genre_path' exists and not empty.
    assert isfile(seed_genre_path)
    assert getsize(seed_genre_path) 
    print('List of seed genres found.')

    # Verify that 'env_path' exists and contains the nessessary credentials.
    env_path: Final[str] = find_dotenv('.env', raise_error_if_not_found=True)
    credentials: Final[dict] = dotenv_values(env_path)
    assert credentials['spotify_id'] 
    assert credentials['spotify_secret'] 
    print('Valid Spotify credentials found.')

    # Request valid Spotify Access Token and create authorization header.
    authorization_token: dict = requests.post(
        'https://accounts.spotify.com/api/token',
        data={
            'grant_type' : 'client_credentials',
            'client_id' : credentials['spotify_id'],
            'client_secret' : credentials['spotify_secret']
        },
        headers={'Content-Type' : 'application/x-www-form-urlencoded'}
    ).json()['access_token']
    authorization_header: dict = {
        'Authorization' : f'Bearer {authorization_token}'
    }

    # Create list of seed genres.
    with open(seed_genre_path) as seed_genres:
        genres: list[str] = seed_genres.read().splitlines()

    # Find the top (50) artists per genre and their associated genres.
    artist_ids: dict = {}
    for genre in alive_it(genres, title=f'Getting top 50 artists per genre:'):
        genre_query_response: dict = requests.get(
            (
                f'https://api.spotify.com/v1/search?q=genre%3A{genre}'
                '&type=artist&limit=50'
            ),
            headers=authorization_header
        ).json()['artists']['items']

        artist_ids |= {
            artist['id']: {
                'name' : artist['name'],
                'genres' : artist['genres'],
                'albums' : []
            }
            for artist in genre_query_response
        }

    # Compile the complete discography of every artist.
    for artist_id, genre_and_albums in alive_it(
        artist_ids.items(),
        title=f'Compling artist discographies:',
        enrich_print=False
    ):
        url: str = (
            f'https://api.spotify.com/v1/artists/{artist_id}'
            '/albums?include_groups=single%2Calbum&limit=50'
        )
        # Since Spotify caps us at 50 results per query max, loop until the
        # artist's entire discography is obtained.
        artist_discography: list[str] = []
        while url != None:
            response: dict = requests.get(
                url,
                headers=authorization_header
            ).json()
            url = response['next']
            batch: list[str] = [album['id'] for album in response['items']]
            artist_discography.extend(batch)

        # Associate artists to their discographies (list of album ids.)
        genre_and_albums['albums'] = artist_discography

    # Count the number of 
    number_of_albums: int = sum([
        len(artist_information['albums'])
        for artist_information in artist_ids.values()
    ])

    # Use the list of album ids to obtain more relevant album metadata,
    # including the tracklist.
    with alive_bar(
        number_of_albums,
        title=f'Retriving individudal album information:',
        enrich_print=False
    ) as progress_bar:
        filename: int = 0
        for artist_id, artist_information in artist_ids.items():
            # In order to reduce the number of A.P.I. calls, retrive album
            # information in chunks of 20.
            chunked_artist_discography: list = list(
                chunked(artist_information['albums'], 20)
            )
            complete_discography: list = []
            for chunk in chunked_artist_discography:
                url: str = (
                    'https://api.spotify.com/v1/albums?'
                    f'ids={"%2C".join(chunk)}'
                )
                discography_chunk: list = requests.get(
                    url,
                    headers=authorization_header
                ).json()['albums']

                # Loop until all tracks in an album's tracklist are retrived.
                for album in discography_chunk:
                    next_url: str = album['tracks']['next']
                    while next_url != None:
                        additional_tracks_response: dict = requests.get(
                            next_url,
                            headers=authorization_header
                        ).json()
                        next_url = additional_tracks_response['next']
                        album['tracks']['items'] += additional_tracks_response['items']

                complete_discography += discography_chunk

                progress_bar(len(chunk))

            # Replace album ids with actual metadata.
            artist_information['albums'] = complete_discography

    # Finally, begin parsing submissions.
    with alive_bar(
        title=f'Parsing metadata into J.S.O.N. submissions:',
        enrich_print=False
    ) as progress_bar:
        id_number: int = 0
        for artist_id, artist_information in artist_ids.items():
            artist_name: str = artist_information['name']
            genre_list: list[str] = artist_information['genres']
            albums: list[dict] = artist_information['albums']

            for album in albums:
                album_title: str = album['name']
                total_tracks: int = album['total_tracks']
                image_link: str = album['images'][0]['url']
                year: str = album['release_date'].split('-')[0]
                tracklist: list[tuple] = [
                    (
                        artist_name,
                        genre_list,
                        album_title,
                        total_tracks,
                        image_link,
                        year,
                        track['name'],
                        track['track_number'],
                        (id_number := id_number + 1)
                    ) for track in album['tracks']['items']
                ]

                with Pool(16) as pool:
                    pool.starmap(create_submission, tracklist)
                    progress_bar()

    print('Done.')
