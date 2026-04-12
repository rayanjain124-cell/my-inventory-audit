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

# --- SIDEBAR ROLE SELECTION ---
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

    if not saved_admin_key:
        st.subheader("Initial Admin Setup")
        new_key = st.text_input("Create Master Admin Password", type="password")
        if st.button("Save Admin Password"):
            if new_key:
                config["admin_key"] = new_key
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.rerun()
    else:
        h_input = st.text_input("Enter Admin Password to Unlock", type="password")
        if st.button("Unlock Admin Panel"):
            if h_input == saved_admin_key: 
                st.session_state.is_host = True
            else: 
                st.error("Access Denied")

    if st.session_state.get('is_host'):
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔒 Admin Controls")
        if st.sidebar.button("🚨 EMERGENCY FULL RESET"):
            for f in [DATA_FILE, CONFIG_FILE, EXCESS_FILE]:
                if os.path.exists(f): os.remove(f)
            st.session_state.clear()
            st.rerun()

        if not os.path.exists(DATA_FILE):
            st.subheader("Setup New Session")
            session_code = st.text_input("Auditor Session Code", "1234")
            file_main = st.file_uploader("Upload Master Stock", type=['xlsx', 'csv'])
            if file_main and st.button("Launch Audit Session 🚀"):
                df_raw = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
                df_main = df_raw.copy()
                df_main['Item No.'] = df_raw.iloc[:, 3]
                df_main['Brand'] = df_raw.iloc[:, 8]
                df_main['Category'] = df_raw.iloc[:, 12]
                
                df_main['Audit_Status'] = "Pending"
                df_main['Scanned_By'] = ""
                df_main['Matched_On'] = ""
                save_data(df_main)
                save_data(pd.DataFrame(columns=df_main.columns), EXCESS_FILE)
                config["session_key"] = session_code
                with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
                st.rerun()
        else:
            df = load_data()
            df_excess = load_data(EXCESS_FILE)
            st.metric("Total Items to Find", len(df[df['Audit_Status'] == "Pending"]))
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df[df['Audit_Status'] == "✅ Scanned"].to_excel(writer, sheet_name='Scanned', index=False)
                df[df['Audit_Status'] == "Pending"].to_excel(writer, sheet_name='Shortages', index=False)
                df_excess.to_excel(writer, sheet_name='Excess', index=False)
            st.download_button("📥 Download Final Detailed Report", buffer.getvalue(), "Audit_Report.xlsx")

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Auditor Station")
    if not os.path.exists(DATA_FILE):
        st.warning("Audit session not active.")
    else:
        with open(CONFIG_FILE, 'r') as f: config = json.load(f)
        
        # Only show login - Hide data completely until successful login
        if not st.session_state.get('is_auditor'):
            a_name = st.text_input("Your Name")
            a_code = st.text_input("Session Code", type="password")
            if st.button("Enter Audit Session"):
                if a_name and a_code == config.get('session_key'):
                    st.session_state.is_auditor = True
                    st.session_state.auditor_name = a_name
                    st.rerun()
                else:
                    st.error("Invalid Code or Name")
        
        # Data is only loaded and shown AFTER login
        else:
            df_audit = load_data()
            df_excess = load_data(EXCESS_FILE)

            st.write(f"Logged in as: **{st.session_state.auditor_name}**")
            
            unique_brands = sorted(df_audit['Brand'].unique().tolist())
            sel_brand = st.selectbox("Filter Missing Items by Brand:", ["All"] + unique_brands)
            
            view_df = df_audit[df_audit['Audit_Status'] == "Pending"]
            if sel_brand != "All": 
                view_df = view_df[view_df['Brand'] == sel_brand]
            
            st.subheader(f"Items to Find ({len(view_df)})")
            st.dataframe(view_df[['Item No.', 'Serial No', 'Product', 'Brand']], width="stretch")

            tab1, tab2 = st.tabs(["⌨️ Manual/Gun Entry", "📷 Camera Scanner"])
            scanned_val = ""
            
            with tab1:
                with st.form("manual_entry", clear_on_submit=True):
                    scanned_val = st.text_input("Scan/Type Barcode Here")
                    submit = st.form_submit_button("Submit Scan")
                    if not submit: scanned_val = ""

            with tab2: 
                if HAS_SCANNER:
                    st.info("Place barcode in front of camera")
                    scanned_val = camera_input_live(show_controls=True)
                else:
                    st.error("Camera not supported on this browser.")

            if scanned_val:
                val = str(scanned_val).strip().upper()
                # Search logic
                m_ser = df_audit[df_audit['Serial No'].astype(str).str.upper() == val]
                m_item = df_audit[df_audit['Item No.'].astype(str).str.upper() == val]
                
                target, m_type = (m_ser, "Serial No") if not m_ser.empty else (m_item, "Item No.") if not m_item.empty else (pd.DataFrame(), "")

                if not target.empty:
                    idx = target.index[0]
                    if df_audit.at[idx, 'Audit_Status'] == "✅ Scanned":
                        st.warning(f"Item already scanned by {df_audit.at[idx, 'Scanned_By']}")
                    else:
                        df_audit.at[idx, 'Audit_Status'] = "✅ Scanned"
                        df_audit.at[idx, 'Scanned_By'] = st.session_state.auditor_name
                        df_audit.at[idx, 'Matched_On'] = m_type
                        save_data(df_audit)
                        st.success(f"SUCCESS: Match found on {m_type}!")
                        st.rerun()
                else:
                    if val not in df_excess['Serial No'].values:
                        new_ex = pd.DataFrame([{"Product": "Excess", "Serial No": val, "Scanned_By": st.session_state.auditor_name, "Audit_Status": "EXCESS"}])
                        df_excess = pd.concat([df_excess, new_ex], ignore_index=True)
                        save_data(df_excess, EXCESS_FILE)
                        st.error(f"EXCESS: Barcode {val} not in master list. Logged to Excess.")
                    else:
                        st.info("Excess item already logged.")
