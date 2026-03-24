import streamlit as st
import pandas as pd

st.set_page_config(page_title="Audit Pro - Multi-Box Dashboard", layout="wide")

# 1. Initialize Memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit (Sum Logic + Separate Excess)")

# 2. Sidebar
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Load Data & Build Logic
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

        # Mapping System (Product=Index 2, Serial=Index 5, EAN=Index 15, Van=Index 3)
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
            if van != 'nan' and van != "": sys_id_map[van] = name
            if ean != 'nan' and ean != "": sys_id_map[ean] = name

        # Mapping Master
        for _, row in df_mst.iterrows():
            m_van, m_ean1, m_ean2, m_name = str(row.iloc[0]), str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3])
            m_data = {"name": m_name, "cat": str(row.iloc[6]), "van": m_van}
            for k in [m_van, m_ean1, m_ean2]:
                if k != 'nan' and k != "": mst_id_map[k] = m_data

    except Exception as e:
        st.error(f"Setup Error: {e}")

# 4. Strict Scan Function
def handle_scan(val):
    val = str(val).strip()
    if not val: return
    
    # RULE: Serial (Col F) blocked after 1st scan. Others allowed.
    if val in all_sys_serials and val in st.session_state.scan_list:
        st.error(f"❌ SERIAL ALREADY SCANNED: {val}")
    else:
        st.session_state.scan_list.append(val)
        st.session_state.active_box = 2 if st.session_state.active_box == 1 else 1
        st.rerun()

# --- Input Area ---
c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        b1 = st.text_input("👇 SCAN BOX 1", key="in1")
        if b1: handle_scan(b1)
with c2:
    if st.session_state.active_box == 2:
        b2 = st.text_input("👇 SCAN BOX 2", key="in2")
        if b2: handle_scan(b2)

# 5. Dashboard & Sum-Linked Calculations
if sys_file and mst_file:
    # A. Process Log
    scan_log = []
    scanned_ser_only = []
    for code in st.session_state.scan_list:
        if code in sys_id_map:
            name = sys_id_map[code]
            is_ser = code if code in all_sys_serials else ""
            if is_ser: scanned_ser_only.append(code)
            scan_log.append({"Product Name": name, "Serial No.": is_ser, "Type": "In System"})
        elif code in mst_id_map:
            scan_log.append({"Product Name": mst_id_map[code]["name"], "Serial No.": "Barcode", "Type": "Excess Out of Stock"})
        else:
            scan_log.append({"Product Name": f"Unknown: {code}", "Serial No.": "", "Type": "Unknown"})

    df_log = pd.DataFrame(scan_log)

    # B. Calculations
    phys_qty = df_log.groupby('Product Name').size().reset_index(name='Scanned Qty')
    sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
    sys_qty.columns = ['Product Name', 'System Qty']
    
    audit = pd.merge(sys_qty, phys_qty, on='Product Name', how='outer').fillna(0)
    audit['Difference'] = audit['Scanned Qty'] - audit['System Qty']

    def calculate_status(row):
        if row['System Qty'] > 0 and row['Scanned Qty'] == 0: return "Short"
        if row['Difference'] < 0: return "Short"
        if row['Difference'] > 0 and row['System Qty'] > 0: return "Excess"
        if row['Difference'] > 0 and row['System Qty'] == 0: return "Excess Out of Stock"
        if row['Difference'] == 0: return "Tally"
        return "Unknown"

    audit['Status'] = audit.apply(calculate_status, axis=1)

    # C. 5-Box Dashboard Metrics
    st.divider()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("System Stock (Sum)", int(audit['System Qty'].sum()))
    m2.metric("Total Scanned", len(st.session_state.scan_list))
    m3.metric("Short Units", int(abs(audit[audit['Difference'] < 0]['Difference'].sum())))
    m4.metric("Excess (In-Stock)", int(audit[(audit['Difference'] > 0) & (audit['System Qty'] > 0)]['Difference'].sum()))
    m5.metric("Excess (Out-of-Stock)", int(audit[audit['Status'] == "Excess Out of Stock"]['Scanned Qty'].sum()))

    # D. Tables
    t1, t2 = st.tabs(["📋 Main Stock Audit", "🔍 Serial Number Detail"])
    with t1:
        st.dataframe(audit[['Status', 'Product Name', 'System Qty', 'Scanned Qty', 'Difference']], use_container_width=True)
    with t2:
        st.dataframe(df_log[['Product Name', 'Serial No.', 'Type']], use_container_width=True)
        missing = [s for s in all_sys_serials if s not in scanned_ser_only]
        if missing:
            with st.expander("🚨 VIEW MISSING SERIAL NUMBERS"):
                st.table(pd.DataFrame(missing, columns=["Serial Number"]))
