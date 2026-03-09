import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", page_icon="📈", layout="wide")

# --- CUSTOM PROCESSING LOGIC (BUFFER FUNCTION) ---
def compute_option_positions(df):
    """
    Cleans the raw NSE data and computes the ATM Straddle Premium.
    """
    # 1. Extract exactly the columns we need by their index position
    # Column 11 = STRIKE, Column 5 = Call LTP, Column 17 = Put LTP
    extracted_df = df.iloc[:, [11, 5, 17]].copy()
    extracted_df.columns = ['Strike_Price', 'Call_LTP', 'Put_LTP']
    
    # 2. Clean the data: Remove commas, replace hyphens with 0, and convert to numbers
    for col in extracted_df.columns:
        extracted_df[col] = extracted_df[col].astype(str).str.replace(',', '', regex=False)
        extracted_df[col] = extracted_df[col].astype(str).str.replace('-', '0', regex=False)
        extracted_df[col] = pd.to_numeric(extracted_df[col], errors='coerce').fillna(0)
        
    # 3. Filter out invalid rows (like the empty summary rows at the bottom of the CSV)
    clean_df = extracted_df[extracted_df['Strike_Price'] > 0].reset_index(drop=True)
    
    # --- PROXY COMPUTATION: ATM STRADDLE ---
    # Find the ATM strike by finding where the difference between Call and Put LTP is the smallest
    clean_df['Price_Diff'] = abs(clean_df['Call_LTP'] - clean_df['Put_LTP'])
    
    # Exclude rows where prices are 0 to avoid false matches
    valid_df = clean_df[(clean_df['Call_LTP'] > 0) & (clean_df['Put_LTP'] > 0)]
    
    if not valid_df.empty:
        atm_index = valid_df['Price_Diff'].idxmin()
        atm_strike = valid_df.loc[atm_index, 'Strike_Price']
        atm_call = valid_df.loc[atm_index, 'Call_LTP']
        atm_put = valid_df.loc[atm_index, 'Put_LTP']
        straddle_premium = atm_call + atm_put
    else:
        atm_strike, atm_call, atm_put, straddle_premium = 0, 0, 0, 0
        
    # Drop the temporary 'Price_Diff' column for the final clean display
    display_df = clean_df[['Strike_Price', 'Call_LTP', 'Put_LTP']].copy()
    
    return display_df, atm_strike, atm_call, atm_put, straddle_premium

# --- WEBSITE UI ---
st.title("📈 NIFTY Options Analyzer")
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
        st.success("Computations Complete!")
        
        # Display the ATM Straddle as a set of highlighted metrics
        st.subheader("🎯 At-The-Money (ATM) Straddle Info")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ATM Strike", f"{atm_strike:,.0f}")
        col2.metric("Call Premium", f"₹{atm_call:,.2f}")
        col3.metric("Put Premium", f"₹{atm_put:,.2f}")
        col4.metric("Total Straddle Premium", f"₹{straddle_premium:,.2f}")
        
        st.divider() # Adds a nice horizontal line
        
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
        st.error(f"An error occurred while processing the file. Please ensure it is a valid NSE CSV. Error: {e}")
else:
    st.info("Awaiting file upload...")
