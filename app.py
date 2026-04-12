import streamlit as st
import pandas as pd

st.set_page_config(page_title="Pro Audit System", layout="wide")

# --- DATA INITIALIZATION ---
if 'main_data' not in st.session_state:
    st.session_state.main_data = None
if 'transfer_data' not in st.session_state:
    st.session_state.transfer_data = None
if 'scanned_list' not in st.session_state:
    st.session_state.scanned_list = []
if 'audit_config' not in st.session_state:
    st.session_state.audit_config = {"mode": "Mixed", "key": "1234"}

st.title("📊 Inventory Audit Portal (v2.0)")

# --- SIDEBAR ROLE SELECTION ---
user_role = st.sidebar.radio("User Role", ["Host (Administrator)", "Auditor (Scanner)"])

# ---------------- HOST SECTION ----------------
if user_role == "Host (Administrator)":
    st.header("Admin Setup")
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.audit_config['key'] = st.text_input("Set Audit Access Code", st.session_state.audit_config['key'])
    with col2:
        audit_type = st.selectbox("Select Audit Category", 
                                ["Only Serial No. Item Audit", 
                                 "Only Non-Serial No. Audit", 
                                 "Mixed Combined Audit"])
        st.session_state.audit_config['mode'] = audit_type

    st.subheader("Data Upload")
    file_main = st.file_uploader("1. Upload Main Stock Excel (A-P Columns)", type=['xlsx', 'csv'])
    file_transfer = st.file_uploader("2. Upload Transfer Sheet (Optional)", type=['xlsx', 'csv'])

    if st.button("Start Audit Session"):
        if file_main:
            # Loading data
            df_m = pd.read_csv(file_main) if file_main.name.endswith('csv') else pd.read_excel(file_main)
            st.session_state.main_data = df_m
            
            if file_transfer:
                df_t = pd.read_csv(file_transfer) if file_transfer.name.endswith('csv') else pd.read_excel(file_transfer)
                st.session_state.transfer_data = df_t
            
            st.success("Audit Session Active! Give the code to your auditors.")
        else:
            st.error("Main Stock file is required to start.")

    if st.session_state.main_data is not None:
        st.divider()
        st.subheader("Host Operations")
        # Download data for Host
        final_csv = st.session_state.main_data.to_csv(index=False).encode('utf-8')
        st.download_button("Download Final Audit Data", final_csv, "final_audit_report.csv")

# ---------------- AUDITOR SECTION ----------------
else:
    st.header("Auditor Scanning")
    input_key = st.text_input("Enter Access Code", type="password")

    if input_key == st.session_state.audit_config['key']:
        if st.session_state.main_data is not None:
            st.success(f"Mode: {st.session_state.audit_config['mode']}")
            
            # SCANNING AREA
            scan_val = st.text_input("Scan Barcode or Serial Number")
            if st.button("Confirm Scan"):
                if scan_val:
                    st.session_state.scanned_list.append(scan_val)
                    st.toast(f"Scanned: {scan_val}")

            # SHOWING DATA TABS
            tab1, tab2, tab3 = st.tabs(["Stock List", "Scanned Items", "Excess/Discrepancy"])
            
            with tab1:
                # Filter display based on audit type
                display_df = st.session_state.main_data.copy()
                # Create a 'Status' column based on scanned list
                display_df['Audited'] = display_df['Serial No'].apply(lambda x: "✅ Yes" if str(x) in st.session_state.scanned_list else "❌ No")
                
                # Show specific columns from your A-P requirement
                cols_to_show = ['SNo', 'Product', 'Item Number', 'Bin', 'Serial No', 'Audited']
                st.dataframe(display_df[cols_to_show], use_container_width=True)

            with tab2:
                st.write("List of all items scanned in this session:")
                st.write(st.session_state.scanned_list)

            with tab3:
                st.write("Excess items (Scanned but not in Stock/Transfer sheets)")
                # Logic to find items in scanned_list NOT in main_data or transfer_data
                main_serials = set(st.session_state.main_data['Serial No'].astype(str))
                excess = [s for s in st.session_state.scanned_list if s not in main_serials]
                st.write(excess)
        else:
            st.warning("Wait for the Host to initialize the audit.")
    else:
        st.info("Please enter the correct access code.")
