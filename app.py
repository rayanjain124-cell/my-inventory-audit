import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Serial Level Audit", layout="wide")

if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit (Serial Number Tracking)")

# Sidebar
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# Dual Box Scanner
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
        # We now store Serial No as part of the identification
        sys_map = {} # ID -> {Name, Van, Cat, Serial}
        all_sys_serials = []

        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            ser = str(row.iloc[5]).strip()
            cat = str(row.iloc[12]).strip()
            ean = str(row.iloc[15]).strip()
            
            data = {"Name": name, "Van": van, "Cat": cat, "Serial": ser if ser != 'nan' else ""}
            
            if ser != 'nan' and ser != "": 
                all_sys_serials.append(ser)
                sys_map[ser] = data
            
            sys_map[van] = data
            sys_map[ean] = data

        # Master Fallback
        mst_map = {}
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip()
            m_cat = str(row.iloc[6]).strip()
            m_data = {"Name": m_name, "Van": m_van, "Cat": m_cat, "Serial": "N/A (Master)"}
            
            mst_map[m_van] = m_data
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_map[m_ean] = m_data

        # --- STEP 2: PROCESS SCANS ---
        scanned_data = []
        scanned_serials_only = []

        for code in st.session_state.scan_list:
            if code in sys_map:
                item = sys_map[code].copy()
                item['Type'] = "System"
                # If we scanned a serial, ensure that specific serial is noted
                if code in all_sys_serials:
                    item['Scanned_ID'] = code
                    scanned_serials_only.append(code)
                else:
                    item['Scanned_ID'] = "Barcode/Van"
                scanned_data.append(item)
            elif code in mst_map:
                item = mst_map[code].copy()
                item['Type'] = "Master (Excess)"
                item['Scanned_ID'] = code
                scanned_data.append(item)
            else:
                scanned_data.append({"Name": f"Unknown: {code}", "Van": "", "Cat": "", "Serial": "", "Type": "Unknown", "Scanned_ID": code})

        df_final_scans = pd.DataFrame(scanned_data)

        # --- STEP 3: DASHBOARD ---
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Scans Today", len(st.session_state.scan_list))
        
        # Calculate Short/Excess logic
        # Group by Name to compare quantities
        phys_qty = df_final_scans.groupby('Name').size().reset_index(name='Scanned Qty')
        sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_qty.columns = ['Name', 'System Qty']
        
        audit_summary = pd.merge(sys_qty, phys_qty, on='Name', how='outer').fillna(0)
        audit_summary['Diff'] = audit_summary['Scanned Qty'] - audit_summary['System Qty']

        m2.metric("Shortage Count", len(audit_summary[audit_summary['Diff'] < 0]))
        m3.metric("Excess Count", len(audit_summary[audit_summary['Diff'] > 0]))

        # --- STEP 4: DISPLAY TABLES ---
        st.subheader("📋 Detailed Scan Log (With Serial Numbers)")
        # Show exactly what was scanned row-by-row
        st.dataframe(df_final_scans[['Type', 'Van', 'Name', 'Serial', 'Scanned_ID', 'Cat']], use_container_width=True)

        # Missing Serials Expandable
        missing = [s for s in all_sys_serials if s not in scanned_serials_only]
        if missing:
            with st.expander("🚨 CLICK TO SEE MISSING SERIAL NUMBERS"):
                st.table(pd.DataFrame(missing, columns=["Serial Numbers Still in System (Not Scanned)"]))

    except Exception as e:
        st.error(f"Error: {e}")
