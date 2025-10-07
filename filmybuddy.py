import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests
import random
from datetime import datetime

st.set_page_config(page_title="🎬 FilmyBuddy", page_icon="🍿")
st.title("🎬 FilmyBuddy")
st.write("Welcome! Track movies and share recommendations with friends.")

# -----------------------------
# Google Sheets setup
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

sheet = client.open("FilmyBuddy_Data").sheet1  # your sheet name
data = sheet.get_all_records()

# -----------------------------
# Users
# -----------------------------
users = list(set([d["user"] for d in data]))
selected_user = st.selectbox("Select your user:", users)

st.subheader(f"{selected_user}'s Movie List")

# Filter user-specific movies
user_movies = [d for d in data if d["user"] == selected_user]

for m in user_movies:
    st.write(f"- **{m['movie']}** ({m['type']}) — {m['note']}")

# -----------------------------
# Add a new movie
# -----------------------------
st.subheader("Add a new movie")
new_movie = st.text_input("Movie Title")
movie_type = st.selectbox("Type", ["recommendation", "wishlist", "watched"])
note = st.text_input("Note (optional)")

if st.button("Add Movie"):
    if new_movie.strip() != "":
        sheet.append_row([selected_user, new_movie, movie_type, note, str(datetime.now())])
        st.success(f"Added **{new_movie}** to {selected_user}'s list!")
    else:
        st.error("Please enter a movie title.")

# -----------------------------
# Random Movie Suggestion from TMDB
# -----------------------------
st.subheader("🎲 Random Movie Suggestion")
TMDB_API_KEY = "YOUR_TMDB_API_KEY"  # get it from https://www.themoviedb.org/settings/api
url = f"https://api.themoviedb.org/3/movie/popular?api_key={TMDB_API_KEY}"
res = requests.get(url).json()
movies = [m["title"] for m in res["results"]]
st.info(random.choice(movies))
st.write("wtf")