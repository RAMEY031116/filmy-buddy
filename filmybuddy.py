# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows, get recommendations, and see latest releases with posters!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key", None)
if not tmdb_api_key:
    st.warning("TMDb API key not found in secrets. TMDb recommendations and posters will not work.")

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
    data = sheet.get_all_records()
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
                
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
            except Exception as e:
                st.error(f"Error adding movie: {e}")
        else:
            st.warning("Please fill at least your name and the movie title.")

# -------------------
# Display current movies/shows
# -------------------
if not df.empty:
    st.subheader("Your Movies/Shows")
    
    search = st.text_input("Search by title:")
    if search:
        df_filtered = df[df['movie'].str.contains(search, case=False, na=False)]
        st.dataframe(df_filtered)
    else:
        st.dataframe(df)

    # -------------------
    # Internal Recommendations
    # -------------------
    st.subheader("Internal Recommendations 🎯")
    if len(df) > 1:
        last_type = df.iloc[-1]['type']
        same_type_movies = df[df['type'] == last_type]['movie'].tolist()
        all_movies = df['movie'].tolist()
        recommendations = random.sample(
            [m for m in all_movies if m not in same_type_movies],
            min(3, max(len(all_movies)-len(same_type_movies), 0))
        )
        if recommendations:
            for rec in recommendations:
                st.write(f"• {rec}")
        else:
            st.info("No new internal recommendations available yet.")
    else:
        st.info("Add more movies to get internal recommendations.")

    # -------------------
    # TMDb Recommendations with posters
    # -------------------
    if tmdb_api_key:
        st.subheader("TMDb Recommendations 🎬")
        
        def get_tmdb_recommendations(title, api_key, count=3):
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {"api_key": api_key, "query": title}
            resp = requests.get(search_url, params=params).json()
            
            recommendations = []
            if resp.get("results"):
                movie_id = resp["results"][0]["id"]
                rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
                rec_resp = requests.get(rec_url, params={"api_key": api_key}).json()
                for m in rec_resp.get("results", [])[:count]:
                    title = m["title"]
                    poster_path = m.get("poster_path")
                    poster_url = f"https://image.tmdb.org/t/p/w200{poster_path}" if poster_path else None
                    recommendations.append((title, poster_url))
            return recommendations
        
        last_movie = df.iloc[-1]['movie']
        tmdb_recs = get_tmdb_recommendations(last_movie, tmdb_api_key)
        if tmdb_recs:
            cols = st.columns(len(tmdb_recs))
            for idx, (title, poster) in enumerate(tmdb_recs):
                with cols[idx]:
                    if poster:
                        st.image(poster, use_column_width=True)
                    st.caption(title)
        else:
            st.info("No TMDb recommendations found for the last movie.")

    # -------------------
    # Latest TMDb Releases with posters
    # -------------------
    if tmdb_api_key:
        st.subheader("Latest TMDb Releases 🎬")
        url = "https://api.themoviedb.org/3/movie/now_playing"
        params = {"api_key": tmdb_api_key, "language": "en-US", "page": 1}
        try:
            response = requests.get(url, params=params).json()
            latest_movies = []
            for m in response.get("results", [])[:5]:
                title = m["title"]
                poster_path = m.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w200{poster_path}" if poster_path else None
                latest_movies.append((title, poster_url))
            
            cols = st.columns(len(latest_movies))
            for idx, (title, poster) in enumerate(latest_movies):
                with cols[idx]:
                    if poster:
                        st.image(poster, use_column_width=True)
                    st.caption(title)
        except Exception as e:
            st.error(f"Error fetching latest TMDb releases: {e}")
else:
    st.info("No data found in the Google Sheet. Check your sheet ID and worksheet name.")
