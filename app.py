import streamlit as st
import pandas as pd
import csv
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- 1. ROBUST CSV PARSER ---
def process_nse_file(file_bytes):
    """
    Decodes the file and uses Python's native CSV reader to safely handle 
    uneven rows and numbers containing commas (like "21,450.00").
    """
    # Decode bytes to a string, ignoring encoding artifacts
    text = file_bytes.decode('utf-8', errors='ignore')
    
    # Use the built-in csv reader which natively understands quotation marks
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    
    # Locate the header row
    header_idx = -1
    for i, row in enumerate(rows):
        # Clean up the row strings for safe searching
        row_upper = [str(cell).upper().strip() for cell in row]
        if 'STRIKE' in row_upper and 'LTP' in row_upper:
            header_idx = i
            break
            
    if header_idx == -1:
        raise ValueError("Could not find the header row. Make sure the CSV contains 'STRIKE' and 'LTP' columns.")
        
    # Get exact column indices from the identified header row
    headers = [str(cell).upper().strip() for cell in rows[header_idx]]
    strike_idx = headers.index('STRIKE')
    ltp_indices = [i for i, h in enumerate(headers) if h == 'LTP']
    
    if len(ltp_indices) < 2:
        raise ValueError("Expected to find 2 'LTP' columns (Call and Put), but found fewer.")
        
    call_idx = ltp_indices[0]
    put_idx = ltp_indices[1]
    
    # Extract only the data we need
    extracted_data = []
    for row in rows[header_idx + 1:]:
        # Ensure the row is long enough (this skips empty lines at the bottom of the file)
        if len(row) > max(strike_idx, call_idx, put_idx):
            extracted_data.append({
                'Strike_Price': row[strike_idx],
                'Call_LTP': row[call_idx],
                'Put_LTP': row[put_idx]
            })
            
    # Convert to a Pandas DataFrame
    df = pd.DataFrame(extracted_data)
    
    # Clean the numbers (remove commas, replace hyphens with 0, convert to float)
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(',', '', regex=False)
        df[col] = df[col].str.replace('-', '0', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    # Filter out empty or 0 strikes
    clean_df = df[df['Strike_Price'] > 0].reset_index(drop=True)
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
            # Pass the raw file bytes to our robust CSV processor
            clean_df = process_nse_file(uploaded_file.getvalue())
            
            # Run the calculations
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
