import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Exact Name Inventory Audit", layout="wide")
st.title("📦 Smart Audit: Exact Product Mapping")

# 1. Upload Section
col1, col2, col3 = st.columns(3)
with col1:
    sys_file = st.file_uploader("Upload 'System' Sheet", type=["xlsx"])
with col2:
    mst_file = st.file_uploader("Upload 'Master_Sheet'", type=["xlsx"])
with col3:
    scn_file = st.file_uploader("Upload 'Scan' Sheet", type=["xlsx"])

if sys_file and mst_file and scn_file:
    try:
        # Load Data
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)
        df_scn = pd.read_excel(scn_file)

        # Standardize Columns (Remove hidden spaces)
        df_sys.columns = df_sys.columns.str.strip()
        df_mst.columns = df_mst.columns.str.strip()
        df_scn.columns = df_scn.columns.str.strip()

        # --- STEP 1: CREATE THE "EXACT NAME" MASTER DICTIONARY ---
        # This acts like your VLOOKUP Waterfall
        ean_to_name = {}

        # Fill from Master Sheet
        for _, row in df_mst.iterrows():
            name = str(row['Product Name']).strip()
            # Try all EAN/VAN columns from your Master Sheet
            for col in ['EAN No.-2025', 'EAN No.-2023,24,25', 'EAN No.-2026', 'VAN No.']:
                if col in df_mst.columns and pd.notna(row[col]):
                    ean_to_name[str(row[col]).strip()] = name

        # Fill/Backup from System Sheet (Serial No and ProductEAN)
        for _, row in df_sys.iterrows():
            name = str(row['Product']).strip()
            for col in ['Serial No', 'ProductEAN', 'Item Number']:
                if col in df_sys.columns and pd.notna(row[col]):
                    val = str(row[col]).strip()
                    if val not in ean_to_name: # Don't overwrite Master Sheet names
                        ean_to_name[val] = name

        # --- STEP 2: IDENTIFY SCANNED ITEMS ---
        # Look at 'Scan_Here' column in your Scan sheet
        scan_col = 'Scan_Here' if 'Scan_Here' in df_scn.columns else df_scn.columns[0]
        df_scn['Clean_Scan'] = df_scn[scan_col].astype(str).str.strip()
        
        # Map to the Exact Name
        df_scn['Exact Product Name'] = df_scn['Clean_Scan'].map(ean_to_name).fillna("UNKNOWN SCAN: " + df_scn['Clean_Scan'])

        # --- STEP 3: CALCULATE TOTALS ---
        # Physical Count (How many times each Exact Name was scanned)
        phys_summary = df_scn.groupby('Exact Product Name').size().reset_index(name='Physical_Scan_Qty')

        # System Count (Sum of 'Quantity' column in System sheet)
        sys_summary = df_sys.groupby('Product')['Quantity'].sum().reset_index()
        sys_summary.columns = ['Exact Product Name', 'System_Stock_Qty']

        # --- STEP 4: FINAL AUDIT TABLE ---
        final_audit = pd.merge(sys_summary, phys_summary, on='Exact Product Name', how='outer').fillna(0)
        final_audit['Difference'] = final_audit['Physical_Scan_Qty'] - final_audit['System_Stock_Qty']
        
        # Status Labeling
        def get_status(row):
            if row['Difference'] == 0: return "Tally"
            return "Short" if row['Difference'] < 0 else "Excess"
        
        final_audit['Status'] = final_audit.apply(get_status, axis=1)

        # Show the Table
        st.subheader("Final Audit: Exact Product Names")
        st.dataframe(final_audit.sort_values('Difference'), use_container_width=True)

        # Download Result
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_audit.to_excel(writer, index=False)
        st.download_button("📥 Download Result", output.getvalue(), "Final_Audit_Report.xlsx")

    except Exception as e:
        st.error(f"Error matching names: {e}")
