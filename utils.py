import csv
from spotipy.exceptions import SpotifyException

def fetch_track_ids_from_playlist(playlist_id, sp, limit=20):
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    count = 0

    while results and count < limit:
        for item in results['items']:
            if count >= limit:
                break
            track = item['track']
            if track and track['id']:
                tracks.append({
                    'Track Name': track['name'],
                    'Track ID': track['id']
                })
                count += 1
        results = sp.next(results) if results['next'] and count < limit else None
    return tracks

def enrich_track_data(tracks, sp, output_file='detailed_tracks.csv'):
    detailed_data = []

    for track in tracks:
        track_id = track['Track ID']
        try:
            track_info = sp.track(track_id)
            data = {
                'Track Name': track_info['name'],
                'Artists': ', '.join([a['name'] for a in track_info['artists']]),
                'Album Name': track_info['album']['name'],
                'Album ID': track_info['album']['id'],
                'Track ID': track_info['id'],
                'Popularity': track_info['popularity'],
                'Release Date': track_info['album']['release_date'],
               
            }

            detailed_data.append(data)
        except SpotifyException as e:
            print(f"Skipping track {track_id} due to error: {e}")

    if detailed_data:
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=detailed_data[0].keys())
            writer.writeheader()
            writer.writerows(detailed_data)
