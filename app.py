import streamlit as st
import pandas as pd
import csv
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="NIFTY Options Analyzer", layout="wide")

# --- CUSTOM CSS FOR UNIFORM FONT SIZES ---
st.markdown("""
<style>
    h1 { font-size: 24px !important; padding-bottom: 10px !important;}
    h2 { font-size: 20px !important; }
    h3 { font-size: 18px !important; }
    p, li { font-size: 16px !important; }
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: bold !important; }
    [data-testid="stMetricLabel"] { font-size: 16px !important; }
</style>
""", unsafe_allow_html=True)

# --- 1. UNIVERSAL ROBUST PARSER ---
def process_universal_csv(uploaded_file):
    """
    Smart parser that auto-detects between the NSE Live Website Format 
    and the Historical EOD Database Format.
    """
    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
    
    # ATTEMPT 1: Check for Historical EOD Database Format
    try:
        df_test = pd.read_csv(io.StringIO(content), nrows=5)
        if 'StrkPric' in df_test.columns and 'OptnTp' in df_test.columns and 'ClsPric' in df_test.columns:
            df = pd.read_csv(io.StringIO(content))
            latest_trade_date = sorted(df['Trading_Date'].unique())[-1]
            df_latest_trade = df[df['Trading_Date'] == latest_trade_date]
            latest_expiry = sorted(df_latest_trade['XpryDt'].unique())[0]
            df_filtered = df_latest_trade[df_latest_trade['XpryDt'] == latest_expiry]
            
            pivot_df = df_filtered.pivot_table(index='StrkPric', columns='OptnTp', values='ClsPric').reset_index()
            if 'CE' not in pivot_df.columns: pivot_df['CE'] = 0.0
            if 'PE' not in pivot_df.columns: pivot_df['PE'] = 0.0
                
            pivot_df.rename(columns={'StrkPric': 'Strike_Price', 'CE': 'Call_LTP', 'PE': 'Put_LTP'}, inplace=True)
            pivot_df.fillna(0, inplace=True) 
            
            clean_df = pivot_df[['Strike_Price', 'Call_LTP', 'Put_LTP']].copy()
            clean_df['Strike_Price'] = pd.to_numeric(clean_df['Strike_Price'])
            clean_df['Call_LTP'] = pd.to_numeric(clean_df['Call_LTP'])
            clean_df['Put_LTP'] = pd.to_numeric(clean_df['Put_LTP'])
            
            return clean_df
    except Exception:
        pass

    # ATTEMPT 2: Fallback to the NSE Live Website Format
    reader = csv.reader(io.StringIO(content))
    extracted_data = []
    
    for row in reader:
        if len(row) >= 18:
            strike_str = row[11].replace(',', '').replace(' ', '').strip()
            try:
                strike_float = float(strike_str)
                if strike_float > 0:
                    extracted_data.append({
                        'Strike_Price': row[11],
                        'Call_LTP': row[5],
                        'Put_LTP': row[17]
                    })
            except ValueError:
                continue 
                
    if not extracted_data:
        raise ValueError("Could not extract data. Ensure it is a valid NSE format.")
        
    df = pd.DataFrame(extracted_data)
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(',', '', regex=False).str.replace('-', '0', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
    return df[df['Strike_Price'] > 0].reset_index(drop=True)

# --- 2. POSITIONS & PAIR COMPUTATION ---
def compute_option_metrics(clean_df):
    """
    Finds the ATM strike, calculates the straddle, and ranks the top 5 custom pairs.
    """
    clean_df['Price_Diff'] = abs(clean_df['Call_LTP'] - clean_df['Put_LTP'])
    valid_df = clean_df[(clean_df['Call_LTP'] > 0) & (clean_df['Put_LTP'] > 0)]
    
    if valid_df.empty:
        return 0, 0, 0, pd.DataFrame(), pd.DataFrame()

    # Determine ATM parameters
    atm_index = valid_df['Price_Diff'].idxmin()
    atm_strike = valid_df.loc[atm_index, 'Strike_Price']
    atm_call = valid_df.loc[atm_index, 'Call_LTP']
    atm_put = valid_df.loc[atm_index, 'Put_LTP']
    
    # --- Pair Analysis 1: ATM PE + ITM CE ---
    # ITM CE means Strike is strictly less than Spot (ATM Strike), capped at 500 pts away
    itm_ce_df = clean_df[(clean_df['Strike_Price'] < atm_strike) & 
                         (atm_strike - clean_df['Strike_Price'] <= 500)]
    
    pairs_1 = []
    for _, row in itm_ce_df.iterrows():
        itm_strike = row['Strike_Price']
        itm_premium = row['Call_LTP']
        if itm_premium == 0: continue
        
        strike_diff = atm_strike - itm_strike
        premium_sum = atm_put + itm_premium
        metric = premium_sum - strike_diff
        
        pairs_1.append({
            'ITM CE Strike': itm_strike,
            'CE Premium': itm_premium,
            'ATM PE Premium': atm_put,
            'Premium Sum': premium_sum,
            'Strike Diff': strike_diff,
            'Metric Value': metric
        })
        
    df_pairs_1 = pd.DataFrame(pairs_1).sort_values('Metric Value', ascending=True).head(5) if pairs_1 else pd.DataFrame()

    # --- Pair Analysis 2: ATM CE + ITM PE ---
    # ITM PE means Strike is strictly greater than Spot (ATM Strike), capped at 500 pts away
    itm_pe_df = clean_df[(clean_df['Strike_Price'] > atm_strike) & 
                         (clean_df['Strike_Price'] - atm_strike <= 500)]
                         
    pairs_2 = []
    for _, row in itm_pe_df.iterrows():
        itm_strike = row['Strike_Price']
        itm_premium = row['Put_LTP']
        if itm_premium == 0: continue
        
        strike_diff = itm_strike - atm_strike
        premium_sum = atm_call + itm_premium
        metric = premium_sum - strike_diff
        
        pairs_2.append({
            'ITM PE Strike': itm_strike,
            'PE Premium': itm_premium,
            'ATM CE Premium': atm_call,
            'Premium Sum': premium_sum,
            'Strike Diff': strike_diff,
            'Metric Value': metric
        })
        
    df_pairs_2 = pd.DataFrame(pairs_2).sort_values('Metric Value', ascending=True).head(5) if pairs_2 else pd.DataFrame()

    return atm_strike, atm_call, atm_put, df_pairs_1, df_pairs_2

# --- WEBSITE UI ---
st.markdown("<h1>NIFTY Options Analyzer</h1>", unsafe_allow_html=True)
st.markdown("<p>Upload your NSE Option Chain CSV file below to compute static option positions and custom pair rankings.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload NSE CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        with st.spinner("Processing file and calculating pairs..."):
            clean_df = process_universal_csv(uploaded_file)
            atm_strike, atm_call, atm_put, df_pairs_1, df_pairs_2 = compute_option_metrics(clean_df)
        
        st.markdown("**Computations Complete.**")
        
        # Base ATM Reference
        st.markdown("<h3>Reference: At-The-Money (ATM) Info</h3>", unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ATM Proxy Strike", f"{atm_strike:,.0f}")
        col2.metric("Call Premium", f"Rs. {atm_call:,.2f}")
        col3.metric("Put Premium", f"Rs. {atm_put:,.2f}")
        col4.metric("Straddle Premium", f"Rs. {(atm_call + atm_put):,.2f}")
        
        st.markdown("---") 
        
        # Custom Pairs Display
        st.markdown(f"<h3>Top 5 Ranked Pairs (Sorted by: Sum of Premiums - Strike Difference)</h3>", unsafe_allow_html=True)
        
        col_table1, col_table2 = st.columns(2)
        
        with col_table1:
            st.markdown("<b>ATM PE + ITM CE Pairs</b>", unsafe_allow_html=True)
            if not df_pairs_1.empty:
                st.dataframe(df_pairs_1.style.format(precision=2), use_container_width=True)
            else:
                st.info("No valid ITM CE pairs found within 500 points.")
                
        with col_table2:
            st.markdown("<b>ATM CE + ITM PE Pairs</b>", unsafe_allow_html=True)
            if not df_pairs_2.empty:
                st.dataframe(df_pairs_2.style.format(precision=2), use_container_width=True)
            else:
                st.info("No valid ITM PE pairs found within 500 points.")
        
        st.markdown("---")
        
        # Raw Data Display
        st.markdown("<h3>Raw Uploaded Data</h3>", unsafe_allow_html=True)
        raw_content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        raw_df = pd.read_csv(io.StringIO(raw_content), on_bad_lines='skip', low_memory=False)
        st.dataframe(raw_df, use_container_width=True)
        
    except Exception as e:
        st.markdown(f"**Error processing file:** {e}")
else:
    st.markdown("<p><i>Awaiting file upload...</i></p>", unsafe_allow_html=True)
