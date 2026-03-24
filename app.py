import streamlit as st
import pandas as pd
import io

# --- Page Setup ---
st.set_page_config(page_title="Inventory Audit Pro", layout="wide")
st.title("📦 Smart Inventory Audit System")

# Settings in Sidebar
st.sidebar.header("Settings")
id_col = st.sidebar.text_input("ID Column Name (e.g., ProductEAN)", "ProductEAN")

# File Uploaders
col1, col2 = st.columns(2)
with col1:
    sys_file = st.file_uploader("1. Upload System Report (Excel/CSV)", type=["csv", "xlsx"])
with col2:
    scn_file = st.file_uploader("2. Upload Physical Scan Data (Excel/CSV)", type=["csv", "xlsx"])

if sys_file and scn_file:
    def load_data(file):
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)

    try:
        df_sys = load_data(sys_file)
        df_scn = load_data(scn_file)

        # Basic Processing
        # Aggregate System Data
        if 'Quantity' in df_sys.columns:
            sys_sum = df_sys.groupby(id_col)['Quantity'].sum().reset_index()
        else:
            sys_sum = df_sys[id_col].value_counts().reset_index(name='Quantity')
        
        # Aggregate Scan Data
        scn_sum = df_scn[df_scn.columns[0]].value_counts().reset_index()
        scn_sum.columns = [id_col, 'Scan Count']

        # Merge for Audit
        audit = pd.merge(sys_sum, scn_sum, on=id_col, how='outer').fillna(0)
        audit['Difference'] = audit['Scan Count'] - audit.get('Quantity', audit.get('count', 0))

        st.subheader("Audit Result")
        st.dataframe(audit, use_container_width=True)

        # Download Button
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            audit.to_excel(writer, index=False)
        st.download_button("📥 Download Result", output.getvalue(), "audit_report.xlsx")

    except Exception as e:
        st.error(f"Error: {e}. Please check if the ID Column name is correct.")
