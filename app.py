import streamlit as st
import pandas as pd
import os
import json
import io

# Try-Except block to handle the missing library gracefully
try:
    from streamlit_barcode_reader import streamlit_barcode_reader 
except ImportError:
    st.error("Missing library! Please run: pip install streamlit-barcode-reader")

# --- CONFIG ---
DATA_FILE = "audit_state.csv"
CONFIG_FILE = "audit_config.json"
EXCESS_FILE = "excess_items.csv"
EMERGENCY_MASTER_KEY = "9619753319"

st.set_page_config(page_title="Audit Master Pro", layout="wide")

# --- ROBUST DATABASE HELPERS ---
def save_data(df, file=DATA_FILE): 
    # CRITICAL FIX: Force all tracking columns to be Strings to prevent the TypeError
    cols_to_fix = ['Audit_Status', 'Scanned_By', 'Matched_On', 'Item No.', 'Brand', 'Category']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "")
    df.to_csv(file, index=False)

def load_data(file=DATA_FILE): 
    if os.path.exists(file):
        df = pd.read_csv(file)
        # Ensure these exist and are text
        for col in ['Audit_Status', 'Scanned_By', 'Matched_On', 'Item No.', 'Brand', 'Category']:
            if col not in df.columns:
                df[col] = ""
            df[col] = df[col].fillna("").astype(str)
        return df
    return pd.DataFrame()

# --- SIDEBAR ---
st.sidebar.title("System Control")
if st.sidebar.button("🚨 Emergency Full Reset"):
    for f in [DATA_FILE, CONFIG_FILE, EXCESS_FILE]:
        if os.path.exists(f): os.remove(f)
    st.session_state.clear()
    st.rerun()

user_role = st.sidebar.radio("Select Role", ["Host (Admin)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Admin)":
    st.header("Host Administration")
    
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    
    saved_admin_key = config.get("admin_key")

    if not saved_admin_key:
        st.subheader("Initial System Setup")
        new_key = st.text_input("Create Your Secret Admin Key", type="password")
        if st.button("Save Admin Key & Proceed"):
            if new_key:
                config["admin_key"] = new_key
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.rerun()
    else:
        # Use 9619753319 here as seen in your screenshot
        h_input = st.text_input(f"Enter Master Host Code ({EMERGENCY_MASTER_KEY})", type="password")
        if st.button("Unlock Admin Panel ➔"):
            if h_input == saved_admin_key or h_input == EMERGENCY_MASTER_KEY:
                st.session_state.is_host = True
            else: st.error("Invalid Master Code")

    if st.session_state.get('is_host'):
        if not os.path.exists(DATA_FILE):
            st.subheader("Prepare Audit Sheet")
            session_code = st.text_input("Set Team Session Code (for auditors)", "1234")
            file_main = st.file_uploader("Upload Master Stock", type=['xlsx', 'csv'])
            
            if file_main:
                df_raw = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                df_main = df_raw.copy()
                # Mapping D, I, M columns
                df_main['Item No.'] = df_raw.iloc[:, 3]
                df_main['Brand'] = df_raw.iloc[:, 8]
                df_main['Category'] = df_raw.iloc[:, 12]
                
                unique_cats = sorted(df_main['Category'].dropna().unique().tolist())
                selected_cats = st.multiselect("Select Categories:", unique_cats)
                
                if st.button("Start Audit Session 🚀"):
                    if selected_cats:
                        df_filtered = df_main[df_main['Category'].isin(selected_cats)].copy()
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
            
            st.subheader("Live Stats")
            c1, c2, c3 = st.columns(3)
            c1.metric("Shortage", len(df[df['Audit_Status'] == "Pending"]))
            c2.metric("Scanned", len(df[df['Audit_Status'] == "✅ Scanned"]))
            c3.metric("Excess", len(df_excess))

            report_cols = ['Product', 'Item No.', 'Brand', 'Category', 'Serial No', 'Matched_On', 'Scanned_By']
            
            st.subheader("Final Precision Export")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df[df['Audit_Status'] == "✅ Scanned"][report_cols].to_excel(writer, sheet_name='Scanned', index=False)
                df[df['Audit_Status'] == "Pending"][report_cols].to_excel(writer, sheet_name='Shortages', index=False)
                df_excess.to_excel(writer, sheet_name='Excess', index=False)
            
            st.download_button("📥 Download Final Precision Report (Excel)", buffer.getvalue(), "Audit_Report.xlsx")

            if st.button("🔥 Close Session"):
                if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
                st.rerun()

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Team Scanning Station")
    if not os.path.exists(DATA_FILE):
        st.warning("Waiting for Host setup...")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        a_name = st.text_input("Your Name")
        a_code = st.text_input("Session Code", type="password")
        
        if st.button("Join Audit ➔"):
            if a_name and a_code == config.get('session_key'):
                st.session_state.is_auditor = True
                st.session_state.auditor_name = a_name

        if st.session_state.get('is_auditor'):
            df_audit = load_data()
            df_excess = load_data(EXCESS_FILE)

            # BRAND FILTER
            unique_brands = sorted(df_audit['Brand'].unique().tolist())
            selected_brand = st.selectbox("Filter Brand:", ["All"] + unique_brands)
            
            view_df = df_audit[df_audit['Audit_Status'] == "Pending"]
            if selected_brand != "All": view_df = view_df[view_df['Brand'] == selected_brand]
            st.info(f"Items remaining: {len(view_df)}")

            tab1, tab2 = st.tabs(["⌨️ Manual/Gun", "📷 Camera"])
            scanned_code = ""
            with tab1: scanned_code = st.text_input("Scan Code", key="manual_scan")
            with tab2: 
                try:
                    scanned_code = streamlit_barcode_reader(key='barcode_reader')
                except:
                    st.error("Camera component failed to load.")

            if scanned_code:
                val = str(scanned_code).strip().upper()
                
                # Double-match logic
                m_serial = df_audit[df_audit['Serial No'].astype(str).str.upper() == val]
                # Column check: 'Item Number' was in previous versions, ensuring it matches your excel column
                m_item = pd.DataFrame()
                if 'Item Number' in df_audit.columns:
                    m_item = df_audit[df_audit['Item Number'].astype(str).str.upper() == val]
                
                target = pd.DataFrame()
                m_type = ""

                if not m_serial.empty:
                    target, m_type = m_serial, "Serial No"
                elif not m_item.empty:
                    target, m_type = m_item, "Item Number"

                if not target.empty:
                    idx = target.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.error(f"⚠️ Already scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        # SETTING VALUES
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = str(st.session_state.auditor_name)
                        df_audit.at[idx, 'Matched_On'] = m_type
                        save_data(df_audit)
                        st.success(f"MATCH ({m_type}): {df_audit.at[idx, 'Product']}")
                else:
                    new_ex = pd.DataFrame([{"Serial No": val, "Scanned_By": st.session_state.auditor_name, "Audit_Status": "EXCESS"}])
                    df_excess = pd.concat([df_excess, new_ex], ignore_index=True)
                    save_data(df_excess, EXCESS_FILE)
                    st.error(f"❌ EXCESS LOGGED.")

            st.dataframe(df_audit[['Product', 'Serial No', 'Matched_On', 'Scanned_By']].tail(5))
