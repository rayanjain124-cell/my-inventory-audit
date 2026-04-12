import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319"

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions
def save_data(df): 
    df.to_csv(DATA_FILE, index=False)

def load_data(): 
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Fix the TypeError: Ensure these columns are always treated as text
        df['Audit_Status'] = df['Audit_Status'].astype(str)
        df['Scanned_By'] = df['Scanned_By'].fillna("").astype(str)
        return df
    return None

# --- SIDEBAR ---
st.sidebar.title("System Menu")
if st.sidebar.button("🚨 Emergency Full Reset"):
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    h_input = st.text_input("Enter Master Host Code", type="password")
    if st.button("Unlock Admin Panel ➔"):
        if h_input == MASTER_KEY:
            st.session_state.is_host = True
        else:
            st.error("Invalid Master Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Create New Audit Session")
            session_key = st.text_input("Create Session Code for Auditors", "1234")
            file_main = st.file_uploader("Upload Main Stock (A-P)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                # Find Column M (Index 12)
                cat_col = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_cats = sorted(df_main[cat_col].unique().tolist())
                selected_cats = st.multiselect("Select Product Categories for Audit", unique_cats)
                
                if st.button("Start Audit Session 🚀") and selected_cats:
                    df_final = df_main[df_main[cat_col].isin(selected_cats)].copy()
                    df_final['Audit_Status'] = "Pending"
                    df_final['Scanned_By'] = "" 
                    save_data(df_final)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"session_key": session_key, "categories": selected_cats}, f)
                    st.rerun()
        else:
            st.subheader("Active Session Summary")
            df = load_data()
            
            # Separate Screens for Summary
            t1, t2 = st.tabs(["Shortage/Excess Report", "Full Inventory"])
            with t1:
                shortage = df[df['Audit_Status'] == "Pending"]
                tally = df[df['Audit_Status'] == "✅ Scanned"]
                st.write(f"**Tally:** {len(tally)} | **Shortage:** {len(shortage)}")
                st.dataframe(shortage)
            
            st.download_button("📥 Download Final Report", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            if st.button("🔥 Wipe & Close Audit"):
                os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("Wait for Host to start.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        a_name = st.text_input("Scanner Name")
        a_code = st.text_input("Session Code", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config['session_key']:
                st.session_state.auditor_name = a_name
                st.session_state.is_auditor = True
                st.session_state.scan_history = [] # For Undo/Redo

        if st.session_state.get('is_auditor'):
            st.info(f"Scanner: {st.session_state.auditor_name}")
            df_audit = load_data()

            # UNDO BUTTON
            if st.session_state.scan_history:
                if st.button("↩️ Undo Last Scan"):
                    last_id = st.session_state.scan_history.pop()
                    df_audit.at[last_id, 'Audit_Status'] = "Pending"
                    df_audit.at[last_id, 'Scanned_By'] = ""
                    save_data(df_audit)
                    st.warning("Last scan undone.")
                    st.rerun()

            # INPUT SECTION
            input_mode = st.radio("Scanner Type", ["Gun Scanner / Type", "Mobile Camera"], horizontal=True)
            
            if input_mode == "Mobile Camera":
                scan_raw = st.camera_input("Scan Barcode")
                # Camera processing requires barcode library; usually used for manual pic check here
            else:
                scan_raw = st.text_input("Scan Item (Auto-Submit Enabled)", key="scan_box")

            if scan_raw:
                # FIX: Case Insensitivity (Upper/Lower match)
                scan = str(scan_raw).strip().upper()
                
                # Check Serial (Column F/H) or Item Number (Column D)
                # We compare everything in UPPER case for the logic
                match = df_audit[(df_audit['Serial No'].astype(str).str.upper() == scan) | 
                                 (df_audit['Item Number'].astype(str).str.upper() == scan)]
                
                if not match.empty:
                    idx = match.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ DUPLICATE! Already scanned by {df_audit.at[idx]['Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        st.session_state.scan_history.append(idx) # Track for undo
                        save_data(df_audit)
                        st.toast("Saved!")
                else:
                    st.error(f"❌ EXCESS ITEM: {scan} not in current audit categories.")

            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']])
