import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
# THIS IS ONLY FOR EMERGENCY/FIRST-TIME SETUP
EMERGENCY_MASTER_KEY = "9619753319" 

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Fix for the TypeError seen in your logs
def save_data(df): 
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

# --- SIDEBAR RESET ---
st.sidebar.title("Audit System")
if st.sidebar.button("🚨 Emergency Full Reset"):
    for f in [DATA_FILE, "transfer_state.csv", CONFIG_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    # Check if an Admin Key has been set yet
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    
    saved_admin_key = config.get("admin_key")

    if not saved_admin_key:
        st.warning("No Admin Key set. Use Emergency Master Key to initialize.")
        m_input = st.text_input("Enter Emergency Master Key", type="password")
        if st.button("Initialize System ➔"):
            if m_input == EMERGENCY_MASTER_KEY:
                st.session_state.initializing = True
            else:
                st.error("Invalid Emergency Key")
        
        if st.session_state.get('initializing'):
            new_key = st.text_input("Set Your Permanent Admin Key", type="password")
            if st.button("Save Admin Key"):
                with open(CONFIG_FILE, 'w') as f:
                    json.dump({"admin_key": new_key}, f)
                st.success("Admin Key saved! Please log in again.")
                st.rerun()
    else:
        # Regular Login using the key YOU created
        h_input = st.text_input("Enter Your Admin Key", type="password")
        if st.button("Unlock Host Panel ➔"):
            if h_input == saved_admin_key or h_input == EMERGENCY_MASTER_KEY:
                st.session_state.is_host = True
            else:
                st.error("Invalid Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("1. Create New Audit Sheet")
            # Session code for the scanners (Auditors)
            session_key = st.text_input("Create Today's Session Code for Scanners", "1234")
            file_main = st.file_uploader("Upload Main Stock (A-P)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                col_m = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_cats = sorted(df_main[col_m].unique().tolist())
                
                selected_cats = st.multiselect("Select Product Categories (Col M):", unique_cats)
                
                if st.button("Start Audit Session 🚀"):
                    if selected_cats:
                        df_filtered = df_main[df_main[col_m].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        save_data(df_filtered)
                        config["session_key"] = session_key
                        with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                        st.rerun()
        else:
            st.subheader("Manage Active Audit")
            df = load_data()
            st.download_button("📥 Download Report", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            if st.button("🔥 Close & Clear Current Audit"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("Host has not started a session.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        a_name = st.text_input("Your Name")
        a_code = st.text_input("Enter Session Code", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config.get('session_key'):
                st.session_state.is_auditor = True
                st.session_state.auditor_name = a_name
                st.session_state.history = []

        if st.session_state.get('is_auditor'):
            df_audit = load_data()
            if st.button("↩️ Undo Last Scan") and st.session_state.history:
                idx = st.session_state.history.pop()
                df_audit.at[idx, 'Audit_Status'] = "Pending"
                df_audit.at[idx, 'Scanned_By'] = ""
                save_data(df_audit)
                st.rerun()

            scan_raw = st.text_input("Scan with Gun (Case Insensitive)", key="scan_input")
            if scan_raw:
                scan = str(scan_raw).strip().upper()
                match = df_audit[(df_audit['Serial No'].astype(str).str.upper() == scan) | 
                                 (df_audit['Item Number'].astype(str).str.upper() == scan)]
                
                if not match.empty:
                    idx = match.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ DUPLICATE! Scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        st.session_state.history.append(idx)
                        save_data(df_audit)
                        st.toast("Saved!")
                else: st.error(f"❌ EXCESS: {scan}")
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']])
