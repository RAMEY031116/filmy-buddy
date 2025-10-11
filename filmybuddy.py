# filmybuddy_final_strict_tmdb.py - UPDATED TO SHOW RATING
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import re

# --- Cache Management ---
if 'tmdb_data_cache_cleared' not in st.session_state:
    st.cache_data.clear()
    st.session_state['tmdb_data_cache_cleared'] = True

# --- Configuration ---
st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Recommend your recent watched")

# --- TMDb API key ---
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. TMDb features will not work.")

# --- Connect to Google Sheet ---
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

# --- Load data from Google Sheet ---
@st.cache_data(ttl=60)
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        required_cols = ["user", "movie", "type", "status", "year", "language", "note", "timestamp"]
        df = df.reindex(columns=required_cols, fill_value=np.nan)
        if 'year' in df.columns:
            df['year'] = df['year'].astype(str).apply(lambda x: re.sub(r'\D','',x)).replace('', np.nan)
        if 'language' in df.columns:
            df['language'] = df['language'].astype(str).str.strip().str.upper().replace('NAN', np.nan)
        if not df.empty and "timestamp" in df.columns:
            df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        return pd.DataFrame(columns=required_cols)

df = load_data()

# --- Helper: TMDb Search with Strict Year & Language ---
@st.cache_data(ttl=86400)
def get_tmdb_data(title, media_type, year=None, language=None):
    if not tmdb_api_key:
        return None
    title = str(title).strip()
    year_str = str(year).strip() if year else None
    lang_code = str(language).strip().upper() if language else None
    
    # Endpoint selection
    url = "https://api.themoviedb.org/3/search/movie" if media_type in ["Movie","Documentary"] else "https://api.themoviedb.org/3/search/tv"
    
    params = {"api_key": tmdb_api_key, "query": title}
    if year_str and len(year_str) == 4:
        params["primary_release_year"] = year_str
    if lang_code and len(lang_code) in [2,3]:
        params["with_original_language"] = lang_code.lower()
    
    try:
        resp = requests.get(url, params=params).json()
        results = resp.get("results", [])
    except:
        return None
    
    # Strict matching: year + language + poster
    for r in results:
        r_year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        r_lang = r.get("original_language","").upper()
        if year_str and r_year != year_str: continue
        if lang_code and r_lang != lang_code: continue
        if not r.get("poster_path"): continue
        r['normalized_title'] = r.get("title") or r.get("name")
        r['normalized_year'] = r_year
        r['normalized_type'] = r.get("media_type") or "movie"
        return r
    
    # Fallback: first result with poster
    if results and results[0].get("poster_path"):
        r = results[0]
        r['normalized_title'] = r.get("title") or r.get("name")
        r['normalized_year'] = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        r['normalized_type'] = r.get("media_type") or "movie"
        return r
    return None

def get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6):
    if not tmdb_api_key or not tmdb_id or tmdb_media_type not in ['movie', 'tv']:
        return []
    url = f"https://api.themoviedb.org/3/{tmdb_media_type}/{tmdb_id}/recommendations"
    try:
        resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    except:
        return []
    return resp.get("results", [])[:count]

