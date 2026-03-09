import streamlit as st
import pandas as pd
import csv
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- CUSTOM CSS FOR UNIFORM FONT SIZES ---
st.markdown("""
<style>
    /* Standardize headers to be much closer in size to regular text */
    h1 { font-size: 24px !important; padding-bottom: 10px !important;}
    h2 { font-size: 20px !important; }
    h3 { font-size: 18px !important; }
    p, li { font-size: 16px !important; }
    
    /* Reduce the massive default size of the Metric numbers */
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold !important; }
    [data-testid="stMetricLabel"] { font-size: 16px !important; }
</style>
""", unsafe_allow_html=True)

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
        # NSE data rows always have at least 18 columns. 
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
st.markdown("<h1>NIFTY Options Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<p>Upload your NSE Option Chain CSV file below to compute static option positions.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing file..."):
            # Execute our bulletproof parser
            clean_df = process_nse_file(uploaded_file)
            
            # Run the straddle math
            final_results, atm_strike, atm_call, atm_put, straddle_premium = compute_atm_straddle(clean_df)
        
        st.markdown("**Computations Complete.**")
        
        st.markdown("<h3>At-The-Money (ATM) Straddle Info</h3>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ATM Strike", f"{atm_strike:,.0f}")
        col2.metric("Call Premium", f"Rs. {atm_call:,.2f}")
        col3.metric("Put Premium", f"Rs. {atm_put:,.2f}")
        col4.metric("Total Straddle Premium", f"Rs. {straddle_premium:,.2f}")
        
        st.markdown("---") 
        
        # --- RAW DATA DISPLAY ---
        st.markdown("<h3>Raw Uploaded Data</h3>", unsafe_allow_html=True)
        
        # Extract the exact string content of the uploaded file to show it "as is"
        raw_content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        
        # Load it into pandas skipping bad formatting lines just to display it properly
        raw_df = pd.read_csv(io.StringIO(raw_content), on_bad_lines='skip', low_memory=False)
        st.dataframe(raw_df, use_container_width=True)
        
    except Exception as e:
        st.markdown(f"**Error processing file:** {e}")
else:
    st.markdown("<p><i>Awaiting file upload...</i></p>", unsafe_allow_html=True)
