# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and see TMDb posters!")

# TMDb API key
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. Posters will not display.")

# Connect to Google Sheet
try:
    sheet = gspread.service_account_from_dict(st.secrets["gcp_service_account"]) \
                      .open_by_key(st.secrets["sheet_id"]) \
                      .worksheet("Sheet1")
except Exception as e:
    st.error(f"Error connecting to Google Sheet: {e}")
    st.stop()

# Load data
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user","movie","type","note","year","language","timestamp"])

# Helper: fetch TMDb poster
def get_tmdb_poster(title, year=None, language=None):
    if not tmdb_api_key:
        return None
    params = {"api_key": tmdb_api_key, "query": title}
    if year:
        params["year"] = year
    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params).json()
    results = resp.get("results", [])
    if language:
        results = [r for r in results if r.get("original_language","").upper() == language.upper()]
    if results:
        poster_path = results[0].get("poster_path")
        if poster_path:
            return f"https://image.tmdb.org/t/p/w200{poster_path}"
    return None

# Form to add movie
st.subheader("Add a new movie/show")
with st.form("add_movie"):
    user = st.text_input("Your Name")
    movie = st.text_input("Movie/Show Title")
    type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
    year = st.text_input("Year (optional)")
    language = st.text_input("Language (optional, e.g., EN, KO)")
    note = st.text_area("Notes / Thoughts")
    submitted = st.form_submit_button("Add")

    if submitted:
        if user and movie:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.append_row([user, movie, type_, note, year, language, timestamp])
                st.success(f"Added {movie} by {user}!")
                df = pd.DataFrame(sheet.get_all_records())  # refresh
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill your name and movie title.")

# Display movies
st.subheader("Your Movies/Shows")
search = st.text_input("Search by title or user:")
if search:
    df_display = df[df["movie"].str.contains(search, case=False, na=False) |
                    df["user"].str.contains(search, case=False, na=False)]
else:
    df_display = df

if df_display.empty:
    st.info("No movies found.")
else:
    # 3 columns layout for posters
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        poster_url = get_tmdb_poster(row["movie"], row.get("year"), row.get("language"))
        with cols[i % 3]:
            if poster_url:
                st.image(poster_url, width=150)
            st.markdown(f"**{row['movie']} ({row.get('year','')}) [{row.get('language','').upper()}]**")
            st.markdown(f"Type: {row['type']}")
            st.markdown(f"Added by: {row['user']}")
            if row['note']:
                st.markdown(f"Notes: {row['note']}")
