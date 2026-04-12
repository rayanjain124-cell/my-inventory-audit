import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
TRANSFER_FILE = "transfer_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319"  # Your Permanent Emergency Host Code

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions
def save_data(df, path=DATA_FILE): df.to_csv(path, index=False)
def load_data(path=DATA_FILE): return pd.read_csv(path) if os.path.exists(path) else None

# --- SIDEBAR & RESET ---
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
    
    # Step 1: Secure Login
    h_input = st.text_input("Enter Master Host Code", type="password")
    if st.button("Unlock Admin Panel ➔"):
        if h_input == MASTER_KEY:
            st.session_state.is_host = True
            st.success("Admin Panel Unlocked")
        else:
            st.error("Invalid Master Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("1. Setup New Audit Session")
            
            # Create a fresh code for auditors for THIS session
            session_key = st.text_input("Create Session Code for Auditors", "1234")
            mode = st.selectbox("Audit Type", ["Serial Only", "Non-Serial Only", "Mixed"])
            
            # File Uploads
            file_main = st.file_uploader("Upload Main Stock (A-P Columns)", type=['xlsx', 'csv'])
            file_transfer = st.file_uploader("Upload Transfer Sheet (Optional)", type=['xlsx', 'csv'])
            
            if file_main:
                # Load main data to extract categories
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                
                # Column M is Index 12. Identifying category column.
                col_m_name = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_categories = sorted(df_main[col_m_name].unique().tolist())
                
                # MULTI-SELECT CATEGORY OPTION
                st.write(f"### Select Product Categories (from {col_m_name})")
                selected_cats = st.multiselect("You can select multiple categories for this audit:", 
                                               options=unique_categories, 
                                               default=None,
                                               help="Items not in these categories will be excluded from the audit.")
                
                if st.button("Start Audit Session 🚀"):
                    if not selected_cats:
                        st.error("Please select at least one product category.")
                    else:
                        # Filter data by selected categories
                        df_filtered = df_main[df_main[col_m_name].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        
                        save_data(df_filtered)
                        
                        # Save Transfer data if provided
                        if file_transfer:
                            df_t = pd.read_csv(file_transfer) if file_transfer.name.endswith('csv') else pd.read_excel(file_transfer)
                            save_data(df_t, TRANSFER_FILE)
                        
                        # Save Config
                        with open(CONFIG_FILE, 'w') as f:
                            json.dump({
                                "mode": mode, 
                                "session_key": session_key, 
                                "categories": selected_cats,
                                "cat_column": col_m_name
                            }, f)
                        st.success(f"Audit Session Started with {len(df_filtered)} items.")
                        st.rerun()
        else:
            # ACTIVE SESSION VIEW
            st.subheader("Active Session Management")
            data = load_data()
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
            
            st.info(f"Session Code: {config['session_key']} | Categories: {', '.join(config['categories'])}")
            
            st.download_button("📥 Download Final Audit Report", data.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            
            if st.button("🔥 Wipe & Close Audit"):
                for f in [DATA_FILE, TRANSFER_FILE, CONFIG_FILE]:
                    if os.path.exists(f): os.remove(f)
                st.session_state.is_host = False
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("No active audit found. Host must initialize the session.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        a_name = st.text_input("Your Name (Scanner Name)")
        a_code = st.text_input("Enter Session Code", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config['session_key']:
                st.session_state.auditor_name = a_name
                st.session_state.is_auditor = True
            else:
                st.error("Invalid Name or Session Code")

        if st.session_state.get('is_auditor'):
            st.info(f"Scanner: {st.session_state.auditor_name} | Mode: {config['mode']}")
            df_audit = load_data()
            df_transfer = load_data(TRANSFER_FILE)
            
            # High-Speed Scanning Input
            scan = st.text_input("Scan / Type Item (Press Enter to Submit)", key="scan_input")
            
            if scan:
                # 1. Search in Main Audit List
                match = df_audit[(df_audit['Serial No'].astype(str) == scan) | 
                                 (df_audit['Item Number'].astype(str) == scan)]
                
                # 2. Search in Transfer Sheet if not found in Main
                on_transfer = False
                if match.empty and df_transfer is not None:
                    # Looking in H column (Serial) of Transfer sheet as per your previous requirement
                    t_col_serial = df_transfer.columns[7] if len(df_transfer.columns) > 7 else df_transfer.columns[-1]
                    match_t = df_transfer[df_transfer[t_col_serial].astype(str) == scan]
                    if not match_t.empty:
                        on_transfer = True
                
                if not match.empty:
                    idx = match.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ DUPLICATE: Already scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']} | Bin: {df_audit.at[idx, 'Bin']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        save_data(df_audit)
                        st.toast("Saved!")
                elif on_transfer:
                    st.warning(f"ℹ️ ITEM ON TRANSFER SHEET: {scan} is valid but not in main stock.")
                else:
                    st.error(f"❌ NOT IN STOCK (EXCESS): {scan}")

            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']], use_container_width=True)
