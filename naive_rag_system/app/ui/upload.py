import streamlit as st
import requests

BACKEND_URL = "http://localhost:8000/api/v1/upload"

st.set_page_config(page_title="Upload PDF", page_icon="📄")

st.title("📄 Upload Document")

# ✅ Unique key for uploader (important)
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# File uploader (key controls reset)
uploaded_file = st.file_uploader(
    "Choose a file",
    type=["pdf", "txt"],
    key=st.session_state.uploader_key
)

if uploaded_file:
    st.success(f"Selected file: {uploaded_file.name}")

# Buttons
col1, col2 = st.columns(2)

# ✅ Upload button (unchanged)
with col1:
    if st.button("Upload 🚀"):
        if uploaded_file:
            files = {
                "file": (uploaded_file.name, uploaded_file, uploaded_file.type)
            }

            with st.spinner("Uploading and processing..."):
                try:
                    response = requests.post(BACKEND_URL, files=files)

                    if response.status_code == 200:
                        st.success("✅ File uploaded and processed successfully!")
                    else:
                        try:
                            error_msg = response.json().get("detail", "upload failed")
                        except:
                            error_msg = "upload failed"

                        st.error(f"❌ {error_msg}")

                except Exception as e:
                    st.error(f"⚠️ Error: {str(e)}")

# ✅ Clear button (FIXED)
with col2:
    if st.button("Clear 🗑️"):
        # 🔥 increment key → forces uploader reset
        st.session_state.uploader_key += 1
        st.rerun()

