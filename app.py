import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
EMERGENCY_MASTER_KEY = "9619753319" # Your private back-door

st.set_page_config(page_title="Audit Master Pro", layout="wide")

def save_data(df): 
    # Fix for TypeError: Ensures all status/name columns remain strings
    if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].astype(str)
    if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].astype(str)
    df.to_csv(DATA_FILE, index=False)

def load_data(): 
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].fillna("Pending").astype(str)
        if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].fillna("").astype(str)
        return df
    return None

# --- SIDEBAR ---
st.sidebar.title("System Control")
if st.sidebar.button("🚨 Emergency Full Reset"):
    for f in [DATA_FILE, CONFIG_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    
    saved_admin_key = config.get("admin_key")

    # Setup Host Password on first run
    if not saved_admin_key:
        st.subheader("Initial System Setup")
        new_key = st.text_input("Create Your Secret Admin Key", type="password")
        if st.button("Save Admin Key & Proceed"):
            if new_key:
                config["admin_key"] = new_key
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.success("Admin Key saved!")
                st.rerun()
    else:
        h_input = st.text_input("Enter Host Admin Key", type="password")
        if st.button("Unlock Host Panel ➔"):
            if h_input == saved_admin_key or h_input == EMERGENCY_MASTER_KEY:
                st.session_state.is_host = True
            else:
                st.error("Invalid Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Prepare New Audit Sheet")
            session_code = st.text_input("Set Session Code for Team (e.g. 1234)", "1234")
            file_main = st.file_uploader("Upload Main Stock (Columns A-P)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                col_m = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_cats = sorted(df_main[col_m].unique().tolist())
                selected_cats = st.multiselect("Select Categories to Audit:", unique_cats)
                
                if st.button("Start Audit Session 🚀"):
                    if selected_cats:
                        df_filtered = df_main[df_main[col_m].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        save_data(df_filtered)
                        config["session_key"] = session_code
                        with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                        st.rerun()
        else:
            st.subheader("Active Session Dashboard")
            df = load_data()
            st.write(f"Progress: {len(df[df['Audit_Status'] != 'Pending'])} / {len(df)} items")
            st.download_button("📥 Download Final Report", df.to_csv(index=False).encode('utf-8'), "Audit_Results.csv")
            if st.button("🔥 Close Audit Session"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Team Scanning Station")
    if not os.path.exists(DATA_FILE):
        st.warning("Audit is not live. Wait for Host setup.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        a_name = st.text_input("Your Name")
        a_code = st.text_input("Team Session Code", type="password")
        
        if st.button("Join Audit ➔"):
            if a_name and a_code == config.get('session_key'):
                st.session_state.is_auditor = True
                st.session_state.auditor_name = a_name
                st.session_state.history = []

        if st.session_state.get('is_auditor'):
            st.success(f"Connected: {st.session_state.auditor_name}")
            df_audit = load_data()

            # SYNC BUTTON: Allows teammates to see each other's work
            if st.button("🔄 Sync with Team"):
                st.rerun()

            # UNDO BUTTON
            if st.button("↩️ Undo My Last Scan") and st.session_state.history:
                idx = st.session_state.history.pop()
                df_audit.at[idx, 'Audit_Status'] = "Pending"
                df_audit.at[idx, 'Scanned_By'] = ""
                save_data(df_audit)
                st.rerun()

            # SCANNING
            scan_raw = st.text_input("Scan Barcode (Auto-Submit)", key="scan_box")
            if scan_raw:
                scan = str(scan_raw).strip().upper() # Case Insensitive
                match = df_audit[(df_audit['Serial No'].astype(str).str.upper() == scan) | 
                                 (df_audit['Item Number'].astype(str).str.upper() == scan)]
                
                if not match.empty:
                    idx = match.index[0]
                    # DUPLICATE PROTECTION: Sees if a teammate already scanned it
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ ALREADY SCANNED by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        st.session_state.history.append(idx)
                        save_data(df_audit)
                        st.toast("Saved!")
                else:
                    st.error(f"❌ EXCESS ITEM: {scan}")

            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']])
