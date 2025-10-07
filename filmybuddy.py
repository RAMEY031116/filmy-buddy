import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=scope
)
client = gspread.authorize(creds)
sheet = client.open("FilmyBuddy_Data").sheet1

st.success("✅ Connected to Google Sheets successfully!")
st.write(sheet.get_all_records())
