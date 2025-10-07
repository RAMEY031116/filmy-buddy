# filmybuddy_fixed.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and get TMDb recommendations with posters!")

# TMDb API key from secrets
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. TMDb posters and recommendations will not work.")

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
# Load data from Google Sheet
# -------------------
try:
    df = pd.DataFrame(sheet.get_all_records())
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user","movie","type","note","year","language","timestamp"])

# -------------------
# Helper functions
# -------------------
def get_tmdb_movie(title, year=None, language=None):
    if not tmdb_api_key:
        return None
    params = {"api_key": tmdb_api_key, "query": title}
    if year:
        params["year"] = year
    # Use 'search/multi' to potentially handle TV shows better, but 'search/movie' is fine for now
    # Since the original code used 'search/movie', I'll keep it for consistency.
    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params).json()
    results = resp.get("results", [])
    if language:
        # Filter by original language (e.g., 'EN' for English)
        results = [r for r in results if r.get("original_language","").upper() == language.upper()]
    if results:
        return results[0]  # Return first matching movie
    return None

def get_tmdb_recommendations(movie_id, count=3):
    if not tmdb_api_key or not movie_id:
        return []
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    return resp.get("results", [])[:count]

# -------------------
# Form to add a new movie/show
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
                st.success(f"Added {movie} by {user}! Refreshing list...")
                # Use st.experimental_rerun to force a clean full script re-execution
                # to ensure the updated df is loaded and the poster is displayed.
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill your name and movie title.")

# -------------------
# Display all entered movies
# -------------------
st.subheader("Your Movies/Shows")
search = st.text_input("Search by title or user:")
if search:
    df_display = df[df["movie"].str.contains(search, case=False, na=False) |
                    df["user"].str.contains(search, case=False, na=False)]
else:
    # Sort by timestamp in descending order to show the latest entries first
    if not df.empty and "timestamp" in df.columns:
        df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
    df_display = df

if df_display.empty:
    st.info("No movies found.")
else:
    # Use st.expander for a cleaner display, especially with many movies
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        tmdb_data = get_tmdb_movie(row["movie"], row.get("year"), row.get("language"))
        
        # Check if tmdb_data is not None before accessing keys
        poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}" if tmdb_data and tmdb_data.get("poster_path") else None
        
        with cols[i % 3]:
            if poster_url:
                st.image(poster_url, width=150)
            
            # Using st.expander to keep the main view clean
            with st.expander(f"**{row['movie']} ({row.get('year','')})**"):
                # Display details inside the expander
                st.markdown(f"**Type:** {row['type']}")
                st.markdown(f"**Language:** [{row.get('language','').upper()}]")
                st.markdown(f"**Added by:** {row['user']}")
                if row['note']:
                    st.markdown(f"**Notes:** {row['note']}")
                # Optional: Show the time it was added
                st.markdown(f"<small>Added: {row['timestamp']}</small>", unsafe_allow_html=True)


# -------------------
# TMDb Recommendations for last added movie
# -------------------
if tmdb_api_key and not df_display.empty:
    st.subheader("TMDb Recommendations 🎬")
    
    # The last movie in the *sorted* df is the most recent entry
    last_movie = df.iloc[0] 
    
    # Ensure the movie data can be retrieved for recommendations
    tmdb_data = get_tmdb_movie(last_movie["movie"], last_movie.get("year"), last_movie.get("language"))
    
    if tmdb_data:
        recs = get_tmdb_recommendations(tmdb_data.get("id"), count=6)
        
        if recs:
            st.markdown(f"Recommendations based on **{last_movie['movie']}**:")
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                with rec_cols[j % 3]:
                    if poster:
                        st.image(poster, width=150)
                    st.markdown(f"**{rec['title']} ({rec.get('release_date','')[:4]}) [{rec.get('original_language','').upper()}]**")
        else:
            st.info(f"No TMDb recommendations found for **{last_movie['movie']}**.")
    else:
        st.info(f"Could not find **{last_movie['movie']}** on TMDb for recommendations.")