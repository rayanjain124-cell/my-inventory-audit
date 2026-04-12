import streamlit as st
import pandas as pd
import os
import json
import io

# Camera library safety
try:
    from camera_input_live import camera_input_live
    HAS_SCANNER = True
except Exception:
    HAS_SCANNER = False

# --- FILE PATHS ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
EXCESS_FILE = "excess_items.csv"

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# --- DATA HELPERS ---
def save_data(df, file=DATA_FILE): 
    try:
        # Ensures all data is saved as clean strings to prevent object errors
        for col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "")
        df.to_csv(file, index=False)
    except Exception as e:
        st.error(f"Save Error: {e}")

def load_data(file=DATA_FILE): 
    if os.path.exists(file):
        try:
            df = pd.read_csv(file)
            cols = ['Audit_Status', 'Scanned_By', 'Matched_On', 'Item No.', 'Brand', 'Category', 'Serial No', 'Product']
            for col in cols:
                if col not in df.columns: df[col] = ""
                df[col] = df[col].fillna("").astype(str)
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# --- NAVIGATION ---
st.sidebar.title("Navigation")
user_role = st.sidebar.radio("Your Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        except Exception: config = {}
    
    saved_admin_key = config.get("admin_key")

    # Force creation of admin if first time
    if not saved_admin_key:
        st.subheader("Initial Admin Setup")
        new_key = st.text_input("Create Master Admin Password", type="password")
        if st.button("Save Admin Password"):
            if new_key:
                config["admin_key"] = new_key
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.rerun()
    else:
        # Unlock logic for Host
        h_input = st.text_input("Enter Admin Password to Unlock Panel", type="password")
        if st.button("Unlock Admin Panel"):
            if h_input == saved_admin_key: 
                st.session_state.is_host = True
            else: 
                st.error("Access Denied")

    # SECURE ADMIN TOOLS (Only visible after password)
    if st.session_state.get('is_host'):
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔒 Admin Controls")
        
        # RESET BUTTON IS HIDDEN HERE
        if st.sidebar.button("🚨 EMERGENCY FULL RESET"):
            for f in [DATA_FILE, CONFIG_FILE, EXCESS_FILE]:
                if os.path.exists(f): os.remove(f)
            st.session_state.clear()
            st.rerun()

        if not os.path.exists(DATA_FILE):
            st.subheader("Setup New Session")
            session_code = st.text_input("Auditor Session Code", "1234")
            file_main = st.file_uploader("Upload Master Stock", type=['xlsx', 'csv'])
            
            if file_main:
                df_raw = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                df_prep = df_raw.copy()
                
                # Column mapping logic
                df_prep['Item No.'] = df_raw.iloc[:, 3]
                df_prep['Brand'] = df_raw.iloc[:, 8]
                df_prep['Category'] = df_raw.iloc[:, 12]
                
                # CATEGORY FILTERING RESTORED
                unique_cats = sorted(df_prep['Category'].dropna().unique().tolist())
                selected_cats = st.multiselect("Select Categories to Audit", unique_cats)
                
                if st.button("Launch Audit Session 🚀"):
                    if selected_cats and session_code:
                        df_filtered = df_prep[df_prep['Category'].isin(selected_cats)].copy()
                        df_filtered['Audit_Status'] = "Pending"
                        df_filtered['Scanned_By'] = ""
                        df_filtered['Matched_On'] = ""
                        save_data(df_filtered)
                        save_data(pd.DataFrame(columns=df_filtered.columns), EXCESS_FILE)
                        config["session_key"] = session_code
                        with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                        st.rerun()
        else:
            df = load_data()
            df_excess = load_data(EXCESS_FILE)
            st.metric("Total Items to Find", len(df[df['Audit_Status'] == "Pending"]))
            
            # Export Report
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df[df['Audit_Status'] == "✅ Scanned"].to_excel(writer, sheet_name='Scanned', index=False)
                df[df['Audit_Status'] == "Pending"].to_excel(writer, sheet_name='Shortages', index=False)
                df_excess.to_excel(writer, sheet_name='Excess', index=False)
            st.download_button("📥 Download Final Audit Report", buffer.getvalue(), "Audit_Report.xlsx")

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Auditor Station")
    if not os.path.exists(DATA_FILE):
        st.warning("No active audit session found.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        # AUDITOR LOGIN (Data remains hidden until code is entered)
        if not st.session_state.get('is_auditor'):
            a_name = st.text_input("Auditor Name")
            a_code = st.text_input("Session Code", type="password")
            if st.button("Login to Audit"):
                if a_name and a_code == config.get('session_key'):
                    st.session_state.is_auditor = True
                    st.session_state.auditor_name = a_name
                    st.rerun()
                else:
                    st.error("Invalid Code or Name")
        else:
            # DATA LOADS ONLY AFTER LOGIN
            df_audit = load_data()
            df_excess = load_data(EXCESS_FILE)

            st.write(f"Active Session: **{st.session_state.auditor_name}**")
            
            unique_brands = sorted(df_audit['Brand'].unique().tolist())
            sel_brand = st.selectbox("Brand Filter:", ["All"] + unique_brands)
            view_df = df_audit[df_audit['Audit_Status'] == "Pending"]
            if sel_brand != "All": view_df = view_df[view_df['Brand'] == sel_brand]
            
            st.subheader(f"Items Pending ({len(view_df)})")
            st.dataframe(view_df[['Item No.', 'Serial No', 'Product', 'Brand']], width="stretch")

            tab1, tab2 = st.tabs(["⌨️ Manual Entry", "📷 Camera"])
            scanned_val = ""
            
            with tab1:
                # INSTANT FETCH: Form allows 'Enter' key to process immediately
                with st.form("scanner_input", clear_on_submit=True):
                    scanned_val = st.text_input("Scan/Type Barcode")
                    if not st.form_submit_button("Submit Scan"): scanned_val = ""

            with tab2: 
                if HAS_SCANNER:
                    # CAMERA FIX: Removed 'facing' and prevented object-logging errors
                    camera_data = camera_input_live(show_controls=True)
                    if camera_data is not None and isinstance(camera_data, str):
                        scanned_val = camera_data
                else:
                    st.error("Scanner not compatible with this device.")

            # PROCESSING LOGIC (Moves data instantly)
            if scanned_val and isinstance(scanned_val, str):
                val = str(scanned_val).strip().upper()
                
                m_ser = df_audit[df_audit['Serial No'].astype(str).str.upper() == val]
                m_item = df_audit[df_audit['Item No.'].astype(str).str.upper() == val]
                target, m_type = (m_ser, "Serial No") if not m_ser.empty else (m_item, "Item No.") if not m_item.empty else (pd.DataFrame(), "")

                if not target.empty:
                    idx = target.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.warning(f"Item previously scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        df_audit.at[idx, 'Matched_On'] = m_type
                        save_data(df_audit)
                        st.success(f"Match Found: {val}")
                        st.rerun() # Forces the list to update instantly
                else:
                    # Log to Excess if not found in list
                    if val not in df_excess['Serial No'].values:
                        new_ex = pd.DataFrame([{"Product": "Excess", "Serial No": val, "Scanned_By": st.session_state.auditor_name, "Audit_Status": "EXCESS"}])
                        df_excess = pd.concat([df_excess, new_ex], ignore_index=True)
                        save_data(df_excess, EXCESS_FILE)
                        st.error(f"Excess Logged: {val}")
                    else:
                        st.info("Barcode already logged in Excess list.")
