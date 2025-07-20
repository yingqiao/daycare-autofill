import streamlit as st
import pandas as pd
from io import BytesIO
from google_places import search_daycares
from daycare_scraper_gemini import scrape_daycare_info
from scoring import compute_score, WEIGHTS as DEFAULT_WEIGHTS
from formatter import classify_type, check_msft_discount
import json, os, time
from datetime import datetime

if os.getenv("GEMINI_DEBUG") == "1":
    st.info("🔍 Gemini debug mode is ON. JSON outputs will print to terminal.")

st.set_page_config(page_title="Daycare Research Tool", layout="wide")
st.title("🏛️ Daycare Research Tool - Multi-Stage Workflow")

# Create tabs for the 3 stages
tab1, tab2, tab3 = st.tabs(["🔍 Stage 1: Search & Discovery", "🌐 Stage 2: Website Scraping", "⚖️ Stage 3: Scoring & Analysis"])

# ============================================================================
# STAGE 1: SEARCH & DISCOVERY
# ============================================================================
with tab1:
    st.header("🔍 Stage 1: Search & Discovery")
    st.markdown("""
    **Purpose**: Find daycare providers using Google Places API and export basic information.
    
    **Process**: 
    1. Search for daycares in your area
    2. Get basic info (name, address, phone, website, rating)
    3. Download Excel file for manual review and enhancement
    
    **Your Next Steps**: 
    - Review the Excel file
    - Add additional website URLs (Facebook, social media, etc.)
    - Correct/update website links
    - Remove unwanted providers
    """)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        location = st.text_input("📍 Enter your address", 
                                value="1028 179th PL NE, Bellevue, WA 98008", 
                                help="Full address for accurate distance calculations")
        
    with col2:
        radius_miles = st.slider("Search Radius (miles)", min_value=1, max_value=15, step=1, value=5)
        limit = st.number_input("Max results", min_value=1, max_value=100, value=10)
    
    if st.button("🔍 Search Daycares", type="primary"):
        with st.spinner("🗺️ Searching Google Places API..."):
            try:
                results = search_daycares(location, max_driving_distance_miles=radius_miles, limit=limit)
                
                if not results:
                    st.error("No daycares found. Try increasing the search radius.")
                else:
                    st.success(f"✅ Found {len(results)} daycare providers!")
                    
                    # Load MSFT discount data
                    try:
                        with open("providers_msft.json") as f:
                            msft_list = json.load(f)
                    except FileNotFoundError:
                        msft_list = []
                        st.warning("⚠️ MSFT discount file not found. Discount info will be marked as 'Unknown'.")
                    
                    # Enhance with additional data
                    for row in results:
                        row["Type"] = classify_type(row["Name"])
                        row["MSFT_Discount"] = check_msft_discount(row["Name"], msft_list)
                        # Add placeholder columns for manual enhancement
                        row["Website_2"] = ""
                        row["Website_3"] = ""
                        row["Notes"] = ""
                        row["Priority"] = ""
                        row["Status"] = "Pending Review"
                    
                    # Create DataFrame with proper column order
                    df = pd.DataFrame(results)
                    column_order = [
                        "Name", "Address", "Phone", "Rating", "Distance_Miles", 
                        "Website", "Website_2", "Website_3", "Type", "MSFT_Discount",
                        "Notes", "Priority", "Status"
                    ]
                    df = df.reindex(columns=column_order)
                    
                    # Display results
                    st.dataframe(df, use_container_width=True)
                    
                    # Create Excel download
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    excel_buffer = BytesIO()
                    
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        # Write data with instructions
                        df.to_excel(writer, sheet_name='Daycare_Search_Results', index=False)
                        
                        # Create instructions sheet
                        instructions = pd.DataFrame({
                            'Column': ['Website_2', 'Website_3', 'Notes', 'Priority', 'Status'],
                            'Purpose': [
                                'Add Facebook, Instagram, or other website URLs',
                                'Add additional website URLs if needed',
                                'Your personal notes about this provider',
                                'High/Medium/Low priority for your search',
                                'Keep/Remove/Maybe - your decision'
                            ],
                            'Example': [
                                'https://facebook.com/daycarename',
                                'https://instagram.com/daycarename',
                                'Close to work, good reviews',
                                'High',
                                'Keep'
                            ]
                        })
                        instructions.to_excel(writer, sheet_name='Instructions', index=False)
                    
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Stage 1 Results (Excel)",
                        data=excel_buffer.getvalue(),
                        file_name=f"daycare_search_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Download this file, review and enhance it, then use it in Stage 2"
                    )
                    
                    st.info("📋 **Next Steps**: Download the Excel file, review and enhance the website URLs, then proceed to Stage 2 for comprehensive scraping.")
                    
            except Exception as e:
                st.error(f"❌ Search failed: {str(e)}")

