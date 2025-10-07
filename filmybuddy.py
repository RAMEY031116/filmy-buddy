# filmybuddy.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

# -------------------
# Streamlit page config
# -------------------
st.set_page_config(page_title="FilmyBuddy 🎬", layout="wide")
st.title("FilmyBuddy 🎬")
st.markdown("Track your movies/shows and get internal + TMDb recommendations!")

# -------------------
# TMDb API key
# -------------------
tmdb_api_key = st.secrets.get("tmdb_api_key")
if not tmdb_api_key:
    st.warning("TMDb API key not found in secrets. Only internal recommendations will work.")

# -------------------
# Connect to Google Sheet
# -------------------
try:
    sheet = gspread.service_account_from_dict(st.secrets["gcp_service_account"]) \
                      .open_by_key(st.secrets["sheet_id"]) \
                      .worksheet("Sheet1")  # Replace with your sheet name
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
with st.form("add_movie_form"):
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
    # TMDb Recommendations
    # -------------------
    if tmdb_api_key:
        st.subheader("TMDb Recommendations 🎬")

        def get_tmdb_recommendations(title, api_key, count=3):
            """Fetch TMDb recommendations for a movie title."""
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {"api_key": api_key, "query": title}
            try:
                resp = requests.get(search_url, params=params).json()
                if resp.get("results"):
                    movie_id = resp["results"][0]["id"]
                    rec_url = f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations"
                    rec_resp = requests.get(rec_url, params={"api_key": api_key}).json()
                    return [m["title"] for m in rec_resp.get("results", [])][:count]
            except Exception as e:
                st.error(f"Error fetching TMDb recommendations: {e}")
            return []

        last_movie = df.iloc[-1]['movie']
        tmdb_recs = get_tmdb_recommendations(last_movie, tmdb_api_key)
        if tmdb_recs:
            for rec in tmdb_recs:
                st.write(f"• {rec}")
        else:
            st.info("No TMDb recommendations found for the last movie.")
else:
    st.info("No data found in the Google Sheet. Check your sheet ID and worksheet name.")
