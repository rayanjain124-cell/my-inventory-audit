import streamlit as st
import pandas as pd
import cv2
import numpy as np
from PIL import Image

st.set_page_config(page_title="Pro Audit & Mobile Scanner", layout="wide")

# 1. Initialize Session State
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1

st.title("📊 Inventory Audit & Mobile Barcode Tracker")

# 2. Sidebar & File Upload
st.sidebar.header("📁 Data Sources")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Reset Audit"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Process Data & Build Lookups
all_sys_serials = set()
sys_id_map = {}
sys_info_map = {}
mst_id_map = {}
total_system_stock_sum = 0

if sys_file and mst_file:
    try:
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # Calculate Total System Stock (Sum of Column H / Index 7)
        total_system_stock_sum = df_sys[df_sys.columns[7]].sum()

        # Build System Lookups (Product=Index 2, Serial=Index 5, EAN=Index 15, Van=Index 3)
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

        # Build Master Lookups (A=Van, B/C=EAN, D=Name, G=Cat)
        for _, row in df_mst.iterrows():
            m_van = str(row.iloc[0]).strip()
            m_name = str(row.iloc[3]).strip()
            m_cat = str(row.iloc[6]).strip()
            m_data = {"name": m_name, "cat": m_cat, "van": m_van}
            
            mst_id_map[m_van] = m_data
            for i in [1, 2]:
                m_ean = str(row.iloc[i]).strip()
                if m_ean != 'nan' and m_ean != "": mst_id_map[m_ean] = m_data

    except Exception as e:
        st.error(f"Error Loading Files: {e}")

# 4. Scanning Logic
def process_scan(val):
    val = str(val).strip()
    if not val: return
    
    # STRICT RULE: Only Serial Numbers (from Col F) are blocked for duplicates
    if val in all_sys_serials and val in st.session_state.scan_list:
        st.error(f"❌ SERIAL ALREADY SCANNED: {val}")
    else:
        st.session_state.scan_list.append(val)
        # Toggle between Box 1 and Box 2
        st.session_state.active_box = 2 if st.session_state.active_box == 1 else 1
        st.rerun()

# --- Display Inputs ---
st.subheader("⌨️ Barcode / Serial Input")
c1, c2 = st.columns(2)
with c1:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN BOX 1", key="input1", placeholder="Type or Scan here...")
        if box1: process_scan(box1)
with c2:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN BOX 2", key="input2", placeholder="Type or Scan here...")
        if box2: process_scan(box2)

# --- Mobile Camera Scan ---
st.subheader("📸 Mobile Camera Scan")
cam_image = st.camera_input("Scan Barcode with Camera")
if cam_image:
    img = Image.open(cam_image)
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    detector = cv2.barcode.BarcodeDetector()
    retval, decoded_info, decoded_type, points = detector.detectAndDecode(img_cv)
    if retval:
        scanned_code = decoded_info[0]
        st.success(f"Detected: {scanned_code}")
        process_scan(scanned_code)
    else:
        st.warning("No barcode detected. Please try holding the camera closer or steadier.")

# 5. Dashboard and Calculations
if sys_file and mst_file:
    try:
        # Generate Log
        scan_log_data = []
        scanned_serials_only = []
        for code in st.session_state.scan_list:
            if code in sys_id_map:
                name = sys_id_map[code]
                is_ser = code if code in all_sys_serials else ""
                if is_ser: scanned_serials_only.append(code)
                scan_log_data.append({"Product Name": name, "Serial No.": is_ser, "Type": "In System"})
            elif code in mst_id_map:
                scan_log_data.append({"Product Name": mst_id_map[code]["name"], "Serial No.": "Out of Sys", "Type": "Excess out of Stock"})
            else:
                scan_log_data.append({"Product Name": f"Unknown: {code}", "Serial No.": "", "Type": "Not Found"})

        df_scan_log = pd.DataFrame(scan_log_data)

        # Audit Calculation (SUM Qty)
        phys_qty = df_scan_log.groupby('Product Name').size().reset_index(name='Scanned Qty')
        sys_sums = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_sums.columns = ['Product Name', 'System Qty']

        audit = pd.merge(sys_sums, phys_qty, on='Product Name', how='outer').fillna(0)
        
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

        # Add Metadata
        def get_meta(name, field):
            if name in sys_info_map: return sys_info_map[name].get(field, "")
            for v in mst_id_map.values():
                if v['name'] == name: return v.get(field.lower(), "")
            return ""

        audit['Van No.'] = audit['Product Name'].apply(lambda x: get_meta(x, "Van"))
        audit['Category'] = audit['Product Name'].apply(lambda x: get_meta(x, "Cat"))

        # --- DISPLAY RESULTS ---
        st.divider()
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total System Stock (H Sum)", int(total_system_stock_sum))
        d2.metric("Total Scanned Today", len(st.session_state.scan_list))
        d3.metric("Shortage Count", len(audit[audit['Difference'] < 0]))
        d4.metric("Excess Out of Stock", len(audit[audit['Status'] == "Excess out of Stock"]))

        tab1, tab2 = st.tabs(["📋 Main Audit Table", "🔍 Serial Detail (Screenshot Style)"])

        with tab1:
            st.subheader("Inventory Stock Comparison")
            st.dataframe(audit[['Status', 'Van No.', 'Product Name', 'Category', 'System Qty', 'Scanned Qty', 'Difference']], use_container_width=True)

        with tab2:
            st.subheader("Serial Tracking Table")
            # Same structure as your requested screenshot
            st.dataframe(df_scan_log[['Product Name', 'Serial No.', 'Type']], use_container_width=True)
            
            missing = [s for s in all_sys_serials if s not in scanned_serials_only]
            if missing:
                with st.expander("🚨 VIEW MISSING SERIAL NUMBERS"):
                    st.table(pd.DataFrame(missing, columns=["Serial Number"]))

    except Exception as e:
        st.error(f"Audit processing error: {e}")