# ============================================================================
# STAGE 2: WEBSITE SCRAPING
# ============================================================================
with tab2:
    st.header("🌐 Stage 2: Website Scraping")
    st.markdown("""
    **Purpose**: Scrape comprehensive information from all website URLs for each provider.
    
    **Process**:
    1. Upload your enhanced Excel file from Stage 1
    2. Comprehensive Gemini scraping for all URLs per provider
    3. Download enriched Excel file with detailed program information
    
    **Your Next Steps**:
    - Review scraped data for accuracy
    - Fill in any missing information manually
    - Prepare for final scoring in Stage 3
    """)
    
    uploaded_file = st.file_uploader(
        "📁 Upload Enhanced Excel from Stage 1", 
        type=['xlsx', 'xls'],
        help="Upload the Excel file you downloaded and enhanced in Stage 1"
    )
    
    if uploaded_file is not None:
        try:
            df_upload = pd.read_excel(uploaded_file, sheet_name='Daycare_Search_Results')
            st.success(f"✅ Loaded {len(df_upload)} providers from Excel file")
            
            # Show preview
            st.subheader("📋 Preview of Loaded Data")
            st.dataframe(df_upload.head(), use_container_width=True)
            
            # Filter options
            col1, col2 = st.columns([1, 1])
            with col1:
                scrape_only_keep = st.checkbox("🎯 Only scrape providers marked as 'Keep'", value=False)
            with col2:
                max_providers = st.number_input("⚡ Max providers to scrape", min_value=1, max_value=len(df_upload), value=min(5, len(df_upload)))
            
            if st.button("🚀 Start Comprehensive Scraping", type="primary"):
                # Filter data if needed
                df_to_scrape = df_upload.copy()
                if scrape_only_keep and 'Status' in df_to_scrape.columns:
                    df_to_scrape = df_to_scrape[df_to_scrape['Status'].str.lower() == 'keep']
                
                df_to_scrape = df_to_scrape.head(max_providers)
                
                if len(df_to_scrape) == 0:
                    st.error("❌ No providers to scrape. Check your filter settings.")
                else:
                    st.info(f"🎯 Scraping {len(df_to_scrape)} providers...")
                    
                    # Initialize progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_container = st.container()
                    
                    # Add columns for scraped data
                    scraped_columns = ["AgesServed", "Mandarin", "MealsProvided", "Curriculum", "CulturalDiversity", "StaffStability"]
                    for col in scraped_columns:
                        if col not in df_to_scrape.columns:
                            df_to_scrape[col] = ""
                    
                    df_to_scrape["Scraping_Status"] = ""
                    df_to_scrape["Scraped_URLs"] = ""
                    df_to_scrape["Last_Updated"] = ""
                    
                    # Scrape each provider
                    for i, (idx, row) in enumerate(df_to_scrape.iterrows()):
                        provider_name = row['Name']
                        status_text.text(f"🌐 Scraping {i+1}/{len(df_to_scrape)}: {provider_name}")
                        
                        try:
                            # Collect all URLs for this provider
                            urls_to_scrape = []
                            for url_col in ['Website', 'Website_2', 'Website_3']:
                                if url_col in row and pd.notna(row[url_col]) and row[url_col].strip():
                                    urls_to_scrape.append(row[url_col].strip())
                            
                            if not urls_to_scrape:
                                df_to_scrape.loc[idx, "Scraping_Status"] = "No URLs"
                                continue
                            
                            # Use enhanced scraping with multiple URLs support
                            scraped_data = scrape_daycare_info(urls_to_scrape, name=provider_name)
                            
                            # Update the dataframe with scraped data
                            for col in scraped_columns:
                                if col in scraped_data:
                                    df_to_scrape.loc[idx, col] = scraped_data[col]
                            
                            df_to_scrape.loc[idx, "Scraping_Status"] = f"Success ({len(urls_to_scrape)} URLs)"
                            df_to_scrape.loc[idx, "Scraped_URLs"] = "; ".join(urls_to_scrape)
                            df_to_scrape.loc[idx, "Last_Updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                        except Exception as e:
                            df_to_scrape.loc[idx, "Scraping_Status"] = f"Error: {str(e)[:50]}"
                        
                        # Update progress
                        progress_bar.progress((i + 1) / len(df_to_scrape))
                        time.sleep(0.5)  # Be respectful to websites
                    
                    status_text.text("✅ Scraping completed!")
                    
                    # Show results
                    st.subheader("📊 Scraping Results")
                    st.dataframe(df_to_scrape, use_container_width=True)
                    
                    # Create download
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    excel_buffer = BytesIO()
                    df_to_scrape.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Stage 2 Results (Scraped Data)",
                        data=excel_buffer.getvalue(),
                        file_name=f"daycare_scraped_{timestamp}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Download this file, review and complete any missing data, then use in Stage 3 for scoring"
                    )
                    
                    # Show summary
                    success_count = len(df_to_scrape[df_to_scrape['Scraping_Status'].str.contains('Success', na=False)])
                    st.metric("✅ Successfully Scraped", f"{success_count}/{len(df_to_scrape)}")
                    
        except Exception as e:
            st.error(f"❌ Error loading Excel file: {str(e)}")