# --- Add new media form ---
st.subheader("Add a new media item ➕")
with st.form("add_movie"):
    col1, col2, col3 = st.columns(3)
    with col1:
        user = st.text_input("Your Name", key="form_user")
        movie = st.text_input("Title", key="form_movie")
    with col2:
        type_ = st.selectbox("Type", ["Movie","Show","Documentary","Anime","Other"], key="form_type")
        status = st.selectbox("Status", ["Completed","Watching","Plan to Watch","Dropped"], key="form_status")
    with col3:
        year = st.text_input("Year (4 digits)", key="form_year")
        language = st.text_input("Language (e.g., KO, EN)", key="form_lang")
    note = st.text_area("Notes / Thoughts", key="form_note")
    submitted = st.form_submit_button("Add to List")

    if submitted:
        clean_year = re.sub(r'\D','', year.strip())
        if not (user and movie):
            st.warning("Please fill your name and title.")
        elif year.strip() and len(clean_year) != 4:
            st.error("Enter a valid 4-digit year or leave blank.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                row_data = [user.strip(), movie.strip(), type_, status, clean_year, language.strip().upper(), note.strip(), timestamp]
                sheet.append_row(row_data)
                st.success(f"Added **{movie.strip()}** by {user.strip()}! Refreshing...")
                load_data.clear()
                get_tmdb_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error adding movie: {e}")

# --- Display media items ---
st.subheader("Your Media Items 📝")
st.markdown("---")
col_search, col_filter = st.columns([3,1])
with col_search:
    search = st.text_input("Search by Title or User:")
with col_filter:
    type_filter = st.selectbox("Filter by Type:", ["All"] + df['type'].unique().tolist() if 'type' in df.columns else ["All"])
    status_filter = st.selectbox("Filter by Status:", ["All"] + df['status'].unique().tolist() if 'status' in df.columns else ["All"])

df_display = df.copy()
if type_filter != "All": df_display = df_display[df_display["type"]==type_filter]
if status_filter != "All": df_display = df_display[df_display["status"]==status_filter]
if search:
    df_display = df_display[df_display["movie"].str.contains(search, case=False, na=False) |
                            df_display["user"].str.contains(search, case=False, na=False)]

if df_display.empty:
    st.info("No media items found.")
else:
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        tmdb_data = get_tmdb_data(row["movie"], row["type"], row.get("year"), row.get("language"))
        
        poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}" if tmdb_data and tmdb_data.get("poster_path") else None
        
        # --- RATING LOGIC ADDED HERE ---
        rating_value = tmdb_data.get("vote_average") if tmdb_data else None
        rating_text = f"⭐ **{rating_value:.1f}/10**" if rating_value else "N/A"
        
        display_title = tmdb_data.get('normalized_title', row['movie']) if tmdb_data else row['movie']
        display_year = tmdb_data.get('normalized_year', row.get('year') or 'N/A') if tmdb_data else row.get('year','N/A')

        with cols[i % 3]:
            if poster_url:
                st.image(poster_url, width=150)
            st.markdown(f"**{display_title} ({display_year})**")
            st.markdown(f"**Rating:** {rating_text}") # DISPLAY RATING
            st.markdown(f"**Type:** {row['type']} | **Status:** `{row.get('status','N/A')}`")
            st.markdown(f"**Added by:** {row['user']}")
            if row['note']:
                st.markdown(f"*Notes:* {row['note']}")
            st.markdown("---")

# --- TMDb Recommendations for last added ---
if tmdb_api_key and not df.empty:
    st.subheader("TMDb Recommendations 💡")
    last_movie = df.iloc[0]
    tmdb_data = get_tmdb_data(last_movie["movie"], last_movie["type"], last_movie.get("year"), last_movie.get("language"))
    if tmdb_data and tmdb_data.get("id"):
        recs = get_tmdb_recommendations(tmdb_data["id"], tmdb_data.get("media_type","movie"), count=6)
        if recs:
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                rec_title = rec.get('title') or rec.get('name')
                rec_year = (rec.get('release_date') or rec.get('first_air_date') or "")[:4]
                rec_type = "Movie" if rec.get('media_type')=='movie' else "Show"
                poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                with rec_cols[j % 3]:
                    if poster:
                        st.image(poster, width=150)
                    st.markdown(f"**{rec_title} ({rec_year})**")
                    st.markdown(f"<small>Type: {rec_type}</small>", unsafe_allow_html=True)
        else:
            st.info(f"No TMDb recommendations found for **{last_movie['movie']}**.")
    else:
        st.info(f"Could not find **{last_movie['movie']}** on TMDb. Recommendations unavailable.")