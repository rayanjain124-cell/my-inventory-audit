import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Inventory Audit Pro", layout="wide")
st.title("📦 Smart Inventory Audit System")

st.sidebar.header("Settings")
id_col = st.sidebar.text_input("ID Column Name", "ProductEAN")

col1, col2 = st.columns(2)
with col1:
    sys_file = st.file_uploader("1. Upload System Report", type=["csv", "xlsx"])
with col2:
    scn_file = st.file_uploader("2. Upload Scan Data", type=["csv", "xlsx"])

if sys_file and scn_file:
    def load_data(file):
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        return pd.read_excel(file)

    try:
        df_sys = load_data(sys_file)
        df_scn = load_data(scn_file)

        # Clean up column names (removes hidden spaces)
        df_sys.columns = df_sys.columns.str.strip()
        df_scn.columns = df_scn.columns.str.strip()

        # 1. Process System Data
        if id_col in df_sys.columns:
            # If there is a Quantity column, sum it. Otherwise count rows.
            qty_col = 'Quantity' if 'Quantity' in df_sys.columns else df_sys.columns[1]
            sys_sum = df_sys.groupby(id_col)[qty_col].sum().reset_index()
            sys_sum.columns = [id_col, 'System Count']
        else:
            st.error(f"Could not find '{id_col}' in System File. Available: {list(df_sys.columns)}")
            st.stop()

        # 2. Process Scan Data
        # We look for 'Scan_Here' or the first column
        scan_id_col = 'Scan_Here' if 'Scan_Here' in df_scn.columns else df_scn.columns[0]
        scn_sum = df_scn.groupby(scan_id_col).size().reset_index(name='Scan Count')
        scn_sum.columns = [id_col, 'Scan Count']

        # 3. Merge and Compare
        audit = pd.merge(sys_sum, scn_sum, on=id_col, how='outer').fillna(0)
        audit['Difference'] = audit['Scan Count'] - audit['System Count']
        
        def highlight_diff(val):
            color = 'red' if val < 0 else 'green' if val > 0 else 'black'
            return f'color: {color}'

        st.subheader("Final Audit Results")
        st.dataframe(audit.style.applymap(highlight_diff, subset=['Difference']), use_container_width=True)

        # Export to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            audit.to_excel(writer, index=False)
        st.download_button("📥 Download Audit Report", output.getvalue(), "audit_report.xlsx")

    except Exception as e:
        st.error(f"Analysis Error: {e}")
