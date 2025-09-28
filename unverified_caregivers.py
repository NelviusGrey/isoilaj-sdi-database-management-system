
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from hashlib import sha1
import logging

# Set up logging
logger = logging.getLogger(__name__)

UNVERIFIED_EXCEL_PATH = "unverified_caregivers.xlsx"

UNVERIFIED_COLS = [
    "unverified_id",
    "name",
    "status",  # "pending", "verified", "rejected"
    "upload_date",
    "notes",
    "verified_date",
    "verified_by"
]

def generate_unverified_id(name: str) -> str:
    """Generate a unique ID for unverified caregiver"""
    timestamp = datetime.now().isoformat()
    raw = f"{name.strip().lower()}|{timestamp}"
    return sha1(raw.encode("utf-8")).hexdigest()[:12]

def ensure_unverified_excel():
    """Create unverified caregivers Excel file if it doesn't exist"""
    if not os.path.exists(UNVERIFIED_EXCEL_PATH):
        df = pd.DataFrame(columns=UNVERIFIED_COLS)
        with pd.ExcelWriter(UNVERIFIED_EXCEL_PATH, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="unverified_caregivers")

def load_unverified_data():
    """Load unverified caregivers data"""
    try:
        ensure_unverified_excel()
        df = pd.read_excel(UNVERIFIED_EXCEL_PATH, sheet_name="unverified_caregivers")
        
        # Ensure all columns exist
        for col in UNVERIFIED_COLS:
            if col not in df.columns:
                df[col] = None
                
        return df[UNVERIFIED_COLS]
    except Exception as e:
        logger.error(f"Error loading unverified data: {str(e)}")
        st.error(f"Error loading unverified data: {str(e)}")
        return pd.DataFrame(columns=UNVERIFIED_COLS)

def save_unverified_data(df: pd.DataFrame):
    """Save unverified caregivers data"""
    try:
        with pd.ExcelWriter(UNVERIFIED_EXCEL_PATH, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, index=False, sheet_name="unverified_caregivers")
    except Exception as e:
        logger.error(f"Error saving unverified data: {str(e)}")
        st.error(f"Error saving unverified data: {str(e)}")

def process_uploaded_file(uploaded_file):
    """Process uploaded CSV or Excel file"""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Please upload a CSV or Excel file")
            return None
            
        return df
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return None

