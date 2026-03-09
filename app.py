import streamlit as st
import pandas as pd

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- 1. DIRECT INDEX PARSER ---
def process_nse_file(uploaded_file):
    """
    Bypasses header text searching completely. 
    It skips the top 2 text rows and pulls the data directly via fixed NSE column indices.
    """
    # Read the file directly, skipping the two header rows. 
    # header=None prevents Pandas from getting confused by column names.
    df = pd.read_csv(uploaded_file, skiprows=2, header=None, on_bad_lines='skip')
    
    # NSE Fixed Structure: 
    # Index 11 = STRIKE, Index 5 = Call LTP, Index 17 = Put LTP
    extracted_df = df.iloc[:, [11, 5, 17]].copy()
    extracted_df.columns = ['Strike_Price', 'Call_LTP', 'Put_LTP']
    
    # Clean the numbers (remove commas, spaces, replace hyphens with 0)
    for col in extracted_df.columns:
        extracted_df[col] = extracted_df[col].astype(str).str.replace(',', '', regex=False)
        extracted_df[col] = extracted_df[col].str.replace(' ', '', regex=False)
        extracted_df[col] = extracted_df[col].str.replace('-', '0', regex=False)
        extracted_df[col] = pd.to_numeric(extracted_df[col], errors='coerce').fillna(0)
        
    # Filter out empty or 0 strikes to keep the grid clean
    clean_df = extracted_df[extracted_df['Strike_Price'] > 0].reset_index(drop=True)
    return clean_df

# --- 2. POSITIONS COMPUTATION ---
def compute_atm_straddle(clean_df):
    """
    Calculates the ATM Straddle premium based on the cleaned data.
    """
    clean_df['Price_Diff'] = abs(clean_df['Call_LTP'] - clean_df['Put_LTP'])
    valid_df = clean_df[(clean_df['Call_LTP'] > 0) & (clean_df['Put_LTP'] > 0)]
    
    if not valid_df.empty:
        atm_index = valid_df['Price_Diff'].idxmin()
        atm_strike = valid_df.loc[atm_index, 'Strike_Price']
        atm_call = valid_df.loc[atm_index, 'Call_LTP']
        atm_put = valid_df.loc[atm_index, 'Put_LTP']
        straddle_premium = atm_call + atm_put
    else:
        atm_strike, atm_call, atm_put, straddle_premium = 0, 0, 0, 0
        
    display_df = clean_df[['Strike_Price', 'Call_LTP', 'Put_LTP']].copy()
    return display_df, atm_strike, atm_call, atm_put, straddle_premium

# --- WEBSITE UI ---
st.title("NIFTY Options Analyzer")
st.markdown("Upload your NSE Option Chain CSV file below to compute static option positions.")

uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing file..."):
            # Execute our direct index parser
            clean_df = process_nse_file(uploaded_file)
            
            # Run the straddle math
            final_results, atm_strike, atm_call, atm_put, straddle_premium = compute_atm_straddle(clean_df)
        
        st.markdown("**Computations Complete.**")
        
        st.subheader("At-The-Money (ATM) Straddle Info")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ATM Strike", f"{atm_strike:,.0f}")
        col2.metric("Call Premium", f"Rs. {atm_call:,.2f}")
        col3.metric("Put Premium", f"Rs. {atm_put:,.2f}")
        col4.metric("Total Straddle Premium", f"Rs. {straddle_premium:,.2f}")
        
        st.markdown("---") 
        
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
        st.markdown(f"**Error processing file:** {e}")
else:
    st.markdown("*Awaiting file upload...*")
