import streamlit as st
import pandas as pd
import os
import json

# --- FILE PATHS ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"

st.set_page_config(page_title="Audit Portal Pro", layout="wide")

# --- EMERGENCY RESET (If you forget your key) ---
# This button stays in the sidebar only during your first setup
if st.sidebar.button("🚨 Emergency Portal Reset"):
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    st.rerun()

def save_audit_data(df):
    df.to_csv(DATA_FILE, index=False)

def load_audit_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return None

st.title("🛡️ Inventory Audit Management")

user_role = st.sidebar.radio("Role Selection", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Control Panel")
    
    # NEW: Host Login with a 'GO' Button
    h_key_input = st.text_input("Enter Host Security Key", type="password", help="Default is 1234")
    if st.button("Login as Host ➔"):
        st.session_state.host_authenticated = (h_key_input == "1234")
    
    if st.session_state.get('host_authenticated'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Step 1: Setup New Audit")
            col1, col2 = st.columns(2)
            with col1:
                audit_type = st.selectbox("Audit Category", ["Serial Only", "Non-Serial Only", "Mixed"])
            with col2:
                session_code = st.text_input("Set Auditor Access Code", "9999")
            
            uploaded_main = st.file_uploader("Upload Main Stock (A-P Columns)", type=['csv', 'xlsx'])

            if st.button("🚀 Initialize Audit & Start Session"):
                if uploaded_main:
                    df = pd.read_csv(uploaded_main) if uploaded_main.name.endswith('csv') else pd.read_excel(uploaded_main)
                    df['Audit_Status'] = "Pending"
                    save_audit_data(df)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"type": audit_type, "code": session_code}, f)
                    st.success("Audit is now LIVE.")
                    st.rerun()
        else:
            # MANAGEMENT AREA
            current_data = load_audit_data()
            st.subheader("Step 2: Active Audit Management")
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                csv_result = current_data.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Final Excel Report", csv_result, "Audit_Report.csv")
            
            with col_d2:
                if st.button("🔥 Wipe All Data (End Audit)"):
                    os.remove(DATA_FILE)
                    os.remove(CONFIG_FILE)
                    st.session_state.host_authenticated = False
                    st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Auditor Station")
    if not os.path.exists(CONFIG_FILE):
        st.error("No active audit found. Please wait for the Host to initialize.")
    else:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Auditor Login with a 'GO' Button
        a_key_input = st.text_input("Enter Auditor Access Code", type="password")
        if st.button("Enter Portal ➔"):
            st.session_state.auditor_authenticated = (a_key_input == config['code'])

        if st.session_state.get('auditor_authenticated'):
            df_audit = load_audit_data()
            
            # SCANNING AREA
            scan_input = st.text_input("Scan / Type Item and press Enter")
            
            if scan_input:
                # Duplicate Check
                is_duplicate = not df_audit[(df_audit['Serial No'].astype(str) == scan_input) & 
                                            (df_audit['Audit_Status'] == "✅ Scanned")].empty
                
                if is_duplicate:
                    st.error(f"⚠️ DUPLICATE! Serial {scan_input} already scanned.")
                else:
                    match = df_audit[(df_audit['Serial No'].astype(str) == scan_input) | 
                                     (df_audit['Item Number'].astype(str) == scan_input)]
                    
                    if not match.empty:
                        idx = match.index[0]
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']} | Bin: {df_audit.at[idx, 'Bin']}")
                        # Auto-save for Gun Scanner
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        save_audit_data(df_audit)
                        st.toast("Saved Successfully")
                    else:
                        st.error("❌ ITEM NOT IN STOCK")

            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status']], use_container_width=True)
