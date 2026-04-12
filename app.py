import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
TRANSFER_FILE = "transfer_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319" # REQUIRED TO UNLOCK HOST PANEL

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions to prevent the "dtype" error
def save_data(df, path=DATA_FILE): 
    if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].astype(str)
    if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].astype(str)
    df.to_csv(path, index=False)

def load_data(path=DATA_FILE): 
    if os.path.exists(path):
        df = pd.read_csv(path)
        if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].fillna("Pending").astype(str)
        if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].fillna("").astype(str)
        return df
    return None

# --- SIDEBAR RESET ---
st.sidebar.title("Audit System")
if st.sidebar.button("🚨 Emergency Full Reset"):
    for f in [DATA_FILE, TRANSFER_FILE, CONFIG_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    h_input = st.text_input("Enter Master Host Code (9619753319)", type="password")
    if st.button("Unlock Admin Panel ➔"):
        if h_input == MASTER_KEY:
            st.session_state.is_host = True
            st.success("Admin Panel Unlocked. You can now create your sheet.")
        else:
            st.error("Invalid Master Code. Please use 9619753319.")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("1. Setup New Audit Session")
            session_key = st.text_input("Create Session Code for Auditors", "1234")
            file_main = st.file_uploader("Upload Main Stock (A-P)", type=['xlsx', 'csv'])
            file_transfer = st.file_uploader("Upload Transfer Sheet (Optional)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                # Column M is Index 12
                col_m = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_cats = sorted(df_main[col_m].unique().tolist())
                
                selected_cats = st.multiselect("Select Product Categories (Col M):", unique_cats)
                
                if st.button("Start Audit Session 🚀"):
                    if not selected_cats:
                        st.error("Select at least one category.")
                    else:
                        df_filtered = df_main[df_main[col_m].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        save_data(df_filtered)
                        if file_transfer:
                            df_t = pd.read_csv(file_transfer) if file_transfer.name.endswith('csv') else pd.read_excel(file_transfer)
                            save_data(df_t, TRANSFER_FILE)
                        with open(CONFIG_FILE, 'w') as f:
                            json.dump({"session_key": session_key, "categories": selected_cats}, f)
                        st.rerun()
        else:
            st.subheader("Active Session")
            df = load_data()
            t1, t2 = st.tabs(["Shortage/Excess", "Full Data"])
            with t1: st.dataframe(df[df['Audit_Status'] == "Pending"])
            with t2: st.dataframe(df)
            st.download_button("📥 Download Report", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            if st.button("🔥 Close Audit"):
                os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("Host must start the session first.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        a_name = st.text_input("Your Name")
        a_code = st.text_input("Session Code (e.g. 1234)", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config['session_key']:
                st.session_state.auditor_name = a_name
                st.session_state.is_auditor = True
                st.session_state.history = []
            else: st.error("Incorrect Name or Code.")

        if st.session_state.get('is_auditor'):
            st.info(f"Scanner: {st.session_state.auditor_name}")
            df_audit = load_data()
            
            # Undo Button
            if st.button("↩️ Undo Last Scan") and st.session_state.history:
                idx = st.session_state.history.pop()
                df_audit.at[idx, 'Audit_Status'] = "Pending"
                df_audit.at[idx, 'Scanned_By'] = ""
                save_data(df_audit)
                st.rerun()

            scan_raw = st.text_input("Scan with Gun (Auto-Submit)", key="scan_input")
            if scan_raw:
                # Case-Insensitive Logic
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
