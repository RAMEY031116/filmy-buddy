# filmybuddy_pro.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime
import numpy as np

# --- Configuration ---
st.set_page_config(page_title="FilmyBuddy Pro 🚀", layout="wide")
st.title("FilmyBuddy Pro 🚀")
st.markdown("Track your media, get accurate TMDb posters/ratings, and recommendations!")

# TMDb API key from secrets
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. TMDb features will not work.")

# -------------------
# Connect to Google Sheet
# -------------------
try:
    # Use st.cache_resource to connect only once
    @st.cache_resource
    def get_spreadsheet():
        return gspread.service_account_from_dict(st.secrets["gcp_service_account"]) \
                      .open_by_key(st.secrets["sheet_id"]) \
                      .worksheet("Sheet1")
    sheet = get_spreadsheet()
except Exception as e:
    st.error(f"Error connecting to Google Sheet. Check your secrets: {e}")
    st.stop()

# -------------------
# Load data from Google Sheet
# -------------------
# Use st.cache_data to reload only when necessary (e.g., after st.experimental_rerun)
@st.cache_data(ttl=60) 
def load_data():
    try:
        # Fetch all records
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Ensure all necessary columns exist for robustness
        required_cols = ["user", "movie", "type", "status", "note", "year", "language", "timestamp"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan # Add missing columns with NaN
        
        # Sort by timestamp descending (latest entries first)
        if not df.empty and "timestamp" in df.columns:
            df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
            
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        return pd.DataFrame(columns=["user", "movie", "type", "status", "note", "year", "language", "timestamp"])

df = load_data()

# -------------------
# Helper functions (Now uses /search/multi for better show support)
# -------------------
@st.cache_data(ttl=86400) # Cache TMDb results for 24 hours
def get_tmdb_data(title, media_type, year=None, language=None):
    """Searches TMDb using /search/multi for both movies and TV shows with strict filtering."""
    if not tmdb_api_key:
        return None
        
    title = str(title).strip()
    year = str(year).strip() if year else None
    
    # Use multi-search to handle both 'Movie' and 'Show' types
    params = {"api_key": tmdb_api_key, "query": title}
    
    try:
        resp = requests.get("https://api.themoviedb.org/3/search/multi", params=params).json()
    except requests.RequestException:
        return None
        
    results = resp.get("results", [])
    
    # Filter and refine results
    for r in results:
        
        # 1. Filter by media type
        if media_type == "Movie" or media_type == "Documentary":
            if r.get("media_type") != "movie":
                continue
            r_year = str(r.get("release_date", "")[:4])
            r_title = r.get("title", "")
        elif media_type == "Show" or media_type == "Anime":
            if r.get("media_type") != "tv":
                continue
            r_year = str(r.get("first_air_date", "")[:4])
            r_title = r.get("name", "")
        else: # Catch-all for 'Other' or unexpected types, use original title
            r_year = str(r.get("release_date", r.get("first_air_date", ""))[:4])
            r_title = r.get("title", r.get("name", ""))
            
        # 2. Strict Year Matching (Crucial Fix)
        if year and r_year != year:
            continue
            
        # 3. Language Matching (if provided)
        if language:
            lang_upper = language.upper().strip()
            if r.get("original_language", "").upper() != lang_upper:
                continue

        # 4. Filter out items with no poster (useless for display)
        if not r.get("poster_path"):
            continue

        # Found a match! Normalize fields before returning
        r['normalized_title'] = r_title
        r['normalized_year'] = r_year
        r['normalized_type'] = 'Movie' if r['media_type'] == 'movie' else 'Show'
        
        return r
        
    return None # No match found after strict filtering

def get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6):
    """Fetches recommendations from TMDb for a given item ID and type."""
    if not tmdb_api_key or not tmdb_id or tmdb_media_type not in ['movie', 'tv']:
        return []
    
    url = f"https://api.themoviedb.org/3/{tmdb_media_type}/{tmdb_id}/recommendations"
    try:
        resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    except requests.RequestException:
        return []
        
    return resp.get("results", [])[:count]

