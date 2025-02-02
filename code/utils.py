import streamlit as st
import hmac
import time
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build


# Password screen for dashboard (note: only very basic authentication!)
# Based on https://docs.streamlit.io/knowledge-base/deploy/authentication-without-sso
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

        del st.session_state.password  # don't store password in session state

    # Return True, username if password was already entered correctly before
    if st.session_state.get("password_correct", False):
        return True, st.session_state.username

    # Otherwise show login screen
    login_form()
    if "password_correct" in st.session_state:
        st.error("User or password incorrect")
    return False, st.session_state.username


def check_if_interview_completed(directory, username):
    """Check if interview transcript/time file exists which signals that interview was completed."""

    # Test account has multiple interview attempts
    if username != "testaccount":

        # Check if file exists
        try:
            with open(os.path.join(directory, f"{username}.txt"), "r") as _:
                return True

        except FileNotFoundError:
            return False

    else:

        return False


def save_interview_data(username, transcripts_directory, times_directory, folder_id):
    """Save interview data locally and upload to Google Drive."""

    # Define file paths
    transcript_file = os.path.join(transcripts_directory, f"{username}.txt")
    time_file = os.path.join(times_directory, f"{username}.txt")

    # Save transcript
    with open(transcript_file, "w") as t:
        t.write(f"Session ID: {st.session_state.session_id}\n\n")
        for message in st.session_state.messages:
            t.write(f"{message['role']}: {message['content']}\n")

    # Save interview timing data
    with open(time_file, "w") as d:
        duration = (time.time() - st.session_state.start_time) / 60
        d.write(
            f"Session ID: {st.session_state.session_id}\n"
            f"Start time (UTC): {time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(st.session_state.start_time))}\n"
            f"Interview duration (minutes): {duration:.2f}"
        )

    # Upload files to Google Drive
    transcript_link = upload_to_google_drive(transcript_file, f"{username}_transcript.txt", folder_id)
    time_link = upload_to_google_drive(time_file, f"{username}_time.txt", folder_id)

    return transcript_link  # Return Google Drive link for sharing
        
def upload_to_google_drive(file_path, file_name, folder_id):
    """Uploads a file to Google Drive inside a specific folder."""
    
    credentials = service_account.Credentials.from_service_account_info(st.secrets["SERVICE_ACCOUNT_JSON"])
    service = build("drive", "v3", credentials=credentials)

    file_metadata = {
        "name": file_name,
        "parents": [folder_id]  # Folder ID where the file will be uploaded
    }
    media = MediaFileUpload(file_path, mimetype="text/plain")

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    return file.get("webViewLink")  # Return the file sharing link