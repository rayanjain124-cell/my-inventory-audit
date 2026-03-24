import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="2-Box Scanner Audit", layout="wide")

# 1. Initialize Memory
if 'scan_list' not in st.session_state:
    st.session_state.scan_list = []
if 'active_box' not in st.session_state:
    st.session_state.active_box = 1  # Start with Box 1

st.title("📦 Dual-Box Inventory Audit")
st.write("The cursor will jump between Box 1 and Box 2 automatically after each scan.")

# 2. Sidebar - File Uploads
st.sidebar.header("📁 Setup Data")
sys_file = st.sidebar.file_uploader("Upload System Sheet", type=["xlsx"])
mst_file = st.sidebar.file_uploader("Upload Master Sheet", type=["xlsx"])

if st.sidebar.button("🗑️ Clear All Scans"):
    st.session_state.scan_list = []
    st.session_state.active_box = 1
    st.rerun()

# 3. Dual-Box Scanner Interface
col_a, col_b = st.columns(2)

# Logic: Only show the 'active' box as an input, show the other as 'previously used'
with col_a:
    if st.session_state.active_box == 1:
        box1 = st.text_input("👇 SCAN HERE (Box 1)", key="input1", placeholder="Ready for scan...")
        if box1:
            st.session_state.scan_list.append(str(box1).strip())
            st.session_state.active_box = 2 # Switch to Box 2
            st.rerun()
    else:
        st.info(f"Last Scan in Box 1: {st.session_state.scan_list[-1] if st.session_state.scan_list else 'None'}")

with col_b:
    if st.session_state.active_box == 2:
        box2 = st.text_input("👇 SCAN HERE (Box 2)", key="input2", placeholder="Ready for scan...")
        if box2:
            st.session_state.scan_list.append(str(box2).strip())
            st.session_state.active_box = 1 # Switch back to Box 1
            st.rerun()
    else:
        if st.session_state.active_box == 1 and len(st.session_state.scan_list) > 0:
             st.info(f"Last Scan in Box 2: {st.session_state.scan_list[-1]}")

st.write(f"**Total Items Scanned:** {len(st.session_state.scan_list)}")

# 4. Processing the Waterfall Logic
if sys_file and mst_file:
    try:
        # Load sheets
        df_sys = pd.read_excel(sys_file)
        df_mst = pd.read_excel(mst_file)

        # Mapping System (C=Name[2], D=Van[3], F=Serial[5], H=Qty[7], M=Cat[12], P=EAN[15])
        sys_map = {}
        for _, row in df_sys.iterrows():
            name = str(row.iloc[2]).strip()
            qty = row.iloc[7] if pd.notna(row.iloc[7]) else 0
            # Link all possible IDs to this product name
            for idx in [3, 5, 15]:
                key = str(row.iloc[idx]).strip()
                if key != 'nan' and key != "":
                    sys_map[key] = {"name": name, "qty": qty}

        # Mapping Master (A=Van[0], B=EAN25[1], D=EAN26[3], E=Name[4])
        mst_map = {}
        for _, row in df_mst.iterrows():
            name = str(row.iloc[4]).strip()
            for idx in [0, 1, 3]:
                key = str(row.iloc[idx]).strip()
                if key != 'nan' and key != "":
                    mst_map[key] = name

        # Match Scans to Names
        processed_scans = []
        for code in st.session_state.scan_list:
            if code in sys_map:
                processed_scans.append(sys_map[code]['name'])
            elif code in mst_map:
                processed_scans.append(mst_map[code])
            else:
                processed_scans.append(f"UNKNOWN: {code}")

        # Summary Math
        phys_counts = pd.Series(processed_scans).value_counts().reset_index()
        phys_counts.columns = ['Product Name', 'Physical Count']

        sys_sums = df_sys.groupby(df_sys.columns[2])[df_sys.columns[7]].sum().reset_index()
        sys_sums.columns = ['Product Name', 'System Qty']

        # Final Report
        audit = pd.merge(sys_sums, phys_counts, on='Product Name', how='outer').fillna(0)
        audit['Difference'] = audit['Physical Count'] - audit['System Qty']
        audit['Status'] = audit['Difference'].apply(lambda x: "Tally" if x==0 else ("Short" if x<0 else "Excess"))

        st.subheader("Final Audit Report")
        st.dataframe(audit.sort_values('Difference'), use_container_width=True)

        # Export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            audit.to_excel(writer, index=False)
        st.download_button("📥 Download Final Report", output.getvalue(), "Audit_Summary.xlsx")

    except Exception as e:
        st.error(f"Logic Error: {e}. Check if Excel columns match the expected order.")
