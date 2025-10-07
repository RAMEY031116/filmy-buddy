# filmybuddy_final_fix.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime

# --- Configuration ---
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
    """Searches TMDb for a movie/show and returns the first result."""
    if not tmdb_api_key:
        return None
        
    params = {"api_key": tmdb_api_key, "query": title}
    
    # Ensuring the year parameter is passed correctly
    if year and str(year).strip().isdigit():
        params["year"] = str(year).strip() 
    
    try:
        resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params).json()
    except requests.RequestException as e:
        st.error(f"TMDb API request failed: {e}")
        return None
        
    results = resp.get("results", [])
    
    # Filter by original language if specified
    if language:
        lang_upper = language.upper().strip()
        results = [r for r in results if r.get("original_language", "").upper() == lang_upper]
        
    if results:
        return results[0]  # Return first matching movie
        
    return None

def get_tmdb_recommendations(movie_id, count=6): # Increased default count for display
    """Fetches recommendations from TMDb for a given movie ID."""
    if not tmdb_api_key or not movie_id:
        return []
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
    try:
        resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    except requests.RequestException:
        return []
        
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
                # Rerun to load the new data and display the poster/recommendations
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error adding movie to sheet: {e}")
        else:
            st.warning("Please fill your name and movie title.")

# -------------------
# Display all entered movies
# -------------------
st.subheader("Your Movies/Shows")
search = st.text_input("Search by title or user:")

# Sort data by timestamp descending (latest first)
if not df.empty and "timestamp" in df.columns:
    df_sorted = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
else:
    df_sorted = df

if search:
    df_display = df_sorted[df_sorted["movie"].str.contains(search, case=False, na=False) |
                          df_sorted["user"].str.contains(search, case=False, na=False)]
else:
    df_display = df_sorted

if df_display.empty:
    st.info("No movies found.")
else:
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        
        # --- TMDb Data Fetching for Poster ---
        tmdb_data = get_tmdb_movie(row["movie"], row.get("year"), row.get("language"))
        
        poster_url = None
        if tmdb_data and tmdb_data.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}"
        
        with cols[i % 3]:
            # Display Poster
            if poster_url:
                st.image(poster_url, caption=row['movie'], width=150)
            elif tmdb_api_key:
                # Only show this warning if we have an API key but failed the search
                st.info(f"Poster not found for: {row['movie']}")
            
            # Display Details
            st.markdown(f"**{row['movie']}** ({row.get('year','')})")
            st.markdown(f"**Type:** {row['type']}")
            st.markdown(f"**Added by:** {row['user']}")
            if row['note']:
                st.markdown(f"*Notes:* {row['note']}")
            st.markdown("---") # Separator for clarity

# -------------------
# TMDb Recommendations for last added movie
# -------------------
if tmdb_api_key and not df_sorted.empty:
    st.subheader("TMDb Recommendations 🎬")
    
    # Use the most recent entry from the fully sorted DataFrame
    last_movie = df_sorted.iloc[0] 
    
    # Fetch TMDb data for the movie ID needed for recommendations
    tmdb_data = get_tmdb_movie(last_movie["movie"], last_movie.get("year"), last_movie.get("language"))
    
    if tmdb_data and tmdb_data.get("id"):
        movie_id = tmdb_data["id"]
        st.markdown(f"Recommendations based on **{last_movie['movie']}**:")
        recs = get_tmdb_recommendations(movie_id, count=6)
        
        if recs:
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                with rec_cols[j % 3]:
                    if poster:
                        st.image(poster, width=150)
                    st.markdown(f"**{rec['title']}** ({rec.get('release_date','')[:4]})")
        else:
            st.info(f"No TMDb recommendations found for **{last_movie['movie']}**.")
    else:
        st.info(f"Could not find **{last_movie['movie']}** on TMDb. Recommendations unavailable.")