def render_unverified_caregivers_section():
    """Render the unverified caregivers management section"""
    
    st.markdown("## 📋 Unverified Caregivers Management")
    st.markdown("---")
    
    # Load existing unverified data
    unverified_df = load_unverified_data()
    
    # Create tabs for different functions
    upload_tab, manage_tab, verify_tab = st.tabs(["📤 Upload Names", "📝 Manage List", "✅ Verify & Add"])
    
    with upload_tab:
        st.subheader("📤 Upload Unverified Caregivers")
        st.write("Upload a CSV or Excel file containing caregiver names to add to the unverified list.")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'xls'],
            help="File should contain caregiver names in a column"
        )
        
        if uploaded_file is not None:
            # Process the uploaded file
            upload_df = process_uploaded_file(uploaded_file)
            
            if upload_df is not None:
                st.write("**Preview of uploaded data:**")
                st.dataframe(upload_df.head(), use_container_width=True)
                
                # Let user select which column contains names
                name_columns = upload_df.columns.tolist()
                selected_column = st.selectbox(
                    "Select the column containing caregiver names:",
                    options=name_columns,
                    help="Choose which column contains the caregiver names"
                )
                
                # Preview selected names
                if selected_column:
                    names_preview = upload_df[selected_column].dropna().unique()
                    st.write(f"**Found {len(names_preview)} unique names:**")
                    
                    # Show first 10 names as preview
                    preview_names = names_preview[:10]
                    for i, name in enumerate(preview_names, 1):
                        st.write(f"{i}. {name}")
                    
                    if len(names_preview) > 10:
                        st.write(f"... and {len(names_preview) - 10} more names")
                    
                    # Upload confirmation
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("📥 Add to Unverified List", type="primary"):
                            # Process and add names
                            new_records = []
                            now = datetime.now().isoformat()
                            
                            for name in names_preview:
                                if name and str(name).strip():
                                    clean_name = str(name).strip()
                                    
                                    # Check if name already exists
                                    if not unverified_df[unverified_df['name'].str.lower() == clean_name.lower()].empty:
                                        continue  # Skip duplicates
                                    
                                    new_record = {
                                        "unverified_id": generate_unverified_id(clean_name),
                                        "name": clean_name,
                                        "status": "pending",
                                        "upload_date": now,
                                        "notes": f"Uploaded from {uploaded_file.name}",
                                        "verified_date": None,
                                        "verified_by": None
                                    }
                                    new_records.append(new_record)
                            
                            if new_records:
                                # Add to existing data
                                new_df = pd.DataFrame(new_records)
                                updated_df = pd.concat([unverified_df, new_df], ignore_index=True)
                                save_unverified_data(updated_df)
                                
                                st.success(f"✅ Successfully added {len(new_records)} new names to unverified list!")
                                st.rerun()
                            else:
                                st.warning("⚠️ No new names to add (all names already exist)")
                    
                    with col2:
                        if st.button("🔄 Clear Upload"):
                            st.rerun()
    
    with manage_tab:
        st.subheader("📝 Manage Unverified Caregivers")
        
        if unverified_df.empty:
            st.info("📭 No unverified caregivers found. Upload some names first!")
        else:
            # Filter options
            filter_col1, filter_col2 = st.columns(2)
            
            with filter_col1:
                status_filter = st.selectbox(
                    "Filter by Status:",
                    options=["All", "pending", "verified", "rejected"],
                    index=0
                )
            
            with filter_col2:
                search_name = st.text_input("🔍 Search by name:", "")
            
            # Apply filters
            filtered_df = unverified_df.copy()
            
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df['status'] == status_filter]
            
            if search_name:
                filtered_df = filtered_df[
                    filtered_df['name'].str.contains(search_name, case=False, na=False)
                ]
            
            # Display summary
            st.write(f"**Showing {len(filtered_df)} of {len(unverified_df)} records**")
            
            # Status summary
            status_summary = unverified_df['status'].value_counts()
            summary_col1, summary_col2, summary_col3 = st.columns(3)
            
            with summary_col1:
                pending_count = status_summary.get('pending', 0)
                st.metric("⏳ Pending", pending_count)
            
            with summary_col2:
                verified_count = status_summary.get('verified', 0)
                st.metric("✅ Verified", verified_count)
            
            with summary_col3:
                rejected_count = status_summary.get('rejected', 0)
                st.metric("❌ Rejected", rejected_count)
            
            # Display and edit data
            if not filtered_df.empty:
                st.markdown("---")
                
                # Editable dataframe
                edited_df = st.data_editor(
                    filtered_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "unverified_id": st.column_config.TextColumn("ID", disabled=True, width="small"),
                        "name": st.column_config.TextColumn("Name", width="medium"),
                        "status": st.column_config.SelectboxColumn(
                            "Status",
                            options=["pending", "verified", "rejected"],
                            width="small"
                        ),
                        "upload_date": st.column_config.DatetimeColumn("Upload Date", disabled=True, width="medium"),
                        "notes": st.column_config.TextColumn("Notes", width="large"),
                        "verified_date": st.column_config.DatetimeColumn("Verified Date", disabled=True, width="medium"),
                        "verified_by": st.column_config.TextColumn("Verified By", disabled=True, width="medium")
                    },
                    key="unverified_editor"
                )
                
                # Save changes
                if st.button("💾 Save Changes"):
                    # Update the main dataframe with changes
                    for idx, row in edited_df.iterrows():
                        original_idx = unverified_df[unverified_df['unverified_id'] == row['unverified_id']].index
                        if not original_idx.empty:
                            unverified_df.loc[original_idx[0]] = row
                    
                    save_unverified_data(unverified_df)
                    st.success("✅ Changes saved successfully!")
                    st.rerun()
                
                # Bulk actions
                st.markdown("---")
                st.subheader("🔧 Bulk Actions")
                
                bulk_col1, bulk_col2, bulk_col3 = st.columns(3)
                
                with bulk_col1:
                    if st.button("✅ Mark All Filtered as Verified"):
                        for idx in filtered_df.index:
                            unverified_df.loc[idx, 'status'] = 'verified'
                            unverified_df.loc[idx, 'verified_date'] = datetime.now().isoformat()
                            unverified_df.loc[idx, 'verified_by'] = 'Bulk Action'
                        
                        save_unverified_data(unverified_df)
                        st.success("✅ All filtered caregivers marked as verified!")
                        st.rerun()
                
                with bulk_col2:
                    if st.button("❌ Mark All Filtered as Rejected"):
                        for idx in filtered_df.index:
                            unverified_df.loc[idx, 'status'] = 'rejected'
                            unverified_df.loc[idx, 'verified_date'] = datetime.now().isoformat()
                            unverified_df.loc[idx, 'verified_by'] = 'Bulk Action'
                        
                        save_unverified_data(unverified_df)
                        st.success("❌ All filtered caregivers marked as rejected!")
                        st.rerun()
                
                with bulk_col3:
                    if st.button("🗑️ Delete All Filtered"):
                        unverified_df = unverified_df[~unverified_df.index.isin(filtered_df.index)]
                        save_unverified_data(unverified_df)
                        st.success("🗑️ All filtered caregivers deleted!")
                        st.rerun()
    
    with verify_tab:
        st.subheader("✅ Verify & Add Caregivers")
        st.write("Verify and add caregivers to the main database.")
        
        # Filter for pending caregivers
        pending_df = unverified_df[unverified_df['status'] == 'pending']
        
        if pending_df.empty:
            st.info("📭 No pending caregivers to verify.")
        else:
            st.write(f"**Pending caregivers ({len(pending_df)}):**")
            
            # Display pending caregivers
            for idx, row in pending_df.iterrows():
                with st.expander(f"📋 {row['name']}"):
                    st.write(f"**ID:** {row['unverified_id']}")
                    st.write(f"**Upload Date:** {row['upload_date']}")
                    st.write(f"**Notes:** {row['notes']}")
                    
                    # Verification form
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✅ Verify", key=f"verify_{row['unverified_id']}"):
                            # Update status to verified
                            unverified_df.loc[idx, 'status'] = 'verified'
                            unverified_df.loc[idx, 'verified_date'] = datetime.now().isoformat()
                            unverified_df.loc[idx, 'verified_by'] = 'Manual Verification'
                            
                            save_unverified_data(unverified_df)
                            st.success(f"✅ {row['name']} verified successfully!")
                            st.rerun()
                    
                    with col2:
                        if st.button("❌ Reject", key=f"reject_{row['unverified_id']}"):
                            # Update status to rejected
                            unverified_df.loc[idx, 'status'] = 'rejected'
                            unverified_df.loc[idx, 'verified_date'] = datetime.now().isoformat()
                            unverified_df.loc[idx, 'verified_by'] = 'Manual Verification'
                            
                            save_unverified_data(unverified_df)
                            st.warning(f"❌ {row['name']} rejected!")
                            st.rerun()

