import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Custom Inventory Audit", layout="wide")
st.title("📦 System-First Audit (Gun Scanner Ready)")

# Initialize session state for scans
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []

# Sidebar for file uploads
st.sidebar.header("1. Upload Data")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Clear Scans"):
    st.session_state.scan_list = []
    st.rerun()

# 2. Scanner Input (Manual or Gun)
st.subheader("Scan or Type Barcode")
current_scan = st.text_input("Input Barcode", key="scanner_box", placeholder="Scan here...")

if current_scan:
    st.session_state.scan_list.append(str(current_scan).strip())
    st.rerun()

st.write(f"**Items Scanned:** {len(st.session_state.scan_list)}")

if sys_file and mst_file:
    try:
        # Load sheets (No headers used, we use indices for accuracy)
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)

        # Build the System Map (Higher Priority)
        # C=Name(2), D=Van(3), F=Serial(5), H=Qty(7), M=Cat(12), P=EAN(15)
        sys_map = {}
        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip() # Column C
            for idx in [3, 5, 15]: # Columns D, F, P
                val = str(row.iloc[idx]).strip()
                if val != 'nan':
                    sys_map[val] = {"name": name, "cat": str(row.iloc[12])}

        # Build the Master Map (Backup)
        mst_map = {}
        for _, row in df_mst.iterrows():
            # Adjust these indices if Master Sheet differs
            name = str(row.iloc[4]).strip() # Product Name
            for idx in [0, 1, 3]: # VAN No, EAN 2025, EAN 2026
                val = str(row.iloc[idx]).strip()
                if val != 'nan':
                    mst_map[val] = {"name": name, "cat": str(row.iloc[6])}

        # Process Scans
        found_scans = []
        for code in st.session_state.scan_list:
            if code in sys_map:
                found_scans.append(sys_map[code]['name'])
            elif code in mst_map:
                found_scans.append(mst_map[code]['name'])
            else:
                found_scans.append(f"NOT FOUND: {code}")

        # Summary Math
        df_phys = pd.Series(found_scans).value_counts().reset_index()
        df_phys.columns = ['Product Name', 'Physical Count']

        # System Quantity Sum (Column C and H)
        df_sys_qty = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        df_sys_qty.columns = ['Product Name', 'System Qty']

        # Final Merge
        audit = pd.merge(df_sys_qty, df_phys, on='Product Name', how='outer').fillna(0)
        audit['Difference'] = audit['Physical Count'] - audit['System Qty']
        
        def status_check(diff):
            if diff == 0: return "Tally"
            return "Short" if diff < 0 else "Excess"
        
        audit['Status'] = audit['Difference'].apply(status_check)

        # Display Result
        st.subheader("Audit Report")
        st.dataframe(audit.sort_values('Difference'), use_container_width=True)

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            audit.to_excel(writer, index=False)
        st.download_button("📥 Download Excel Report", output.getvalue(), "Audit_Report.xlsx")

    except Exception as e:
        st.error(f"Mapping Error: {e}. Check if column counts match.")
