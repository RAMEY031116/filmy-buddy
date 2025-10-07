# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows, see posters, and get recommendations!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key")
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
# Load data
# -------------------
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "year", "language", "timestamp"])

# -------------------
# Add a new movie/show
# -------------------
st.subheader("Add a New Movie/Show")
with st.form("add_movie"):
    user = st.text_input("Your Name")
    movie = st.text_input("Movie/Show Title")
    type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
    note = st.text_area("Notes / Thoughts")
    year = st.number_input("Release Year (optional)", min_value=1800, max_value=datetime.now().year, step=1)
    language = st.text_input("Original Language (optional, e.g., en, fr)")
    submitted = st.form_submit_button("Add")
    
    if submitted:
        if user and movie:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.append_row([user, movie, type_, note, year if year else "", language, timestamp])
                st.success(f"Added {movie} by {user}!")
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill at least your name and the movie title.")

# -------------------
# TMDb Poster function
# -------------------
def get_tmdb_poster(title, api_key, year=None, language=None):
    if not api_key:
        return None
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year
    if language:
        params["language"] = language
    resp = requests.get(search_url, params=params).json()
    results = resp.get("results")
    if results:
        poster_path = results[0].get("poster_path")
        if poster_path:
            return f"https://image.tmdb.org/t/p/w200{poster_path}"
    return None

# -------------------
# Display movies in grid with posters
# -------------------
if not df.empty:
    st.subheader("Your Movies/Shows")
    search = st.text_input("Search by title:")
    if search:
        df_filtered = df[df['movie'].str.contains(search, case=False, na=False)]
    else:
        df_filtered = df

    cols = st.columns(3)
    for i, row in df_filtered.iterrows():
        poster = get_tmdb_poster(row["movie"], tmdb_api_key, year=row.get("year"), language=row.get("language"))
        with cols[i % 3]:
            st.write(f"**{row['movie']} ({row.get('year','')})**")
            if poster:
                st.image(poster, use_container_width=True)
            else:
                st.write("Poster not found")
            if row.get("note"):
                st.caption(row["note"])

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
                st.write(f"• {rec}")
        else:
            st.info("No new internal recommendations available yet.")
    else:
        st.info("Add more movies to get internal recommendations.")

    # -------------------
    # TMDb Recommendations
    # -------------------
    if tmdb_api_key and not df_filtered.empty:
        st.subheader("TMDb Recommendations 🎬")
        last_movie = df.iloc[-1]['movie']
        last_year = df.iloc[-1].get("year")
        last_lang = df.iloc[-1].get("language")

        def get_tmdb_recommendations(title, api_key, year=None, language=None, count=3):
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {"api_key": api_key, "query": title}
            if year:
                params["year"] = year
            if language:
                params["language"] = language
            resp = requests.get(search_url, params=params).json()
            if resp.get("results"):
                movie_id = resp["results"][0]["id"]
                rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
                rec_resp = requests.get(rec_url, params={"api_key": api_key}).json()
                recs = [{"title": m["title"], "poster": f"https://image.tmdb.org/t/p/w200{m['poster_path']}"}
                        for m in rec_resp.get("results", []) if m.get("poster_path")]
                return recs[:count]
            return []

        tmdb_recs = get_tmdb_recommendations(last_movie, tmdb_api_key, last_year, last_lang)
        rec_cols = st.columns(3)
        for i, rec in enumerate(tmdb_recs):
            with rec_cols[i % 3]:
                st.write(f"**{rec['title']}**")
                st.image(rec['poster'], use_container_width=True)
else:
    st.info("No data found in the Google Sheet. Check your sheet ID and worksheet name.")
