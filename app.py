import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Gun Scanner Audit", layout="wide")
st.title("🔫 Live Barcode Audit System")

# Initialize scan list in memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []

# Sidebar - Setup & Controls
st.sidebar.header("1. Setup Data")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet (Backup)", type=["xlsx"])

if st.sidebar.button("🗑️ Clear All Scans"):
    st.session_state.scan_list = []
    st.rerun()

# 2. Scanner Input Field
st.subheader("Ready to Scan")
# This text input is designed for the Barcode Gun
current_scan = st.text_input("Scan Barcode Here (Gun Scanner)", key="scanner_input", placeholder="Click here and start scanning...")

if current_scan:
    # Add scan to list if not empty
    st.session_state.scan_list.append(str(current_scan).strip())
    # Clear input for next scan immediately
    st.empty() 
    st.rerun()

# Display current scan count
st.write(f"**Total Items Scanned:** {len(st.session_state.scan_list)}")

if sys_file and mst_file:
    try:
        # Load Data
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)

        # Standardize Columns
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()

        # Build Logic Maps
        # Map 1: System Map (Highest Priority)
        sys_map = {}
        for _, row in df_sys.iterrows():
            name = str(row['Product']).strip()
            for col in ['ProductEAN', 'Item Number', 'Serial No']:
                if col in df_sys.columns and pd.notna(row[col]):
                    sys_map[str(row[col]).strip()] = name

        # Map 2: Master Map (Backup for new items)
        mst_map = {}
        for _, row in df_mst.iterrows():
            name = str(row['Product Name']).strip()
            for col in ['EAN No.-2025', 'VAN No.', 'EAN No.-2026']:
                if col in df_mst.columns and pd.notna(row[col]):
                    mst_map[str(row[col]).strip()] = name

        # Process Scans
        scan_data = []
        for barcode in st.session_state.scan_list:
            if barcode in sys_map:
                scan_data.append({'Name': sys_map[barcode], 'Source': 'System'})
            elif barcode in mst_map:
                scan_data.append({'Name': mst_map[barcode], 'Source': 'Master (Excess)'})
            else:
                scan_data.append({'Name': f"Unknown: {barcode}", 'Source': 'Not Found'})

        df_scanned = pd.DataFrame(scan_data)

        # --- AUDIT CALCULATIONS ---
        # 1. Summarize Physical Scans
        phys_counts = df_scanned.groupby('Name').size().reset_index(name='Physical_Qty')

        # 2. Summarize System Quantity (Sum the 'Quantity' column)
        sys_counts = df_sys.groupby('Product')['Quantity'].sum().reset_index()
        sys_counts.columns = ['Name', 'System_Qty']

        # 3. Merge Audit
        # Outer join ensures items in System show up even if not scanned (Shortage)
        # And items scanned but not in System show up (Excess)
        audit = pd.merge(sys_counts, phys_counts, on='Name', how='outer').fillna(0)
        
        audit['Difference'] = audit['Physical_Qty'] - audit['System_Qty']
        
        def get_status(diff):
            if diff == 0: return "Tally"
            return "Short" if diff < 0 else "Excess"
        
        audit['Status'] = audit['Difference'].apply(get_status)

        # Display Final Table
        st.subheader("Audit Report")
        st.dataframe(audit.sort_values('Difference'), use_container_width=True)

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            audit.to_excel(writer, index=False)
        st.download_button("📥 Download Final Audit Excel", output.getvalue(), "Audit_Report.xlsx")

    except Exception as e:
        st.error(f"Error processing files: {e}")
