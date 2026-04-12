import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- FILE PATHS ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"

st.set_page_config(page_title="High-Speed Audit Portal", layout="wide")

def save_audit_data(df):
    df.to_csv(DATA_FILE, index=False)

def load_audit_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return None

# --- APP LOGIC ---
st.title("🛡️ Secure Inventory Audit System")
user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    host_key = st.text_input("Enter Host Security Key", type="password")
    
    if host_key == "1234":
        if not os.path.exists(DATA_FILE):
            st.subheader("Start New Audit")
            audit_type = st.selectbox("Audit Category", ["Serial Only", "Non-Serial Only", "Mixed"])
            session_code = st.text_input("Set Auditor Access Code", "9999")
            uploaded_main = st.file_uploader("Upload Main Stock (A-P)", type=['csv', 'xlsx'])

            if st.button("🚀 Initialize Audit"):
                if uploaded_main:
                    df = pd.read_csv(uploaded_main) if uploaded_main.name.endswith('csv') else pd.read_excel(uploaded_main)
                    df['Audit_Status'] = "Pending"
                    df['Scan_Count'] = 0
                    save_audit_data(df)
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump({"type": audit_type, "code": session_code}, f)
                    st.success("Audit is now LIVE.")
                    st.rerun()
        else:
            current_data = load_audit_data()
            st.subheader("Active Audit Summary")
            st.write(f"Items Scanned: {len(current_data[current_data['Audit_Status'] == '✅ Scanned'])} / {len(current_data)}")
            
            csv_result = current_data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Final Report", csv_result, "Final_Audit.csv")
            
            if st.button("🔥 WIPE ALL DATA & RESET"):
                os.remove(DATA_FILE)
                os.remove(CONFIG_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Auditor Scanning")
    if not os.path.exists(CONFIG_FILE):
        st.error("No active audit found.")
    else:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        auth_code = st.text_input("Enter Access Code", type="password")
        if auth_code == config['code']:
            df_audit = load_audit_data()
            
            # INPUT METHOD TOGGLE
            input_mode = st.radio("Input Method", ["Gun Scanner / Typing", "Mobile Camera"], horizontal=True)
            
            scan_input = ""
            if input_mode == "Mobile Camera":
                img_file = st.camera_input("Scan Barcode")
                # (Note: Camera scanning requires additional library for auto-decoding, 
                # standard camera input here is for manual verification)
            else:
                # GUN SCANNER LOGIC: 'on_change' triggers auto-save when scanner hits 'Enter'
                scan_input = st.text_input("Scan Item (Gun Scanner Auto-Mode)", key="scanner_input")

            if scan_input:
                # 1. CHECK FOR DUPLICATE
                already_scanned = df_audit[(df_audit['Serial No'].astype(str) == scan_input) & 
                                          (df_audit['Audit_Status'] == "✅ Scanned")]
                
                if not already_scanned.empty:
                    st.error(f"⚠️ DUPLICATE SCAN! Serial {scan_input} is already recorded.")
                    st.warning(f"Item: {already_scanned.iloc[0]['Product']}")
                else:
                    # 2. FIND ITEM
                    match = df_audit[(df_audit['Serial No'].astype(str) == scan_input) | 
                                     (df_audit['Item Number'].astype(str) == scan_input)]
                    
                    if not match.empty:
                        idx = match.index[0]
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scan_Count'] += 1
                        save_audit_data(df_audit)
                        st.success(f"SAVED: {df_audit.at[idx, 'Product']}")
                        st.toast(f"Updated {scan_input}")
                    else:
                        st.error("❌ ITEM NOT IN STOCK (EXCESS)")

            # DISPLAY
            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status']], use_container_width=True)
