# filmybuddy_final_clean.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import re

# --- IMPORTANT: Cache Management ---
# Ensures a clean slate on initial load to prevent persistent errors
if 'tmdb_data_cache_cleared' not in st.session_state:
    st.cache_data.clear()
    st.session_state['tmdb_data_cache_cleared'] = True

# --- Configuration ---
st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your media, get accurate TMDb posters/ratings, and recommendations!")

# TMDb API key from secrets
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. TMDb features will not work.")

# -------------------
# Connect to Google Sheet (Resource Cache)
# -------------------
try:
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
# Load data from Google Sheet (Data Cache)
# -------------------
@st.cache_data(ttl=60) 
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        required_cols = ["user", "movie", "type", "status", "year", "language", "note", "timestamp"]
        df = df.reindex(columns=required_cols, fill_value=np.nan)

        # Robust data cleaning
        if 'year' in df.columns:
            df['year'] = df['year'].astype(str).apply(lambda x: re.sub(r'\D', '', x)).replace('', np.nan)
        
        if 'language' in df.columns:
            df['language'] = df['language'].astype(str).str.strip().str.upper().replace('NAN', np.nan)
        
        if not df.empty and "timestamp" in df.columns:
            df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
            
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        return pd.DataFrame(columns=required_cols)

df = load_data()

# -------------------
# Helper functions (TMDb Search with Strict Year/Language Matching)
# -------------------
@st.cache_data(ttl=86400) # Cache TMDb results for 24 hours
def get_tmdb_data(title, media_type, year=None, language=None):
    """Searches TMDb using /search/multi with robust filtering."""
    if not tmdb_api_key:
        return None
        
    title = str(title).strip()
    year = str(year).strip() if year else None
    language_code = str(language).strip() if language else None
    
    params = {"api_key": tmdb_api_key, "query": title}
    
    if year and len(year) == 4 and year.isdigit():
        params['year'] = year
        
    if language_code and len(language_code) in [2, 3]: 
        params['language'] = language_code.lower()

    try:
        resp = requests.get("https://api.themoviedb.org/3/search/multi", params=params).json()
    except requests.RequestException:
        return None
        
    results = resp.get("results", [])
    
    # --- Strict Matching Filter (The code that forces the right poster) ---
    for r in results:
        
        is_movie = r.get("media_type") == "movie"
        is_tv = r.get("media_type") == "tv"
        
        if is_movie:
            r_year = str(r.get("release_date", "")[:4])
        elif is_tv:
            r_year = str(r.get("first_air_date", "")[:4])
        else:
            continue
            
        # 1. Type Match
        if media_type in ["Movie", "Documentary"] and not is_movie:
            continue
        if media_type in ["Show", "Anime"] and not is_tv:
            continue
            
        # 2. Strict Year Matching
        if year and r_year != year:
            continue
            
        # 3. Strict Original Language Matching (The key differentiator)
        if language_code:
            r_lang_upper = r.get("original_language", "").upper()
            if r_lang_upper != language_code:
                continue

        # 4. Filter out items with no poster (useless for display)
        if not r.get("poster_path"):
            continue

        # Found a perfect match! 
        r['normalized_title'] = r.get("title") or r.get("name")
        r['normalized_year'] = r_year
        r['normalized_type'] = r['media_type']
        
        return r
        
    # Fallback: return the best result TMDb offered, but only if it has a poster
    if results and results[0].get("poster_path"):
         r = results[0]
         r['normalized_title'] = r.get("title") or r.get("name")
         r['normalized_year'] = (r.get("release_date") or r.get("first_air_date") or "")[:4]
         r['normalized_type'] = r['media_type']
         return r

    return None

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
# Form to add a new movie/show
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
        year = st.text_input("Year (4 digits, e.g., 2023)", key="form_year")
        language = st.text_input("Language (e.g., KO for Korean)", key="form_lang")
    
    note = st.text_area("Notes / Thoughts", key="form_note")
    submitted = st.form_submit_button("Add to List")

    if submitted:
        clean_year = re.sub(r'\D', '', year.strip())
        
        if not (user and movie):
            st.warning("Please fill your name and title.")
        elif year.strip() and (len(clean_year) != 4):
            st.error("Please enter a valid 4-digit year or leave the field empty.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                row_data = [
                    user.strip(), 
                    movie.strip(), 
                    type_, 
                    status,
                    clean_year, 
                    language.strip().upper(), 
                    note.strip(), 
                    timestamp
                ]
                sheet.append_row(row_data)
                st.success(f"Added **{movie.strip()}** by {user.strip()}! Refreshing list...")
                load_data.clear()
                get_tmdb_data.clear() 
                st.rerun()
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
    type_filter = st.selectbox("Filter by Type:", ["All"] + df['type'].unique().tolist() if 'type' in df.columns else ["All"])
    status_filter = st.selectbox("Filter by Status:", ["All"] + df['status'].unique().tolist() if 'status' in df.columns else ["All"])

df_display = df.copy()

# Apply filters and search... 
if type_filter != "All":
    df_display = df_display[df_display["type"] == type_filter]
if status_filter != "All":
    df_display = df_display[df_display["status"] == status_filter]
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
        display_title = row['movie']
        display_year = row.get('year') or 'N/A'
        
        with cols[i % 3]:
            
            # --- Poster Logic ---
            if tmdb_data and tmdb_data.get("poster_path"):
                poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}"
                st.image(poster_url, caption=row['movie'], width=150)
                
                rating = tmdb_data.get("vote_average")
                if rating and rating > 0:
                    # Use TMDb's info for cleaner display if a match was found
                    display_title = tmdb_data.get('normalized_title', row['movie'])
                    display_year = tmdb_data.get('normalized_year', row.get('year') or 'N/A')
                    rating_text = f"⭐ {rating:.1f}/10"
                    
            elif tmdb_api_key:
                 st.warning(f"TMDb search failed for: **{row['movie']}** (Year: {row.get('year') or 'N/A'}, Lang: {row.get('language') or 'N/A'}).")
            
            # Display Details
            st.markdown(f"**{display_title}** ({display_year})")
            st.markdown(f"**Type:** {row['type']} | **Status:** `{row.get('status', 'N/A')}`")
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
    
    last_movie = df.iloc[0] 
    
    tmdb_data = get_tmdb_data(last_movie["movie"], last_movie["type"], last_movie.get("year"), last_movie.get("language"))
    
    if tmdb_data and tmdb_data.get("id"):
        tmdb_id = tmdb_data["id"]
        tmdb_media_type = tmdb_data.get("media_type")
        
        st.markdown(f"Recommendations based on **{last_movie['movie']}**:")
        
        recs = get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6)
        
        if recs:
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                
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