# -------------------
# Form to add a new movie/show (with Status field)
# -------------------
st.subheader("Add a new media item ➕")
with st.form("add_movie"):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        user = st.text_input("Your Name", key="form_user")
        movie = st.text_input("Title", key="form_movie")
        
    with col2:
        type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"], key="form_type")
        status = st.selectbox("Status", ["Completed", "Watching", "Plan to Watch", "Dropped"], key="form_status")
        
    with col3:
        year = st.text_input("Year (Required for accurate poster!)", key="form_year")
        language = st.text_input("Language (e.g., EN, KO)", key="form_lang")
    
    note = st.text_area("Notes / Thoughts", key="form_note")
    submitted = st.form_submit_button("Add to List")

    if submitted:
        if not (user and movie and year.strip()):
            st.warning("Please fill your name, title, and **Year** for accurate matching.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                # Clean and prepare data for the sheet
                row_data = [
                    user.strip(), 
                    movie.strip(), 
                    type_, 
                    status,
                    note.strip(), 
                    year.strip(), 
                    language.strip().upper(), 
                    timestamp
                ]
                # Note: Sheet must have the headers: user, movie, type, status, note, year, language, timestamp
                sheet.append_row(row_data)
                st.success(f"Added **{movie.strip()}** by {user.strip()}! Refreshing list...")
                # Clear TMDb cache for the new item and force a full script re-run
                get_tmdb_data.clear()
                load_data.clear()
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error adding movie to sheet: {e}")

# -------------------
# Display control
# -------------------
st.subheader("Your Media Items 📝")
st.markdown("---")

col_search, col_filter = st.columns([3, 1])

with col_search:
    search = st.text_input("Search by Title or User:")

with col_filter:
    type_filter = st.selectbox("Filter by Type:", ["All"] + df['type'].unique().tolist())
    status_filter = st.selectbox("Filter by Status:", ["All"] + df['status'].unique().tolist())

df_display = df.copy()

# Apply filters
if type_filter != "All":
    df_display = df_display[df_display["type"] == type_filter]
if status_filter != "All":
    df_display = df_display[df_display["status"] == status_filter]
    
# Apply search
if search:
    df_display = df_display[df_display["movie"].str.contains(search, case=False, na=False) |
                            df_display["user"].str.contains(search, case=False, na=False)]

if df_display.empty:
    st.info("No media items found matching your filters.")
else:
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        
        # --- TMDb Data Fetching ---
        tmdb_data = get_tmdb_data(row["movie"], row["type"], row.get("year"), row.get("language"))
        
        poster_url = None
        rating_text = "N/A"
        
        if tmdb_data and tmdb_data.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}"
            
            # Fetch and display rating
            rating = tmdb_data.get("vote_average")
            if rating and rating > 0:
                rating_text = f"⭐ {rating:.1f}/10"
        
        with cols[i % 3]:
            # Display Poster
            if poster_url:
                st.image(poster_url, caption=row['movie'], width=150)
            elif tmdb_api_key:
                st.info(f"Poster not found for: **{row['movie']}** (Year: {row.get('year')})")
            
            # Display Details
            st.markdown(f"**{row['movie']}** ({row.get('year','')})")
            st.markdown(f"**Type:** {row['type']} | **Status:** `{row['status']}`")
            st.markdown(f"**Rating:** {rating_text}")
            st.markdown(f"**Added by:** {row['user']}")
            
            if row['note']:
                st.markdown(f"*Notes:* {row['note']}")
            st.markdown("---") 

# -------------------
# TMDb Recommendations for last added movie
# -------------------
if tmdb_api_key and not df.empty:
    st.subheader("TMDb Recommendations 💡")
    
    # Use the most recent entry from the full, sorted DataFrame
    last_movie = df.iloc[0] 
    
    # Fetch TMDb data for the movie ID needed for recommendations
    tmdb_data = get_tmdb_data(last_movie["movie"], last_movie["type"], last_movie.get("year"), last_movie.get("language"))
    
    if tmdb_data and tmdb_data.get("id"):
        tmdb_id = tmdb_data["id"]
        tmdb_media_type = tmdb_data.get("media_type")
        
        st.markdown(f"Recommendations based on **{last_movie['movie']}**:")
        
        recs = get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6)
        
        if recs:
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                
                # Check for movie or TV show title/year/type fields
                rec_title = rec.get('title') or rec.get('name')
                rec_year = (rec.get('release_date') or rec.get('first_air_date') or "")[:4]
                rec_type = "Movie" if rec.get('media_type') == 'movie' else "Show"
                
                poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                with rec_cols[j % 3]:
                    if poster:
                        st.image(poster, width=150)
                    st.markdown(f"**{rec_title}** ({rec_year})")
                    st.markdown(f"<small>Type: {rec_type}</small>", unsafe_allow_html=True)

        else:
            st.info(f"No TMDb recommendations found for **{last_movie['movie']}**.")
    else:
        st.info(f"Could not find **{last_movie['movie']}** on TMDb. Recommendations unavailable.")