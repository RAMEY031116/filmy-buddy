# filmybuddy_threaded.py
import streamlit as st
import gspread
import pandas as pd
import requests
from datetime import datetime
import numpy as np
import re

# Cache management
if 'tmdb_data_cache_cleared' not in st.session_state:
    st.cache_data.clear()
    st.session_state['tmdb_data_cache_cleared'] = True

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your media with posters, ratings, and threaded recommendations!")

tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found. TMDb features will not work.")

# Connect to Google Sheet
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

# Load data
@st.cache_data(ttl=60)
def load_data():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        required_cols = ["user","movie","type","status","year","language","note","timestamp"]
        df = df.reindex(columns=required_cols, fill_value=np.nan)
        df['year'] = df['year'].astype(str).apply(lambda x: re.sub(r'\D','',x)).replace('', np.nan)
        df['language'] = df['language'].astype(str).str.strip().str.upper().replace('NAN', np.nan)
        df = df.sort_values(by="timestamp", ascending=False).reset_index(drop=True) if not df.empty else df
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(columns=required_cols)

df = load_data()

# TMDb search with strict matching
@st.cache_data(ttl=86400)
def get_tmdb_data(title, media_type, year=None, language=None):
    if not tmdb_api_key: return None
    title = str(title).strip()
    year_str = str(year).strip() if year else None
    lang_code = str(language).strip().upper() if language else None

    url = "https://api.themoviedb.org/3/search/movie" if media_type in ["Movie","Documentary"] else "https://api.themoviedb.org/3/search/tv"
    params = {"api_key": tmdb_api_key, "query": title}
    if year_str and len(year_str)==4: params["primary_release_year"]=year_str
    if lang_code and len(lang_code) in [2,3]: params["with_original_language"]=lang_code.lower()

    try:
        resp = requests.get(url, params=params).json()
        results = resp.get("results",[])
    except:
        return None

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

    if results and results[0].get("poster_path"):
        r = results[0]
        r['normalized_title'] = r.get("title") or r.get("name")
        r['normalized_year'] = (r.get("release_date") or r.get("first_air_date") or "")[:4]
        r['normalized_type'] = r.get("media_type") or "movie"
        return r
    return None

def get_tmdb_recommendations(tmdb_id, tmdb_media_type, count=6):
    if not tmdb_api_key or not tmdb_id or tmdb_media_type not in ['movie','tv']: return []
    url = f"https://api.themoviedb.org/3/{tmdb_media_type}/{tmdb_id}/recommendations"
    try:
        resp = requests.get(url, params={"api_key": tmdb_api_key}).json()
    except:
        return []
    return resp.get("results",[])[:count]

# Add new media form
st.subheader("Add a new media item ➕")
with st.form("add_movie"):
    col1,col2,col3 = st.columns(3)
    with col1:
        user = st.text_input("Your Name")
        movie = st.text_input("Title")
    with col2:
        type_ = st.selectbox("Type", ["Movie","Show","Documentary","Anime","Other"])
        status = st.selectbox("Status", ["Completed","Watching","Plan to Watch","Dropped"])
    with col3:
        year = st.text_input("Year (4 digits)")
        language = st.text_input("Language (KO, EN, etc.)")
    note = st.text_area("Notes / Thoughts")
    submitted = st.form_submit_button("Add to List")

    if submitted:
        clean_year = re.sub(r'\D','', year.strip())
        if not (user and movie):
            st.warning("Please fill your name and title.")
        elif year.strip() and len(clean_year)!=4:
            st.error("Enter a valid 4-digit year or leave blank.")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                sheet.append_row([user.strip(), movie.strip(), type_, status, clean_year, language.strip().upper(), note.strip(), timestamp])
                st.success(f"Added **{movie.strip()}** by {user.strip()}! Refreshing...")
                load_data.clear()
                get_tmdb_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error adding movie: {e}")

# Display threaded media items
st.subheader("Your Media Items 📝")
st.markdown("---")
df_display = df.copy()
for i, (_, row) in enumerate(df_display.iterrows()):
    tmdb_data = get_tmdb_data(row["movie"], row["type"], row.get("year"), row.get("language"))
    poster_url = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}" if tmdb_data and tmdb_data.get("poster_path") else None
    rating_text = f"⭐ {tmdb_data.get('vote_average', 'N/A')}/10" if tmdb_data and tmdb_data.get("vote_average") else "N/A"
    display_title = tmdb_data.get('normalized_title', row['movie']) if tmdb_data else row['movie']
    display_year = tmdb_data.get('normalized_year', row.get('year','N/A')) if tmdb_data else row.get('year','N/A')

    if poster_url:
        st.image(poster_url, width=150)
    st.markdown(f"**{display_title} ({display_year})** | **Type:** {row['type']} | **Status:** {row.get('status','N/A')} | **Added by:** {row['user']}")
    
    with st.expander("Details & Recommendations"):
        if row['note']:
            st.markdown(f"*Notes:* {row['note']}")
        if tmdb_data and tmdb_data.get("id"):
            recs = get_tmdb_recommendations(tmdb_data["id"], tmdb_data.get("media_type","movie"), count=4)
            if recs:
                st.markdown("**TMDb Recommendations:**")
                rec_cols = st.columns(2)
                for j, rec in enumerate(recs):
                    rec_title = rec.get('title') or rec.get('name')
                    rec_year = (rec.get('release_date') or rec.get('first_air_date') or "")[:4]
                    rec_type = "Movie" if rec.get('media_type')=='movie' else "Show"
                    rec_poster = f"https://image.tmdb.org/t/p/w200{rec['poster_path']}" if rec.get("poster_path") else None
                    with rec_cols[j%2]:
                        if rec_poster:
                            st.image(rec_poster, width=100)
                        st.markdown(f"{rec_title} ({rec_year}) | {rec_type}")
    st.markdown("---")
