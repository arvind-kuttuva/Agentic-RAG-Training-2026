import streamlit as st
import requests

# Backend URL
BACKEND_URL = "http://localhost:8000/api/v1/chat"

st.set_page_config(page_title="Audio Retrieval RAG", page_icon="🤖", layout="wide")

st.title("🤖 Audio Retrieval RAG")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Type your Audio related query...")

# Send message
if user_input:
      # Add user message
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )    

    with st.chat_message("user"):
        st.markdown(user_input) 

    # Call backend
    response = requests.post(
        BACKEND_URL,
        json={"query": user_input}
    )
    #bot_reply = response.json()["response"]
    data = response.json() # converts the json received to dict
    bot_reply = data.get("results","No answer received. Please try again later") #gets the value from dict
   
    # Save response
    st.session_state.messages.append(
        {"role": "assistant", "content": bot_reply}
    )

    # Display response
    with st.chat_message("assistant"):
        st.markdown(bot_reply)