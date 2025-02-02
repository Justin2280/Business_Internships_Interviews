import streamlit as st
import time
from utils import (
    check_password,
    check_if_interview_completed,
    save_interview_data,
)
import os
import config
import html
import uuid

# Load API library
if "gpt" in config.MODEL.lower():
    api = "openai"
    from openai import OpenAI

elif "claude" in config.MODEL.lower():
    api = "anthropic"
    import anthropic
else:
    raise ValueError("Model does not contain 'gpt' or 'claude'; unable to determine API.")

# Set page title and icon
st.set_page_config(page_title="Interview", page_icon=config.AVATAR_INTERVIEWER)

# Function to validate query parameters
def validate_query_params(params, required_keys):
    missing_keys = [key for key in required_keys if key not in params or not params[key]]
    return len(missing_keys) == 0, missing_keys

# Extract query parameters
query_params = st.query_params

# Define required parameters
required_params = ["student_number", "name", "company"]

# Validate parameters
is_valid, missing_params = validate_query_params(query_params, required_params)

# Stop execution if parameters are missing
if not is_valid:
    st.error(f"Missing required parameter(s): {', '.join(missing_params)}")
    st.stop()

# Extract respondent's name
respondent_name = html.unescape(query_params["name"])

# Generate a session ID if it doesn't exist
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Sidebar with interview details
st.sidebar.title("Interview Details")
for param in required_params:
    st.sidebar.write(f"{param.capitalize()}: {html.unescape(query_params[param])}")
st.sidebar.write(f"Session ID: {st.session_state.session_id}")

# Handle login authentication
if config.LOGINS:
    pwd_correct, username = check_password()
    if not pwd_correct:
        st.stop()
    else:
        st.session_state.username = username
else:
    st.session_state.username = "testaccount"

# Ensure necessary directories exist
for directory in [config.TRANSCRIPTS_DIRECTORY, config.TIMES_DIRECTORY, config.BACKUPS_DIRECTORY]:
    os.makedirs(directory, exist_ok=True)

# Initialize session state
st.session_state.setdefault("interview_active", True)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("start_time", time.time())
st.session_state.setdefault("transcript_link", None)

# Check if the interview was previously completed
if check_if_interview_completed(config.TIMES_DIRECTORY, st.session_state.username):
    st.session_state.interview_active = False
    st.markdown("### Interview already completed.")

# Quit button
col1, col2 = st.columns([0.85, 0.15])
with col2:
    if st.session_state.interview_active and st.button("Quit", help="End the interview."):
        st.session_state.interview_active = False  # Mark interview as inactive
        st.session_state.messages.append({"role": "assistant", "content": "Interview ended."})

        # Save and upload the transcript
        transcript_link = save_interview_data(
            username=st.session_state.username,
            transcripts_directory=config.TRANSCRIPTS_DIRECTORY,
            times_directory=config.TIMES_DIRECTORY,
        )

        # Store the transcript link in session state
        if transcript_link:
            st.session_state.transcript_link = transcript_link

