import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Audit Dashboard Pro", layout="wide")

# 1. Initialize Session State
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit Dashboard")

# 2. Sidebar & File Upload
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
        
        # Clean column names
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # --- STEP 1: MAPS ---
        # System Map (Key: ID -> Value: {Name, Van, Cat, Serial})
        sys_id_map = {}
        all_sys_serials = []
        sys_details_by_name = {}

        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            serial = str(row.iloc[5]).strip()
            qty = row.iloc[7] if pd.notna(row.iloc[7]) else 0
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            sys_details_by_name[name] = {"Van": van, "Cat": cat}
            if serial != 'nan' and serial != "": all_sys_serials.append(serial)
            
            for key in [van, serial, ean]:
                if key != 'nan' and key != "": sys_id_map[key] = name

        # Master Map (Fallback for Excess Out of System)
        mst_id_map = {}
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip() # Product Name in D
            m_cat = str(row.iloc[6]).strip()  # Category in G
            
            details = {"name": m_name, "cat": m_cat, "van": m_van}
            mst_id_map[m_van] = details
            for i in [1, 2]: # EANs in B and C
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_id_map[m_ean] = details

        # --- STEP 2: PROCESS SCANS ---
        scan_results = []
        scanned_serials = []
        for code in st.session_state.scan_list:
            if code in sys_id_map:
                name = sys_id_map[code]
                scan_results.append({"Name": name, "Type": "In System"})
                scanned_serials.append(code)
            elif code in mst_id_map:
                name = mst_id_map[code]["name"]
                scan_results.append({"Name": name, "Type": "Out of System"})
            else:
                scan_results.append({"Name": f"Unknown: {code}", "Type": "Unknown"})

        df_scans = pd.DataFrame(scan_results)

        # --- STEP 3: CALCULATE AUDIT ---
        phys_qty = df_scans.groupby('Name').size().reset_index(name='Scanned Qty')
        sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_qty.columns = ['Name', 'System Qty']

        audit = pd.merge(sys_qty, phys_qty, on='Name', how='outer').fillna(0)
        
        # Define Status
        def get_status(row):
            if row['System Qty'] > 0 and row['Scanned Qty'] == 0: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] < row['System Qty']: return "Short"
            if row['System Qty'] > 0 and row['Scanned Qty'] == row['System Qty']: return "Tally"
            if row['System Qty'] > 0 and row['Scanned Qty'] > row['System Qty']: return "Excess"
            if row['System Qty'] == 0 and row['Scanned Qty'] > 0: return "Excess out of Stock"
            return "Unknown"

        audit['Status'] = audit.apply(get_status, axis=1)
        audit['Difference'] = audit['Scanned Qty'] - audit['System Qty']

        # --- STEP 4: DASHBOARD METRICS ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Items Scanned", len(st.session_state.scan_list))
        m2.metric("Short Items", len(audit[audit['Status'] == "Short"]))
        m3.metric("Excess (In System)", len(audit[audit['Status'] == "Excess"]))
        m4.metric("Excess Out of Stock", len(audit[audit['Status'] == "Excess out of Stock"]))

        # --- STEP 5: FINAL DISPLAY ---
        st.subheader("📋 Audit Table")
        # Add metadata (Van/Cat) back
        def add_meta(name, field):
            if name in sys_details_by_name: return sys_details_by_name[name].get(field, "")
            # If not in system, check master
            for key, val in mst_id_map.items():
                if val['name'] == name: return val.get(field.lower(), "")
            return ""

        audit['Van No.'] = audit['Name'].apply(lambda x: add_meta(x, "Van"))
        audit['Category'] = audit['Name'].apply(lambda x: add_meta(x, "Cat"))

        st.dataframe(audit[['Status', 'Van No.', 'Name', 'Category', 'System Qty', 'Scanned Qty', 'Difference']], use_container_width=True)

        # Missing Serials Section
        missing = [s for s in all_sys_serials if s not in scanned_serials]
        if missing:
            with st.expander("🚨 VIEW MISSING SERIAL NUMBERS"):
                st.write(pd.DataFrame(missing, columns=["Missing Serial Numbers"]))

    except Exception as e:
        st.error(f"Error: {e}")
