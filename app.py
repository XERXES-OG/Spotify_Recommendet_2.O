import os
import re
import pandas as pd
from flask import Flask, session, request, redirect, render_template, url_for
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from utils import fetch_track_ids_from_playlist, enrich_track_data
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

sp_oauth = SpotifyOAuth(
    os.getenv("SPOTIPY_CLIENT_ID"),
    os.getenv("SPOTIPY_CLIENT_SECRET"),
    os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="playlist-read-private playlist-read-collaborative",
    cache_path=".cache"
)

if os.path.exists(".cache"):
    os.remove(".cache")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('playlists'))

@app.route('/playlists')
def playlists():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    results = sp.current_user_playlists()
    user_playlists = [{'name': item['name'], 'id': item['id']} for item in results['items']]
    return render_template('playlists.html', playlists=user_playlists)

@app.route('/generate_csv/<playlist_id>/<playlist_name>')
def generate_csv(playlist_id, playlist_name):
    try:
        token_info = session.get('token_info', None)
        sp = spotipy.Spotify(auth=token_info['access_token'])

        safe_name = re.sub(r'[\\/*?:"<>|]', "", playlist_name)
        os.makedirs("csv", exist_ok=True)

        tracks = fetch_track_ids_from_playlist(playlist_id, sp)
        file_name = f"csv/playlist_{safe_name}.csv"
        enrich_track_data(tracks, sp, output_file=file_name)

        return redirect(url_for('recommend_form',
                                playlist_name=safe_name,
                                playlist_id=playlist_id))
    except Exception as e:
        return f"<h3>Error: {e}</h3>"

@app.route('/recommend/<playlist_name>')
def recommend_form(playlist_name):
    playlist_id = request.args.get('playlist_id')
    return render_template('recommend_form.html',
                           playlist_name=playlist_name,
                           playlist_id=playlist_id)

@app.route('/recommend_songs', methods=['POST'])
def recommend_songs():
    playlist_name = request.form.get('playlist_name')
    playlist_id = request.form.get('playlist_id')
    input_song = request.form.get('song_name')
    safe_name = re.sub(r'[\\/*?:"<>|]', "", playlist_name)
    file_path = f"csv/playlist_{safe_name}.csv"

    try:
        df = pd.read_csv(file_path)
        recommendations = metadataBasedRecommendations(input_song, df)

        if len(recommendations) == 0:
            return render_template('recommend_form.html', playlist_name=playlist_name, playlist_id=playlist_id,
                                   error="Song not found or no recommendations.")

        return render_template('recommendations.html',
                               playlist_name=playlist_name,
                               playlist_id=playlist_id,
                               song_name=input_song,
                               recommendations=recommendations.to_dict(orient='records'))
    except Exception as e:
        return f"<h3>Error: {e}</h3>"

@app.route('/logout')
def logout():
    session.clear()
    if os.path.exists(".cache"):
        os.remove(".cache")
    return redirect(url_for('index'))

def metadataBasedRecommendations(inputSongName, musicDf, numRecommendations=5):
    if inputSongName not in musicDf['Track Name'].values:
        return []

    inputSong = musicDf[musicDf['Track Name'] == inputSongName].iloc[0]
    df = musicDf.copy()

    df['score'] = 0
    df['score'] += (df['Artists'] == inputSong['Artists']).astype(int) * 3
    df['score'] += (df['Album ID'] == inputSong['Album ID']).astype(int) * 2
    df['score'] += df['Popularity'] / 20

    def date_weight(release_date):
        try:
            delta = (datetime.now() - datetime.strptime(release_date, '%Y-%m-%d')).days
            return 1 / (delta + 1)
        except:
            return 0.001

    df['score'] += df['Release Date'].apply(date_weight)
    df = df[df['Track Name'] != inputSongName]

    return df.sort_values(by='score', ascending=False).head(numRecommendations)[
        ['Track Name', 'Artists', 'Album Name', 'Release Date', 'Track ID', 'Popularity']]

if __name__ == '__main__':
    app.run(host='127.0.0.0:5000', debug=True)
