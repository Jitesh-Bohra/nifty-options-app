import streamlit as st
import pandas as pd
import csv
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- 1. BULLETPROOF CSV PARSER ---
def process_nse_file(uploaded_file):
    """
    Reads the CSV line by line. Identifies valid data rows by checking 
    if the Strike column (index 11) contains a valid number.
    """
    # Read the raw text
    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
    reader = csv.reader(io.StringIO(content))
    
    extracted_data = []
    
    for row in reader:
        # NSE data rows always have at least 21 columns. 
        # Strike is index 11, Call LTP is index 5, Put LTP is index 17.
        if len(row) >= 18:
            strike_str = row[11].replace(',', '').replace(' ', '').strip()
            
            # If the Strike column is a number, this is a valid data row
            try:
                strike_float = float(strike_str)
                if strike_float > 0:
                    extracted_data.append({
                        'Strike_Price': row[11],
                        'Call_LTP': row[5],
                        'Put_LTP': row[17]
                    })
            except ValueError:
                # If it's not a number (e.g., header text or empty), skip the row
                continue
                
    if not extracted_data:
        raise ValueError("Could not extract any data. Ensure the CSV has standard NSE Option Chain columns.")
        
    # Convert our perfectly extracted rows into Pandas
    df = pd.DataFrame(extracted_data)
    
    # Clean the numbers (remove commas, replace hyphens with 0)
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(',', '', regex=False)
        df[col] = df[col].str.replace('-', '0', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    return df

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
            # Execute our bulletproof parser
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
