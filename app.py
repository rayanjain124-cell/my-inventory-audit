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
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    # Use Master Key to unlock the "Creation" area
    h_input = st.text_input("Enter Master Host Code to Unlock", type="password")
    if st.button("Unlock Admin Panel ➔"):
        if h_input == MASTER_KEY:
            st.session_state.is_host = True
            st.success("Admin Panel Unlocked")
        else:
            st.error("Invalid Master Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("1. Create Fresh Audit Session")
            
            # Here you create the code for THIS specific audit
            new_session_code = st.text_input("Create a Fresh Code for this Audit", "1234")
            mode = st.selectbox("Audit Type", ["Serial Only", "Non-Serial Only", "Mixed"])
            
            # File Uploads
            file_main = st.file_uploader("Upload Main Stock (A-P)", type=['xlsx', 'csv'])
            file_transfer = st.file_uploader("Upload Transfer Sheet (Optional)", type=['xlsx', 'csv'])
            
            if file_main:
                df_temp = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                
                # Column M (Index 12) for Category Filtering
                cat_col = df_temp.columns[12] if len(df_temp.columns) > 12 else df_temp.columns[-1]
                all_categories = df_temp[cat_col].unique().tolist()
                selected_cats = st.multiselect(f"Select Categories from {cat_col}", all_categories, default=all_categories)
                
                if st.button("Start Audit Session 🚀"):
                    df_final = df_temp[df_temp[cat_col].isin(selected_cats)].copy()
                    df_final['Audit_Status'] = "Pending"
                    df_final['Scanned_By'] = ""
                    
                    # Store Transfer Data separately if uploaded
                    if file_transfer:
                        df_t = pd.read_csv(file_transfer) if file_transfer.name.endswith('csv') else pd.read_excel(file_transfer)
                        df_t.to_csv("transfer_state.csv", index=False)
                    
                    save_data(df_final)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"mode": mode, "session_key": new_session_code, "categories": selected_cats}, f)
                    st.success("Session Created! You can now use your fresh code.")
                    st.rerun()
        else:
            # Active Session Management
            st.subheader("Manage Active Session")
            data = load_data()
            
            # Log in to active session
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
            st.info(f"Active Session Code: {config['session_key']}")
            
            st.download_button("📥 Download Final Report", data.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            
            if st.button("🔥 Wipe & Close Audit"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                if os.path.exists("transfer_state.csv"): os.remove("transfer_state.csv")
                st.session_state.is_host = False
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("No active audit found. Wait for Host.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        # Auditor uses the FRESH code created by the host
        a_name = st.text_input("Scanner Name")
        a_code = st.text_input("Enter Session Code", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config['session_key']:
                st.session_state.auditor_name = a_name
                st.session_state.is_auditor = True
            else:
                st.error("Invalid Name or Session Code")

        if st.session_state.get('is_auditor'):
            st.info(f"Scanning as: {st.session_state.auditor_name}")
            df_audit = load_data()
            
            scan = st.text_input("Scan / Type Item (Press Enter)")
            if scan:
                # Search logic
                match = df_audit[(df_audit['Serial No'].astype(str) == scan) | (df_audit['Item Number'].astype(str) == scan)]
                
                if not match.empty:
                    idx = match.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ DUPLICATE: Already scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        save_data(df_audit)
                        st.toast("Saved!")
                else:
                    st.error("❌ NOT IN STOCK (EXCESS)")
            
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']])
