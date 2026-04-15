"""
API Key Guide — How to get your Groq API key.
"""

import streamlit as st

st.title("🔑 Getting Your Groq API Key")

st.markdown("""
## Step-by-Step Guide

### 1. Create a Groq Account
1. Go to [console.groq.com](https://console.groq.com)
2. Click **Sign Up** and create an account using your email
3. Verify your email address

### 2. Generate API Key
1. After logging in, go to the **API Keys** section in the left sidebar
2. Click **Create API Key**
3. Give your key a name (e.g., "OxData App")
4. Copy the generated key (it will only be shown once!)

### 3. Add Key to OxData
1. Go to the Chat page
2. In the left sidebar, find the **API Keys** section
3. Paste your Groq API key in the input field
4. The key is stored only for your current session

---

## ⚠️ Important Notes

- **Free Tier**: Groq offers free API calls with generous limits
- **Security**: Never share your API key publicly
- **Session Storage**: The key is only stored in your browser session for security

## 🔧 Troubleshooting

If you see an "API key error":
1. Verify you're using the correct key from [console.groq.com](https://console.groq.com)
2. Check that the key hasn't expired
3. Ensure you have API credits available in your account

For more help, visit the [Groq Documentation](https://docs.groq.com).
""")

st.divider()
st.caption("")