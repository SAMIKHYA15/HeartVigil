import streamlit as st
from supabase import create_client, Client

url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(url, key)