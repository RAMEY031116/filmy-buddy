# filmybuddy_strict_posters.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import re

# --- Page Config ---
st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your media, get accurate TMDb posters/ratings, and recommendations!")

# --- TMDb API Key ---
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
    st.error(f"Error connecting to Google Sheet: {e}")
    st.stop()

# --- Load Data ---
@st.cache_data(ttl=60)
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        required_cols = ["user", "movie", "type", "status", "year", "language", "note", "timestamp"]
        df = df.reindex(columns=required_cols, fill_value=np.nan)
        df['year'] = df['year'].astype(str).apply(lambda x: re.sub(r'\D', '', x)).replace('', np.nan)
        df['language'] = df['language'].astype(str).str.strip().str.upper().replace('NAN', np.nan)
        if not df.empty and "timestamp" in df.columns:
            df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        return pd.DataFrame(columns=required_cols)

df = load_data()

# --- TMDb Helper Functions ---
@st.cache_data(ttl=86400)
def get_tmdb_data(title, media_type, year=None, language=None):
    """Search TMDb with strict matching on title, year, language."""
    if not tmdb_api_key:
        return None
    params = {"api_key": tmdb_api_key, "query": title}
    if year: params['year'] = year
    if language and len(language) in [2,3]: params['language'] = language.lower()
    
    try:
        resp = requests.get("https://api.themoviedb.org/3/search/multi", params=params).json()
    except:
        return None
    results = resp.get("results", [])
    
    # Strict filtering
    for r in results:
        is_movie = r.get("media_type") == "movie"
        is_tv = r.get("media_type") == "tv"
        r_year = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        r_lang = r.get("original_language","").upper()
        
        # Type filter
        if media_type in ["Movie","Documentary"] and not is_movie: continue
        if media_type in ["Show","Anime"] and not is_tv: continue
        # Year filter
        if year and r_year != year: continue
        # Language filter
        if language and r_lang != language.upper(): continue
        # Poster filter
        if not r.get("poster_path"): continue
        
        r['normalized_title'] = r.get("title") or r.get("name")
        r['normalized_year'] = r_year
        r['normalized_type'] = r['media_type']
        return r
    
    # Fallback: first result with poster
    for r in results:
        if r.get("poster_path"):
            r['normalized_title'] = r.get("title") or r.get("name")
            r['normalized_year'] = (r.get("release_date") or r.get("first_air_date") or "")[:4]
            r['normalized_type'] = r['media_type']
            return r
    return None

def get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6):
    if not tmdb_api_key or not tmdb_id: return []
    url = f"https://api.themoviedb.org/3/{tmdb_media_type}/{tmdb_id}/recommendations"
    try:
        resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    except:
        return []
    return resp.get("results", [])[:count]

# --- Add New Media Form ---
st.subheader("Add New Media ➕")
with st.form("add_movie"):
    col1, col2, col3 = st.columns(3)
    with col1:
        user = st.text_input("Your Name")
        movie = st.text_input("Title")
    with col2:
        type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
        status = st.selectbox("Status", ["Completed","Watching","Plan to Watch","Dropped"])
    with col3:
        year = st.text_input("Year (YYYY)")
        language = st.text_input("Language (ISO, e.g., EN, KO)")
    note = st.text_area("Notes / Thoughts")
    submitted = st.form_submit_button("Add to List")
    
    if submitted:
        clean_year = re.sub(r'\D','',year.strip())
        if not user or not movie:
            st.warning("Name and title are required.")
        elif year.strip() and len(clean_year)!=4:
            st.error("Year must be 4 digits or empty.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [user.strip(), movie.strip(), type_, status, clean_year, language.strip().upper(), note.strip(), timestamp]
            try:
                sheet.append_row(row_data)
                st.success(f"Added **{movie.strip()}** by {user.strip()}!")
                load_data.clear()
                get_tmdb_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error adding media: {e}")

# --- Display Media List ---
st.subheader("Your Media List 🎬")
st.markdown("---")

col_search, col_filter = st.columns([3,1])
with col_search: search = st.text_input("Search by title or user")
with col_filter:
    type_filter = st.selectbox("Filter by Type:", ["All"] + df['type'].dropna().unique().tolist())
    status_filter = st.selectbox("Filter by Status:", ["All"] + df['status'].dropna().unique().tolist())

df_display = df.copy()
if type_filter!="All": df_display=df_display[df_display["type"]==type_filter]
if status_filter!="All": df_display=df_display[df_display["status"]==status_filter]
if search: df_display=df_display[df_display["movie"].str.contains(search,case=False,na=False)|
                               df_display["user"].str.contains(search,case=False,na=False)]

if df_display.empty: st.info("No media found.")
else:
    cols = st.columns(3)
    for i, (_, row) in enumerate(df_display.iterrows()):
        tmdb_data = get_tmdb_data(row["movie"], row["type"], row.get("year"), row.get("language"))
        poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}" if tmdb_data and tmdb_data.get("poster_path") else None
        display_title = tmdb_data.get("normalized_title") if tmdb_data else row["movie"]
        display_year = tmdb_data.get("normalized_year") if tmdb_data else (row.get("year") or "N/A")
        rating_text = f"⭐ {tmdb_data['vote_average']:.1f}/10" if tmdb_data and tmdb_data.get("vote_average") else "N/A"
        with cols[i%3]:
            if poster_url: st.image(poster_url, width=150)
            st.markdown(f"**{display_title}** ({display_year})")
            st.markdown(f"**Type:** {row['type']} | **Status:** {row.get('status','N/A')}")
            st.markdown(f"**Rating:** {rating_text}")
            st.markdown(f"**Added by:** {row['user']}")
            if row['note']: st.markdown(f"*Notes:* {row['note']}")
            st.markdown("---")

# --- TMDb Recommendations for last added ---
if tmdb_api_key and not df.empty:
    st.subheader("TMDb Recommendations 💡")
    last_movie = df.iloc[0]
    tmdb_data = get_tmdb_data(last_movie["movie"], last_movie["type"], last_movie.get("year"), last_movie.get("language"))
    if tmdb_data and tmdb_data.get("id"):
        recs = get_tmdb_recommendations(tmdb_data["id"], tmdb_data["media_type"])
        if recs:
            rec_cols = st.columns(3)
            for j, rec in enumerate(recs):
                rec_title = rec.get('title') or rec.get('name')
                rec_year = (rec.get('release_date') or rec.get('first_air_date') or "")[:4]
                rec_type = "Movie" if rec.get('media_type')=='movie' else "Show"
                poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                with rec_cols[j%3]:
                    if poster: st.image(poster, width=150)
                    st.markdown(f"**{rec_title}** ({rec_year})")
                    st.markdown(f"<small>Type: {rec_type}</small>", unsafe_allow_html=True)
        else:
            st.info(f"No recommendations found for **{last_movie['movie']}**.")
    else:
        st.info(f"Could not find **{last_movie['movie']}** on TMDb.")