# After the interview ends
if not st.session_state.interview_active:
    st.empty()  # Clear screen

    # Display the evaluation button
    evaluation_url_with_session = f"https://leidenuniv.eu.qualtrics.com/jfe/form/SV_bvafC8YWGQJC1Ey?session_id={st.session_state.session_id}"
    st.markdown(
        f"""
        <div style="text-align: center;">
            <a href="{evaluation_url_with_session}" target="_blank" 
               style="text-decoration: none; background-color: #4CAF50; color: white; padding: 15px 32px; text-align: center; font-size: 16px; border-radius: 8px;">
                Click here to evaluate the interview
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Show transcript download link if available
    if st.session_state.transcript_link:
        st.markdown(f"### 📄 [Download your interview transcript]({st.session_state.transcript_link})", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No transcript link available. Please try again later.")

# Upon rerun, display the previous conversation
for message in st.session_state.messages[1:]:
    if message["role"] == "assistant":
        avatar = config.AVATAR_INTERVIEWER
    else:
        avatar = config.AVATAR_RESPONDENT

    if not any(code in message["content"] for code in config.CLOSING_MESSAGES.keys()):
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

# Load API client
if api == "openai":
    client = OpenAI(api_key=st.secrets["API_KEY"])
    api_kwargs = {"stream": True}
elif api == "anthropic":
    client = anthropic.Anthropic(api_key=st.secrets["API_KEY"])
    api_kwargs = {"system": config.SYSTEM_PROMPT}

# API kwargs
api_kwargs["messages"] = st.session_state.messages
api_kwargs["model"] = config.MODEL
api_kwargs["max_tokens"] = config.MAX_OUTPUT_TOKENS
if config.TEMPERATURE is not None:
    api_kwargs["temperature"] = config.TEMPERATURE

# In case the interview history is still empty, pass system prompt to model, and
# generate and display its first message
if not st.session_state.messages:

    # Replace greeting in the interview outline with a personalized message
    personalized_prompt = config.INTERVIEW_OUTLINE.replace(
        "Hello! I'm glad to have the opportunity to speak about your educational journey today.",
        f"Hello {respondent_name}! I'm glad to have the opportunity to speak about your educational journey today."
    )

    if api == "openai":

        st.session_state.messages.append(
            {"role": "system", "content": personalized_prompt}
        )
        with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
            stream = client.chat.completions.create(**api_kwargs)
            message_interviewer = st.write_stream(stream)

    elif api == "anthropic":

        st.session_state.messages.append({"role": "user", "content": "Hi"})
        with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):
            message_placeholder = st.empty()
            message_interviewer = ""
            with client.messages.stream(**api_kwargs) as stream:
                for text_delta in stream.text_stream:
                    if text_delta != None:
                        message_interviewer += text_delta
                    message_placeholder.markdown(message_interviewer + "▌")
            message_placeholder.markdown(message_interviewer)

    st.session_state.messages.append(
        {"role": "assistant", "content": message_interviewer}
    )

    # Store first backup files to record who started the interview
    save_interview_data(
        username=st.session_state.username,
        transcripts_directory=config.BACKUPS_DIRECTORY,
        times_directory=config.BACKUPS_DIRECTORY,
        file_name_addition_transcript=f"_transcript_started_{st.session_state.start_time_file_names}",
        file_name_addition_time=f"_time_started_{st.session_state.start_time_file_names}",
    )

# Main chat if interview is active
if st.session_state.interview_active:

    # Chat input and message for respondent
    if message_respondent := st.chat_input("Your message here"):
        st.session_state.messages.append(
            {"role": "user", "content": message_respondent}
        )

        # Display respondent message
        with st.chat_message("user", avatar=config.AVATAR_RESPONDENT):
            st.markdown(message_respondent)

        # Generate and display interviewer message
        with st.chat_message("assistant", avatar=config.AVATAR_INTERVIEWER):

            # Create placeholder for message in chat interface
            message_placeholder = st.empty()

            # Initialise message of interviewer
            message_interviewer = ""

            if api == "openai":

                # Stream responses
                stream = client.chat.completions.create(**api_kwargs)

                for message in stream:
                    text_delta = message.choices[0].delta.content
                    if text_delta != None:
                        message_interviewer += text_delta
                    # Start displaying message only after 5 characters to first check for codes
                    if len(message_interviewer) > 5:
                        message_placeholder.markdown(message_interviewer + "▌")
                    if any(
                        code in message_interviewer
                        for code in config.CLOSING_MESSAGES.keys()
                    ):
                        # Stop displaying the progress of the message in case of a code
                        message_placeholder.empty()
                        break

            elif api == "anthropic":

                # Stream responses
                with client.messages.stream(**api_kwargs) as stream:
                    for text_delta in stream.text_stream:
                        if text_delta != None:
                            message_interviewer += text_delta
                        # Start displaying message only after 5 characters to first check for codes
                        if len(message_interviewer) > 5:
                            message_placeholder.markdown(message_interviewer + "▌")
                        if any(
                            code in message_interviewer
                            for code in config.CLOSING_MESSAGES.keys()
                        ):
                            # Stop displaying the progress of the message in case of a code
                            message_placeholder.empty()
                            break

            # If no code is in the message, display and store the message
            if not any(
                code in message_interviewer for code in config.CLOSING_MESSAGES.keys()
            ):

                message_placeholder.markdown(message_interviewer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": message_interviewer}
                )

                # Regularly store interview progress as backup, but prevent script from
                # stopping in case of a write error
                try:

                    save_interview_data(
                        username=st.session_state.username,
                        transcripts_directory=config.BACKUPS_DIRECTORY,
                        times_directory=config.BACKUPS_DIRECTORY,
                        file_name_addition_transcript=f"_transcript_started_{st.session_state.start_time_file_names}",
                        file_name_addition_time=f"_time_started_{st.session_state.start_time_file_names}",
                    )

                except:

                    pass

            # If code in the message, display the associated closing message instead
            # Loop over all codes
            for code in config.CLOSING_MESSAGES.keys():

                if code in message_interviewer:
                    # Store message in list of messages
                    st.session_state.messages.append(
                        {"role": "assistant", "content": message_interviewer}
                    )

                    # Set chat to inactive and display closing message
                    st.session_state.interview_active = False
                    closing_message = config.CLOSING_MESSAGES[code]
                    st.markdown(closing_message)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": closing_message}
                    )

                    # Store final transcript and time
                    final_transcript_stored = False
                    while final_transcript_stored == False:

                        save_interview_data(
                            username=st.session_state.username,
                            transcripts_directory=config.TRANSCRIPTS_DIRECTORY,
                            times_directory=config.TIMES_DIRECTORY,
                        )

                        final_transcript_stored = check_if_interview_completed(
                            config.TRANSCRIPTS_DIRECTORY, st.session_state.username
                        )
                        time.sleep(0.1)
