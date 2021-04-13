import streamlit as st
import time
import os
import bcrypt
from botocore.exceptions import ClientError

def login_process(state):
    st.title("Login page")
    login_instructions = st.empty()
    login_instructions.markdown("Please type your username and password")

    user_name = st.empty()
    state.user_name = user_name.text_input("Username")

    user_pass = st.empty()
    state.user_pass = user_pass.text_input("Password", type="password")

    login_button = st.empty()
    login_button_state = login_button.button("Log in")


    if login_button_state and state.user_name.strip() != "" and state.user_pass.strip != "":
        try:
            # TODO: Process to check if username and password is correct
            access_granted = True
            if (access_granted):
                login_instructions = login_instructions.empty()
                user_name = user_name.empty()
                user_pass = user_pass.empty()
                login_button = login_button.empty()
                state.login = True

                log_in_msg = st.empty()
                log_in_msg.write("Log in Successful!")
                time.sleep(5)
                log_in_msg = log_in_msg.empty()
            else: 
                st.write("Log in Unsuccessful :(")
                st.write("Did you key in the correct username/password?")
        except ClientError as e:
            st.write(e.response['Error']['Message'])

        