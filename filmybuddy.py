# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and get TMDb posters & recommendations!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key", None)
if not tmdb_api_key:
    st.warning("TMDb API key not found. Posters and TMDb info will not work.")

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
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "year", "language", "timestamp"])

# -------------------
# Helper: Fetch TMDb poster
# -------------------
def get_tmdb_poster(title, year=None, language=None, api_key=None):
    if not api_key:
        return None
    params = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year
    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params).json()
    results = resp.get("results", [])
    if language:
        results = [m for m in results if m.get("original_language","").upper() == language.upper()]
    if results:
        movie = results[0]
        if movie.get("poster_path"):
            return f"https://image.tmdb.org/t/p/w200{movie['poster_path']}"
    return None

# -------------------
# Form to add new movie
# -------------------
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
                # Refresh dataframe
                df = pd.DataFrame(sheet.get_all_records())
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill at least your name and the movie title.")

# -------------------
# Display movies with posters
# -------------------
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
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        poster = get_tmdb_poster(row["movie"], row.get("year"), row.get("language"), tmdb_api_key)
        with cols[i % 3]:
            if poster:
                st.image(poster, width=150)
            st.markdown(f"**{row['movie']} ({row.get('year','')}) [{row.get('language','').upper()}]**")
            st.markdown(f"Type: {row['type']}")
            st.markdown(f"Added by: {row['user']}")
            if row['note']:
                st.markdown(f"Notes: {row['note']}")

# -------------------
# TMDb Recommendations for last movie
# -------------------
if tmdb_api_key and not df.empty:
    st.subheader("TMDb Recommendations 🎬")
    last_movie = df.iloc[-1]["movie"]
    last_year = df.iloc[-1].get("year")
    last_lang = df.iloc[-1].get("language")

    search_params = {"api_key": tmdb_api_key, "query": last_movie}
    if last_year:
        search_params["year"] = last_year
    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=search_params).json()
    results = resp.get("results", [])
    if last_lang:
        results = [m for m in results if m.get("original_language","").upper() == last_lang.upper()]
    if results:
        movie_id = results[0]["id"]
        rec_resp = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations",
                                params={"api_key": tmdb_api_key}).json()
        recs = rec_resp.get("results", [])[:6]

        rec_cols = st.columns(3)
        for j, r in enumerate(recs):
            poster = f"https://image.tmdb.org/t/p/w200{r['poster_path']}" if r.get('poster_path') else None
            title = r['title']
            year = r.get('release_date','')[:4]
            lang = r.get('original_language','').upper()
            with rec_cols[j % 3]:
                if poster:
                    st.image(poster, width=150)
                st.markdown(f"**{title} ({year}) [{lang}]**")
