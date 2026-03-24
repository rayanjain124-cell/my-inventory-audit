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

# 3. Load Data & Create Serial Set for Validation
all_sys_serials = set()
sys_id_map = {}
sys_info_map = {}
mst_id_map = {}

if sys_file and mst_file:
    try:
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # Build System Lookups
        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            serial = str(row.iloc[5]).strip()
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            sys_info_map[name] = {"Van": van, "Cat": cat}
            
            if serial != 'nan' and serial != "": 
                all_sys_serials.add(serial)
                sys_id_map[serial] = name
            
            if van != 'nan': sys_id_map[van] = name
            if ean != 'nan': sys_id_map[ean] = name

        # Build Master Lookups
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip()
            m_cat = str(row.iloc[6]).strip()
            m_data = {"name": m_name, "cat": m_cat, "van": m_van}
            mst_id_map[m_van] = m_data
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_id_map[m_ean] = m_data

    except Exception as e:
        st.error(f"File Error: {e}")

# 4. Dual Box Scanner with Conditional Duplicate Check
def process_scan(val):
    val = str(val).strip()
    # RULE: If it's a System Serial, check for duplicates. Otherwise, allow multiples.
    if val in all_sys_serials and val in st.session_state.scan_list:
        st.error(f"❌ SERIAL ALREADY SCANNED: {val}")
    else:
        st.session_state.scan_list.append(val)
        st.session_state.active_box = 2 if st.session_state.active_box == 1 else 1
        st.rerun()

c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN BOX 1", key="input1", placeholder="Ready...")
        if box1: process_scan(box1)
with c2:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN BOX 2", key="input2", placeholder="Ready...")
        if box2: process_scan(box2)

# 5. Calculations & Display
if sys_file and mst_file:
    try:
        # Step A: Process Scan Log
        scan_log = []
        scanned_serials_only = []
        for code in st.session_state.scan_list:
            if code in sys_id_map:
                p_name = sys_id_map[code]
                is_serial = code if code in all_sys_serials else ""
                if is_serial: scanned_serials_only.append(code)
                scan_log.append({"Product Name": p_name, "Serial No.": is_serial, "Type": "In System"})
            elif code in mst_id_map:
                scan_log.append({"Product Name": mst_id_map[code]["name"], "Serial No.": "Non-Serial", "Type": "Excess out of Stock"})
            else:
                scan_log.append({"Product Name": f"Unknown: {code}", "Serial No.": "", "Type": "Not Found"})

        df_scan_log = pd.DataFrame(scan_log)

        # Step B: Main Audit (Summing Column H)
        phys_qty = df_scan_log.groupby('Product Name').size().reset_index(name='Scanned Qty')
        sys_sums = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_sums.columns = ['Product Name', 'System Qty']

        audit = pd.merge(sys_sums, phys_qty, on='Product Name', how='outer').fillna(0)
        
        # Status logic
        def get_status(row):
            if row['System Qty'] > 0 and row['Scanned Qty'] == 0: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] < row['System Qty']: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] == row['System Qty']: return "Tally"
            if row['System Qty'] > 0 and row['Scanned Qty'] > row['System Qty']: return "Excess"
            if row['System Qty'] == 0 and row['Scanned Qty'] > 0: return "Excess out of Stock"
            return "Unknown"

        audit['Status'] = audit.apply(get_status, axis=1)
        audit['Difference'] = audit['Scanned Qty'] - audit['System Qty']

        # Meta Data
        def get_meta(name, field):
            if name in sys_info_map: return sys_info_map[name].get(field, "")
            for v in mst_id_map.values():
                if v['name'] == name: return v.get(field.lower(), "")
            return ""

        audit['Van No.'] = audit['Product Name'].apply(lambda x: get_meta(x, "Van"))
        audit['Category'] = audit['Product Name'].apply(lambda x: get_meta(x, "Cat"))

        # Step C: UI Display
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Scanned", len(st.session_state.scan_list))
        m2.metric("Shortage", len(audit[audit['Status'] == "Short"]))
        m3.metric("Excess (Sys)", len(audit[audit['Status'] == "Excess"]))
        m4.metric("Out of Stock", len(audit[audit['Status'] == "Excess out of Stock"]))

        tab1, tab2 = st.tabs(["📋 Main Stock Audit", "🔍 Serial Number Detail"])

        with tab1:
            st.dataframe(audit[['Status', 'Van No.', 'Product Name', 'Category', 'System Qty', 'Scanned Qty', 'Difference']], use_container_width=True)

        with tab2:
            # Table exactly as per requested screenshot
            st.dataframe(df_scan_log[['Product Name', 'Serial No.', 'Type']], use_container_width=True)
            
            # Missing Serial section
            missing = [s for s in all_sys_serials if s not in scanned_serials_only]
            if missing:
                st.warning("⚠️ Serial Numbers Missing from Audit:")
                st.table(pd.DataFrame(missing, columns=["Missing Serials"]))

    except Exception as e:
        st.error(f"Audit Error: {e}")
