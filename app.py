import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Audit Pro", layout="wide")

# 1. Initialize Session State
if 'scan_list' not in st.session_state:
    st.session_state.index_scans = [] # Using a list of dicts to keep order and details
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("🔫 Live Audit & Serial Tracker")

# 2. Sidebar & File Upload
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.index_scans = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Dual Box Scanner
c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN BOX 1", key="input1", placeholder="Ready...")
        if box1:
            st.session_state.index_scans.append(str(box1).strip())
            st.session_state.active_box = 2
            st.rerun()
with c2:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN BOX 2", key="input2", placeholder="Ready...")
        if box2:
            st.session_state.index_scans.append(str(box2).strip())
            st.session_state.active_box = 1
            st.rerun()

if sys_file and mst_file:
    try:
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # --- STEP 1: PREPARE MASTER DATA ---
        # System Map (C=Name, D=Van, F=Serial, M=Cat, P=EAN, H=Qty)
        sys_lookup = {}
        all_sys_serials = []
        
        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            ser = str(row.iloc[5]).strip()
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            item_info = {"Name": name, "Van": van, "Cat": cat, "System_Serial": ser if ser != 'nan' else ""}
            
            if ser != 'nan' and ser != "": all_sys_serials.append(ser)
            
            for key in [van, ser, ean]:
                if key != 'nan' and key != "": sys_lookup[key] = item_info

        # Master Map (A=Van, B=EAN25, C=EAN23/24, D=Name, G=Cat)
        mst_lookup = {}
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip()
            m_cat = str(row.iloc[6]).strip()
            
            m_info = {"Name": m_name, "Van": m_van, "Cat": m_cat, "System_Serial": "NOT IN SYSTEM"}
            
            for i in [0, 1, 2]: # Van and EANs
                key = str(row.iloc[i]).strip()
                if key != 'nan' and key != "": mst_lookup[key] = m_info

        # --- STEP 2: PROCESS LIVE SCANS ---
        processed_log = []
        scanned_serials = []
        
        for code in st.session_state.index_scans:
            if code in sys_lookup:
                entry = sys_lookup[code].copy()
                entry["Scanned_Code"] = code
                entry["Status"] = "In System"
                if code in all_sys_serials: scanned_serials.append(code)
                processed_log.append(entry)
            elif code in mst_lookup:
                entry = mst_lookup[code].copy()
                entry["Scanned_Code"] = code
                entry["Status"] = "Excess out of Stock"
                processed_log.append(entry)
            else:
                processed_log.append({"Name": "UNKNOWN", "Van": "N/A", "Cat": "N/A", "System_Serial": "N/A", "Scanned_Code": code, "Status": "Not Found"})

        df_log = pd.DataFrame(processed_log)

        # --- STEP 3: DASHBOARD METRICS ---
        st.divider()
        # Summary calculations for Dashboard
        phys_counts = df_log.groupby('Name').size().reset_index(name='Scanned_Qty')
        sys_counts = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_counts.columns = ['Name', 'System_Qty']
        
        comparison = pd.merge(sys_counts, phys_counts, on='Name', how='outer').fillna(0)
        comparison['Diff'] = comparison['Scanned_Qty'] - comparison['System_Qty']
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Scans", len(st.session_state.index_scans))
        m2.metric("Short Items", len(comparison[comparison['Diff'] < 0]))
        m3.metric("Excess (System)", len(comparison[(comparison['Diff'] > 0) & (comparison['System_Qty'] > 0)]))
        m4.metric("Excess (Out of Stock)", len(df_log[df_log['Status'] == "Excess out of Stock"]))

        # --- STEP 4: TABLES ---
        st.subheader("📋 Detailed Scan Log")
        # This table shows every scan with its Serial and Status
        if not df_log.empty:
            st.dataframe(df_log[['Status', 'Name', 'System_Serial', 'Scanned_Code', 'Van', 'Cat']], use_container_width=True)

        # Missing Serials
        missing_list = [s for s in all_sys_serials if s not in scanned_serials]
        if missing_list:
            with st.expander("🚨 VIEW MISSING SERIAL NUMBERS"):
                st.write(pd.DataFrame(missing_list, columns=["Serial Number"]))

    except Exception as e:
        st.error(f"Error processing audit: {e}")
