import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319" # Your permanent emergency key

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions
def save_data(df): df.to_csv(DATA_FILE, index=False)
def load_data(): return pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else None

# --- SIDEBAR & RESET ---
st.sidebar.title("Navigation")
if st.sidebar.button("🚨 Emergency Full Reset"):
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Admin Control Center")
    
    # Login Logic
    h_input = st.text_input("Enter Host Key", type="password")
    if st.button("Open Host Panel ➔"):
        if h_input == MASTER_KEY or h_input == "1234":
            st.session_state.is_host = True
            st.success("Access Granted!")
        else:
            st.error("Invalid Key")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Setup New Audit Session")
            c1, c2 = st.columns(2)
            with c1:
                mode = st.selectbox("Category", ["Serial Only", "Non-Serial Only", "Mixed"])
            with c2:
                a_code = st.text_input("Auditor Code", "9999")
            
            file = st.file_uploader("Upload Master Stock", type=['xlsx', 'csv'])
            if st.button("Start Audit 🚀"):
                if file:
                    df = pd.read_csv(file) if file.name.endswith('csv') else pd.read_excel(file)
                    df['Audit_Status'] = "Pending"
                    save_data(df)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"mode": mode, "code": a_code}, f)
                    st.rerun()
        else:
            # Active Session Management
            st.subheader("Active Session")
            data = load_data()
            st.download_button("📥 Download Final Report", data.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            
            if st.button("🔥 Wipe & Close Audit"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                st.session_state.is_host = False
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("Waiting for Host to start audit...")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        a_input = st.text_input("Enter Auditor Code", type="password")
        if st.button("Start Scanning ➔"):
            st.session_state.is_auditor = (a_input == config['code'])

        if st.session_state.get('is_auditor'):
            df_audit = load_data()
            scan = st.text_input("Scan / Type Item (Press Enter)")
            
            if scan:
                # Duplicate Check
                dup = df_audit[(df_audit['Serial No'].astype(str) == scan) & (df_audit['Audit_Status'] == "✅ Scanned")]
                if not dup.empty:
                    st.error(f"⚠️ DUPLICATE: {scan} already scanned!")
                else:
                    match = df_audit[(df_audit['Serial No'].astype(str) == scan) | (df_audit['Item Number'].astype(str) == scan)]
                    if not match.empty:
                        idx = match.index[0]
                        st.success(f"FOUND: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        save_data(df_audit)
                        st.toast("Saved!")
                    else:
                        st.error("❌ NOT IN STOCK")
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status']], use_container_width=True)
