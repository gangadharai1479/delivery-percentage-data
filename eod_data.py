import io
import datetime
from datetime import date, timedelta

import pandas as pd
import numpy as np
import requests
import streamlit as st
from nselib import capital_market


# Configure page with custom theme
st.set_page_config(
    page_title="NSE Bhavcopy Viewer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container styling */
    .main-header {
        background: linear-gradient(90deg, #1f4e79, #2e7d32);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        color: white;
    }
    
    .metric-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2e7d32;
        margin: 0.5rem 0;
    }
    
    .filter-section {
        background: #ffffff;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .success-message {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    
    .info-card {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa, #e9ecef);
    }
    
    /* Table styling enhancements */
    .dataframe {
        border: 1px solid #dee2e6;
        border-radius: 5px;
    }
    
    /* Custom button styling */
    .stButton > button {
        background: linear-gradient(90deg, #2e7d32, #388e3c);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: 600;
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #1b5e20, #2e7d32);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Reduce top padding */
    .main .block-container {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# NSE index constituents CSVs
INDEX_URLS = {
    "NIFTY50": "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "NIFTY100": "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "NIFTY200": "https://archives.nseindia.com/content/indices/ind_nifty200list.csv",
    "NIFTY500": "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
}

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_index_members(index_name: str) -> set:
    """Fetch and cache the latest index constituents for the given index."""
    index_key = (index_name or "").upper()
    url = INDEX_URLS.get(index_key)
    if not url:
        return set()
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        resp.raise_for_status()
        df_idx = pd.read_csv(io.StringIO(resp.text))
    except Exception:
        return set()
    
    # Resolve symbol column name
    symbol_col = None
    for c in ["Symbol", "SYMBOL", "symbol"]:
        if c in df_idx.columns:
            symbol_col = c
            break
    if symbol_col is None:
        for c in df_idx.columns:
            if "symbol" in str(c).lower():
                symbol_col = c
                break
    if symbol_col is None:
        return set()
    return set(df_idx[symbol_col].astype(str).str.upper().str.strip())

@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def get_symbol_to_name_map() -> dict:
    """Return mapping SYMBOL -> NAME OF COMPANY from NSE equity master."""
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception:
        return {}
    
    symbol_col = None
    name_col = None
    for col in df.columns:
        low = str(col).lower()
        if symbol_col is None and low.startswith("symbol"):
            symbol_col = col
        if name_col is None and ("name" in low and "company" in low):
            name_col = col
    if not symbol_col or not name_col:
        return {}
    
    df = df[[symbol_col, name_col]].dropna()
    df[symbol_col] = df[symbol_col].astype(str).str.upper().str.strip()
    return dict(zip(df[symbol_col], df[name_col].astype(str)))

# Compact header - reduced padding
st.markdown("""
<div style="background: linear-gradient(90deg, #1f4e79, #2e7d32); padding: 0.8rem; border-radius: 8px; margin-bottom: 1rem;">
    <h2 style="color: white; margin: 0; font-size: 1.8rem;">📈 NSE Bhavcopy Viewer</h2>
    <p style="color: #e8f5e8; margin: 0.2rem 0 0 0; font-size: 0.9rem;">Daily equity stock data from NSE</p>
</div>
""", unsafe_allow_html=True)

# Enhanced sidebar - removed quick select buttons
with st.sidebar:
    st.markdown("## 📅 Date Selection")
    selected_date = st.date_input(
        "Select a trading date",
        value=date.today(),
        max_value=date.today(),
        help="Select a date to fetch Bhavcopy data. Data is typically available after market hours.",
        key="bhavcopy_date_input",
    )
    
    # Add market status indicator
    st.markdown("---")
    st.markdown("### 🕐 Market Status")
    now = datetime.datetime.now()
    if now.weekday() < 5:  # Monday to Friday
        market_time = now.time()
        if datetime.time(9, 15) <= market_time <= datetime.time(15, 30):
            st.success("🟢 Market Open")
        else:
            st.info("🔵 Market Closed")
    else:
        st.error("🔴 Weekend")

# Compact main content area
col_left, col_right = st.columns([4, 1])
with col_left:
    st.markdown(f"### 📊 Bhavcopy Data - {selected_date.strftime('%d %B, %Y')}")
with col_right:
    st.metric("📅 Date", selected_date.strftime('%d-%b-%Y'))

# Compact market hours warning
if selected_date == date.today():
    now = datetime.datetime.now().time()
    market_open = datetime.time(9, 15)
    market_close = datetime.time(15, 30)
    if market_open <= now <= market_close:
        st.warning("⚠️ Market is open. Data may not be available yet.")
    elif now < market_open:
        st.info("ℹ️ Market hasn't opened. Previous day's data shown if available.")

# Fetch and display data
try:
    with st.spinner("🔄 Fetching Bhavcopy data..."):
        qdate = selected_date.strftime('%d-%m-%Y')
        df = capital_market.bhav_copy_with_delivery(qdate)

        if df is None or df.empty:
            # Enhanced error handling
            st.error("❌ **No data available for the selected date.**")
            
            with st.expander("💡 **Troubleshooting Tips**", expanded=True):
                st.markdown("""
                **Possible reasons:**
                - 📅 Selected date is a weekend or market holiday
                - ⏰ Data is not yet available (market may still be open)
                - 🔧 NSE servers are temporarily unavailable
                - 📊 No trading occurred on this date
                """)
                
                if selected_date.weekday() >= 5:
                    prev_working_day = selected_date - timedelta(days=selected_date.weekday() - 4)
                    st.info(f"**Suggestion:** Try selecting {prev_working_day.strftime('%d-%b-%Y')} (Previous Friday)")
                elif selected_date == date.today():
                    prev_day = selected_date - timedelta(days=1)
                    st.info(f"**Suggestion:** Try selecting {prev_day.strftime('%d-%b-%Y')} (Previous day)")
        else:
            # Compact success message
            st.success(f"✅ Fetched data for {len(df)} stocks on {selected_date.strftime('%d-%b-%Y')}")

            # Data transformation
            display_df = pd.DataFrame()
            display_df['Date'] = pd.to_datetime(df['DATE1'], format='%d-%b-%Y').dt.strftime('%d-%m-%Y')
            display_df['Symbol'] = df['SYMBOL']
            
            # Get company names mapping
            symbol_to_name = get_symbol_to_name_map()
            display_df['Company Name'] = (
                display_df['Symbol'].astype(str).str.upper().map(symbol_to_name)
                .fillna(display_df['Symbol'])
            )
            
            display_df['Prev Close'] = df['PREV_CLOSE'].round(2)
            display_df["Close Price"] = df['CLOSE_PRICE'].round(2)
            display_df['% Change'] = (
                (df['CLOSE_PRICE'] - df['PREV_CLOSE']) / df['PREV_CLOSE'] * 100
            ).round(2)
            display_df['Volume'] = df['TTL_TRD_QNTY'].astype(int)
            display_df['Delivered Qty'] = pd.to_numeric(df['DELIV_QTY'], errors='coerce').fillna(0).astype(int)
            display_df['% Delivery'] = pd.to_numeric(df['DELIV_PER'], errors='coerce').fillna(0).round(2)
            display_df['Turnover (₹ Cr)'] = (df['TURNOVER_LACS'] / 100).round(2)
            display_df = display_df.fillna(0)

            # Compact filters section
            st.markdown("### 🔍 Filters")
            
            with st.expander("🎛️ Filter Options", expanded=True):
                f1, f2, f3, f4 = st.columns(4)
                
                with f1:
                    st.markdown("**📈 Price Change**")
                    min_chg = st.slider(
                        "Min %",
                        min_value=float(display_df['% Change'].min()),
                        max_value=float(display_df['% Change'].max()),
                        value=float(display_df['% Change'].min()),
                        step=0.1,
                    )
                    max_chg = st.slider(
                        "Max %",
                        min_value=float(display_df['% Change'].min()),
                        max_value=float(display_df['% Change'].max()),
                        value=float(display_df['% Change'].max()),
                        step=0.1,
                    )
                
                with f2:
                    st.markdown("**📦 Delivery %**")
                    min_del = st.slider(
                        "Min Delivery",
                        min_value=0.0,
                        max_value=100.0,
                        value=0.0,
                        step=1.0,
                    )
                    max_del = st.slider(
                        "Max Delivery",
                        min_value=0.0,
                        max_value=100.0,
                        value=100.0,
                        step=1.0,
                    )
                
                with f3:
                    st.markdown("**📊 Volume**")
                    volume_threshold = st.number_input(
                        "Min Volume",
                        min_value=0,
                        value=0,
                        step=1000,
                        format="%d"
                    )
                    turnover_threshold = st.number_input(
                        "Min Turnover (Cr)",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        format="%.1f"
                    )
                
                with f4:
                    st.markdown("**🎯 Filters**")
                    index_choice = st.selectbox(
                        "Index",
                        options=["All Stocks", "NIFTY50", "NIFTY100", "NIFTY200", "NIFTY500"],
                        index=0,
                    )
                    symbol_filter = st.text_input(
                        "Symbol",
                        placeholder="e.g., RELIANCE",
                        help="Filter by symbol name"
                    )
            
            st.markdown('</div>', unsafe_allow_html=True)

            # Apply filters
            filtered_df = display_df[
                (display_df['% Change'] >= min_chg) &
                (display_df['% Change'] <= max_chg) &
                (display_df['% Delivery'] >= min_del) &
                (display_df['% Delivery'] <= max_del) &
                (display_df['Volume'] >= volume_threshold) &
                (display_df['Turnover (₹ Cr)'] >= turnover_threshold)
            ].copy()
            
            if symbol_filter:
                filtered_df = filtered_df[
                    filtered_df['Symbol'].str.contains(symbol_filter.upper(), na=False)
                ]
            
            if index_choice and index_choice != "All Stocks":
                index_name = index_choice.replace("All Stocks", "")
                members = get_index_members(index_name)
                if members:
                    filtered_df = filtered_df[
                        filtered_df['Symbol'].str.upper().isin(members)
                    ]
                else:
                    st.warning(f"⚠️ Could not fetch {index_choice} constituent list. Showing all stocks.")

            # Compact metrics dashboard
            m1, m2, m3, m4, m5 = st.columns(5)
            
            with m1:
                st.metric("📈 Stocks", f"{len(filtered_df):,}")
            with m2:
                avg_change = filtered_df['% Change'].mean()
                st.metric("📊 Avg Change", f"{avg_change:.1f}%")
            with m3:
                avg_delivery = filtered_df['% Delivery'].mean()
                st.metric("📦 Avg Delivery", f"{avg_delivery:.1f}%")
            with m4:
                total_volume = filtered_df['Volume'].sum()
                st.metric("📊 Volume", f"{total_volume/1e7:.1f}Cr")
            with m5:
                total_turnover = filtered_df['Turnover (₹ Cr)'].sum()
                st.metric("💰 Turnover", f"₹{total_turnover:,.0f}Cr")

            # Enhanced data table
            st.markdown("### 📋 Stock Data Table")
            
            # Pagination and sorting controls
            pc1, pc2, pc3 = st.columns([1, 1, 1])
            with pc1:
                page_size = st.selectbox(
                    "📄 Rows per page", 
                    [25, 50, 100, 200], 
                    index=1,
                    help="Select number of rows to display per page"
                )
            with pc2:
                sort_by = st.selectbox(
                    "🔤 Sort by", 
                    ['% Change', 'Volume', '% Delivery', 'Turnover (₹ Cr)', 'Symbol'],
                    help="Choose column to sort by"
                )
            with pc3:
                sort_order = st.selectbox(
                    "📶 Sort order", 
                    ['Descending', 'Ascending'],
                    help="Choose sort direction"
                )

            # Apply sorting
            ascending = sort_order == 'Ascending'
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

            # Pagination
            total_rows = len(filtered_df)
            num_pages = (total_rows + page_size - 1) // page_size
            
            if num_pages > 1:
                page = st.selectbox(
                    f"📖 Page (1 to {num_pages})", 
                    range(1, num_pages + 1), 
                    index=0,
                    help=f"Navigate through {num_pages} pages of data"
                )
                start_idx = (page - 1) * page_size
                end_idx = min(start_idx + page_size, total_rows)
                page_df = filtered_df.iloc[start_idx:end_idx]
                st.info(f"📄 Showing rows **{start_idx + 1}** to **{end_idx}** of **{total_rows:,}** filtered results")
            else:
                page_df = filtered_df
                st.info(f"📄 Showing all **{total_rows:,}** filtered results")

            # Enhanced dataframe display
            st.dataframe(
                page_df,
                use_container_width=True,
                column_config={
                    "Date": st.column_config.TextColumn(
                        "📅 Date",
                        help="Trading date",
                        width="small"
                    ),
                    "Symbol": st.column_config.TextColumn(
                        "🏷️ Symbol",
                        help="Stock symbol",
                        width="medium"
                    ),
                    "Company Name": st.column_config.TextColumn(
                        "🏢 Company Name",
                        help="Full company name",
                        width="large"
                    ),
                    "Prev Close": st.column_config.NumberColumn(
                        "📊 Prev Close",
                        help="Previous day's closing price",
                        format="₹%.2f"
                    ),
                    "Close Price": st.column_config.NumberColumn(
                        "💰 Close Price",
                        help="Today's closing price",
                        format="₹%.2f"
                    ),
                    "% Change": st.column_config.NumberColumn(
                        "📈 % Change",
                        help="Percentage price change",
                        format="%.2f%%"
                    ),
                    "Volume": st.column_config.NumberColumn(
                        "📊 Volume",
                        help="Total traded volume",
                        format="%,d"
                    ),
                    "Delivered Qty": st.column_config.NumberColumn(
                        "📦 Delivered Qty",
                        help="Delivered quantity",
                        format="%,d"
                    ),
                    "% Delivery": st.column_config.NumberColumn(
                        "📦 % Delivery",
                        help="Delivery percentage",
                        format="%.2f%%"
                    ),
                    "Turnover (₹ Cr)": st.column_config.NumberColumn(
                        "💰 Turnover (₹ Cr)",
                        help="Total turnover in crores",
                        format="₹%.2f"
                    ),
                },
                height=600
            )

            # Enhanced download section
            st.markdown("### 📥 Export Data")
            dl1, dl2, dl3 = st.columns(3)
            
            with dl1:
                csv_data = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📊 Download Filtered CSV",
                    data=csv_data,
                    file_name=f"nse_bhavcopy_filtered_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with dl2:
                full_csv = display_df.to_csv(index=False)
                st.download_button(
                    label="📈 Download Complete CSV",
                    data=full_csv,
                    file_name=f"nse_bhavcopy_complete_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with dl3:
                # Top performers CSV (top 100 by % change)
                top_performers = display_df.nlargest(100, '% Change')
                top_csv = top_performers.to_csv(index=False)
                st.download_button(
                    label="🏆 Download Top 100 Performers",
                    data=top_csv,
                    file_name=f"nse_top_performers_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Summary statistics
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown(f"""
            ### 📊 **Data Summary**
            - **Original Dataset:** {len(display_df):,} stocks  
            - **Filtered Dataset:** {len(filtered_df):,} stocks  
            - **Filter Efficiency:** {(len(filtered_df)/len(display_df)*100):.1f}% of total data
            - **Date:** {selected_date.strftime('%A, %d %B %Y')}
            """)
            st.markdown('</div>', unsafe_allow_html=True)

except Exception as e:
    st.error(f"❌ **Error fetching Bhavcopy data:** {str(e)}")
    
    with st.expander("🔍 **Error Details & Solutions**", expanded=True):
        error_msg = str(e)
        st.code(error_msg)
        
        st.markdown("""
        ### 💡 **Possible Solutions:**
        1. **Check Internet Connection** - Ensure stable internet connectivity
        2. **Try Different Date** - Select a previous trading day
        3. **Server Issues** - NSE servers might be temporarily unavailable
        4. **Library Issues** - nselib package might need updating
        """)

# Enhanced footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; padding: 1.5rem; background: #f8f9fa; border-radius: 10px; margin-top: 1rem;'>
    <h4>📊 NSE Bhavcopy Viewer</h4>
    <p><strong>Data Source:</strong> National Stock Exchange (NSE) via nselib package</p>
    <p><strong>Note:</strong> Bhavcopy data is typically available after market hours (3:30 PM IST)</p>
    <p><em>Made with ❤️ using Streamlit</em></p>
</div>
""", unsafe_allow_html=True)