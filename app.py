import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- CUSTOM PROCESSING LOGIC (BUFFER FUNCTION) ---
def compute_option_positions(df_raw):
    """
    Scans the raw CSV for headers, extracts exactly the columns needed, 
    and computes the ATM Straddle Premium.
    """
    # 1. Find the actual header row by scanning for the word 'STRIKE'
    header_row_index = -1
    for i in range(min(10, len(df_raw))):
        # Convert the row to uppercase text to search it safely
        row_vals = [str(x).upper().strip() for x in df_raw.iloc[i].values]
        if 'STRIKE' in row_vals or 'STRIKE PRICE' in row_vals:
            header_row_index = i
            break
            
    if header_row_index == -1:
        raise ValueError("Could not find the header row containing 'STRIKE'.")
        
    # 2. Get the exact column positions based on the found header row
    row_vals = [str(x).upper().strip() for x in df_raw.iloc[header_row_index].values]
    
    try:
        strike_idx = row_vals.index('STRIKE')
    except ValueError:
        strike_idx = row_vals.index('STRIKE PRICE') # Fallback
        
    ltp_indices = [i for i, x in enumerate(row_vals) if x == 'LTP']
    
    if len(ltp_indices) < 2:
        raise ValueError("Expected 2 'LTP' columns (Call & Put), but did not find them.")
        
    call_idx = ltp_indices[0]
    put_idx = ltp_indices[1]
    
    # 3. Extract only the data rows (everything below the header) and the 3 specific columns
    data_df = df_raw.iloc[header_row_index + 1:, [strike_idx, call_idx, put_idx]].copy()
    data_df.columns = ['Strike_Price', 'Call_LTP', 'Put_LTP']
    
    # 4. Clean the data: Remove commas, replace hyphens with 0, and convert to numbers
    for col in data_df.columns:
        data_df[col] = data_df[col].astype(str).str.replace(',', '', regex=False)
        data_df[col] = data_df[col].str.replace('-', '0', regex=False)
        data_df[col] = pd.to_numeric(data_df[col], errors='coerce').fillna(0)
        
    # 5. Filter out invalid rows (like summary text at the bottom of the CSV)
    clean_df = data_df[data_df['Strike_Price'] > 0].reset_index(drop=True)
    
    # --- PROXY COMPUTATION: ATM STRADDLE ---
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
        # We read the CSV without assuming any headers (header=None) so our custom logic can process it
        raw_df = pd.read_csv(uploaded_file, header=None)
        
        # Show a quick preview of the raw uploaded data
        with st.expander("Preview Raw Data (Click to expand)"):
            st.dataframe(raw_df.head(10))
        
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
        st.markdown(f"**Error processing file:** Please ensure it is a valid NSE CSV. Details: {e}")
else:
    st.markdown("*Awaiting file upload...*")
