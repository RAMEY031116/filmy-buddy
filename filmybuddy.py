# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
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
    st.warning("TMDb API key not found in secrets. Only titles will be shown without TMDb data.")

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
# Helper: Fetch TMDb movie details
# -------------------
def fetch_tmdb_data(title, api_key):
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": api_key, "query": title}
    resp = requests.get(search_url, params=params).json()
    if resp.get("results"):
        movie = resp["results"][0]
        poster_url = f"https://image.tmdb.org/t/p/w200{movie['poster_path']}" if movie.get('poster_path') else None
        release_year = movie.get('release_date','')[:4]
        language = movie.get('original_language','').upper()
        return poster_url, release_year, language
    return None, None, None

# -------------------
# Display movies/shows
# -------------------
st.subheader("Your Movies/Shows")

search = st.text_input("Search by title or user:")
if search:
    df_filtered = df[df['movie'].str.contains(search, case=False, na=False) |
                     df['user'].str.contains(search, case=False, na=False)]
else:
    df_filtered = df

for _, row in df_filtered.iterrows():
    poster, year, language = fetch_tmdb_data(row['movie'], tmdb_api_key) if tmdb_api_key else (None, None, None)
    
    if poster:
        st.image(poster, width=150)
    
    info = f"**{row['movie']}** ({row['type']})"
    if year:
        info += f" - {year}"
    if language:
        info += f" [{language}]"
    info += f"\nAdded by: {row['user']}"
    if row['note']:
        info += f"\nNotes: {row['note']}"
    
    st.markdown(info)
    st.markdown("---")

# -------------------
# TMDb Recommendations
# -------------------
if tmdb_api_key and not df.empty:
    st.subheader("TMDb Recommendations 🎬")
    last_movie = df.iloc[-1]['movie']
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": tmdb_api_key, "query": last_movie}
    resp = requests.get(search_url, params=params).json()
    
    if resp.get("results"):
        movie_id = resp["results"][0]["id"]
        rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
        rec_resp = requests.get(rec_url, params={"api_key": tmdb_api_key}).json()
        recs = rec_resp.get("results", [])[:6]  # show more recommendations
        
        for r in recs:
            poster = f"https://image.tmdb.org/t/p/w200{r['poster_path']}" if r.get('poster_path') else None
            title = r['title']
            year = r.get('release_date','')[:4]
            language = r.get('original_language','').upper()
            
            if poster:
                st.image(poster, width=120)
            info = f"**{title}**"
            if year:
                info += f" - {year}"
            if language:
                info += f" [{language}]"
            st.markdown(info)
            st.markdown("---")
    else:
        st.info("No TMDb recommendations found for the last movie.")
