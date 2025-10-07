# filmybuddy_super.py
import streamlit as st
import gspread
import pandas as pd
import random
import requests
from datetime import datetime

st.title("FilmyBuddy Super 🎬")
st.markdown("Track your movies/shows and get smart recommendations! 🍿")

# -------------------
# TMDb API setup
# -------------------
try:
    TMDB_API_KEY = st.secrets["tmdb_api_key"]
except KeyError:
    st.warning("TMDb API key not found in secrets. Only internal recommendations will work.")
    TMDB_API_KEY = None

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"

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
# Load data
# -------------------
try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
except Exception as e:
    st.error(f"Error loading Google Sheet: {e}")
    df = pd.DataFrame(columns=["user", "movie", "type", "note", "timestamp"])

# -------------------
# Add new movie/show
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
    # Internal recommendations
    # -------------------
    st.subheader("Recommendations 🎯")
    if len(df) > 1:
        last_type = df.iloc[-1]['type']
        same_type_movies = df[df['type'] == last_type]['movie'].tolist()
        all_movies = df['movie'].tolist()
        internal_recs = random.sample([m for m in all_movies if m not in same_type_movies], 
                                      min(3, max(0, len(all_movies)-len(same_type_movies))))
        if internal_recs:
            st.markdown("**From your list:**")
            for rec in internal_recs:
                st.write(f"• {rec}")
        else:
            st.info("No new internal recommendations yet.")
    else:
        st.info("Add more movies to get internal recommendations.")

    # -------------------
    # TMDb API recommendations
    # -------------------
    if TMDB_API_KEY:
        st.markdown("**From TMDb API:**")
        try:
            last_movie = df.iloc[-1]['movie']
            params = {"api_key": TMDB_API_KEY, "query": last_movie}
            resp = requests.get(TMDB_SEARCH_URL, params=params).json()
            results = resp.get("results", [])
            if results:
                st.write(f"Similar or related to **{last_movie}**:")
                for m in results[:5]:  # show top 5 results
                    title = m.get("title")
                    release = m.get("release_date", "N/A")
                    overview = m.get("overview", "")
                    st.markdown(f"**{title} ({release[:4]})** - {overview}")
            else:
                st.info("No TMDb recommendations found.")
        except Exception as e:
            st.error(f"TMDb API error: {e}")

else:
    st.info("No data found in the Google Sheet. Check your sheet ID and worksheet name.")
