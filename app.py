import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Audit Pro - Multi-Download", layout="wide")

# 1. Initialize Memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Live Inventory Audit System")

# 2. Sidebar & File Upload
st.sidebar.header("1. Setup Data")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet (Backup)", type=["xlsx"])

if st.sidebar.button("🗑️ Clear All Scans"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Load Data & Build Logic
all_sys_serials = {} # Serial: Product Name
sys_info_map = {}    # Product Name: {Van, Cat}
sys_id_map = {}      # ID: Product Name
mst_id_map = {}      # ID: {Name, Cat, Van}

if sys_file and mst_file:
    try:
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # Build System Maps
        for _, row in df_sys.iterrows():
            p_name = str(row.iloc[2]).strip()
            v_no = str(row.iloc[3]).strip()
            s_no = str(row.iloc[5]).strip()
            c_name = str(row.iloc[12]).strip()
            e_no = str(row.iloc[15]).strip()
            
            sys_info_map[p_name] = {"Van": v_no, "Cat": c_name}
            
            if s_no != 'nan' and s_no != "": 
                all_sys_serials[s_no] = p_name
                sys_id_map[s_no] = p_name
            
            if v_no != 'nan': sys_id_map[v_no] = p_name
            if e_no != 'nan': sys_id_map[e_no] = p_name

        # Build Master Maps
        for _, row in df_mst.iterrows():
            m_v, m_n, m_c = str(row.iloc[0]), str(row.iloc[3]), str(row.iloc[6])
            m_d = {"name": m_n, "cat": m_c, "van": m_v}
            for k in [m_v, str(row.iloc[1]), str(row.iloc[2])]:
                if k != 'nan' and k != "": mst_id_map[k] = m_d
    except Exception as e:
        st.error(f"Error processing files: {e}")

# 4. Scan Input Area
st.subheader("Ready to Scan")
def handle_scan(val):
    val = str(val).strip()
    if not val: return
    if val in all_sys_serials and val in st.session_state.scan_list:
        st.error(f"❌ SERIAL ALREADY SCANNED: {val}")
    else:
        st.session_state.scan_list.append(val)
        st.session_state.active_box = 2 if st.session_state.active_box == 1 else 1
        st.rerun()

# Dynamic Input Boxes
c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        b1 = st.text_input("Scan Barcode Here (Gun Scanner)", key="in1", placeholder="Box 1 Active...")
        if b1: handle_scan(b1)
with c2:
    if st.session_state.active_box == 2:
        b2 = st.text_input("Scan Barcode Here (Gun Scanner)", key="in2", placeholder="Box 2 Active...")
        if b2: handle_scan(b2)

st.write(f"**Total Items Scanned:** {len(st.session_state.scan_list)}")

# 5. Dashboard & Reports
if sys_file and mst_file:
    # Build Scan History
    scan_log = []
    scanned_sers = []
    for code in st.session_state.scan_list:
        if code in sys_id_map:
            nm = sys_id_map[code]
            is_s = code if code in all_sys_serials else ""
            if is_s: scanned_sers.append(code)
            scan_log.append({"Product Name": nm, "Serial No.": is_s, "Type": "In System"})
        elif code in mst_id_map:
            scan_log.append({"Product Name": mst_id_map[code]["name"], "Serial No.": "Barcode", "Type": "Excess Out of Stock"})
        else:
            scan_log.append({"Product Name": f"Unknown: {code}", "Serial No.": "", "Type": "Unknown"})

    df_log = pd.DataFrame(scan_log)
    
    # Audit Table Calculations
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

    # Add Van and Category back for the display and export
    def add_meta(name, field):
        if name in sys_info_map: return sys_info_map[name].get(field, "")
        for v in mst_id_map.values():
            if v['name'] == name: return v.get(field.lower(), "")
        return ""
    
    audit['Van No.'] = audit['Product Name'].apply(lambda x: add_meta(x, "Van"))
    audit['Category'] = audit['Product Name'].apply(lambda x: add_meta(x, "Cat"))
    audit = audit[['Status', 'Van No.', 'Product Name', 'Category', 'System Qty', 'Scanned Qty', 'Difference']]

    # Prepare Missing Serials List
    missing_data = []
    for s, p in all_sys_serials.items():
        if s not in scanned_sers:
            missing_data.append({
                "Serial No.": s, 
                "Product Name": p,
                "Van No.": sys_info_map[p]["Van"],
                "Category": sys_info_map[p]["Cat"]
            })
    df_missing = pd.DataFrame(missing_data)

    # --- THE DOWNLOAD BUTTON (ALWAYS VISIBLE) ---
    st.divider()
    st.header("🏁 Finish & Download")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        audit.to_excel(writer, sheet_name='Final_Audit_Summary', index=False)
        df_log.to_excel(writer, sheet_name='Full_Scan_History', index=False)
        df_missing.to_excel(writer, sheet_name='Missing_Serials_Report', index=False)
    
    # This button has no limit - you can click it as many times as you want
    st.download_button(
        label="📥 CLICK TO DOWNLOAD ALL EXCEL REPORTS",
        data=buffer.getvalue(),
        file_name="Final_Inventory_Audit_Report.xlsx",
        mime="application/vnd.ms-excel",
        help="Click here to download the Summary, Scan Log, and Missing Serials in one file."
    )

    # Dashboard Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("System Qty Sum", int(audit['System Qty'].sum()))
    m2.metric("Total Scanned", len(st.session_state.scan_list))
    m3.metric("Short Units", int(abs(audit[audit['Difference'] < 0]['Difference'].sum())))
    m4.metric("Excess (In-Stock)", int(audit[(audit['Difference'] > 0) & (audit['System Qty'] > 0)]['Difference'].sum()))
    m5.metric("Excess (Out-of-Stock)", int(audit[audit['Status'] == "Excess Out of Stock"]['Scanned Qty'].sum()))

    # Detailed Tabs
    tab1, tab2 = st.tabs(["📋 Main Stock Audit", "🔍 Serial Tracking & Missing"])
    with tab1:
        st.dataframe(audit, use_container_width=True)
    with tab2:
        st.write("### Every Scan Log")
        st.dataframe(df_log, use_container_width=True)
        if not df_missing.empty:
            st.write("### 🚨 Missing Serials (Not Scanned)")
            st.dataframe(df_missing, use_container_width=True)