# ============================================================================
# STAGE 3: SCORING & ANALYSIS
# ============================================================================
with tab3:
    st.header("⚖️ Stage 3: Scoring & Analysis")
    st.markdown("""
    **Purpose**: Apply custom scoring weights to generate final rankings and recommendations.
    
    **Process**:
    1. Upload your completed Excel file from Stage 2
    2. Adjust scoring weights based on your priorities
    3. Generate final scored results and rankings
    4. Download final analysis for decision making
    """)
    
    # Scoring weights configuration
    st.subheader("🎯 Configure Scoring Weights")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        mandarin_weight = st.slider("🇨🇳 Mandarin Exposure", 0, 5, DEFAULT_WEIGHTS["Mandarin"])
        meals_weight = st.slider("🍽️ Meals Provided", 0, 5, DEFAULT_WEIGHTS["Meals"])
    
    with col2:
        curriculum_weight = st.slider("📚 Curriculum Quality", 0, 5, DEFAULT_WEIGHTS["Curriculum"])
        staff_weight = st.slider("👥 Staff Stability", 0, 5, DEFAULT_WEIGHTS["Staff Stability"])
    
    with col3:
        diversity_weight = st.slider("🌍 Cultural Diversity", 0, 5, DEFAULT_WEIGHTS["Cultural Diversity"])
        msft_weight = st.slider("💼 MSFT Discount", 0, 5, DEFAULT_WEIGHTS["MSFT Discount"])
    
    user_weights = {
        "Mandarin": mandarin_weight,
        "Meals": meals_weight,
        "Curriculum": curriculum_weight,
        "Staff Stability": staff_weight,
        "Cultural Diversity": diversity_weight,
        "MSFT Discount": msft_weight
    }
    
    # File upload for scoring
    scoring_file = st.file_uploader(
        "📁 Upload Completed Excel from Stage 2", 
        type=['xlsx', 'xls'],
        help="Upload the Excel file with scraped data from Stage 2",
        key="scoring_upload"
    )
    
    if scoring_file is not None:
        try:
            df_scoring = pd.read_excel(scoring_file)
            st.success(f"✅ Loaded {len(df_scoring)} providers for scoring")
            
            if st.button("🎯 Calculate Scores & Rankings", type="primary"):
                # Calculate scores
                for idx, row in df_scoring.iterrows():
                    score = compute_score(row, weights=user_weights)
                    df_scoring.loc[idx, "Final_Score"] = score
                
                # Sort by score (descending)
                df_scoring = df_scoring.sort_values("Final_Score", ascending=False).reset_index(drop=True)
                df_scoring["Rank"] = range(1, len(df_scoring) + 1)
                
                # Reorder columns for better display
                display_columns = ["Rank", "Name", "Final_Score"] + [col for col in df_scoring.columns if col not in ["Rank", "Name", "Final_Score"]]
                df_display = df_scoring[display_columns]
                
                st.subheader("🏆 Final Rankings")
                st.dataframe(df_display, use_container_width=True)
                
                # Show top recommendations
                st.subheader("🌟 Top Recommendations")
                top_3 = df_scoring.head(3)
                for i, (_, row) in enumerate(top_3.iterrows(), 1):
                    with st.expander(f"#{i} - {row['Name']} (Score: {row['Final_Score']:.1f})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Address**: {row.get('Address', 'N/A')}")
                            st.write(f"**Phone**: {row.get('Phone', 'N/A')}")
                            st.write(f"**Rating**: {row.get('Rating', 'N/A')} ⭐")
                            st.write(f"**Distance**: {row.get('Distance_Miles', 'N/A')} miles")
                        with col2:
                            st.write(f"**Ages**: {row.get('AgesServed', 'N/A')}")
                            st.write(f"**Mandarin**: {row.get('Mandarin', 'N/A')}")
                            st.write(f"**Meals**: {row.get('MealsProvided', 'N/A')}")
                            st.write(f"**Curriculum**: {row.get('Curriculum', 'N/A')}")
                
                # Create final download
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                excel_buffer = BytesIO()
                
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    # Main results
                    df_display.to_excel(writer, sheet_name='Final_Rankings', index=False)
                    
                    # Scoring summary
                    scoring_summary = pd.DataFrame({
                        'Criteria': list(user_weights.keys()),
                        'Weight': list(user_weights.values()),
                        'Impact': ['High' if w >= 4 else 'Medium' if w >= 2 else 'Low' for w in user_weights.values()]
                    })
                    scoring_summary.to_excel(writer, sheet_name='Scoring_Weights', index=False)
                
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Final Analysis & Rankings",
                    data=excel_buffer.getvalue(),
                    file_name=f"daycare_final_rankings_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Final ranked results ready for your decision making"
                )
                
                # Show scoring distribution
                st.subheader("📈 Score Distribution")
                score_stats = {
                    "Average Score": f"{df_scoring['Final_Score'].mean():.1f}",
                    "Highest Score": f"{df_scoring['Final_Score'].max():.1f}",
                    "Lowest Score": f"{df_scoring['Final_Score'].min():.1f}",
                    "Score Range": f"{df_scoring['Final_Score'].max() - df_scoring['Final_Score'].min():.1f}"
                }
                
                cols = st.columns(len(score_stats))
                for i, (metric, value) in enumerate(score_stats.items()):
                    cols[i].metric(metric, value)
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: Follow the stages in order for best results. Each stage builds on the previous one to give you comprehensive daycare research and analysis.")
