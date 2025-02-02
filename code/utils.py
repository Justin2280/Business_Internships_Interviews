import streamlit as st
import hmac
import time
import os
import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload

# Load Google Cloud credentials from Streamlit secrets
def get_google_credentials():
    """Retrieve Google Cloud credentials from Streamlit secrets."""
    try:
        service_account_info = json.loads(st.secrets["gcp"]["SERVICE_ACCOUNT_JSON"])
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        return credentials
    except Exception as e:
        print(f"Error loading Google Cloud credentials: {e}")
        return None

def authenticate_drive():
    """Authenticate and return the Google Drive service instance."""
    credentials = get_google_credentials()
    if credentials:
        return build("drive", "v3", credentials=credentials)
    else:
        return None

def upload_to_google_drive(file_path, file_name):
    """Upload a file to Google Drive and return its shareable link."""
    service = authenticate_drive()
    if not service:
        print("Google Drive authentication failed.")
        return None

    try:
        file_metadata = {"name": file_name}
        media = MediaFileUpload(file_path, mimetype="text/plain")
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = file.get("id")

        # Make the file accessible via link
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"}  # Change "anyone" to "user" for restricted access
        ).execute()

        shareable_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        print(f"File uploaded successfully: {shareable_link}")
        return shareable_link
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")
        return None  # Return None if an error occurs

def save_interview_data(username, transcripts_directory, times_directory):
    """Write interview data to disk, upload to Google Drive, and return download link."""
    transcript_path = os.path.join(transcripts_directory, f"{username}.txt")

    # Store chat transcript
    with open(transcript_path, "w") as t:
        t.write(f"Session ID: {st.session_state.session_id}\n\n")
        for message in st.session_state.messages:
            t.write(f"{message['role']}: {message['content']}\n")

    # Upload to Google Drive
    shareable_link = upload_to_google_drive(transcript_path, f"{username}_transcript.txt")

    if not shareable_link:
        print("Warning: No valid transcript link was generated.")
    
    return shareable_link  # Ensure the function returns the correct link
