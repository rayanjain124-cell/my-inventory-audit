import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Audit Pro - Final Report", layout="wide")

# 1. Initialize Memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit & Excel Reporter")

# 2. Sidebar & File Upload
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Load Data & Build Maps
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

        for _, row in df_sys.iterrows():
            name, van, serial, ean = str(row.iloc[2]).strip(), str(row.iloc[3]).strip(), str(row.iloc[5]).strip(), str(row.iloc[15]).strip()
            sys_info_map[name] = {"Van": van, "Cat": str(row.iloc[12]).strip()}
            if serial != 'nan' and serial != "": 
                all_sys_serials.add(serial)
                sys_id_map[serial] = name
            if van != 'nan': sys_id_map[van] = name
            if ean != 'nan': sys_id_map[ean] = name

        for _, row in df_mst.iterrows():
            m_van, m_name = str(row.iloc[0]), str(row.iloc[3])
            m_data = {"name": m_name, "cat": str(row.iloc[6]), "van": m_van}
            for k in [m_van, str(row.iloc[1]), str(row.iloc[2])]:
                if k != 'nan': mst_id_map[k] = m_data
    except Exception as e:
        st.error(f"Setup Error: {e}")

# 4. Scanning Logic
def handle_scan(val):
    val = str(val).strip()
    if not val: return
    if val in all_sys_serials and val in st.session_state.scan_list:
        st.error(f"❌ SERIAL ALREADY SCANNED: {val}")
    else:
        st.session_state.scan_list.append(val)
        st.session_state.active_box = 2 if st.session_state.active_box == 1 else 1
        st.rerun()

c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        b1 = st.text_input("👇 SCAN BOX 1", key="in1")
        if b1: handle_scan(b1)
with c2:
    if st.session_state.active_box == 2:
        b2 = st.text_input("👇 SCAN BOX 2", key="in2")
        if b2: handle_scan(b2)

# 5. Dashboard & Export
if sys_file and mst_file:
    # Build Logs
    scan_log = []
    scanned_ser_only = []
    for code in st.session_state.scan_list:
        if code in sys_id_map:
            name = sys_id_map[code]
            is_ser = code if code in all_sys_serials else ""
            if is_ser: scanned_ser_only.append(code)
            scan_log.append({"Product Name": name, "Serial No.": is_ser, "Type": "In System"})
        elif code in mst_id_map:
            scan_log.append({"Product Name": mst_id_map[code]["name"], "Serial No.": "Barcode", "Type": "Out of Stock"})
        else:
            scan_log.append({"Product Name": f"Unknown: {code}", "Serial No.": "", "Type": "Unknown"})

    df_log = pd.DataFrame(scan_log)
    phys_qty = df_log.groupby('Product Name').size().reset_index(name='Scanned Qty')
    sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
    sys_qty.columns = ['Product Name', 'System Qty']
    
    audit = pd.merge(sys_qty, phys_qty, on='Product Name', how='outer').fillna(0)
    audit['Difference'] = audit['Scanned Qty'] - audit['System Qty']

    def get_status(row):
        if row['Difference'] < 0: return "Short"
        if row['Difference'] > 0 and row['System Qty'] > 0: return "Excess"
        if row['Difference'] > 0 and row['System Qty'] == 0: return "Excess Out of Stock"
        return "Tally"
    audit['Status'] = audit.apply(get_status, axis=1)

    # Sidebar Export Tool
    st.sidebar.divider()
    st.sidebar.header("📥 Export Audit")
    
    # Prep Missing Serials
    missing_list = [s for s in all_sys_serials if s not in scanned_ser_only]
    df_missing = pd.DataFrame(missing_list, columns=["Serial Numbers NOT Found"])

    # Excel Buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        audit.to_excel(writer, sheet_name='Audit_Summary', index=False)
        df_log.to_excel(writer, sheet_name='Every_Scan_Log', index=False)
        df_missing.to_excel(writer, sheet_name='Missing_Serials', index=False)
    
    st.sidebar.download_button(
        label="💾 Download Excel Report",
        data=buffer.getvalue(),
        file_name="Inventory_Audit_Report.xlsx",
        mime="application/vnd.ms-excel"
    )

    # UI Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sys Stock", int(audit['System Qty'].sum()))
    m2.metric("Scanned", len(st.session_state.scan_list))
    m3.metric("Short Units", int(abs(audit[audit['Difference'] < 0]['Difference'].sum())))
    m4.metric("Excess (In)", int(audit[(audit['Difference'] > 0) & (audit['System Qty'] > 0)]['Difference'].sum()))
    m5.metric("Excess (Out)", int(audit[audit['Status'] == "Excess Out of Stock"]['Scanned Qty'].sum()))

    t1, t2 = st.tabs(["📋 Audit Summary", "🔍 Serial Tracking"])
    with t1: st.dataframe(audit, use_container_width=True)
    with t2:
        st.dataframe(df_log, use_container_width=True)
        if missing_list:
            with st.expander("🚨 VIEW MISSING SERIALS"): st.table(df_missing)
