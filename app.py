import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
# THIS IS YOUR PRIVATE EMERGENCY KEY (DO NOT SHARE)
EMERGENCY_MASTER_KEY = "9619753319"

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Error Prevention: Force columns to text to avoid "dtype" errors
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
    for f in [DATA_FILE, CONFIG_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    # Load config to check for Admin Key
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    
    admin_key = config.get("admin_key")

    # Step 1: First Run - Setup Admin Key
    if not admin_key:
        st.warning("First Run: Use Emergency Key to set your Admin password.")
        m_input = st.text_input("Enter Emergency Master Key", type="password")
        if st.button("Authorize Setup ➔"):
            if m_input == EMERGENCY_MASTER_KEY:
                st.session_state.setup_mode = True
            else:
                st.error("Invalid Emergency Key")
        
        if st.session_state.get('setup_mode'):
            new_admin_key = st.text_input("Create Your Secret Admin Key", type="password")
            if st.button("Save Admin Key"):
                config["admin_key"] = new_admin_key
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.success("Admin Key Saved! You can now log in.")
                st.rerun()
    else:
        # Step 2: Regular Host Login
        h_input = st.text_input("Enter Host Admin Key", type="password")
        if st.button("Unlock Host Panel ➔"):
            if h_input == admin_key or h_input == EMERGENCY_MASTER_KEY:
                st.session_state.is_host = True
            else:
                st.error("Invalid Code")

    # Step 3: Preparing the Sheet
    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Prepare Audit Sheet")
            session_key = st.text_input("Set Today's Session Code for Auditors", "1234")
            file_main = st.file_uploader("Upload Main Stock (A-P Columns)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                # Locate Column M (Category)
                col_m = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_cats = sorted(df_main[col_m].unique().tolist())
                
                selected_cats = st.multiselect("Select Categories to Audit:", unique_cats)
                
                if st.button("Finalize & Start Audit 🚀"):
                    if selected_cats:
                        df_filtered = df_main[df_main[col_m].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        save_data(df_filtered)
                        config["session_key"] = session_key
                        with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                        st.success("Audit is now LIVE. Auditors can start.")
                        st.rerun()
        else:
            st.subheader("Active Session")
            df = load_data()
            st.download_button("📥 Download Final Report", df.to_csv(index=False).encode('utf-8'), "Audit.csv")
            if st.button("🔥 Close Audit Session"):
                os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(DATA_FILE):
        st.warning("Please wait. Host is still preparing the audit sheet.")
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
            # Undo functionality
            if st.button("↩️ Undo Last Scan") and st.session_state.history:
                idx = st.session_state.history.pop()
                df_audit.at[idx, 'Audit_Status'] = "Pending"
                df_audit.at[idx, 'Scanned_By'] = ""
                save_data(df_audit)
                st.rerun()

            scan_raw = st.text_input("Scan / Type (Case Insensitive)", key="scan_box")
            if scan_raw:
                # Case Insensitive Logic: wwety matches WWETY
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
                        st.toast("Recorded!")
                else: st.error(f"❌ EXCESS: {scan}")
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']])
