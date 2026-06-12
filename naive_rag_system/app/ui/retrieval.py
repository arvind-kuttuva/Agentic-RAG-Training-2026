import streamlit as st
import requests

# Backend URL
BACKEND_URL = "http://localhost:8000/api/v1/chat"

st.set_page_config(page_title="Personalized Wealth Management Advisor", page_icon="🤖", layout="wide")

st.title("🤖 Personalized Wealth Management Advisor")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Type your wealth management related query...")

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
    # answer = data.get("answer", "No answer received. Please try again later")
    # sources = data.get("sources", [])

    # results = data.get("results",[])
    # bot_reply = "\n\n".join([r.get("content","") for r in results])
    # print(f"inside ui {response}")
    # bot_reply = response["messages"]

    # Save response
    st.session_state.messages.append(
        {"role": "assistant", "content": bot_reply}
    )

    # Display response
    with st.chat_message("assistant"):
        st.markdown(bot_reply)

        # if sources:
        #     st.markdown("Citations:")
        #     for s in sources:
        #         source = s.get("metadata", {}).get("source")
        #         page = s.get("metadata", {}).get("page")                

        #         st.markdown(f"- {source} (Page {page} ")