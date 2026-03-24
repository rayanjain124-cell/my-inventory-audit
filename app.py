import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Pro Audit & Serial Tracker", layout="wide")

# 1. Initialize Memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit & Serial Tracker")

# 2. Sidebar
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Dual Box Scanner
c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN BOX 1", key="input1", placeholder="Ready...")
        if box1:
            st.session_state.scan_list.append(str(box1).strip())
            st.session_state.active_box = 2
            st.rerun()
with c2:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN BOX 2", key="input2", placeholder="Ready...")
        if box2:
            st.session_state.scan_list.append(str(box2).strip())
            st.session_state.active_box = 1
            st.rerun()

if sys_file and mst_file:
    try:
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # --- STEP 1: SMART MAPPING ---
        sys_id_map = {} # ID -> Product Name
        all_sys_serials = []
        sys_info_map = {} # Name -> {Van, Cat}

        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            serial = str(row.iloc[5]).strip()
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            sys_info_map[name] = {"Van": van, "Cat": cat}
            if serial != 'nan' and serial != "": 
                all_sys_serials.append(serial)
                sys_id_map[serial] = name
            
            sys_id_map[van] = name
            sys_id_map[ean] = name

        # Master Fallback
        mst_id_map = {}
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip()
            m_cat = str(row.iloc[6]).strip()
            m_data = {"name": m_name, "cat": m_cat, "van": m_van}
            mst_id_map[m_van] = m_data
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_id_map[m_ean] = m_data

        # --- STEP 2: PROCESS SCANS ---
        scan_log = []
        scanned_serials_only = []
        for code in st.session_state.scan_list:
            if code in sys_id_map:
                p_name = sys_id_map[code]
                is_serial = code if code in all_sys_serials else ""
                if is_serial: scanned_serials_only.append(code)
                scan_log.append({"Name": p_name, "Serial": is_serial, "Type": "In System"})
            elif code in mst_id_map:
                scan_log.append({"Name": mst_id_map[code]["name"], "Serial": "Out of Sys", "Type": "Excess out of Stock"})
            else:
                scan_log.append({"Name": f"Unknown: {code}", "Serial": "", "Type": "Unknown"})

        df_scan_log = pd.DataFrame(scan_log)

        # --- STEP 3: AUDIT CALCULATION ---
        # PHYSICAL COUNT
        phys_qty = df_scan_log.groupby('Name').size().reset_index(name='Scanned Qty')
        
        # SYSTEM QTY (SUM OF COLUMN H)
        sys_sums = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_sums.columns = ['Name', 'System Qty']

        audit = pd.merge(sys_sums, phys_qty, on='Name', how='outer').fillna(0)
        
        # Status Logic
        def get_status(row):
            if row['System Qty'] > 0 and row['Scanned Qty'] == 0: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] < row['System Qty']: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] == row['System Qty']: return "Tally"
            if row['System Qty'] > 0 and row['Scanned Qty'] > row['System Qty']: return "Excess"
            if row['System Qty'] == 0 and row['Scanned Qty'] > 0: return "Excess out of Stock"
            return "Unknown"

        audit['Status'] = audit.apply(get_status, axis=1)
        audit['Difference'] = audit['Scanned Qty'] - audit['System Qty']

        # Add Van/Cat back to audit table
        def get_meta(name, field):
            if name in sys_info_map: return sys_info_map[name].get(field, "")
            for v in mst_id_map.values():
                if v['name'] == name: return v.get(field.lower(), "")
            return ""

        audit['Van No.'] = audit['Name'].apply(lambda x: get_meta(x, "Van"))
        audit['Category'] = audit['Name'].apply(lambda x: get_meta(x, "Cat"))

        # --- STEP 4: DISPLAY ---
        # DASHBOARD
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Scanned", len(st.session_state.scan_list))
        m2.metric("Shortage", len(audit[audit['Status'] == "Short"]))
        m3.metric("Excess (Sys)", len(audit[audit['Status'] == "Excess"]))
        m4.metric("Out of Stock", len(audit[audit['Status'] == "Excess out of Stock"]))

        # TABLES
        tab1, tab2 = st.tabs(["📋 Main Stock Audit", "🔍 Serial Number Detail"])

        with tab1:
            st.subheader("Inventory Stock List")
            st.dataframe(audit[['Status', 'Van No.', 'Name', 'Category', 'System Qty', 'Scanned Qty', 'Difference']], use_container_width=True)

        with tab2:
            st.subheader("Serial Number Audit Table")
            # Show every scan with its serial number
            if not df_scan_log.empty:
                st.dataframe(df_scan_log[['Name', 'Serial', 'Type']], use_container_width=True)
            
            # Missing Serial Check
            missing = [s for s in all_sys_serials if s not in scanned_serials_only]
            if missing:
                st.warning("⚠️ Serials still in system (Not Scanned):")
                st.table(pd.DataFrame(missing, columns=["Missing Serial Numbers"]))

    except Exception as e:
        st.error(f"Error: {e}")
