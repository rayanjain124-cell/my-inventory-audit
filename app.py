import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Serial Audit Pro", layout="wide")

if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("🛡️ Advanced Serial & Inventory Audit")

# Sidebar
st.sidebar.header("📁 Data Source")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# Dual Box Scanner
col_a, col_b = st.columns(2)
with col_a:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN BOX 1", key="input1", placeholder="Scan here...")
        if box1:
            st.session_state.scan_list.append(str(box1).strip())
            st.session_state.active_box = 2
            st.rerun()
with col_b:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN BOX 2", key="input2", placeholder="Scan here...")
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

        # 1. BUILD SYSTEM DICTIONARY (C=Name, D=Van, M=Cat, F=Serial, P=EAN, H=Qty)
        sys_info_map = {} # To get details
        all_system_serials = [] # To track missing units
        
        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            van = str(row.iloc[3]).strip()
            cat = str(row.iloc[12]).strip()
            serial = str(row.iloc[5]).strip()
            ean = str(row.iloc[15]).strip()
            
            # Store metadata
            sys_info_map[name] = {"Van": van, "Category": cat}
            
            # Record serials for the "Missing" check
            if serial != 'nan' and serial != "":
                all_system_serials.append({"Serial": serial, "Product": name})
            
            # Map EAN and Van to the Name for scanning
            sys_info_map[ean] = {"name": name, "type": "System"}
            sys_info_map[van] = {"name": name, "type": "System"}
            sys_info_map[serial] = {"name": name, "type": "System"}

        # 2. BUILD MASTER DICTIONARY (A=Van, D=Name, G=Cat)
        mst_info_map = {}
        for _, row in df_mst.iterrows():
            m_name = str(row.iloc[3]).strip() # Col D
            m_van = str(row.iloc[0]).strip()  # Col A
            m_cat = str(row.iloc[6]).strip()  # Col G
            
            # Map Master identifiers
            mst_info_map[m_van] = {"name": m_name, "cat": m_cat}
            # Also map EANs (Col B and C)
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan': mst_info_map[m_ean] = {"name": m_name, "cat": m_cat}

        # 3. PROCESS SCANS
        scanned_names = []
        scanned_serials = set()
        
        for code in st.session_state.scan_list:
            if code in sys_info_map:
                p_name = sys_info_map[code].get("name", sys_info_map[code])
                scanned_names.append(p_name)
                scanned_serials.add(code) # Track if the scanned code was a serial
            elif code in mst_info_map:
                scanned_names.append(mst_info_map[code]["name"])
            else:
                scanned_names.append(f"NEW: {code}")

        # 4. AUDIT TABLE
        phys_counts = pd.Series(scanned_names).value_counts().reset_index()
        phys_counts.columns = ['Product Name', 'Scanned Qty']

        sys_totals = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_totals.columns = ['Product Name', 'System Qty']

        final_audit = pd.merge(sys_totals, phys_counts, on='Product Name', how='outer').fillna(0)
        
        # Add Van and Category back to the table
        def get_extra_info(name, field):
            if name in sys_info_map and isinstance(sys_info_map[name], dict):
                return sys_info_map[name].get(field, "")
            return ""

        final_audit['Van No.'] = final_audit['Product Name'].apply(lambda x: get_extra_info(x, "Van"))
        final_audit['Category'] = final_audit['Product Name'].apply(lambda x: get_extra_info(x, "Category"))
        
        final_audit['Diff'] = final_audit['Scanned Qty'] - final_audit['System Qty']
        
        st.subheader("📊 Main Audit Report")
        st.dataframe(final_audit[['Van No.', 'Product Name', 'Category', 'System Qty', 'Scanned Qty', 'Diff']], use_container_width=True)

        # 5. MISSING SERIALS LOGIC
        st.divider()
        st.subheader("🔍 Missing Serial Numbers")
        missing_serials = [s for s in all_system_serials if s['Serial'] not in scanned_serials]
        
        if missing_serials:
            df_missing = pd.DataFrame(missing_serials)
            st.warning(f"The following {len(missing_serials)} serial numbers are in System but were NOT scanned:")
            st.table(df_missing)
        else:
            st.success("All system serial numbers have been scanned!")

    except Exception as e:
        st.error(f"Error: {e}")
