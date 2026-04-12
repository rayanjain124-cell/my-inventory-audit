import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319"  # Permanent Emergency Host Code

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions
def save_data(df): df.to_csv(DATA_FILE, index=False)
def load_data(): return pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else None

# --- SIDEBAR & RESET ---
st.sidebar.title("System Menu")
if st.sidebar.button("🚨 Emergency Full Reset"):
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    # Login with Go Button
    h_input = st.text_input("Enter Host Code", type="password", help="Use your permanent emergency code")
    if st.button("Open Host Panel ➔"):
        if h_input == MASTER_KEY:
            st.session_state.is_host = True
            st.success("Access Granted!")
        else:
            st.error("Invalid Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("1. Initialize New Audit")
            
            # Audit Mode
            mode = st.selectbox("Audit Type", ["Serial Only", "Non-Serial Only", "Mixed"])
            
            # Auditor Code Setup
            a_code = st.text_input("Create Code for Auditors", "9999")
            
            # File Upload
            file = st.file_uploader("Upload Main Stock (A-P)", type=['xlsx', 'csv'])
            
            if file:
                # Load data immediately to extract categories from Column M (Index 12)
                df_temp = pd.read_csv(file) if file.name.endswith('csv') else pd.read_excel(file)
                
                # Column M is typically index 12. Adjusting for standard A-P sheet:
                # If Column M is 'Product Category', we find unique values.
                cat_col = 'Product Category' if 'Product Category' in df_temp.columns else df_temp.columns[12]
                all_categories = df_temp[cat_col].unique().tolist()
                
                selected_cats = st.multiselect("Select Product Categories for today's Audit (Column M)", all_categories, default=all_categories)
                
                if st.button("Start Audit Session 🚀"):
                    # Filter data by selected categories
                    df_final = df_temp[df_temp[cat_col].isin(selected_cats)].copy()
                    df_final['Audit_Status'] = "Pending"
                    df_final['Scan_Count'] = 0
                    
                    save_data(df_final)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"mode": mode, "code": a_code, "categories": selected_cats}, f)
                    st.success("Audit is LIVE with selected categories.")
                    st.rerun()
        else:
            # Active Session Management
            st.subheader("Manage Active Session")
            data = load_data()
            st.write(f"Items in current Audit: {len(data)}")
            
            st.download_button("📥 Download Final Report", data.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            
            if st.button("🔥 Wipe & Close Audit"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                st.session_state.is_host = False
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("No active audit. Wait for Host to initialize.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        a_input = st.text_input("Enter Auditor Code", type="password")
        if st.button("Enter Scanner Portal ➔"):
            st.session_state.is_auditor = (a_input == config['code'])

        if st.session_state.get('is_auditor'):
            df_audit = load_data()
            st.info(f"Audit Categories: {', '.join(config['categories'])}")
            
            # Auto-submit logic for Gun Scanners
            scan = st.text_input("Scan / Type Item (Press Enter)", key="auditor_scan")
            
            if scan:
                # Duplicate Check
                dup = df_audit[(df_audit['Serial No'].astype(str) == scan) & (df_audit['Audit_Status'] == "✅ Scanned")]
                if not dup.empty:
                    st.error(f"⚠️ DUPLICATE: {scan} already scanned!")
                else:
                    # Match on Serial (Col F/H) or Item Number (Col D)
                    match = df_audit[(df_audit['Serial No'].astype(str) == scan) | (df_audit['Item Number'].astype(str) == scan)]
                    
                    if not match.empty:
                        idx = match.index[0]
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scan_Count'] += 1
                        save_data(df_audit)
                        st.toast("Saved!")
                    else:
                        st.error("❌ NOT IN STOCK (EXCESS)")
            
            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status']], use_container_width=True)
