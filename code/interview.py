import streamlit as st
import time
from utils import (
    check_password,
    check_if_interview_completed,
    save_interview_data,
)
import os
import config

# Load API library
if "gpt" in config.MODEL.lower():
    api = "openai"
    from openai import OpenAI
elif "claude" in config.MODEL.lower():
    api = "anthropic"
    import anthropic
else:
    raise ValueError(
        "Model does not contain 'gpt' or 'claude'; unable to determine API."
    )

# Set page title and icon
st.set_page_config(page_title="Interview", page_icon=config.AVATAR_INTERVIEWER)

# Extract query parameters from URL
query_params = st.query_params  # Updated API
student_number = query_params.get('student_number', [None])[0]
name = query_params.get('name', [None])[0]
company = query_params.get('company', [None])[0]

# Display respondent information or handle missing data
if not all([student_number, name, company]):
    st.error("Missing required respondent information. Please ensure all fields are passed.")
    st.stop()
else:
    st.sidebar.markdown(f"### Respondent Info")
    st.sidebar.markdown(f"- **Student Number:** {student_number}")
    st.sidebar.markdown(f"- **Name:** {name}")
    st.sidebar.markdown(f"- **Company:** {company}")

# Check if usernames and logins are enabled
if config.LOGINS:
    # Check password (displays login screen)
    pwd_correct, username = check_password()
    if not pwd_correct:
        st.stop()
    else:
        st.session_state.username = username
else:
    st.session_state.username = "testaccount"

# Create directories if they do not already exist
if not os.path.exists(config.TRANSCRIPTS_DIRECTORY):
    os.makedirs(config.TRANSCRIPTS_DIRECTORY)
if not os.path.exists(config.TIMES_DIRECTORY):
    os.makedirs(config.TIMES_DIRECTORY)
if not os.path.exists(config.BACKUPS_DIRECTORY):
    os.makedirs(config.BACKUPS_DIRECTORY)

# Initialise session state
if "interview_active" not in st.session_state:
    st.session_state.interview_active = True

# Initialise messages list in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Store start time in session state
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()
    st.session_state.start_time_file_names = time.strftime(
        "%Y_%m_%d_%H_%M_%S", time.localtime(st.session_state.start_time)
    )

# Check if interview previously completed
interview_previously_completed = check_if_interview_completed(
    config.TIMES_DIRECTORY, st.session_state.username
)

# If app started but interview was previously completed
if interview_previously_completed and not st.session_state.messages:
    st.session_state.interview_active = False
    st.markdown("Interview already completed.")

# Add 'Quit' button to dashboard
col1, col2 = st.columns([0.85, 0.15])
with col2:
    if st.session_state.interview_active and st.button(
        "Quit", help="End the interview."
    ):
        st.session_state.interview_active = False
        st.session_state.messages.append(
            {"role": "assistant", "content": "You have cancelled the interview."}
        )
        save_interview_data(
            st.session_state.username,
            config.TRANSCRIPTS_DIRECTORY,
            config.TIMES_DIRECTORY,
        )

# Display previous messages
for message in st.session_state.messages[1:]:
    avatar = (
        config.AVATAR_INTERVIEWER
        if message["role"] == "assistant"
        else config.AVATAR_RESPONDENT
    )
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Load API client
client = (
    OpenAI(api_key=st.secrets["API_KEY"])
    if api == "openai"
    else anthropic.Anthropic(api_key=st.secrets["API_KEY"])
)
api_kwargs = {
    "messages": st.session_state.messages,
    "model": config.MODEL,
    "max_tokens": config.MAX_OUTPUT_TOKENS,
    "temperature": config.TEMPERATURE,
}

# If no messages, initialize conversation
if not st.session_state.messages:
    st.session_state.messages.append(
        {"role": "system", "content": config.SYSTEM_PROMPT}
    )
    with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
        stream = client.chat.completions.create(**api_kwargs) if api == "openai" else None
        message_interviewer = st.write_stream(stream) if stream else ""
        st.session_state.messages.append(
            {"role": "assistant", "content": message_interviewer}
        )

# Main chat if interview is active
if st.session_state.interview_active:
    if message_respondent := st.chat_input("Your message here"):
        st.session_state.messages.append(
            {"role": "user", "content": message_respondent}
        )
        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT):
            st.markdown(message_respondent)
