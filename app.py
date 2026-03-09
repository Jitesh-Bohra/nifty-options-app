import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
# Set the page configuration without any emojis
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- CUSTOM PROCESSING LOGIC (BUFFER FUNCTION) ---
def compute_option_positions(df):
    """
    Cleans the raw NSE data and computes the ATM Straddle Premium.
    """
    # 1. Dynamically locate columns to prevent index errors
    # Pandas handles duplicate column names (like 'LTP') by automatically naming the second one 'LTP.1'
    strike_cols = [col for col in df.columns if 'STRIKE' in str(col).upper()]
    ltp_cols = [col for col in df.columns if 'LTP' in str(col).upper()]
    
    if not strike_cols or len(ltp_cols) < 2:
        raise ValueError("Could not locate the STRIKE or LTP columns. Please check the CSV format.")
        
    strike_col = strike_cols[0]
    call_col = ltp_cols[0]
    put_col = ltp_cols[1]
    
    extracted_df = df[[strike_col, call_col, put_col]].copy()
    extracted_df.columns = ['Strike_Price', 'Call_LTP', 'Put_LTP']
    
    # 2. Clean the data: Remove commas, replace hyphens with 0, and convert to numbers
    for col in extracted_df.columns:
        extracted_df[col] = extracted_df[col].astype(str).str.replace(',', '', regex=False)
        extracted_df[col] = extracted_df[col].str.replace('-', '0', regex=False)
        extracted_df[col] = pd.to_numeric(extracted_df[col], errors='coerce').fillna(0)
        
    # 3. Filter out invalid rows (like summary text at the bottom of the CSV)
    clean_df = extracted_df[extracted_df['Strike_Price'] > 0].reset_index(drop=True)
    
    # --- PROXY COMPUTATION: ATM STRADDLE ---
    # Find the ATM strike by finding where the difference between Call and Put premium is the smallest
    clean_df['Price_Diff'] = abs(clean_df['Call_LTP'] - clean_df['Put_LTP'])
    
    # Exclude rows where prices are 0 to avoid false matches on empty strikes
    valid_df = clean_df[(clean_df['Call_LTP'] > 0) & (clean_df['Put_LTP'] > 0)]
    
    if not valid_df.empty:
        atm_index = valid_df['Price_Diff'].idxmin()
        atm_strike = valid_df.loc[atm_index, 'Strike_Price']
        atm_call = valid_df.loc[atm_index, 'Call_LTP']
        atm_put = valid_df.loc[atm_index, 'Put_LTP']
        straddle_premium = atm_call + atm_put
    else:
        atm_strike, atm_call, atm_put, straddle_premium = 0, 0, 0, 0
        
    # Drop the temporary 'Price_Diff' column for the final display
    display_df = clean_df[['Strike_Price', 'Call_LTP', 'Put_LTP']].copy()
    
    return display_df, atm_strike, atm_call, atm_put, straddle_premium

# --- WEBSITE UI ---
st.title("NIFTY Options Analyzer")
st.markdown("Upload your NSE Option Chain CSV file below to compute static option positions.")

# File Uploader
uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        # Load the CSV. We skip row 0 because the NSE file has a merged top row.
        raw_df = pd.read_csv(uploaded_file, header=1)
        
        # Show a quick preview of the raw uploaded data
        with st.expander("Preview Raw Data (Click to expand)"):
            st.dataframe(raw_df.head())
        
        # --- RUN COMPUTATIONS ---
        with st.spinner("Cleaning data and computing option positions..."):
            final_results, atm_strike, atm_call, atm_put, straddle_premium = compute_option_positions(raw_df)
        
        # --- DISPLAY RESULTS ---
        st.markdown("**Computations Complete.**")
        
        # Display the ATM Straddle as highlighted metrics
        st.subheader("At-The-Money (ATM) Straddle Info")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ATM Strike", f"{atm_strike:,.0f}")
        col2.metric("Call Premium", f"Rs. {atm_call:,.2f}")
        col3.metric("Put Premium", f"Rs. {atm_put:,.2f}")
        col4.metric("Total Straddle Premium", f"Rs. {straddle_premium:,.2f}")
        
        st.markdown("---") 
        
        # Display the cleaned options table
        st.subheader("Cleaned Option Chain")
        st.dataframe(
            final_results.style.format({
                'Strike_Price': '{:,.2f}',
                'Call_LTP': '{:,.2f}',
                'Put_LTP': '{:,.2f}'
            }),
            use_container_width=True
        )
        
    except Exception as e:
        # Using markdown instead of st.error to avoid the default error emoji
        st.markdown(f"**Error processing file:** Please ensure it is a valid NSE CSV. Details: {e}")
else:
    st.markdown("*Awaiting file upload...*")
