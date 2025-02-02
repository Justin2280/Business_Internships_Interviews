import streamlit as st
import hmac
import time
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload

# Load Google Cloud credentials from Streamlit secrets
def get_google_credentials():
    """Retrieve Google Cloud credentials from Streamlit secrets."""
    service_account_info = json.loads(st.secrets["gcp"]["SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(service_account_info)
    return credentials

def authenticate_drive():
    """Authenticate and return the Google Drive service instance."""
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)

def upload_to_google_drive(file_path, file_name):
    """Upload a file to Google Drive and return its shareable link."""
    service = authenticate_drive()

    file_metadata = {"name": file_name}
    media = MediaFileUpload(file_path, mimetype="text/plain")

    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")

    # Make the file accessible via link
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"}  # Change "anyone" to "user" and specify email for restricted access
    ).execute()

    shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    print(f"File Uploaded: {shareable_link}")
    return shareable_link

# Password screen for dashboard (basic authentication)
def check_password():
    """Returns 'True' if the user has entered a correct password."""

    def login_form():
        """Form with widgets to collect user information"""
        with st.form("Credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log in", on_click=password_entered)

    def password_entered():
        """Checks whether username and password entered by the user are correct."""
        if st.session_state.username in st.secrets.passwords and hmac.compare_digest(
            st.session_state.password,
            st.secrets.passwords[st.session_state.username],
        ):
            st.session_state.password_correct = True
        else:
            st.session_state.password_correct = False

        del st.session_state.password  # Don't store password in session state

    # Return True if password was entered correctly before
    if st.session_state.get("password_correct", False):
        return True, st.session_state.username

    # Otherwise, show login screen
    login_form()
    if "password_correct" in st.session_state:
        st.error("User or password incorrect")
    return False, st.session_state.username

def check_if_interview_completed(directory, username):
    """Check if interview transcript/time file exists, signaling that interview was completed."""
    if username != "testaccount":
        try:
            with open(os.path.join(directory, f"{username}.txt"), "r") as _:
                return True
        except FileNotFoundError:
            return False
    return False

def save_interview_data(username, transcripts_directory, times_directory, file_name_addition_transcript="", file_name_addition_time=""):
    """Write interview data (transcript and time) to disk and upload it to Google Drive."""
    transcript_path = os.path.join(transcripts_directory, f"{username}{file_name_addition_transcript}.txt")

    # Store chat transcript with session ID
    with open(transcript_path, "w") as t:
        t.write(f"Session ID: {st.session_state.session_id}\n\n")
        for message in st.session_state.messages:
            t.write(f"{message['role']}: {message['content']}\n")

    # Store file with start time and duration of interview
    time_path = os.path.join(times_directory, f"{username}{file_name_addition_time}.txt")
    with open(time_path, "w") as d:
        duration = (time.time() - st.session_state.start_time) / 60
        d.write(
            f"Session ID: {st.session_state.session_id}\n"
            f"Start time (UTC): {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(st.session_state.start_time))}\n"
            f"Interview duration (minutes): {duration:.2f}"
        )

    # Upload transcript to Google Drive
    try:
        shareable_link = upload_to_google_drive(transcript_path, f"{username}_transcript.txt")
        print(f"Transcript uploaded successfully: {shareable_link}")
    except Exception as e:
        print(f"Failed to upload transcript: {e}")
