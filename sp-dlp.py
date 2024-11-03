#!/usr/bin/env python

import os
import requests
import shutil
import yt_dlp
import spotipy
from configparser import ConfigParser
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, error

# Ask user for playlist link
playlist_id = input("Your Playlist Link: ")

cfg_file_path = "config.cfg"

# Check if the configuration file exists
if not os.path.exists(cfg_file_path):
    # Define the template configuration file content with placeholders
    cfg_template = """
    [Spotify]
    client_id = {client_id}
    client_secret = {client_secret}
    """

    # Get user input for each configuration value
    client_id = input("Enter your spotify client id: ")
    client_secret = input("Enter your spotify client secret: ")

    # Replace placeholders in the template with user input
    cfg_content = cfg_template.format(client_id=client_id, client_secret=client_secret)

    # Write the configuration content to a cfg file
    with open(cfg_file_path, "w") as cfg_file:
        cfg_file.write(cfg_content)

    print("Configuration saved to 'config.cfg'")
else:
    print("Configuration file already exists. Skipping input prompts.")

# Parse config from config.cfg
config = ConfigParser()
config.read('config.cfg')

# Get user-specific variables from config.cfg
client_id = config.get('Spotify', 'client_id')
client_secret = config.get('Spotify', 'client_secret')

# Set up Spotify client
client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Function to get playlist metadata from Spotify
def get_playlist_metadata(playlist_id):
    playlist = sp.playlist(playlist_id)
    playlist_data = []

    for item in playlist["tracks"]["items"]:
        track = item["track"]
        track_info = {
            "track_name": track["name"],
            "artist_name": [artist["name"] for artist in track["artists"]][0],
            "album_name": track["album"]["name"],
            "release_date": track["album"]["release_date"],
            "album_cover_url": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
        }
        playlist_data.append(track_info)

    return playlist_data

# Function to search, download, and add metadata to the audio file
def download_and_embed_metadata(track):
    search_query = f"{track['track_name']} {track['artist_name']} official audio"
    videos_search = VideosSearch(search_query, limit=1)
    search_results = videos_search.result()

    if search_results["result"]:
        video_url = f"https://www.youtube.com/watch?v={search_results['result'][0]['id']}"
        filename = f"{track['track_name']} - {track['artist_name']}.mp3"

        # Download the YouTube video as an MP3
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"{track['track_name']} - {track['artist_name']}",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        print(f"Downloading {track['track_name']} by {track['artist_name']} from YouTube: {video_url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Add metadata to the downloaded MP3 file
        add_metadata(filename, track)

# Function to add metadata to the downloaded MP3 file
def add_metadata(filename, track):
    audio = EasyID3(filename)
    audio["title"] = track["track_name"]
    audio["artist"] = track["artist_name"]
    audio["album"] = track["album_name"]
    audio["date"] = track["release_date"]
    audio.save()

    # If album cover URL is available, download and add it as album art
    if track["album_cover_url"]:
        try:
            response = requests.get(track["album_cover_url"])
            response.raise_for_status()  # Check if the request was successful
            album_cover_data = response.content

            audio = ID3(filename)
            audio["APIC"] = APIC(
                encoding=3,         # UTF-8
                mime="image/jpeg",  # MIME type for JPEG images
                type=3,             # Cover (front)
                desc="Cover",
                data=album_cover_data
            )
            audio.save(v2_version=3)
            print(f"Metadata and album art added to {filename}")
        except (requests.RequestException, error) as e:
            print(f"Could not add album cover: {e}")

def moveToDownloads():
    # Define the current directory and the new folder name
    playlist = sp.playlist(playlist_id)
    playlist_name = playlist["name"]

    # Define the name for the Downloads directory and the subdirectory
    downloads_directory = "Downloads"
    subdirectory = playlist_name

    # Get the current working directory
    current_directory = os.getcwd()

    # Create the full path for the Downloads directory
    path_downloads_directory = os.path.join(current_directory, downloads_directory)

    # Create the Downloads directory
    os.makedirs(path_downloads_directory, exist_ok=True)

    # Create the full path for the subdirectory inside Downloads
    path_subdirectory = os.path.join(path_downloads_directory, subdirectory)

    # Create the subdirectory
    os.makedirs(path_subdirectory, exist_ok=True)

    # Move all mp3 files from the current directory to the subdirectory
    for filename in os.listdir(current_directory):
        if filename.endswith('.mp3'):
            # Construct full file path
            file_path = os.path.join(current_directory, filename)
            # Construct the destination file path
            destination_file_path = os.path.join(path_subdirectory, filename)

            # Check if the file already exists at the destination
            if os.path.exists(destination_file_path):
                # If it exists, remove the existing file
                os.remove(destination_file_path)

            # Move the mp3 file to the subdirectory
            shutil.move(file_path, path_subdirectory)

# Main function
def download_spotify_playlist(playlist_id):
    playlist_data = get_playlist_metadata(playlist_id)
    for track in playlist_data:
        download_and_embed_metadata(track)
    moveToDownloads()

# Call main function
download_spotify_playlist(playlist_id)
