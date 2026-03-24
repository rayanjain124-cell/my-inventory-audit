import streamlit as st
import pandas as pd
import io

# --- Page Config ---
st.set_page_config(page_title="Pro Inventory Audit System", layout="wide")

st.title("📦 Advanced Inventory Audit System")
st.markdown("Upload your **System Report** and **Scan Data** to perform a deep-dive audit.")

# --- Sidebar: Configuration ---
st.sidebar.header("Configuration")
id_column = st.sidebar.text_input("Unique ID Column (e.g., EAN, Item Number, or Product Code)", "ProductEAN")

# --- File Uploaders ---
col1, col2 = st.columns(2)

with col1:
    system_file = st.file_uploader("1. Upload System (ERP) Data (CSV)", type=["csv"])
    
with col2:
    scan_file = st.file_uploader("2. Upload Scan (Physical) Data (CSV)", type=["csv"])

# --- Processing Logic ---
if system_file and scan_file:
    try:
        # Load Data
        df_system = pd.read_csv(system_file)
        df_scan = pd.read_csv(scan_file)

        st.success("Files uploaded successfully!")

        # Pre-processing: Aggregation
        # If the scan file is raw (one row per scan), we sum it up.
        # Check if 'Scan Count' exists, else count occurrences.
        if 'Scan Count' in df_scan.columns:
            scan_summary = df_scan.groupby(id_column).agg({
                'Scan Count': 'sum',
                'Product Name': 'first'
            }).reset_index()
        else:
            # If it's a raw barcode list, count each row
            scan_summary = df_scan.groupby(id_column).size().reset_index(name='Scan Count')

        # Aggregate System Data
        if 'Quantity' in df_system.columns:
            system_summary = df_system.groupby(id_column).agg({
                'Quantity': 'sum',
                'Product': 'first'
            }).reset_index().rename(columns={'Quantity': 'System Count'})
        else:
            system_summary = df_system.groupby(id_column).size().reset_index(name='System Count')

        # --- Deep Audit (Merge) ---
        audit_df = pd.merge(system_summary, scan_summary, on=id_column, how='outer').fillna(0)

        # Calculate Variance
        audit_df['Variance'] = audit_df['Scan Count'] - audit_df['System Count']
        
        # Categorize
        def get_status(row):
            if row['Variance'] == 0: return "Tally ✅"
            if row['Variance'] > 0: return "Excess 📈"
            return "Shortage 📉"

        audit_df['Audit Status'] = audit_df.apply(get_status, axis=1)

        # --- Dashboard Metrics ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total SKU Count", len(audit_df))
        m2.metric("Shortage Items", len(audit_df[audit_df['Variance'] < 0]))
        m3.metric("Excess Items", len(audit_df[audit_df['Variance'] > 0]))
        m4.metric("Matched (Tally)", len(audit_df[audit_df['Variance'] == 0]))

        # --- Filters ---
        status_filter = st.multiselect("Filter by Status", options=audit_df['Audit Status'].unique(), default=audit_df['Audit Status'].unique())
        filtered_df = audit_df[audit_df['Audit Status'].isin(status_filter)]

        # --- Data Table ---
        st.subheader("Deep Audit Results")
        st.dataframe(filtered_df, use_container_width=True)

        # --- Export to Excel ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            filtered_df.to_excel(writer, index=False, sheet_name='Audit_Report')
        
        st.download_button(
            label="📥 Download Audit Report (Excel)",
            data=output.getvalue(),
            file_name="Audit_Report_Deep_Analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error processing data: {e}")
        st.info("Check if your 'Unique ID' column name matches exactly what is in your files.")

else:
    st.info("Please upload both System and Scan files to begin the deep audit.")
