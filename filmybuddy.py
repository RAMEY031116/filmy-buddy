# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

# -------------------
# Page config
# -------------------
st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("🎥 FilmyBuddy")
st.markdown("Track your movies, discover new ones, and get personalized recommendations.")

# -------------------
# Load secrets
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key", None)
sheet_id = st.secrets.get("sheet_id", None)
gcp_service_account = st.secrets.get("gcp_service_account", None)

if not tmdb_api_key:
    st.warning("⚠️ TMDb API key not found in secrets. TMDb recommendations will not work.")
if not sheet_id or not gcp_service_account:
    st.error("❌ Google Sheets credentials missing. Please check your Streamlit secrets.")
    st.stop()

# -------------------
# Connect to Google Sheets
# -------------------
try:
    gc = gspread.service_account_from_dict(gcp_service_account)
    worksheet = gc.open_by_key(sheet_id).worksheet("Sheet1")
except Exception as e:
    st.error(f"Error connecting to Google Sheet: {e}")
    st.stop()

# -------------------
# Load data from sheet
# -------------------
try:
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
except Exception:
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "timestamp"])

# -------------------
# Helper: TMDb requests
# -------------------
def tmdb_request(endpoint, params=None):
    """Helper to query TMDb API safely."""
    base_url = "https://api.themoviedb.org/3"
    headers = {"accept": "application/json"}
    if not params:
        params = {}
    params["api_key"] = tmdb_api_key
    try:
        response = requests.get(f"{base_url}/{endpoint}", headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"TMDb error: {response.status_code}")
    except Exception as e:
        st.error(f"TMDb connection failed: {e}")
    return None

# -------------------
# Add movie form
# -------------------
st.subheader("➕ Add a Movie/Show")
with st.form("add_movie"):
    user = st.text_input("Your Name")
    movie = st.text_input("Movie/Show Title")
    type_ = st.selectbox("Type", ["Movie", "Show", "Documentary", "Anime", "Other"])
    note = st.text_area("Notes / Thoughts")
    submit = st.form_submit_button("Add Entry")

    if submit:
        if user and movie:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                worksheet.append_row([user, movie, type_, note, timestamp])
                st.success(f"✅ Added *{movie}* by {user}!")
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
            except Exception as e:
                st.error(f"Error writing to Google Sheet: {e}")
        else:
            st.warning("Please enter both name and movie title.")

# -------------------
# Display movie log
# -------------------
st.subheader("📜 Your Watchlist")
if not df.empty:
    search = st.text_input("Search your movies/shows")
    if search:
        filtered = df[df['movie'].str.contains(search, case=False, na=False)]
        st.dataframe(filtered)
    else:
        st.dataframe(df)
else:
    st.info("No entries found yet. Add a movie above!")

# -------------------
# Internal recommendations
# -------------------
if not df.empty:
    st.subheader("🎯 Internal Recommendations")
    all_movies = df['movie'].tolist()
    recs = random.sample(all_movies, min(len(all_movies), 3))
    for r in recs:
        st.write(f"• {r}")

# -------------------
# TMDb Recommendations
# -------------------
if tmdb_api_key:
    st.subheader("🌟 TMDb Recommendations")

    def get_tmdb_recommendations(title, count=3):
        search_data = tmdb_request("search/movie", {"query": title})
        if search_data and search_data.get("results"):
            movie_id = search_data["results"][0]["id"]
            rec_data = tmdb_request(f"movie/{movie_id}/recommendations")
            if rec_data and rec_data.get("results"):
                return [m["title"] for m in rec_data["results"][:count]]
        return []

    if not df.empty:
        last_movie = df.iloc[-1]['movie']
        recs = get_tmdb_recommendations(last_movie)
        if recs:
            st.success(f"Because you watched **{last_movie}**, you might like:")
            for rec in recs:
                st.write(f"🎬 {rec}")
        else:
            st.info("No similar TMDb recommendations found.")
    else:
        st.info("Add some movies to start getting recommendations!")

# -------------------
# Latest releases section
# -------------------
if tmdb_api_key:
    st.subheader("🆕 Latest Releases")

    latest_data = tmdb_request("movie/now_playing", {"language": "en-US", "page": 1})
    if latest_data and latest_data.get("results"):
        cols = st.columns(3)
        for i, movie in enumerate(latest_data["results"][:9]):
            with cols[i % 3]:
                st.image(f"https://image.tmdb.org/t/p/w500{movie['poster_path']}", width=150)
                st.markdown(f"**{movie['title']}**")
                st.caption(movie.get("release_date", ""))
    else:
        st.info("Could not fetch the latest movies right now.")