def get_unverified_stats():
    """Get statistics for unverified caregivers"""
    try:
        unverified_df = load_unverified_data()
        if unverified_df.empty:
            return {
                'total': 0,
                'pending': 0,
                'verified': 0,
                'rejected': 0
            }
        
        status_counts = unverified_df['status'].value_counts()
        return {
            'total': len(unverified_df),
            'pending': status_counts.get('pending', 0),
            'verified': status_counts.get('verified', 0),
            'rejected': status_counts.get('rejected', 0)
        }
    except Exception as e:
        logger.error(f"Error getting unverified stats: {str(e)}")
        return {
            'total': 0,
            'pending': 0,
            'verified': 0,
            'rejected': 0
        }

def get_unverified_stats():
    """Get statistics for unverified caregivers"""
    try:
        unverified_df = load_unverified_data()
        if unverified_df.empty:
            return {
                'total': 0,
                'pending': 0,
                'verified': 0,
                'rejected': 0
            }
        
        status_counts = unverified_df['status'].value_counts()
        return {
            'total': len(unverified_df),
            'pending': status_counts.get('pending', 0),
            'verified': status_counts.get('verified', 0),
            'rejected': status_counts.get('rejected', 0)
        }
    except Exception as e:
        logger.error(f"Error getting unverified stats: {str(e)}")
        return {
            'total': 0,
            'pending': 0,
            'verified': 0,
            'rejected': 0
        }
