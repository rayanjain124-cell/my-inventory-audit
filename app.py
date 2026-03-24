import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Audit Pro", layout="wide")

# 1. Initialize Session State
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit & Serial Tracker")

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
        
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # --- STEP 1: MAPS ---
        sys_id_map = {}
        all_sys_serials = []
        sys_details_by_name = {}

        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            serial = str(row.iloc[5]).strip()
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            sys_details_by_name[name] = {"Van": van, "Cat": cat}
            if serial != 'nan' and serial != "": all_sys_serials.append(serial)
            
            for key in [van, serial, ean]:
                if key != 'nan' and key != "": sys_id_map[key] = name

        mst_id_map = {}
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip() 
            m_cat = str(row.iloc[6]).strip()
            details = {"name": m_name, "cat": m_cat, "van": m_van}
            mst_id_map[m_van] = details
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_id_map[m_ean] = details

        # --- STEP 2: PROCESS SCANS ---
        scanned_details = []
        scanned_serials_list = []
        for code in st.session_state.scan_list:
            if code in sys_id_map:
                name = sys_id_map[code]
                # Check if the code scanned was actually a serial number
                found_serial = code if code in all_sys_serials else ""
                if found_serial: scanned_serials_list.append(found_serial)
                scanned_details.append({"Name": name, "Scanned Serial": found_serial})
            elif code in mst_id_map:
                name = mst_id_map[code]["name"]
                scanned_details.append({"Name": name, "Scanned Serial": "Out of Sys"})
            else:
                scanned_details.append({"Name": f"Unknown: {code}", "Scanned Serial": ""})

        df_scans = pd.DataFrame(scanned_details)

        # --- STEP 3: CALCULATE AUDIT ---
        # Group by Name but also collect the serial numbers scanned for that name
        phys_qty = df_scans.groupby('Name').agg({
            'Name': 'size',
            'Scanned Serial': lambda x: ', '.join([s for s in x if s and s != "Out of Sys"])
        }).rename(columns={'Name': 'Scanned Qty'}).reset_index()

        sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_qty.columns = ['Name', 'System Qty']

        audit = pd.merge(sys_qty, phys_qty, on='Name', how='outer').fillna(0)
        
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
        st.subheader("📋 Audit Table (Serial Numbers Included)")
        
        def add_meta(name, field):
            if name in sys_details_by_name: return sys_details_by_name[name].get(field, "")
            for val in mst_id_map.values():
                if val['name'] == name: return val.get(field.lower(), "")
            return ""

        audit['Van No.'] = audit['Name'].apply(lambda x: add_meta(x, "Van"))
        audit['Category'] = audit['Name'].apply(lambda x: add_meta(x, "Cat"))

        # Reordering columns to show Status first and Serial Numbers near Name
        display_cols = ['Status', 'Van No.', 'Name', 'Scanned Serial', 'Category', 'System Qty', 'Scanned Qty', 'Difference']
        st.dataframe(audit[display_cols], use_container_width=True)

        # Missing Serials Section
        missing = [s for s in all_sys_serials if s not in scanned_serials_list]
        if missing:
            with st.expander("🚨 VIEW MISSING SERIAL NUMBERS"):
                st.write(pd.DataFrame(missing, columns=["Serial Numbers NOT Scanned"]))

    except Exception as e:
        st.error(f"Error: {e}")
