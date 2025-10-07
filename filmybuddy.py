# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and see their posters!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key", None)
if not tmdb_api_key:
    st.warning("TMDb API key not found in secrets. TMDb posters will not work.")

# -------------------
# Connect to Google Sheet
# -------------------
try:
    sheet = gspread.service_account_from_dict(st.secrets["gcp_service_account"]) \
                      .open_by_key(st.secrets["sheet_id"]) \
                      .worksheet("Sheet1")
except Exception as e:
    st.error(f"Error connecting to Google Sheet: {e}")
    st.stop()

# -------------------
# Load data
# -------------------
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "timestamp"])

# -------------------
# Add new movie/show
# -------------------
st.subheader("Add a New Movie/Show")
with st.form("add_movie"):
    user = st.text_input("Your Name")
    movie = st.text_input("Movie/Show Title")
    type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
    note = st.text_area("Notes / Thoughts")
    submitted = st.form_submit_button("Add")
    if submitted and user and movie:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            sheet.append_row([user, movie, type_, note, timestamp])
            st.success(f"Added {movie} by {user}!")
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error adding movie: {e}")
    elif submitted:
        st.warning("Please fill at least your name and the movie title.")

# -------------------
# Function to get TMDb poster
# -------------------
def get_tmdb_poster(title, api_key):
    if not api_key:
        return None
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": api_key, "query": title}
    resp = requests.get(search_url, params=params).json()
    results = resp.get("results")
    if results:
        poster_path = results[0].get("poster_path")
        if poster_path:
            return f"https://image.tmdb.org/t/p/w200{poster_path}"
    return None

# -------------------
# Display movies/shows with posters
# -------------------
if not df.empty:
    st.subheader("Your Movies/Shows with Posters")
    cols = st.columns(3)
    for i, row in df.iterrows():
        poster = get_tmdb_poster(row["movie"], tmdb_api_key)
        with cols[i % 3]:
            st.write(f"**{row['movie']}**")
            if poster:
                st.image(poster, use_container_width=True)
            else:
                st.write("Poster not found")
else:
    st.info("No movies/shows found in your Google Sheet.")
