import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", page_icon="📈", layout="wide")

# --- CUSTOM PROCESSING LOGIC (BUFFER FUNCTION) ---
def compute_option_positions(df):
    """
    This is your buffer function. 
    Drop your specific Pandas logic here to calculate straddles, strangles, or filter strikes.
    """
    # Example buffer logic: Filter out rows where Strike Price is missing or 0
    df = df[df['STRIKE'] > 0].copy()
    
    # Example: Let's just grab the Strike, Call LTP, and Put LTP for a clean view
    # Note: NSE CSV has duplicated column names for Calls and Puts, so we locate by index
    # Column index 10 is STRIKE, 4 is Call LTP, 16 is Put LTP
    clean_df = df.iloc[:, [10, 4, 16]].copy()
    clean_df.columns = ['Strike_Price', 'Call_LTP', 'Put_LTP']
    
    # Sort by Strike Price
    clean_df = clean_df.sort_values('Strike_Price').reset_index(drop=True)
    
    return clean_df

# --- WEBSITE UI ---
st.title("📈 NIFTY Options Analyzer")
st.markdown("Upload your NSE Option Chain CSV file below to compute static option positions.")

# File Uploader
uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        # Load the CSV. The NSE file has a merged top row ("CALLS", "PUTS"), 
        # so we skip row 0 and use row 1 as the actual column headers.
        raw_df = pd.read_csv(uploaded_file, header=1)
        
        # Clean up column names by stripping extra spaces
        raw_df.columns = raw_df.columns.str.strip()
        
        # Show a quick preview of the raw uploaded data
        with st.expander("Preview Raw Data (Click to expand)"):
            st.dataframe(raw_df.head())
        
        # --- RUN COMPUTATIONS ---
        with st.spinner("Computing option positions..."):
            final_results = compute_option_positions(raw_df)
        
        # --- DISPLAY RESULTS ---
        st.success("Computations Complete!")
        st.subheader("Calculated Positions")
        st.dataframe(
            final_results.style.format({
                'Strike_Price': '{:,.2f}',
                'Call_LTP': '{:,.2f}',
                'Put_LTP': '{:,.2f}'
            }),
            use_container_width=True
        )
        
    except Exception as e:
        st.error(f"An error occurred while processing the file. Please ensure it is a valid NSE CSV. Error: {e}")
else:
    st.info("Awaiting file upload...")