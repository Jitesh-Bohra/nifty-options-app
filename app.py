import streamlit as st
import pandas as pd
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- 1. RAW TEXT PREPROCESSING ---
def preprocess_text_to_csv(file_bytes):
    """
    Reads the raw text of the file, finds the headers, fixes the duplicate 
    column names, and returns a clean, Pandas-compatible CSV string.
    """
    # Decode the file bytes into raw text lines
    lines = file_bytes.decode('utf-8', errors='replace').splitlines()
    
    header_idx = -1
    # Scan line by line to find the header row containing STRIKE and LTP
    for i, line in enumerate(lines):
        line_upper = line.upper()
        if 'STRIKE' in line_upper and 'LTP' in line_upper:
            header_idx = i
            break
            
    if header_idx == -1:
        raise ValueError("Could not find the header row containing 'STRIKE' and 'LTP' in the text.")
        
    # Split the header row into individual column names
    raw_headers = lines[header_idx].split(',')
    clean_headers = [h.strip().replace('"', '').upper() for h in raw_headers]
    
    # Locate the exact indices for Strike and the two LTP columns
    try:
        strike_idx = clean_headers.index('STRIKE')
    except ValueError:
        try:
            strike_idx = clean_headers.index('STRIKE PRICE')
        except ValueError:
            raise ValueError("Found headers, but could not locate the exact 'STRIKE' column.")
            
    ltp_indices = [i for i, h in enumerate(clean_headers) if h == 'LTP']
    
    if len(ltp_indices) < 2:
        raise ValueError("Expected to find 2 'LTP' columns, but found fewer.")
        
    # Rename them directly in the text so Pandas doesn't get confused
    clean_headers[ltp_indices[0]] = 'Call_LTP'
    clean_headers[ltp_indices[1]] = 'Put_LTP'
    clean_headers[strike_idx] = 'Strike_Price'
    
    # Reconstruct the header line
    new_header_line = ",".join(clean_headers)
    
    # Keep only the new header and the actual data rows below it
    valid_lines = [new_header_line]
    for line in lines[header_idx + 1:]:
        # Basic check to skip empty lines or the "Total" row at the bottom
        if line.strip() and "Total" not in line and len(line.split(',')) > 5:
            valid_lines.append(line)
            
    # Join everything back into a single clean text block
    clean_csv_text = "\n".join(valid_lines)
    return clean_csv_text

# --- 2. PANDAS COMPUTATION ---
def compute_option_positions(df):
    """
    Takes the cleaned Pandas dataframe, filters the numbers, 
    and computes the ATM Straddle.
    """
    # Extract only our explicitly named columns
    extracted_df = df[['Strike_Price', 'Call_LTP', 'Put_LTP']].copy()
    
    # Clean the data: Remove commas, replace hyphens with 0, and convert to numeric
    for col in extracted_df.columns:
        extracted_df[col] = extracted_df[col].astype(str).str.replace(',', '', regex=False)
        extracted_df[col] = extracted_df[col].str.replace('-', '0', regex=False)
        extracted_df[col] = pd.to_numeric(extracted_df[col], errors='coerce').fillna(0)
        
    # Filter out empty strikes
    clean_df = extracted_df[extracted_df['Strike_Price'] > 0].reset_index(drop=True)
    
    # Compute ATM Straddle
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

# File Uploader
uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing raw text and computing positions..."):
            # Step 1: Preprocess the raw text completely
            clean_csv_text = preprocess_text_to_csv(uploaded_file.getvalue())
            
            # Step 2: Feed the perfectly clean text into Pandas
            raw_df = pd.read_csv(io.StringIO(clean_csv_text))
            
            # Step 3: Run the computations
            final_results, atm_strike, atm_call, atm_put, straddle_premium = compute_option_positions(raw_df)
        
        # --- DISPLAY RESULTS ---
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
        st.markdown(f"**Error processing file:** Details: {e}")
else:
    st.markdown("*Awaiting file upload...*")
