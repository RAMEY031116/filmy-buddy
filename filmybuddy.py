# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and get recommendations with posters!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key", None)
if not tmdb_api_key:
    st.warning("TMDb API key not found in secrets. Only internal recommendations will work.")

# -------------------
# Connect to Google Sheet
# -------------------
try:
    sheet = gspread.service_account_from_dict(st.secrets["gcp_service_account"]) \
                      .open_by_key(st.secrets["sheet_id"]) \
                      .worksheet("Sheet1")
except KeyError:
    st.error("Missing 'gcp_service_account' or 'sheet_id' in Streamlit secrets.toml")
    st.stop()
except Exception as e:
    st.error(f"Error connecting to Google Sheet: {e}")
    st.stop()

# -------------------
# Load data from Google Sheet
# -------------------
try:
    data = sheet.get_all_records(expected_headers=["user","movie","type","note","timestamp"])
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "timestamp"])

# -------------------
# Form to add a new movie/show
# -------------------
st.subheader("Add a new movie/show")
with st.form("add_movie"):
    user = st.text_input("Your Name")
    movie = st.text_input("Movie/Show Title")
    type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
    note = st.text_area("Notes / Thoughts")
    submitted = st.form_submit_button("Add")

    if submitted:
        if user and movie:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.append_row([user, movie, type_, note, timestamp])
                st.success(f"Added {movie} by {user}!")

                # Refresh dataframe
                data = sheet.get_all_records(expected_headers=["user","movie","type","note","timestamp"])
                df = pd.DataFrame(data)
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill at least your name and the movie title.")

# -------------------
# Display current movies/shows
# -------------------
def fetch_tmdb_poster(title, api_key):
    """Return the TMDb poster URL for a movie."""
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": api_key, "query": title}
    resp = requests.get(search_url, params=params).json()
    if resp.get("results"):
        poster_path = resp["results"][0].get("poster_path")
        if poster_path:
            return f"https://image.tmdb.org/t/p/w200{poster_path}"  # smaller width
    return None

if not df.empty:
    st.subheader("Your Movies/Shows")
    
    search = st.text_input("Search by title or user:")
    if search:
        df_filtered = df[df['movie'].str.contains(search, case=False, na=False) |
                         df['user'].str.contains(search, case=False, na=False)]
    else:
        df_filtered = df

    for _, row in df_filtered.iterrows():
        col1, col2 = st.columns([1,4])
        poster = fetch_tmdb_poster(row['movie'], tmdb_api_key) if tmdb_api_key else None
        if poster:
            col1.image(poster, width=100)
        col2.markdown(f"**{row['movie']}** ({row['type']})  \nAdded by: {row['user']}  \nNotes: {row['note']}  \nTimestamp: {row['timestamp']}")

    # -------------------
    # Internal Recommendations
    # -------------------
    st.subheader("Internal Recommendations 🎯")
    if len(df) > 1:
        last_type = df.iloc[-1]['type']
        same_type_movies = df[df['type'] == last_type]['movie'].tolist()
        all_movies = df['movie'].tolist()
        recommendations = random.sample([m for m in all_movies if m not in same_type_movies], 
                                        min(3, max(len(all_movies)-len(same_type_movies), 0)))
        if recommendations:
            for rec in recommendations:
                poster = fetch_tmdb_poster(rec, tmdb_api_key) if tmdb_api_key else None
                cols = st.columns([1,4])
                if poster:
                    cols[0].image(poster, width=100)
                cols[1].write(rec)
        else:
            st.info("No new internal recommendations available yet.")
    else:
        st.info("Add more movies to get internal recommendations.")

    # -------------------
    # TMDb Recommendations
    # -------------------
    if tmdb_api_key:
        st.subheader("TMDb Recommendations 🎬")
        last_movie = df.iloc[-1]['movie']
        search_url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": tmdb_api_key, "query": last_movie}
        resp = requests.get(search_url, params=params).json()
        if resp.get("results"):
            movie_id = resp["results"][0]["id"]
            rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
            rec_resp = requests.get(rec_url, params={"api_key": tmdb_api_key}).json()
            recs = rec_resp.get("results", [])[:3]
            for r in recs:
                poster = f"https://image.tmdb.org/t/p/w200{r['poster_path']}" if r.get('poster_path') else None
                cols = st.columns([1,4])
                if poster:
                    cols[0].image(poster, width=100)
                cols[1].markdown(f"**{r['title']}** ({r.get('release_date','')[:4]})")
        else:
            st.info("No TMDb recommendations found for the last movie.")
else:
    st.info("No data found in the Google Sheet. Check your sheet ID and worksheet name.")
