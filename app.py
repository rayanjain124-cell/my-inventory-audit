import streamlit as st
import pandas as pd
import os
import json

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
TRANSFER_FILE = "transfer_state.csv"
CONFIG_FILE = "audit_config.json"
MASTER_KEY = "9619753319"  # Permanent Emergency Host Code

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# Helper functions
def save_data(df, path=DATA_FILE): 
    # Fix for your screenshot error: Ensure columns are saved as text
    if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].astype(str)
    if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].astype(str)
    df.to_csv(path, index=False)

def load_data(path=DATA_FILE): 
    if os.path.exists(path):
        df = pd.read_csv(path)
        # Prevent TypeError by forcing text format immediately
        if 'Audit_Status' in df.columns: df['Audit_Status'] = df['Audit_Status'].fillna("Pending").astype(str)
        if 'Scanned_By' in df.columns: df['Scanned_By'] = df['Scanned_By'].fillna("").astype(str)
        return df
    return None

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
            session_key = st.text_input("Create Session Code for Auditors", "1234")
            file_main = st.file_uploader("Upload Main Stock (A-P Columns)", type=['xlsx', 'csv'])
            file_transfer = st.file_uploader("Upload Transfer Sheet (Optional)", type=['xlsx', 'csv'])
            
            if file_main:
                df_main = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                
                # Column M (Index 12) for Product Category
                col_m_name = df_main.columns[12] if len(df_main.columns) > 12 else df_main.columns[-1]
                unique_categories = sorted(df_main[col_m_name].unique().tolist())
                
                st.write(f"### Select Product Categories (from {col_m_name})")
                selected_cats = st.multiselect("Select categories to include in this audit:", 
                                               options=unique_categories, 
                                               default=None)
                
                if st.button("Start Audit Session 🚀"):
                    if not selected_cats:
                        st.error("Please select at least one category.")
                    else:
                        df_filtered = df_main[df_main[col_m_name].isin(selected_cats)].copy()
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
            st.subheader("Active Session Management")
            df = load_data()
            
            # Host Summary View (Separate Shortage/Excess)
            t1, t2 = st.tabs(["Shortage & Excess", "All Inventory"])
            with t1:
                st.dataframe(df[df['Audit_Status'] == "Pending"])
            with t2:
                st.dataframe(df)
                
            st.download_button("📥 Download Final Report", df.to_csv(index=False).encode('utf-8'), "Audit_Report.csv")
            if st.button("🔥 Wipe & Close Audit"):
                for f in [DATA_FILE, TRANSFER_FILE, CONFIG_FILE]:
                    if os.path.exists(f): os.remove(f)
                st.session_state.is_host = False
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Scanning Station")
    if not os.path.exists(CONFIG_FILE):
        st.warning("No active audit found.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        a_name = st.text_input("Your Name")
        a_code = st.text_input("Session Code", type="password")
        
        if st.button("Start Scanning ➔"):
            if a_name and a_code == config['session_key']:
                st.session_state.auditor_name = a_name
                st.session_state.is_auditor = True
                st.session_state.history = [] # For Undo/Redo
                st.session_state.redo_stack = []

        if st.session_state.get('is_auditor'):
            st.info(f"Scanner: {st.session_state.auditor_name}")
            df_audit = load_data()
            df_transfer = load_data(TRANSFER_FILE)

            # --- UNDO / REDO ---
            c1, c2 = st.columns(2)
            with c1:
                if st.button("↩️ Undo Last Scan") and st.session_state.history:
                    idx = st.session_state.history.pop()
                    st.session_state.redo_stack.append(idx)
                    df_audit.at[idx, 'Audit_Status'] = "Pending"
                    df_audit.at[idx, 'Scanned_By'] = ""
                    save_data(df_audit)
                    st.rerun()
            with c2:
                if st.button("↪️ Redo Scan") and st.session_state.redo_stack:
                    idx = st.session_state.redo_stack.pop()
                    st.session_state.history.append(idx)
                    df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                    df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                    save_data(df_audit)
                    st.rerun()

            # --- SCAN INPUT ---
            scan_raw = st.text_input("Scan with Gun / Type (Press Enter)", key="scan_input")
            
            if scan_raw:
                # 1. Clean data and handle Case Insensitivity
                scan = str(scan_raw).strip().upper()
                
                # 2. Match Logic (Case Insensitive)
                match = df_audit[(df_audit['Serial No'].astype(str).str.upper() == scan) | 
                                 (df_audit['Item Number'].astype(str).str.upper() == scan)]
                
                if not match.empty:
                    idx = match.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ DUPLICATE! Already scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        st.success(f"MATCH: {df_audit.at[idx, 'Product']}")
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        st.session_state.history.append(idx)
                        st.session_state.redo_stack = [] # Clear redo on new scan
                        save_data(df_audit)
                        st.toast("Saved!")
                else:
                    # 3. Transfer Check
                    on_t = False
                    if df_transfer is not None:
                        t_ser_col = df_transfer.columns[7] if len(df_transfer.columns) > 7 else df_transfer.columns[-1]
                        if not df_transfer[df_transfer[t_ser_col].astype(str).str.upper() == scan].empty:
                            on_t = True
                    
                    if on_t: st.warning(f"ℹ️ ITEM ON TRANSFER: {scan}")
                    else: st.error(f"❌ EXCESS ITEM: {scan}")

            st.divider()
            st.dataframe(df_audit[['Product', 'Bin', 'Serial No', 'Audit_Status', 'Scanned_By']], use_container_width=True)
