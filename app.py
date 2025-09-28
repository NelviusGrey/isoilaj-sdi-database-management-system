
import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime
from hashlib import sha1
import logging
import traceback
from io import BytesIO
from unverified_caregivers import render_unverified_caregivers_section, get_unverified_stats

# Add PIL import for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

EXCEL_PATH = "caregivers_database.xlsx"

CAREGIVER_COLS = [
    "caregiver_key",       # internal, auto; used to link children
    "caregiver_name",
    "gender",
    "profession",
    "date_of_birth",
    "age",
    "phone_number",
    "address",
    "zonal_leader",
    "bank",
    "account_number",
    "number_of_kids",
    "last_updated"
]

CHILD_COLS = [
    "caregiver_key",       # internal link to caregiver
    "caregiver_name",      # for readability
    "child_name",
    "child_gender",
    "child_phone_number",
    "child_age",
    "child_date_of_birth",
    "child_education_level",
    "child_school_name",   # New column
    "child_class_level",   # New column
    "child_profession",
    "last_updated"
]

def stable_key(name: str, phone: str) -> str:
    name = (name or "").strip().lower()
    phone = "".join(ch for ch in (phone or "") if ch.isdigit())
    raw = f"{name}|{phone}"
    return sha1(raw.encode("utf-8")).hexdigest()[:12] if raw.strip("|") else sha1(os.urandom(16)).hexdigest()[:12]

def validate_phone_number(phone):
    """No phone number validation - accepts anything"""
    return True

def calculate_age(dob):
    """Calculate age from date of birth."""
    if not dob:
        return None
    today = datetime.now().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def ensure_excel():
    if not os.path.exists(EXCEL_PATH):
        cg_df = pd.DataFrame(columns=CAREGIVER_COLS)
        ch_df = pd.DataFrame(columns=CHILD_COLS)
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            cg_df.to_excel(writer, index=False, sheet_name="caregivers")
            ch_df.to_excel(writer, index=False, sheet_name="children")

def load_data():
    try:
        ensure_excel()
        xls = pd.ExcelFile(EXCEL_PATH, engine="openpyxl")
        cg_df = pd.read_excel(xls, sheet_name="caregivers")
        ch_df = pd.read_excel(xls, sheet_name="children")
        
        # ensure columns exist
        for col in CAREGIVER_COLS:
            if col not in cg_df.columns:
                cg_df[col] = None
        for col in CHILD_COLS:
            if col not in ch_df.columns:
                ch_df[col] = None
        
        # Convert date columns to proper datetime format, then to date
        if 'date_of_birth' in cg_df.columns:
            cg_df['date_of_birth'] = pd.to_datetime(cg_df['date_of_birth'], errors='coerce').dt.date
        if 'child_date_of_birth' in ch_df.columns:
            ch_df['child_date_of_birth'] = pd.to_datetime(ch_df['child_date_of_birth'], errors='coerce').dt.date
            
        return cg_df[CAREGIVER_COLS], ch_df[CHILD_COLS]
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Error loading data: {str(e)}")
        # Return empty dataframes as fallback
        return pd.DataFrame(columns=CAREGIVER_COLS), pd.DataFrame(columns=CHILD_COLS)

def save_data(cg_df: pd.DataFrame, ch_df: pd.DataFrame):
    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl", mode="w") as writer:
            cg_df.to_excel(writer, index=False, sheet_name="caregivers")
            ch_df.to_excel(writer, index=False, sheet_name="children")
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Error saving data: {str(e)}")


def migrate_child_phone_numbers():
    """One-time migration to populate empty child phone numbers with caregiver phone numbers"""
    cg_df, ch_df = load_data()

    # Track changes
    updated_count = 0

    # Create a mapping of caregiver_key to phone_number
    caregiver_phones = dict(zip(cg_df['caregiver_key'], cg_df['phone_number']))

    # Update children with empty phone numbers
    for idx, row in ch_df.iterrows():
        child_phone = row.get('child_phone_number')
        caregiver_key = row.get('caregiver_key')

        # Check if child phone is empty/null and caregiver has a phone
        if (pd.isna(child_phone) or str(child_phone).strip() == "") and caregiver_key in caregiver_phones:
            caregiver_phone = caregiver_phones[caregiver_key]
            if caregiver_phone and str(caregiver_phone).strip():
                ch_df.at[idx, 'child_phone_number'] = str(caregiver_phone).strip()
                updated_count += 1

    if updated_count > 0:
        # Save the updated data
        save_data(cg_df, ch_df)
        return updated_count
    return 0


def backup_database():
    """Create a timestamped backup of the database."""
    if not os.path.exists(EXCEL_PATH):
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)

    backup_path = os.path.join(backup_dir, f"caregivers_database_{timestamp}.xlsx")
    try:
        shutil.copy2(EXCEL_PATH, backup_path)
        return backup_path
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        logger.error(traceback.format_exc())
        st.error(f"Error creating backup: {str(e)}")
        return None



st.set_page_config(
    page_title="ISOILAJ SDI - Caregivers & Children Registry", 
    page_icon="🗂️", 
    layout="centered"
)

# Add organization header with logo
logo_path = r"C:\Users\user\OneDrive\Desktop\ISOILAJ SDI\isoilaj logo.png"

# Create header with logo and organization name
header_col1, header_col2 = st.columns([1, 4])

with header_col1:
    if os.path.exists(logo_path) and PIL_AVAILABLE:
        try:
            logo = Image.open(logo_path)
            st.image(logo, width=120)
        except Exception as e:
            st.write("🏢")  # Fallback emoji if image fails to load
    else:
        st.write("🏢")  # Fallback emoji if no PIL or image not found

with header_col2:
    st.markdown("""
    # ISOILAJ SOCIAL DEVELOPMENT INITIATIVE
    ## 🗂️ Caregivers & Children Registry
    """)

st.markdown("---")  # Add a separator line
st.caption("Streamlit app to record caregivers and their children into a single Excel file.")

cg_df, ch_df = load_data()


# Add this right after: cg_df, ch_df = load_data()

# Enhanced sidebar with unverified caregivers info
# Enhanced sidebar with unverified caregivers info
with st.sidebar:
    st.markdown("### 📋 Quick Actions")

    # Expandable unverified caregivers section
    with st.expander("📝 Unverified Caregivers", expanded=False):
        # Get unverified stats
        unverified_stats = get_unverified_stats()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("⏳ Pending", unverified_stats['pending'])
            st.metric("✅ Verified", unverified_stats['verified'])
        with col2:
            st.metric("❌ Rejected", unverified_stats['rejected'])
            st.metric("📊 Total", unverified_stats['total'])

    # Performance info (your existing code)
    if st.checkbox("Show Performance Info", value=False, key="performance_info_checkbox"):
        st.markdown("**Performance Metrics**")
        st.write(f"Caregivers loaded: {len(cg_df)}")
        st.write(f"Children loaded: {len(ch_df)}")
        st.write(f"Unverified total: {unverified_stats['total']}")
        st.write(f"Memory usage: {cg_df.memory_usage(deep=True).sum() + ch_df.memory_usage(deep=True).sum()} bytes")


        st.markdown("---")

    # Data Migration Section
    with st.expander("🔧 Data Migration Tools", expanded=False):
        st.markdown("**Fix Missing Child Phone Numbers**")
        st.write("This will populate empty child phone numbers with their caregiver's phone number.")

        if st.button("🔄 Migrate Child Phone Numbers", type="secondary"):
            with st.spinner("Migrating data..."):
                updated_count = migrate_child_phone_numbers()
                if updated_count > 0:
                    st.success(f"✅ Updated {updated_count} child phone numbers!")
                    st.rerun()  # Refresh to show updated data
                else:
                    st.info("ℹ️ No child phone numbers needed updating.")

# Replace the form section around line 130-180
# Initialize session state for form clearing
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0

with st.form("caregiver_form", clear_on_submit=True):
    st.subheader("Caregiver details")
    c_name = st.text_input("Caregiver Name *", key=f"c_name_{st.session_state.form_key}")

    col1, col2 = st.columns(2)
    with col1:
        c_dob = st.date_input("Date of Birth", value=None, format="YYYY-MM-DD",
                             min_value=datetime(1900, 1, 1),
                             max_value=datetime.now(),
                             key=f"c_dob_{st.session_state.form_key}")
    with col2:
        # If DOB is provided, calculate age as default
        default_age = calculate_age(c_dob) if c_dob else 0
        c_age = st.number_input("Age", min_value=0, max_value=120, step=1,
                               value=default_age if default_age else 0,
                               key=f"c_age_{st.session_state.form_key}")

    c_gender = st.selectbox("Gender", ["", "male", "female"], key=f"c_gender_{st.session_state.form_key}")
    c_prof = st.text_input("Profession", key=f"c_prof_{st.session_state.form_key}")
    c_phone = st.text_input("Phone Number", key=f"c_phone_{st.session_state.form_key}")
    c_address = st.text_area("Address", height=100, help="Enter the full address of the caregiver", key=f"c_address_{st.session_state.form_key}")
    c_zonal_leader = st.text_input("Zonal Leader", help="Enter the name of the zonal leader", key=f"c_zonal_leader_{st.session_state.form_key}")
    



    # Add the new bank fields
    bank_col1, bank_col2 = st.columns(2)
    with bank_col1:
        c_bank = st.text_input("Bank Name", help="Enter the bank name", key=f"c_bank_{st.session_state.form_key}")
    with bank_col2:
        c_account_number = st.text_input("Account Number", help="Enter the account number", key=f"c_account_number_{st.session_state.form_key}")
    
    c_numkids = st.number_input("Number of Kids", min_value=0, step=1, key=f"c_numkids_{st.session_state.form_key}")

    st.markdown("---")
    st.subheader("Children")
    st.write("Add one row per child (leave phone blank if not applicable).")

    # Define class/level options
    class_level_options = [
        "", "Primary 1", "Primary 2", "Primary 3", "Primary 4", "Primary 5", "Primary 6",
        "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3",
        "ND1", "ND2", "HND1", "HND2",
        "100 Level", "200 Level", "300 Level", "400 Level", "500 Level",
        "Dropped-Out", "Temporary Pause", "Wish to Further"
    ]

    child_template = pd.DataFrame([{
        "child_name": "",
        "child_gender": "",
        "child_phone_number": "",
        "child_age": None,
        "child_date_of_birth": None,
        "child_education_level": "",
        "child_school_name": "",
        "child_class_level": "",
        "child_profession": ""
    }])

    edited = st.data_editor(
        child_template,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"children_editor_{st.session_state.form_key}",
        column_config={
            "child_gender": st.column_config.SelectboxColumn(options=["", "male", "female"]),
            "child_age": st.column_config.NumberColumn(min_value=0, max_value=120, step=1),
            "child_date_of_birth": st.column_config.DateColumn(
                format="YYYY-MM-DD",
                min_value=datetime(1900, 1, 1),
                max_value=datetime(2035, 12, 31)
            ),
            "child_education_level": st.column_config.SelectboxColumn(
                options=["", "Pre-primary", "Primary", "Junior Secondary", "O'Level",
                         "Senior Secondary", "Tertiary", "Vocational", "Not in School", "Graduate"]
            ),
            "child_school_name": st.column_config.TextColumn(
                label="School Name",
                help="Enter the name of the school"
            ),
            "child_class_level": st.column_config.SelectboxColumn(
                label="Class/Level",
                options=class_level_options,
                help="Select the current class or level"
            ),
        }
    )

    submitted = st.form_submit_button("💾 Save / Update Caregiver")

if submitted:
    # Basic validation
    if not c_name:
        st.error("Caregiver Name is required.")
        st.stop()

    # Validate children's phone numbers and names
    invalid_child_phones = []
    missing_child_names = []
    for i, r in edited.iterrows():
        name = str(r.get("child_name") or "").strip()
        phone = str(r.get("child_phone_number") or "").strip()

        if not name and (phone or pd.notna(r.get("child_age")) or pd.notna(r.get("child_date_of_birth")) or
                         r.get("child_education_level") or r.get("child_profession")):
            missing_child_names.append(f"Row {i+1}")

        if phone and not validate_phone_number(phone):
            invalid_child_phones.append(f"Row {i+1}: {name or 'Unnamed'}")

    if missing_child_names:
        st.error(f"Child name is required in: {', '.join(missing_child_names)}")
        st.stop()

    if invalid_child_phones:
        st.error(f"Invalid phone number format for: {', '.join(invalid_child_phones)}")
        st.stop()

    # Compute stable key
    key = stable_key(c_name, c_phone)
    now = datetime.utcnow().isoformat()

    # Update the new_row dictionary around line 240
    # Upsert caregiver row - ensure date is properly converted
    new_row = {
        "caregiver_key": key,
        "caregiver_name": c_name.strip(),
        "gender": c_gender or "",
        "profession": c_prof.strip(),
        "date_of_birth": c_dob if c_dob else None,  # Keep as date object
        "age": int(c_age) if pd.notna(c_age) and c_age > 0 else None,
        "phone_number": c_phone.strip(),
        "address": c_address.strip() if c_address else "",
        "zonal_leader": c_zonal_leader.strip() if c_zonal_leader else "",  # Add this line
        "bank": c_bank.strip() if c_bank else "",  # Add this line
        "account_number": c_account_number.strip() if c_account_number else "",  # Add this line
        "number_of_kids": int(c_numkids) if pd.notna(c_numkids) else None,
        "last_updated": now
    }

    # Remove existing caregiver with same key (upsert)
    cg_df = cg_df[cg_df["caregiver_key"] != key]
    cg_df = pd.concat([cg_df, pd.DataFrame([new_row])], ignore_index=True)

    # Update the children row creation section (around line 350-380)
    # Prepare children rows (clean empty rows)
    children_rows = []
    for _, r in edited.iterrows():
        name = str(r.get("child_name") or "").strip()
        if not name:
            continue

        # Handle child date of birth properly
        child_dob = r.get("child_date_of_birth")
        if pd.notna(child_dob):
            if isinstance(child_dob, str):
                child_dob = pd.to_datetime(child_dob).date()
            elif hasattr(child_dob, 'date'):
                child_dob = child_dob.date()
        else:
            child_dob = None

        # Get child phone number, use caregiver's phone if child's is empty
        child_phone_raw = r.get("child_phone_number")
        if pd.isna(child_phone_raw) or str(child_phone_raw).strip() == "":
            child_phone = c_phone.strip()  # Use caregiver's phone number
        else:
            child_phone = str(child_phone_raw).strip()

        child = {
            "caregiver_key": key,
            "caregiver_name": c_name.strip(),
            "child_name": name,
            "child_gender": str(r.get("child_gender") or "").strip(),
            "child_phone_number": child_phone,
            "child_age": int(r.get("child_age")) if pd.notna(r.get("child_age")) else None,
            "child_date_of_birth": child_dob,
            "child_education_level": str(r.get("child_education_level") or "").strip(),
            "child_school_name": str(r.get("child_school_name") or "").strip(),  # New field
            "child_class_level": str(r.get("child_class_level") or "").strip(),  # New field
            "child_profession": str(r.get("child_profession") or "").strip(),
            "last_updated": now
        }
        children_rows.append(child)

    # Remove previous children for this caregiver to avoid duplicates, then add new set
    ch_df = ch_df[ch_df["caregiver_key"] != key]
    if children_rows:
        ch_df = pd.concat([ch_df, pd.DataFrame(children_rows)], ignore_index=True)

    # Save to Excel
    save_data(cg_df, ch_df)
    st.success(f"Saved caregiver '{c_name}' and {len(children_rows)} child(ren).")
    
    # Clear the form by incrementing the form key
    st.session_state.form_key += 1
    st.rerun()  # Refresh the app

    # Add an edit/update section after the main form
    st.markdown("---")
    st.subheader("🔄 Edit Existing Caregiver")

    if not cg_df.empty:
        # Create a searchable dropdown for existing caregivers
        caregiver_options = {}
        for _, row in cg_df.iterrows():
            display_name = f"{row['caregiver_name']} - {row['phone_number'] or 'No phone'}"
            caregiver_options[display_name] = row['caregiver_key']

        selected_caregiver = st.selectbox(
            "Select caregiver to edit:",
            options=[""] + list(caregiver_options.keys()),
            help="Choose a caregiver to edit their information"
        )

        if selected_caregiver:
            selected_key = caregiver_options[selected_caregiver]
            caregiver_data = cg_df[cg_df['caregiver_key'] == selected_key].iloc[0]
            children_data = ch_df[ch_df['caregiver_key'] == selected_key]

            st.info(f"Editing: {caregiver_data['caregiver_name']}")

            # Create edit form with pre-filled data
            with st.form("edit_caregiver_form", clear_on_submit=False):
                st.subheader("Edit Caregiver Details")

                # Pre-fill caregiver data
                edit_name = st.text_input("Caregiver Name *", value=caregiver_data['caregiver_name'])

                col1, col2 = st.columns(2)
                with col1:
                    edit_dob = st.date_input(
                        "Date of Birth",
                        value=caregiver_data['date_of_birth'] if pd.notna(caregiver_data['date_of_birth']) else None,
                        format="YYYY-MM-DD",
                        min_value=datetime(1900, 1, 1),
                        max_value=datetime.now()
                    )
                with col2:
                    default_age = calculate_age(edit_dob) if edit_dob else (
                        caregiver_data['age'] if pd.notna(caregiver_data['age']) else 0)
                    edit_age = st.number_input("Age", min_value=0, max_value=120, step=1,
                                               value=int(default_age) if default_age else 0)

                edit_gender = st.selectbox("Gender", ["", "male", "female"],
                                           index=["", "male", "female"].index(caregiver_data['gender']) if
                                           caregiver_data['gender'] in ["", "male", "female"] else 0)
                edit_prof = st.text_input("Profession", value=caregiver_data['profession'] or "")
                edit_phone = st.text_input("Phone Number", value=caregiver_data['phone_number'] or "")
                edit_address = st.text_area("Address", value=caregiver_data['address'] or "", height=100)
                edit_zonal_leader = st.text_input("Zonal Leader", value=caregiver_data['zonal_leader'] or "")

                # Bank fields
                bank_col1, bank_col2 = st.columns(2)
                with bank_col1:
                    edit_bank = st.text_input("Bank Name", value=caregiver_data['bank'] or "")
                with bank_col2:
                    edit_account_number = st.text_input("Account Number", value=caregiver_data['account_number'] or "")

                edit_numkids = st.number_input("Number of Kids", min_value=0, step=1,
                                               value=int(caregiver_data['number_of_kids']) if pd.notna(
                                                   caregiver_data['number_of_kids']) else 0)

                st.markdown("---")
                st.subheader("Edit Children")

                # Define class/level options for editing
                class_level_options = [
                    "", "Primary 1", "Primary 2", "Primary 3", "Primary 4", "Primary 5", "Primary 6",
                    "JSS1", "JSS2", "JSS3", "SS1", "SS2", "SS3",
                    "ND1", "ND2", "HND1", "HND2",
                    "100 Level", "200 Level", "300 Level", "400 Level", "500 Level",
                    "Dropped-Out", "Temporary Pause", "Wish to Further"
                ]

                # Prepare existing children data for editing
                if not children_data.empty:
                    edit_children_data = children_data[[
                        'child_name', 'child_gender', 'child_phone_number', 'child_age',
                        'child_date_of_birth', 'child_education_level', 'child_school_name',
                        'child_class_level', 'child_profession'
                    ]].copy()

                    # Convert date columns to proper format for display
                    if 'child_date_of_birth' in edit_children_data.columns:
                        edit_children_data['child_date_of_birth'] = pd.to_datetime(
                            edit_children_data['child_date_of_birth'], errors='coerce').dt.date
                else:
                    # Create empty template if no children exist
                    edit_children_data = pd.DataFrame([{
                        "child_name": "",
                        "child_gender": "",
                        "child_phone_number": "",
                        "child_age": None,
                        "child_date_of_birth": None,
                        "child_education_level": "",
                        "child_school_name": "",
                        "child_class_level": "",
                        "child_profession": ""
                    }])

                edited_children = st.data_editor(
                    edit_children_data,
                    num_rows="dynamic",
                    use_container_width=True,
                    hide_index=True,
                    key=f"edit_children_{selected_key}",
                    column_config={
                        "child_gender": st.column_config.SelectboxColumn(options=["", "male", "female"]),
                        "child_age": st.column_config.NumberColumn(min_value=0, max_value=120, step=1),
                        "child_date_of_birth": st.column_config.DateColumn(
                            format="YYYY-MM-DD",
                            min_value=datetime(1900, 1, 1),
                            max_value=datetime(2035, 12, 31)
                        ),
                        "child_education_level": st.column_config.SelectboxColumn(
                            options=["", "Pre-primary", "Primary", "Junior Secondary", "O'Level",
                                     "Senior Secondary", "Tertiary", "Vocational", "Not in School", "Graduate"]
                        ),
                        "child_school_name": st.column_config.TextColumn(
                            label="School Name",
                            help="Enter the name of the school"
                        ),
                        "child_class_level": st.column_config.SelectboxColumn(
                            label="Class/Level",
                            options=class_level_options,
                            help="Select the current class or level"
                        ),
                        "child_profession": st.column_config.TextColumn(
                            label="Profession",
                            help="Enter the child's profession if applicable"
                        ),
                    }
                )

                update_submitted = st.form_submit_button("🔄 Update Caregiver", type="primary")

                if update_submitted:
                    # Validation
                    if not edit_name:
                        st.error("Caregiver Name is required.")
                        st.stop()

                    # Update caregiver data
                    now = datetime.utcnow().isoformat()

                    updated_caregiver = {
                        "caregiver_key": selected_key,
                        "caregiver_name": edit_name.strip(),
                        "gender": edit_gender or "",
                        "profession": edit_prof.strip(),
                        "date_of_birth": edit_dob if edit_dob else None,
                        "age": int(edit_age) if pd.notna(edit_age) and edit_age > 0 else None,
                        "phone_number": edit_phone.strip(),
                        "address": edit_address.strip() if edit_address else "",
                        "zonal_leader": edit_zonal_leader.strip() if edit_zonal_leader else "",
                        "bank": edit_bank.strip() if edit_bank else "",
                        "account_number": edit_account_number.strip() if edit_account_number else "",
                        "number_of_kids": int(edit_numkids) if pd.notna(edit_numkids) else None,
                        "last_updated": now
                    }

                    # Remove old caregiver record and add updated one
                    cg_df = cg_df[cg_df["caregiver_key"] != selected_key]
                    cg_df = pd.concat([cg_df, pd.DataFrame([updated_caregiver])], ignore_index=True)

                    # Update children data
                    updated_children_rows = []
                    for _, r in edited_children.iterrows():
                        name = str(r.get("child_name") or "").strip()
                        if not name:
                            continue

                        # Handle child date of birth properly
                        child_dob = r.get("child_date_of_birth")
                        if pd.notna(child_dob):
                            if isinstance(child_dob, str):
                                child_dob = pd.to_datetime(child_dob).date()
                            elif hasattr(child_dob, 'date'):
                                child_dob = child_dob.date()
                        else:
                            child_dob = None

                        # Get child phone number, use caregiver's phone if child's is empty
                        child_phone_raw = r.get("child_phone_number")
                        if pd.isna(child_phone_raw) or str(child_phone_raw).strip() == "":
                            child_phone = edit_phone.strip()
                        else:
                            child_phone = str(child_phone_raw).strip()

                        child = {
                            "caregiver_key": selected_key,
                            "caregiver_name": edit_name.strip(),
                            "child_name": name,
                            "child_gender": str(r.get("child_gender") or "").strip(),
                            "child_phone_number": child_phone,
                            "child_age": int(r.get("child_age")) if pd.notna(r.get("child_age")) else None,
                            "child_date_of_birth": child_dob,
                            "child_education_level": str(r.get("child_education_level") or "").strip(),
                            "child_school_name": str(r.get("child_school_name") or "").strip(),
                            "child_class_level": str(r.get("child_class_level") or "").strip(),
                            "child_profession": str(r.get("child_profession") or "").strip(),
                            "last_updated": now
                        }
                        updated_children_rows.append(child)



# Add this before displaying the data overview
st.markdown("### 🔍 Search and Filter Data")

# Create filter columns
filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    st.subheader("General Filters")
    search_term = st.text_input("🔍 Search by name", "")
    
with filter_col2:
    st.subheader("Quick Actions")
    if st.button("🔄 Reset All Filters"):
        st.rerun()

# Advanced filters in expandable section
with st.expander("🎛️ Advanced Filters", expanded=False):
    filter_tabs = st.tabs(["Caregiver Filters", "Children Filters"])
    
    with filter_tabs[0]:
        st.write("**Caregiver Filters**")
        cg_filter_col1, cg_filter_col2 = st.columns(2)
        
        with cg_filter_col1:
            # Gender filter
            cg_gender_filter = st.multiselect(
                "Gender",
                options=["male", "female"],
                default=[]
            )
            
            # Age group filter
            cg_age_groups = ["Under 18", "18-29", "30-39", "40-49", "50-59", "60+"]
            cg_age_filter = st.multiselect(
                "Age Group",
                options=cg_age_groups,
                default=[]
            )
        
        with cg_filter_col2:
            # Profession filter
            cg_professions = cg_df['profession'].dropna().unique().tolist()
            cg_profession_filter = st.multiselect(
                "Profession",
                options=sorted([p for p in cg_professions if p.strip()]),
                default=[]
            )
            
            # Zonal leader filter
            cg_zonal_leaders = cg_df['zonal_leader'].dropna().unique().tolist()
            cg_zonal_filter = st.multiselect(
                "Zonal Leader",
                options=sorted([z for z in cg_zonal_leaders if z.strip()]),
                default=[]
            )
    
    with filter_tabs[1]:
        st.write("**Children Filters**")
        ch_filter_col1, ch_filter_col2 = st.columns(2)
        
        with ch_filter_col1:
            # Gender filter
            ch_gender_filter = st.multiselect(
                "Child Gender",
                options=["male", "female"],
                default=[]
            )
            
            # Age group filter
            ch_age_groups = ["0-5", "6-12", "13-17", "18-25", "26+"]
            ch_age_filter = st.multiselect(
                "Child Age Group",
                options=ch_age_groups,
                default=[]
            )
        
        with ch_filter_col2:
            # Education level filter
            ch_education_levels = ch_df['child_education_level'].dropna().unique().tolist()
            ch_education_filter = st.multiselect(
                "Education Level",
                options=sorted([e for e in ch_education_levels if e.strip()]),
                default=[]
            )
            
            # Profession filter
            ch_professions = ch_df['child_profession'].dropna().unique().tolist()
            ch_profession_filter = st.multiselect(
                "Child Profession",
                options=sorted([p for p in ch_professions if p.strip()]),
                default=[]
            )

# Apply filters function
def apply_caregiver_filters(df):
    filtered_df = df.copy()
    
    # Name search
    if search_term:
        filtered_df = filtered_df[filtered_df['caregiver_name'].str.contains(search_term, case=False, na=False)]
    
    # Gender filter
    if cg_gender_filter:
        filtered_df = filtered_df[filtered_df['gender'].isin(cg_gender_filter)]
    
    # Age group filter
    if cg_age_filter:
        def get_age_group(age):
            if pd.isna(age):
                return "Unknown"
            elif age < 18:
                return "Under 18"
            elif age < 30:
                return "18-29"
            elif age < 40:
                return "30-39"
            elif age < 50:
                return "40-49"
            elif age < 60:
                return "50-59"
            else:
                return "60+"
        
        filtered_df['temp_age_group'] = filtered_df['age'].apply(get_age_group)
        filtered_df = filtered_df[filtered_df['temp_age_group'].isin(cg_age_filter)]
        filtered_df = filtered_df.drop('temp_age_group', axis=1)
    
    # Profession filter
    if cg_profession_filter:
        filtered_df = filtered_df[filtered_df['profession'].isin(cg_profession_filter)]
    
    # Zonal leader filter
    if cg_zonal_filter:
        filtered_df = filtered_df[filtered_df['zonal_leader'].isin(cg_zonal_filter)]
    
    return filtered_df

def apply_children_filters(df):
    filtered_df = df.copy()
    
    # Name search
    if search_term:
        filtered_df = filtered_df[
            filtered_df['child_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['caregiver_name'].str.contains(search_term, case=False, na=False)
        ]
    
    # Gender filter
    if ch_gender_filter:
        filtered_df = filtered_df[filtered_df['child_gender'].isin(ch_gender_filter)]
    
    # Age group filter
    if ch_age_filter:
        def get_child_age_group(age):
            if pd.isna(age):
                return "Unknown"
            elif age <= 5:
                return "0-5"
            elif age <= 12:
                return "6-12"
            elif age <= 17:
                return "13-17"
            elif age <= 25:
                return "18-25"
            else:
                return "26+"
        
        filtered_df['temp_age_group'] = filtered_df['child_age'].apply(get_child_age_group)
        filtered_df = filtered_df[filtered_df['temp_age_group'].isin(ch_age_filter)]
        filtered_df = filtered_df.drop('temp_age_group', axis=1)
    
    # Education level filter
    if ch_education_filter:
        filtered_df = filtered_df[filtered_df['child_education_level'].isin(ch_education_filter)]
    
    # Profession filter
    if ch_profession_filter:
        filtered_df = filtered_df[filtered_df['child_profession'].isin(ch_profession_filter)]
    
    return filtered_df

# Apply filters
cg_filtered = apply_caregiver_filters(cg_df)
ch_filtered = apply_children_filters(ch_df)

# Display filter summary
if any([search_term, cg_gender_filter, cg_age_filter, cg_profession_filter, cg_zonal_filter, 
        ch_gender_filter, ch_age_filter, ch_education_filter, ch_profession_filter]):
    st.info(f"📊 Showing {len(cg_filtered)} caregivers and {len(ch_filtered)} children (filtered from {len(cg_df)} caregivers and {len(ch_df)} children)")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Caregivers", "Children", "Download Excel", "Analytics", "Unverified"])

with tab1:
    # Convert date columns to string for display to avoid Arrow conversion issues
    cg_display = cg_filtered.drop(columns=["caregiver_key"]).copy()
    if 'date_of_birth' in cg_display.columns:
        cg_display['date_of_birth'] = cg_display['date_of_birth'].astype(str)
    st.dataframe(cg_display, use_container_width=True)
with tab2:
    # Convert date columns to string for display
    ch_display = ch_filtered.drop(columns=["caregiver_key"]).copy()
    if 'child_date_of_birth' in ch_display.columns:
        ch_display['child_date_of_birth'] = ch_display['child_date_of_birth'].astype(str)
    st.dataframe(ch_display, use_container_width=True)
with tab3:
    st.write("The Excel file contains two sheets: **caregivers** and **children** (linked internally).")
    col1, col2 = st.columns(2)

    with col1:
        if os.path.exists(EXCEL_PATH):
            with open(EXCEL_PATH, "rb") as f:
                st.download_button("⬇️ Download caregivers_database.xlsx", f, file_name="caregivers_database.xlsx")
        else:
            st.info("Excel file will appear here after the first save.")

    with col2:
        if st.button("📦 Create Backup"):
            backup_path = backup_database()
            if backup_path:
                st.success(f"Backup created: {os.path.basename(backup_path)}")
            else:
                st.error("No database file to backup.")

# Analytics tab content goes here...

with tab4:
    st.subheader("📊 Data Analytics")

    if not PLOTLY_AVAILABLE:
        st.info("📊 Install plotly for enhanced analytics: `pip install plotly`")

        # Show basic statistics without plotly
        analytics_col1, analytics_col2 = st.columns(2)

        with analytics_col1:
            if not cg_df.empty:
                st.write("### 👥 Caregiver Statistics")
                st.metric("Total Caregivers", len(cg_df))

                if 'gender' in cg_df.columns:
                    gender_counts = cg_df['gender'].value_counts()
                    st.write("**Gender Distribution:**")
                    for gender, count in gender_counts.items():
                        st.write(f"- {gender.title()}: {count}")

                if 'age' in cg_df.columns and cg_df['age'].notna().any():
                    avg_age = cg_df['age'].mean()
                    st.metric("Average Age", f"{avg_age:.1f} years")

                # Profession distribution
                if 'profession' in cg_df.columns:
                    prof_counts = cg_df['profession'].value_counts().head(5)
                    st.write("**Top 5 Professions:**")
                    for prof, count in prof_counts.items():
                        st.write(f"- {prof}: {count}")

                # Zonal leader distribution
                if 'zonal_leader' in cg_df.columns:
                    zonal_counts = cg_df['zonal_leader'].value_counts().head(5)
                    st.write("**Top 5 Zonal Leaders:**")
                    for zonal, count in zonal_counts.items():
                        st.write(f"- {zonal}: {count}")

        with analytics_col2:
            if not ch_df.empty:
                st.write("### 👶 Children Statistics")
                st.metric("Total Children", len(ch_df))

                if 'child_gender' in ch_df.columns:
                    child_gender_counts = ch_df['child_gender'].value_counts()
                    st.write("**Gender Distribution:**")
                    for gender, count in child_gender_counts.items():
                        st.write(f"- {gender.title()}: {count}")

                if 'child_education_level' in ch_df.columns:
                    # Include "Unknown" for missing education data
                    edu_data = ch_df['child_education_level'].fillna('Unknown')
                    edu_data = edu_data.replace('', 'Unknown')
                    edu_counts = edu_data.value_counts().head(7)
                    st.write("**Education Level Distribution:**")
                    for edu, count in edu_counts.items():
                        st.write(f"- {edu}: {count}")

                if 'child_age' in ch_df.columns and ch_df['child_age'].notna().any():
                    avg_child_age = ch_df['child_age'].mean()
                    st.metric("Average Child Age", f"{avg_child_age:.1f} years")

    else:
        # Enhanced analytics with plotly
        analytics_tabs = st.tabs(["📈 Overview", "👥 Caregivers", "👶 Children", "🔗 Relationships", "📈 Advanced Insights", "👨‍👩‍👧‍👦 Family Structure Analysis"])

        with analytics_tabs[0]:
            # Add custom CSS for better styling
            st.markdown("""
            <style>
            .metric-container {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1rem;
                border-radius: 10px;
                color: white;
                text-align: center;
                margin: 0.5rem 0;
            }
            .metric-value {
                font-size: 2rem;
                font-weight: bold;
                margin: 0;
            }
            .metric-label {
                font-size: 0.9rem;
                opacity: 0.9;
                margin: 0;
            }
            </style>
            """, unsafe_allow_html=True)

            # Overview metrics with enhanced styling
            st.markdown("### 📊 Key Metrics")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(f"""
                <div class="metric-container">
                    <p class="metric-value">{len(cg_df)}</p>
                    <p class="metric-label">Total Caregivers</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div class="metric-container">
                    <p class="metric-value">{len(ch_df)}</p>
                    <p class="metric-label">Total Children</p>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                avg_children_per_caregiver = len(ch_df) / len(cg_df) if len(cg_df) > 0 else 0
                st.markdown(f"""
                <div class="metric-container">
                    <p class="metric-value">{avg_children_per_caregiver:.1f}</p>
                    <p class="metric-label">Avg Children/Caregiver</p>
                </div>
                """, unsafe_allow_html=True)

            with col4:
                if 'age' in cg_df.columns and cg_df['age'].notna().any():
                    avg_caregiver_age = cg_df['age'].mean()
                    age_display = f"{avg_caregiver_age:.1f}"
                else:
                    age_display = "N/A"
                st.markdown(f"""
                <div class="metric-container">
                    <p class="metric-value">{age_display}</p>
                    <p class="metric-label">Avg Caregiver Age</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # Quick summary charts with improved styling
            if not cg_df.empty and not ch_df.empty:
                summary_col1, summary_col2 = st.columns(2)

                with summary_col1:
                    # Caregiver gender pie chart with better colors
                    if 'gender' in cg_df.columns and cg_df['gender'].notna().any():
                        gender_data = cg_df['gender'].fillna('Unknown')
                        gender_data = gender_data.replace('', 'Unknown')
                        gender_counts = gender_data.value_counts().reset_index()
                        gender_counts.columns = ['Gender', 'Count']

                        fig_gender = px.pie(
                            gender_counts,
                            values='Count',
                            names='Gender',
                            title="🚻 Caregiver Gender Distribution",
                            color_discrete_map={
                                'male': '#3498db',
                                'female': '#e74c3c',
                                'Unknown': '#95a5a6'
                            }
                        )
                        fig_gender.update_traces(textposition='inside', textinfo='percent+label')
                        fig_gender.update_layout(
                            font=dict(size=12),
                            title_font_size=16,
                            showlegend=True
                        )
                        st.plotly_chart(fig_gender, use_container_width=True)

                with summary_col2:
                    # Children education level with improved handling
                    if 'child_education_level' in ch_df.columns:
                        edu_data = ch_df['child_education_level'].fillna('Unknown')
                        edu_data = edu_data.replace('', 'Unknown')
                        edu_counts = edu_data.value_counts().head(8).reset_index()
                        edu_counts.columns = ['Education Level', 'Count']

                        # Custom color palette
                        colors = px.colors.qualitative.Set3

                        fig_edu = px.bar(
                            edu_counts,
                            x='Count',
                            y='Education Level',
                            orientation='h',
                            title="🎓 Children Education Levels",
                            color='Education Level',
                            color_discrete_sequence=colors
                        )
                        fig_edu.update_layout(
                            showlegend=False,
                            font=dict(size=11),
                            title_font_size=16,
                            yaxis={'categoryorder': 'total ascending'}
                        )
                        st.plotly_chart(fig_edu, use_container_width=True)

        with analytics_tabs[1]:
            st.subheader("👥 Caregiver Analytics")

            caregiver_chart_col1, caregiver_chart_col2 = st.columns(2)

            with caregiver_chart_col1:
                # Age distribution histogram with better styling
                if not cg_df.empty and cg_df['age'].notna().any():
                    fig_age_hist = px.histogram(
                        cg_df[cg_df['age'].notna()],
                        x="age",
                        title="📊 Age Distribution of Caregivers",
                        labels={"age": "Age", "count": "Number of Caregivers"},
                        nbins=20,
                        color_discrete_sequence=['#2ecc71']
                    )
                    fig_age_hist.update_layout(
                        showlegend=False,
                        title_font_size=16,
                        xaxis_title_font_size=14,
                        yaxis_title_font_size=14
                    )
                    fig_age_hist.update_traces(opacity=0.8)
                    st.plotly_chart(fig_age_hist, use_container_width=True)

                # Profession distribution with improved handling
                if 'profession' in cg_df.columns:
                    prof_data = cg_df['profession'].fillna('Unknown')
                    prof_data = prof_data.replace('', 'Unknown')
                    prof_counts = prof_data.value_counts().head(10).reset_index()
                    prof_counts.columns = ['Profession', 'Count']

                    fig_prof = px.bar(
                        prof_counts,
                        x='Count',
                        y='Profession',
                        orientation='h',
                        title="💼 Top 10 Caregiver Professions",
                        color='Count',
                        color_continuous_scale='viridis'
                    )
                    fig_prof.update_layout(
                        title_font_size=16,
                        yaxis={'categoryorder': 'total ascending'}
                    )
                    st.plotly_chart(fig_prof, use_container_width=True)

            with caregiver_chart_col2:
                # Age group distribution with better categories
                if not cg_df.empty and cg_df['age'].notna().any():
                    def age_group(age):
                        if pd.isna(age):
                            return "Unknown"
                        elif age < 18:
                            return "Under 18"
                        elif age < 30:
                            return "18-29"
                        elif age < 40:
                            return "30-39"
                        elif age < 50:
                            return "40-49"
                        elif age < 60:
                            return "50-59"
                        else:
                            return "60+"

                    cg_temp = cg_df.copy()
                    cg_temp['age_group'] = cg_temp['age'].apply(age_group)
                    age_group_counts = cg_temp['age_group'].value_counts().reset_index()
                    age_group_counts.columns = ['Age Group', 'Count']

                    # Sort by age group in logical order
                    age_order = ["Under 18", "18-29", "30-39", "40-49", "50-59", "60+", "Unknown"]
                    age_group_counts['Age Group'] = pd.Categorical(
                        age_group_counts['Age Group'],
                        categories=age_order,
                        ordered=True
                    )
                    age_group_counts = age_group_counts.sort_values('Age Group')

                    fig_age_group = px.bar(
                        age_group_counts,
                        x='Age Group',
                        y='Count',
                        title="Caregivers by Age Group",
                        color='Age Group',
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig_age_group.update_layout(showlegend=False)
                    st.plotly_chart(fig_age_group, use_container_width=True)

                # Zonal leader distribution
                if 'zonal_leader' in cg_df.columns and cg_df['zonal_leader'].notna().any():
                    zonal_counts = cg_df['zonal_leader'].value_counts().head(10).reset_index()
                    zonal_counts.columns = ['Zonal Leader', 'Count']
                    fig_zonal = px.bar(
                        zonal_counts,
                        x='Zonal Leader',
                        y='Count',
                        title="Top 10 Zonal Leaders by Caregiver Count",
                        color='Count',
                        color_continuous_scale='plasma'
                    )
                    fig_zonal.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_zonal, use_container_width=True)

        with analytics_tabs[2]:
            st.subheader("👶 Children Analytics")
            
            children_chart_col1, children_chart_col2 = st.columns(2)
            
            with children_chart_col1:
                # Children age distribution
                if not ch_df.empty and ch_df['child_age'].notna().any():
                    fig_child_age = px.histogram(
                        ch_df[ch_df['child_age'].notna()],
                        x="child_age",
                        title="Age Distribution of Children",
                        labels={"child_age": "Age", "count": "Number of Children"},
                        nbins=25,
                        color_discrete_sequence=['#f39c12']
                    )
                    fig_child_age.update_layout(showlegend=False)
                    st.plotly_chart(fig_child_age, use_container_width=True)

                # Children gender distribution
                if 'child_gender' in ch_df.columns and ch_df['child_gender'].notna().any():
                    child_gender_counts = ch_df['child_gender'].value_counts().reset_index()
                    child_gender_counts.columns = ['Gender', 'Count']
                    fig_child_gender = px.pie(
                        child_gender_counts,
                        values='Count',
                        names='Gender',
                        title="Children Gender Distribution",
                        color_discrete_map={'male': '#3498db', 'female': '#e74c3c'}
                    )
                    st.plotly_chart(fig_child_gender, use_container_width=True)

            with children_chart_col2:
                # Children education level distribution
                if 'child_education_level' in ch_df.columns and ch_df['child_education_level'].notna().any():
                    edu_counts = ch_df['child_education_level'].value_counts().head(8).reset_index()
                    edu_counts.columns = ['Education Level', 'Count']
                    fig_edu = px.bar(
                        edu_counts,
                        x='Education Level',
                        y='Count',
                        title="Top 8 Children Education Levels",
                        color='Count',
                        color_continuous_scale='Blues'
                    )
                    fig_edu.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_edu, use_container_width=True)

                # Children profession distribution
                if 'child_profession' in ch_df.columns and ch_df['child_profession'].notna().any():
                    prof_counts = ch_df['child_profession'].value_counts().head(8).reset_index()
                    prof_counts.columns = ['Profession', 'Count']
                    fig_prof = px.bar(
                        prof_counts,
                        x='Profession',
                        y='Count',
                        title="Top 8 Children Professions",
                        color='Count',
                        color_continuous_scale='Reds'
                    )
                    fig_prof.update_xaxes(tickangle=45)
                    st.plotly_chart(fig_prof, use_container_width=True)

        # Add this content to the empty "Relationships" tab (around line 900-950):

        with analytics_tabs[3]:  # Relationships tab
            st.subheader("🔗 Caregiver-Children Relationships")

            if not cg_df.empty and not ch_df.empty:
                # Create relationship metrics
                rel_col1, rel_col2, rel_col3 = st.columns(3)

                with rel_col1:
                    # Caregivers with no children
                    caregivers_with_children = ch_df['caregiver_key'].unique()
                    caregivers_without_children = len(cg_df[~cg_df['caregiver_key'].isin(caregivers_with_children)])

                    st.markdown(f"""
                    <div class="metric-container">
                        <p class="metric-value">{caregivers_without_children}</p>
                        <p class="metric-label">Caregivers with No Children</p>
                    </div>
                    """, unsafe_allow_html=True)

                with rel_col2:
                    # Average children per caregiver
                    children_per_caregiver = ch_df.groupby('caregiver_key').size()
                    avg_children = children_per_caregiver.mean() if len(children_per_caregiver) > 0 else 0

                    st.markdown(f"""
                    <div class="metric-container">
                        <p class="metric-value">{avg_children:.1f}</p>
                        <p class="metric-label">Avg Children per Active Caregiver</p>
                    </div>
                    """, unsafe_allow_html=True)

                with rel_col3:
                    # Max children for one caregiver
                    max_children = children_per_caregiver.max() if len(children_per_caregiver) > 0 else 0

                    st.markdown(f"""
                    <div class="metric-container">
                        <p class="metric-value">{max_children}</p>
                        <p class="metric-label">Max Children per Caregiver</p>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("---")

                # Charts section
                rel_chart_col1, rel_chart_col2 = st.columns(2)

                with rel_chart_col1:
                    # Distribution of children per caregiver
                    if len(children_per_caregiver) > 0:
                        children_dist = children_per_caregiver.value_counts().sort_index().reset_index()
                        children_dist.columns = ['Number of Children', 'Number of Caregivers']

                        fig_children_dist = px.bar(
                            children_dist,
                            x='Number of Children',
                            y='Number of Caregivers',
                            title="📊 Distribution: Children per Caregiver",
                            color='Number of Caregivers',
                            color_continuous_scale='blues'
                        )
                        fig_children_dist.update_layout(
                            showlegend=False,
                            title_font_size=16
                        )
                        st.plotly_chart(fig_children_dist, use_container_width=True)

                with rel_chart_col2:
                    # Age gap analysis between caregivers and their children
                    if 'age' in cg_df.columns and 'child_age' in ch_df.columns:
                        # Merge caregiver and children data
                        merged_data = ch_df.merge(
                            cg_df[['caregiver_key', 'age', 'caregiver_name']],
                            on='caregiver_key',
                            how='left'
                        )

                        # Calculate age gaps where both ages are available
                        valid_ages = merged_data[
                            merged_data['age'].notna() &
                            merged_data['child_age'].notna()
                        ].copy()

                        if not valid_ages.empty:
                            valid_ages['age_gap'] = valid_ages['age'] - valid_ages['child_age']

                            fig_age_gap = px.histogram(
                                valid_ages,
                                x='age_gap',
                                title="👥 Age Gap: Caregiver vs Children",
                                labels={'age_gap': 'Age Gap (years)', 'count': 'Frequency'},
                                nbins=20,
                                color_discrete_sequence=['#e74c3c']
                            )
                            fig_age_gap.update_layout(
                                showlegend=False,
                                title_font_size=16
                            )
                            st.plotly_chart(fig_age_gap, use_container_width=True)

                st.markdown("---")

                # Detailed relationship table
                st.subheader("📋 Detailed Caregiver-Children Relationships")

                # Create summary table
                relationship_summary = []
                for _, caregiver in cg_df.iterrows():
                    caregiver_children = ch_df[ch_df['caregiver_key'] == caregiver['caregiver_key']]

                    relationship_summary.append({
                        'Caregiver Name': caregiver['caregiver_name'],
                        'Caregiver Age': caregiver['age'] if pd.notna(caregiver['age']) else 'Unknown',
                        'Caregiver Gender': caregiver['gender'].title() if caregiver['gender'] else 'Unknown',
                        'Number of Children': len(caregiver_children),
                        'Children Names': ', '.join(caregiver_children['child_name'].tolist()) if len(caregiver_children) > 0 else 'No children',
                        'Children Ages': ', '.join([str(age) for age in caregiver_children['child_age'].dropna().tolist()]) if len(caregiver_children) > 0 else 'N/A',
                        'Zonal Leader': caregiver['zonal_leader'] if caregiver['zonal_leader'] else 'Unknown'
                    })

                relationship_df = pd.DataFrame(relationship_summary)

                # Add filters for the relationship table
                rel_filter_col1, rel_filter_col2 = st.columns(2)

                with rel_filter_col1:
                    min_children = st.slider("Minimum number of children", 0, 10, 0)

                with rel_filter_col2:
                    max_children = st.slider("Maximum number of children", 0, 20, 20)

                # Apply filters
                filtered_relationships = relationship_df[
                    (relationship_df['Number of Children'] >= min_children) &
                    (relationship_df['Number of Children'] <= max_children)
                ]

                st.dataframe(filtered_relationships, use_container_width=True)

                # Export relationship data
                if st.button("📤 Export Relationship Summary"):
                    csv = filtered_relationships.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "⬇️ Download Relationship Summary CSV",
                        csv,
                        file_name="caregiver_children_relationships.csv",
                        mime="text/csv"
                    )

                # Insights section
                st.markdown("---")
                st.subheader("💡 Relationship Insights")

                insights_col1, insights_col2 = st.columns(2)

                with insights_col1:
                    st.write("**Key Statistics:**")
                    total_caregivers = len(cg_df)
                    caregivers_with_kids = len(relationship_df[relationship_df['Number of Children'] > 0])

                    st.write(f"• {caregivers_with_kids}/{total_caregivers} caregivers have registered children ({(caregivers_with_kids/total_caregivers*100):.1f}%)")

                    if len(children_per_caregiver) > 0:
                        most_children = children_per_caregiver.max()
                        caregiver_with_most = cg_df[cg_df['caregiver_key'] == children_per_caregiver.idxmax()]['caregiver_name'].iloc[0]
                        st.write(f"• {caregiver_with_most} has the most children ({most_children})")

                with insights_col2:
                    st.write("**Recommendations:**")
                    if caregivers_without_children > 0:
                        st.write(f"• Follow up with {caregivers_without_children} caregivers who haven't registered children")

                    if len(children_per_caregiver) > 0:
                        single_child_caregivers = len(children_per_caregiver[children_per_caregiver == 1])
                        st.write(f"• {single_child_caregivers} caregivers have only one registered child")

            else:
                st.info("No relationship data available. Add caregivers and children to see relationship analytics.")

        # Add this new tab to your analytics section:

with analytics_tabs[4]:  # Add a new "📈 Advanced Insights" tab
    st.subheader("📈 Advanced Analytics & Insights")

    # Time-based analysis
    if 'last_updated' in cg_df.columns:
        st.markdown("##### 📅 Registration Trends Over Time")

        # Convert last_updated to datetime
        cg_df_temp = cg_df.copy()
        cg_df_temp['registration_date'] = pd.to_datetime(cg_df_temp['last_updated']).dt.date

        # Daily registrations
        daily_reg = cg_df_temp.groupby('registration_date').size().reset_index()
        daily_reg.columns = ['Date', 'New Registrations']

        # Cumulative registrations
        daily_reg['Cumulative Registrations'] = daily_reg['New Registrations'].cumsum()

        trend_col1, trend_col2 = st.columns(2)

        with trend_col1:
            fig_daily = px.line(daily_reg, x='Date', y='New Registrations',
                               title='📊 Daily Registration Trends')
            st.plotly_chart(fig_daily, use_container_width=True)

        with trend_col2:
            fig_cumulative = px.line(daily_reg, x='Date', y='Cumulative Registrations',
                                   title='📈 Cumulative Registrations')
            st.plotly_chart(fig_cumulative, use_container_width=True)

    st.markdown("---")

with tab5:
    render_unverified_caregivers_section()






    # Geographic insights
    if 'address' in cg_df.columns and cg_df['address'].notna().any():
        st.markdown("### 🗺️ Geographic Distribution")

        # Extract cities/areas from addresses (simple keyword extraction)
        addresses = cg_df['address'].dropna().str.lower()

        # Common Nigerian cities/areas for pattern matching
        cities = ['lagos', 'abuja', 'kano', 'ibadan', 'port harcourt', 'benin', 'kaduna',
                 'jos', 'ilorin', 'aba', 'onitsha', 'warri', 'calabar', 'uyo', 'enugu', 'Isolo', 'Ilasamaja']

        city_counts = {}
        for city in cities:
            count = addresses.str.contains(city, na=False).sum()
            if count > 0:
                city_counts[city.title()] = count

        if city_counts:
            city_df = pd.DataFrame(list(city_counts.items()), columns=['City', 'Count'])
            city_df = city_df.sort_values('Count', ascending=False).head(10)

            fig_cities = px.bar(city_df, x='City', y='Count',
                              title='🏙️ Top Cities by Caregiver Count',
                              color='Count', color_continuous_scale='viridis')
            fig_cities.update_xaxes(tickangle=45)
            st.plotly_chart(fig_cities, use_container_width=True)

    st.markdown("---")




with analytics_tabs[5]:  # Family Structure Analysis tab
            st.subheader("👨‍👩‍👧‍👦 Family Structure Analysis")

            family_col1, family_col2 = st.columns(2)

            with family_col1:
                # Children age distribution by caregiver age groups
                if 'age' in cg_df.columns and 'child_age' in ch_df.columns:
                    merged_family = ch_df.merge(cg_df[['caregiver_key', 'age']], on='caregiver_key')

                    # Create caregiver age groups
                    def caregiver_age_group(age):
                        if pd.isna(age): return "Unknown"
                        elif age < 30: return "Under 30"
                        elif age < 40: return "30-39"
                        elif age < 50: return "40-49"
                        else: return "50+"

                    merged_family['caregiver_age_group'] = merged_family['age'].apply(caregiver_age_group)

                    fig_family_age = px.box(merged_family, x='caregiver_age_group', y='child_age',
                                          title='👶 Children Age Distribution by Caregiver Age Group',
                                          color='caregiver_age_group',
                                          color_discrete_sequence=px.colors.qualitative.Set2)
                    fig_family_age.update_layout(showlegend=False)
                    st.plotly_chart(fig_family_age, use_container_width=True)

            with family_col2:
                # Education progression analysis
                if 'child_education_level' in ch_df.columns and 'child_age' in ch_df.columns:
                    edu_age_data = ch_df[ch_df['child_education_level'].notna() & ch_df['child_age'].notna()]

                    if not edu_age_data.empty:
                        fig_edu_age = px.scatter(edu_age_data, x='child_age', y='child_education_level',
                                               title='🎓 Education Level vs Age',
                                               color='child_education_level',
                                               size_max=15,
                                               opacity=0.7)
                        fig_edu_age.update_yaxes(categoryorder='array',
                                               categoryarray=['Pre-primary', 'Primary', 'Junior Secondary',
                                                            'O\'Level', 'Senior Secondary', 'Tertiary'])
                        fig_edu_age.update_layout(showlegend=False)
                        st.plotly_chart(fig_edu_age, use_container_width=True)

            # Add these new family structure charts:
            st.markdown("#### 📊 Additional Family Insights")

            family_row2_col1, family_row2_col2 = st.columns(2)

            with family_row2_col1:
                # Family size distribution
                if not ch_df.empty:
                    family_sizes = ch_df.groupby('caregiver_key').size().reset_index()
                    family_sizes.columns = ['caregiver_key', 'family_size']

                    # Add caregivers with no children
                    caregivers_with_children = set(ch_df['caregiver_key'].unique())
                    all_caregivers = set(cg_df['caregiver_key'].unique())
                    caregivers_no_children = all_caregivers - caregivers_with_children

                    # Add zero-child families
                    for caregiver_key in caregivers_no_children:
                        family_sizes = pd.concat([family_sizes, pd.DataFrame([{
                            'caregiver_key': caregiver_key,
                            'family_size': 0
                        }])], ignore_index=True)

                    family_size_dist = family_sizes['family_size'].value_counts().sort_index().reset_index()
                    family_size_dist.columns = ['Number of Children', 'Number of Families']

                    fig_family_size = px.bar(family_size_dist, x='Number of Children', y='Number of Families',
                                            title='👨‍👩‍👧‍👦 Family Size Distribution',
                                            color='Number of Families',
                                            color_continuous_scale='viridis',
                                            text='Number of Families')
                    fig_family_size.update_traces(texttemplate='%{text}', textposition='outside')
                    fig_family_size.update_layout(showlegend=False)
                    st.plotly_chart(fig_family_size, use_container_width=True)

            with family_row2_col2:
                # Gender distribution across families
                if 'child_gender' in ch_df.columns and ch_df['child_gender'].notna().any():
                    gender_by_family = ch_df.groupby('caregiver_key')['child_gender'].value_counts().unstack(fill_value=0)

                    if 'male' in gender_by_family.columns and 'female' in gender_by_family.columns:
                        gender_by_family['total'] = gender_by_family['male'] + gender_by_family['female']
                        gender_by_family['male_ratio'] = gender_by_family['male'] / gender_by_family['total']

                        fig_gender_ratio = px.histogram(gender_by_family, x='male_ratio',
                                                      title='⚖️ Male-Female Ratio Distribution in Families',
                                                      labels={'male_ratio': 'Proportion of Male Children', 'count': 'Number of Families'},
                                                      nbins=10,
                                                      color_discrete_sequence=['#3498db'])
                        fig_gender_ratio.update_layout(showlegend=False)
                        st.plotly_chart(fig_gender_ratio, use_container_width=True)

            # Add third row of family insights
            st.markdown("#### 🔍 Detailed Family Patterns")

            family_row3_col1, family_row3_col2 = st.columns(2)

            with family_row3_col1:
                # Age gap analysis between caregivers and children
                if 'age' in cg_df.columns and 'child_age' in ch_df.columns:
                    merged_age_data = ch_df.merge(cg_df[['caregiver_key', 'age']], on='caregiver_key')
                    valid_ages = merged_age_data[
                        merged_age_data['age'].notna() &
                        merged_age_data['child_age'].notna()
                    ].copy()

                    if not valid_ages.empty:
                        valid_ages['age_gap'] = valid_ages['age'] - valid_ages['child_age']

                        fig_age_gap = px.histogram(valid_ages, x='age_gap',
                                                 title='👥 Age Gap: Caregiver vs Children',
                                                 labels={'age_gap': 'Age Gap (years)', 'count': 'Frequency'},
                                                 nbins=20,
                                                 color_discrete_sequence=['#e74c3c'])
                        fig_age_gap.add_vline(x=valid_ages['age_gap'].mean(),
                                            line_dash="dash",
                                            line_color="green",
                                            annotation_text=f"Avg: {valid_ages['age_gap'].mean():.1f} years")
                        fig_age_gap.update_layout(showlegend=False)
                        st.plotly_chart(fig_age_gap, use_container_width=True)

            with family_row3_col2:
                # Children per caregiver by gender
                if 'gender' in cg_df.columns and not ch_df.empty:
                    caregiver_children_count = ch_df.groupby('caregiver_key').size().reset_index()
                    caregiver_children_count.columns = ['caregiver_key', 'children_count']

                    # Merge with caregiver gender
                    gender_children = caregiver_children_count.merge(
                        cg_df[['caregiver_key', 'gender']],
                        on='caregiver_key'
                    )

                    if not gender_children.empty and gender_children['gender'].notna().any():
                        fig_gender_children = px.box(gender_children, x='gender', y='children_count',
                                                   title='👨‍👩‍👧‍👦 Children Count by Caregiver Gender',
                                                   color='gender',
                                                   color_discrete_map={'male': '#3498db', 'female': '#e91e63'})
                        fig_gender_children.update_layout(showlegend=False)
                        st.plotly_chart(fig_gender_children, use_container_width=True)

            # Continue with all other family analysis sections...
            # (Add the remaining sections with proper indentation)

# Add fourth row for profession and education insights
st.markdown("#### 💼 Professional & Educational Patterns")

family_row4_col1, family_row4_col2 = st.columns(2)

with family_row4_col1:
    # Children education level by caregiver profession
    if 'profession' in cg_df.columns and 'child_education_level' in ch_df.columns:
        prof_edu_data = ch_df.merge(cg_df[['caregiver_key', 'profession']], on='caregiver_key')
        prof_edu_clean = prof_edu_data[
            prof_edu_data['profession'].notna() &
            prof_edu_data['child_education_level'].notna() &
            (prof_edu_data['profession'] != '')
        ]

        if not prof_edu_clean.empty:
            # Get top 5 professions
            top_professions = prof_edu_clean['profession'].value_counts().head(5).index
            prof_edu_filtered = prof_edu_clean[prof_edu_clean['profession'].isin(top_professions)]

            # Create cross-tabulation
            prof_edu_crosstab = pd.crosstab(prof_edu_filtered['profession'],
                                          prof_edu_filtered['child_education_level'])

            fig_prof_edu = px.imshow(prof_edu_crosstab.values,
                                   x=prof_edu_crosstab.columns,
                                   y=prof_edu_crosstab.index,
                                   title='🎓 Children Education by Caregiver Profession',
                                   color_continuous_scale='Blues',
                                   aspect='auto')
            fig_prof_edu.update_xaxes(tickangle=45)
            fig_prof_edu.update_yaxes(tickangle=0)
            st.plotly_chart(fig_prof_edu, use_container_width=True)

with family_row4_col2:
    # Average children age by caregiver age groups
    if 'age' in cg_df.columns and 'child_age' in ch_df.columns:
        merged_avg_data = ch_df.merge(cg_df[['caregiver_key', 'age']], on='caregiver_key')
        valid_avg_data = merged_avg_data[
            merged_avg_data['age'].notna() &
            merged_avg_data['child_age'].notna()
        ].copy()

        if not valid_avg_data.empty:
            valid_avg_data['caregiver_age_group'] = valid_avg_data['age'].apply(caregiver_age_group)

            avg_child_age = valid_avg_data.groupby('caregiver_age_group')['child_age'].agg(['mean', 'std']).reset_index()
            avg_child_age.columns = ['Caregiver Age Group', 'Average Child Age', 'Std Dev']

            fig_avg_child_age = px.bar(avg_child_age, x='Caregiver Age Group', y='Average Child Age',
                                     error_y='Std Dev',
                                     title='📊 Average Children Age by Caregiver Age Group',
                                     color='Average Child Age',
                                                                 color_continuous_scale='plasma')
            fig_avg_child_age.update_layout(showlegend=False)
            st.plotly_chart(fig_avg_child_age, use_container_width=True)

# Add fifth row for advanced family analytics
st.markdown("#### 🔬 Advanced Family Analytics")

family_row5_col1, family_row5_col2 = st.columns(2)

with family_row5_col1:
    # Sibling age gaps analysis
    if not ch_df.empty and 'child_age' in ch_df.columns:
        # Find families with multiple children
        multi_child_families = ch_df.groupby('caregiver_key').filter(lambda x: len(x) > 1)

        if not multi_child_families.empty:
            age_gaps = []
            for caregiver_key in multi_child_families['caregiver_key'].unique():
                family_children = multi_child_families[
                    (multi_child_families['caregiver_key'] == caregiver_key) &
                    (multi_child_families['child_age'].notna())
                ]['child_age'].sort_values()

                if len(family_children) > 1:
                    for i in range(len(family_children) - 1):
                        gap = family_children.iloc[i+1] - family_children.iloc[i]
                        age_gaps.append(gap)

            if age_gaps:
                age_gaps_df = pd.DataFrame({'age_gap': age_gaps})
                fig_sibling_gaps = px.histogram(age_gaps_df, x='age_gap',
                                              title='👫 Sibling Age Gaps Distribution',
                                              labels={'age_gap': 'Age Gap (years)', 'count': 'Frequency'},
                                              nbins=15,
                                              color_discrete_sequence=['#9b59b6'])
                fig_sibling_gaps.add_vline(x=pd.Series(age_gaps).mean(),
                                         line_dash="dash",
                                         line_color="red",
                                         annotation_text=f"Avg: {pd.Series(age_gaps).mean():.1f} years")
                fig_sibling_gaps.update_layout(showlegend=False)
                st.plotly_chart(fig_sibling_gaps, use_container_width=True)

with family_row5_col2:
    # Education progression within families
    if 'child_education_level' in ch_df.columns and 'child_age' in ch_df.columns:
        # Create education level hierarchy
        edu_hierarchy = {
            'Pre-primary': 1, 'Primary': 2, 'Junior Secondary': 3,
            'O\'Level': 4, 'Senior Secondary': 5, 'Tertiary': 6,
            'Vocational': 5.5, 'Graduate': 7
        }

        edu_progress_data = ch_df[
            ch_df['child_education_level'].notna() &
            ch_df['child_age'].notna() &
            ch_df['child_education_level'].isin(edu_hierarchy.keys())
        ].copy()

        if not edu_progress_data.empty:
            edu_progress_data['edu_level_numeric'] = edu_progress_data['child_education_level'].map(edu_hierarchy)

            # Calculate expected education level based on age
            def expected_education(age):
                if age < 6: return 1  # Pre-primary
                elif age < 12: return 2  # Primary
                elif age < 15: return 3  # Junior Secondary
                elif age < 18: return 4  # O'Level
                elif age < 21: return 5  # Senior Secondary
                else: return 6  # Tertiary

            edu_progress_data['expected_edu'] = edu_progress_data['child_age'].apply(expected_education)
            edu_progress_data['edu_progress'] = edu_progress_data['edu_level_numeric'] - edu_progress_data['expected_edu']

            fig_edu_progress = px.scatter(edu_progress_data, x='child_age', y='edu_progress',
                                        title='📚 Education Progress vs Expected Level',
                                        labels={'edu_progress': 'Progress (Above/Below Expected)', 'child_age': 'Child Age'},
                                        color='edu_progress',
                                        color_continuous_scale='RdYlGn',
                                        hover_data=['child_name', 'child_education_level'])
            fig_edu_progress.add_hline(y=0, line_dash="dash", line_color="black",
                                     annotation_text="Expected Level")
            st.plotly_chart(fig_edu_progress, use_container_width=True)

# Add sixth row for zonal leader analysis
st.markdown("#### 🌍 Zonal Leadership Analysis")

family_row6_col1, family_row6_col2 = st.columns(2)

with family_row6_col1:
    # Families per zonal leader
    if 'zonal_leader' in cg_df.columns and cg_df['zonal_leader'].notna().any():
        zonal_families = cg_df[cg_df['zonal_leader'].notna() & (cg_df['zonal_leader'] != '')]

        if not zonal_families.empty:
            zonal_counts = zonal_families['zonal_leader'].value_counts().head(10)

            fig_zonal = px.bar(x=zonal_counts.index, y=zonal_counts.values,
                             title='👥 Families per Zonal Leader (Top 10)',
                             labels={'x': 'Zonal Leader', 'y': 'Number of Families'},
                             color=zonal_counts.values,
                             color_continuous_scale='viridis')
            fig_zonal.update_xaxes(tickangle=45)
            fig_zonal.update_layout(showlegend=False)
            st.plotly_chart(fig_zonal, use_container_width=True)

with family_row6_col2:
    # Children distribution by zonal leader
    if 'zonal_leader' in cg_df.columns and not ch_df.empty:
        zonal_children = ch_df.merge(cg_df[['caregiver_key', 'zonal_leader']], on='caregiver_key')
        zonal_children_clean = zonal_children[
            zonal_children['zonal_leader'].notna() &
            (zonal_children['zonal_leader'] != '')
        ]

        if not zonal_children_clean.empty:
            zonal_child_counts = zonal_children_clean['zonal_leader'].value_counts().head(10)

            fig_zonal_children = px.pie(values=zonal_child_counts.values,
                                      names=zonal_child_counts.index,
                                      title='👶 Children Distribution by Zonal Leader')
            fig_zonal_children.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_zonal_children, use_container_width=True)

# Add summary insights section
st.markdown("#### 💡 Family Structure Insights")

insights_col1, insights_col2, insights_col3 = st.columns(3)

with insights_col1:
    st.markdown("**👨‍👩‍👧‍👦 Family Composition**")
    if not ch_df.empty:
        avg_family_size = ch_df.groupby('caregiver_key').size().mean()
        st.metric("Average Family Size", f"{avg_family_size:.1f} children")

        largest_family = ch_df.groupby('caregiver_key').size().max()
        st.metric("Largest Family", f"{largest_family} children")

with insights_col2:
    st.markdown("**📊 Age Demographics**")
    if 'child_age' in ch_df.columns and ch_df['child_age'].notna().any():
        avg_child_age = ch_df['child_age'].mean()
        st.metric("Average Child Age", f"{avg_child_age:.1f} years")

        if 'age' in cg_df.columns and cg_df['age'].notna().any():
            avg_caregiver_age = cg_df['age'].mean()
            st.metric("Average Caregiver Age", f"{avg_caregiver_age:.1f} years")

with insights_col3:
    st.markdown("**🎓 Education Status**")
    if 'child_education_level' in ch_df.columns:
        in_school = ch_df[
            ch_df['child_education_level'].notna() &
            (ch_df['child_education_level'] != 'Not in School') &
            (ch_df['child_education_level'] != '')
        ]
        school_rate = len(in_school) / len(ch_df) * 100 if len(ch_df) > 0 else 0
        st.metric("School Enrollment Rate", f"{school_rate:.1f}%")

        tertiary_students = ch_df[ch_df['child_education_level'].isin(['Tertiary', 'Graduate'])]
        tertiary_rate = len(tertiary_students) / len(ch_df) * 100 if len(ch_df) > 0 else 0
        st.metric("Higher Education Rate", f"{tertiary_rate:.1f}%")

# Add recommendations section
st.markdown("#### 🎯 Recommendations")

rec_col1, rec_col2 = st.columns(2)

with rec_col1:
    st.markdown("**📈 Growth Opportunities**")

    # Calculate families without children
    caregivers_with_children = set(ch_df['caregiver_key'].unique()) if not ch_df.empty else set()
    all_caregivers = set(cg_df['caregiver_key'].unique())
    families_without_children = len(all_caregivers - caregivers_with_children)

    if families_without_children > 0:
        st.write(f"• Follow up with {families_without_children} caregivers to register their children")

    # Check for incomplete education data
    if 'child_education_level' in ch_df.columns:
        missing_education = ch_df[
            ch_df['child_education_level'].isna() |
            (ch_df['child_education_level'] == '')
        ]
        if len(missing_education) > 0:
            st.write(f"• Update education information for {len(missing_education)} children")

with rec_col2:
    st.markdown("**🎯 Focus Areas**")

    # Identify large families that might need more support
    if not ch_df.empty:
        large_families = ch_df.groupby('caregiver_key').size()
        very_large_families = large_families[large_families >= 5]
        if len(very_large_families) > 0:
            st.write(f"• {len(very_large_families)} families have 5+ children - consider additional support")

    # Check for age gaps in education
    if 'child_age' in ch_df.columns and 'child_education_level' in ch_df.columns:
        school_age_not_in_school = ch_df[
            (ch_df['child_age'] >= 6) &
            (ch_df['child_age'] <= 18) &
            ((ch_df['child_education_level'] == 'Not in School') |
             (ch_df['child_education_level'].isna()))
        ]
        if len(school_age_not_in_school) > 0:
            st.write(f"• {len(school_age_not_in_school)} school-age children are not in school")

    st.markdown("---")




# Add this after your data overview section
st.markdown("### ✏️ Edit or Delete Records")

edit_tab1, edit_tab2 = st.tabs(["Edit Caregiver", "Delete Records"])

with edit_tab1:
    st.write("Select a caregiver to edit:")
    selected_caregiver = st.selectbox(
        "Choose caregiver",
        options=cg_df["caregiver_name"].tolist(),
        index=None
    )

    if selected_caregiver:
        caregiver_data = cg_df[cg_df["caregiver_name"] == selected_caregiver].iloc[0]
        caregiver_key = caregiver_data["caregiver_key"]

        with st.form("edit_caregiver_form"):
            st.write(f"Editing: {selected_caregiver}")

            edit_name = st.text_input("Caregiver Name *", value=caregiver_data["caregiver_name"])

            col1, col2 = st.columns(2)
            with col1:
                edit_dob = st.date_input("Date of Birth",
                                        value=caregiver_data["date_of_birth"] if pd.notna(caregiver_data["date_of_birth"]) else None,
                                        format="YYYY-MM-DD",
                                        min_value=datetime(1900, 1, 1),
                                        max_value=datetime.now())
            with col2:
                # If DOB is provided, calculate age as default
                default_edit_age = calculate_age(edit_dob) if edit_dob else (int(caregiver_data["age"]) if pd.notna(caregiver_data["age"]) else 0)
                edit_age = st.number_input("Age", min_value=0, max_value=120, step=1, value=default_edit_age)

            # Update the edit form section around line 450-470
            edit_gender = st.selectbox("Gender", ["", "male", "female"],
                                      index=["", "male", "female"].index(caregiver_data["gender"]) if caregiver_data["gender"] in ["", "male", "female"] else 0)
            edit_prof = st.text_input("Profession", value=caregiver_data["profession"] or "")
            edit_phone = st.text_input("Phone Number", value=caregiver_data["phone_number"] or "")
            edit_address = st.text_area("Address", value=caregiver_data["address"] or "", height=100, help="Enter the full address of the caregiver")  # Add this line
            edit_zonal_leader = st.text_input("Zonal Leader", value=caregiver_data["zonal_leader"] or "")  # Add this new field

            # Add the new bank fields
            edit_bank_col1, edit_bank_col2 = st.columns(2)
            with edit_bank_col1:
                edit_bank = st.text_input("Bank Name", value=caregiver_data["bank"] or "", help="Enter the bank name")
            with edit_bank_col2:
                edit_account_number = st.text_input("Account Number", value=caregiver_data["account_number"] or "", help="Enter the account number")

            # Handle number of kids
            kids_value = int(caregiver_data["number_of_kids"]) if pd.notna(caregiver_data["number_of_kids"]) else 0
            edit_numkids = st.number_input("Number of Kids", min_value=0, step=1, value=kids_value)

            # Get children for this caregiver
            caregiver_children = ch_df[ch_df["caregiver_key"] == caregiver_key].copy()

            st.markdown("---")
            st.subheader("Children")

            if len(caregiver_children) > 0:
                # Prepare children data for editing

                if len(caregiver_children) > 0:
                    # Prepare children data for editing
                    children_edit_data = caregiver_children[
                        ["child_name", "child_gender", "child_phone_number", "child_age",
                         "child_date_of_birth", "child_education_level", "child_school_name", "child_class_level",
                         "child_profession"]].copy()

                    # Convert date to datetime for the editor
                    if "child_date_of_birth" in children_edit_data.columns:
                        children_edit_data["child_date_of_birth"] = pd.to_datetime(
                            children_edit_data["child_date_of_birth"])

                    # Convert NaN values to empty strings for text columns and ensure proper data types
                    children_edit_data["child_school_name"] = children_edit_data["child_school_name"].fillna("").astype(
                        str)
                    children_edit_data["child_class_level"] = children_edit_data["child_class_level"].fillna("").astype(
                        str)
                    children_edit_data["child_profession"] = children_edit_data["child_profession"].fillna("").astype(
                        str)
                    children_edit_data["child_gender"] = children_edit_data["child_gender"].fillna("").astype(str)
                    children_edit_data["child_phone_number"] = children_edit_data["child_phone_number"].fillna(
                        "").astype(str)

                    edited_children = st.data_editor(
                        children_edit_data,
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        key=f"edit_children_{caregiver_key}",
                        column_config={
                            "child_gender": st.column_config.SelectboxColumn(options=["", "male", "female"]),
                            "child_age": st.column_config.NumberColumn(min_value=0, max_value=120, step=1),
                            "child_date_of_birth": st.column_config.DateColumn(
                                format="YYYY-MM-DD",
                                min_value=datetime(1900, 1, 1),
                                max_value=datetime(2035, 12, 31)
                            ),
                            "child_education_level": st.column_config.SelectboxColumn(
                                options=["", "Pre-primary", "Primary", "Junior Secondary", "O'Level",
                                         "Senior Secondary", "Tertiary", "Vocational", "Not in School", "Graduate"]
                            ),
                            "child_school_name": st.column_config.TextColumn(
                                label="School Name",
                                help="Enter the name of the school"
                            ),
                            "child_class_level": st.column_config.SelectboxColumn(
                                label="Class/Level",
                                options=class_level_options,
                                help="Select the current class or level"
                            ),
                            "child_profession": st.column_config.TextColumn(
                                label="Profession",
                                help="Enter the child's profession if applicable"
                            ),
                        }
                    )

                else:
                    # No children yet, show empty template
                    child_template = pd.DataFrame([{
                        "child_name": "",
                        "child_gender": "",
                        "child_phone_number": "",
                        "child_age": None,
                        "child_date_of_birth": None,
                        "child_education_level": "",
                        "child_school_name": "",
                        "child_class_level": "",
                        "child_profession": ""
                    }])

                    # Ensure proper data types for the template
                    child_template["child_school_name"] = child_template["child_school_name"].astype(str)
                    child_template["child_class_level"] = child_template["child_class_level"].astype(str)
                    child_template["child_profession"] = child_template["child_profession"].astype(str)
                    child_template["child_gender"] = child_template["child_gender"].astype(str)
                    child_template["child_phone_number"] = child_template["child_phone_number"].astype(str)

                    edited_children = st.data_editor(
                        child_template,
                        num_rows="dynamic",
                        use_container_width=True,
                        hide_index=True,
                        key=f"edit_children_template_{caregiver_key}",
                        column_config={
                            "child_gender": st.column_config.SelectboxColumn(options=["", "male", "female"]),
                            "child_age": st.column_config.NumberColumn(min_value=0, max_value=120, step=1),
                            "child_date_of_birth": st.column_config.DateColumn(
                                format="YYYY-MM-DD",
                                min_value=datetime(1900, 1, 1),
                                max_value=datetime(2035, 12, 31)
                            ),
                            "child_education_level": st.column_config.SelectboxColumn(
                                options=["", "Pre-primary", "Primary", "Junior Secondary", "O'Level",
                                         "Senior Secondary", "Tertiary", "Vocational", "Not in School", "Graduate"]
                            ),
                            "child_school_name": st.column_config.TextColumn(
                                label="School Name",
                                help="Enter the name of the school"
                            ),
                            "child_class_level": st.column_config.SelectboxColumn(
                                label="Class/Level",
                                options=class_level_options,
                                help="Select the current class or level"
                            ),
                            "child_profession": st.column_config.TextColumn(
                                label="Profession",
                                help="Enter the child's profession if applicable"
                            ),
                        }
                    )

            update_submitted = st.form_submit_button("💾 Update Caregiver")

            if update_submitted:
                # Basic validation
                if not edit_name:
                    st.error("Caregiver Name is required.")
                    st.stop()

                # Validate children's phone numbers
                invalid_child_phones = []
                for i, r in edited_children.iterrows():
                    phone = str(r.get("child_phone_number") or "").strip()
                    if phone and not validate_phone_number(phone):
                        invalid_child_phones.append(f"Row {i+1}: {r.get('child_name')}")

                if invalid_child_phones:
                    st.error(f"Invalid phone number format for: {', '.join(invalid_child_phones)}")
                    st.stop()

                # Update caregiver
                now = datetime.utcnow().isoformat()

                # Check if name or phone changed - if so, generate new key
                if edit_name != caregiver_data["caregiver_name"] or edit_phone != caregiver_data["phone_number"]:
                    new_key = stable_key(edit_name, edit_phone)
                    # Remove old records
                    cg_df = cg_df[cg_df["caregiver_key"] != caregiver_key]
                    ch_df = ch_df[ch_df["caregiver_key"] != caregiver_key]
                else:
                    new_key = caregiver_key
                    # Remove old caregiver record but keep the key
                    cg_df = cg_df[cg_df["caregiver_key"] != new_key]

                # Create updated caregiver record
                updated_caregiver = {
                    "caregiver_key": new_key,
                    "caregiver_name": edit_name.strip(),
                    "gender": edit_gender or "",
                    "profession": edit_prof.strip(),
                    "date_of_birth": pd.to_datetime(edit_dob).date() if edit_dob else None,
                    "age": int(edit_age) if pd.notna(edit_age) else None,
                    "phone_number": edit_phone.strip(),
                    "address": edit_address.strip() if edit_address else "",  # Add this line
                    "zonal_leader": edit_zonal_leader.strip(),  # Add this new field
                    "bank": edit_bank.strip() if edit_bank else "",  # Add this line
                    "account_number": edit_account_number.strip() if edit_account_number else "",  # Add this line
                    "number_of_kids": int(edit_numkids) if pd.notna(edit_numkids) else None,
                    "last_updated": now
                }

                # Add updated caregiver
                cg_df = pd.concat([cg_df, pd.DataFrame([updated_caregiver])], ignore_index=True)

                # Process children
                children_rows = []
                for _, r in edited_children.iterrows():
                    name = str(r.get("child_name") or "").strip()
                    if not name:
                        continue

                    # Get the child phone number from the row data
                    child_phone = str(r.get("child_phone_number") or "").strip()

                    child = {
                        "caregiver_key": new_key,
                        "caregiver_name": edit_name.strip(),
                        "child_name": name,
                        "child_gender": str(r.get("child_gender") or "").strip(),
                        "child_phone_number": child_phone,
                        "child_age": int(r.get("child_age")) if pd.notna(r.get("child_age")) else None,
                        "child_date_of_birth": pd.to_datetime(r.get("child_date_of_birth")).date() if pd.notna(r.get("child_date_of_birth")) else None,
                        "child_education_level": str(r.get("child_education_level") or "").strip(),
                        "child_school_name": str(r.get("child_school_name") or "").strip(),
                        "child_class_level": str(r.get("child_class_level") or "").strip(),
                        "child_profession": str(r.get("child_profession") or "").strip(),
                        "last_updated": now
                    }
                    children_rows.append(child)

                # Add updated children
                if children_rows:
                    ch_df = pd.concat([ch_df, pd.DataFrame(children_rows)], ignore_index=True)

                # Save to Excel
                save_data(cg_df, ch_df)
                st.success(f"Updated caregiver '{edit_name}' and {len(children_rows)} child(ren).")
                st.rerun()  # Refresh the app

with edit_tab2:
    st.write("⚠️ Danger Zone: Delete Records")
    delete_caregiver = st.selectbox(
        "Select caregiver to delete",
        options=cg_df["caregiver_name"].tolist(),
        index=None
    )

    if delete_caregiver:
        caregiver_key = cg_df[cg_df["caregiver_name"] == delete_caregiver]["caregiver_key"].iloc[0]
        child_count = len(ch_df[ch_df["caregiver_key"] == caregiver_key])

        st.warning(f"This will delete {delete_caregiver} and {child_count} associated children records.")

        if st.button("🗑️ Confirm Delete", key="delete_confirm"):
            # Remove the caregiver and their children
            cg_df = cg_df[cg_df["caregiver_key"] != caregiver_key]
            ch_df = ch_df[ch_df["caregiver_key"] != caregiver_key]
            save_data(cg_df, ch_df)
            st.success(f"Deleted {delete_caregiver} and {child_count} children records.")
            st.rerun()  # Refresh the app

# Add a new tab or section for import/export
st.markdown("### 📤 Import/Export Data")
import_export_tab1, import_export_tab2 = st.tabs(["Export Data", "Import Data"])

with import_export_tab1:
    st.write("Export data in different formats")

    # Add option to export filtered data
    export_filtered = st.checkbox("Export only filtered data", value=False)

    # Use the appropriate dataframes based on the filter choice
    export_cg = cg_filtered if export_filtered and search_term else cg_df
    export_ch = ch_filtered if export_filtered and search_term else ch_df

    export_format = st.selectbox(
        "Select export format",
        options=["Excel", "CSV", "JSON"]
    )

    if export_format == "Excel":
        # Create Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            export_cg.to_excel(writer, index=False, sheet_name="caregivers")
            export_ch.to_excel(writer, index=False, sheet_name="children")

        output.seek(0)
        file_name = "filtered_caregivers_database.xlsx" if export_filtered else "caregivers_database.xlsx"
        st.download_button("⬇️ Download Excel", output, file_name=file_name)
    elif export_format == "CSV":
        # Export as CSV
        csv_cg = export_cg.to_csv(index=False).encode('utf-8')
        csv_ch = export_ch.to_csv(index=False).encode('utf-8')
        col1, col2 = st.columns(2)
        with col1:
            file_name = "filtered_caregivers.csv" if export_filtered else "caregivers.csv"
            st.download_button("⬇️ Download Caregivers CSV", csv_cg, file_name=file_name)
        with col2:
            file_name = "filtered_children.csv" if export_filtered else "children.csv"
            st.download_button("⬇️ Download Children CSV", csv_ch, file_name=file_name)
    elif export_format == "JSON":
        # Export as JSON
        json_cg = export_cg.to_json(orient="records").encode('utf-8')
        json_ch = export_ch.to_json(orient="records").encode('utf-8')
        col1, col2 = st.columns(2)
        with col1:
            file_name = "filtered_caregivers.json" if export_filtered else "caregivers.json"
            st.download_button("⬇️ Download", json_cg, file_name=file_name)
        with col2:
            file_name = "filtered_children.json" if export_filtered else "children.json"
            st.download_button("⬇️ Download", json_ch, file_name=file_name)

with import_export_tab2:
    st.write("Import data from CSV or Excel")
    uploaded_file = st.file_uploader("Choose a file", type=["xlsx", "csv"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                # Handle CSV import
                import_df = pd.read_csv(uploaded_file)
                st.write("Preview of imported data:")
                st.dataframe(import_df.head())

                # Determine if this is caregivers or children data
                is_caregiver_data = "caregiver_name" in import_df.columns and "caregiver_key" not in import_df.columns
                is_child_data = "child_name" in import_df.columns

                if st.button("Confirm Import"):
                    if is_caregiver_data:
                        # Process caregiver data
                        for _, row in import_df.iterrows():
                            name = str(row.get("caregiver_name") or "").strip()
                            phone = str(row.get("phone_number") or "").strip()

                            if not name:
                                continue

                            key = stable_key(name, phone)
                            now = datetime.utcnow().isoformat()

                            new_row = {
                                "caregiver_key": key,
                                "caregiver_name": name,
                                "gender": str(row.get("gender") or "").strip(),
                                "profession": str(row.get("profession") or "").strip(),
                                "date_of_birth": pd.to_datetime(row.get("date_of_birth"), errors='coerce').date() if pd.notna(row.get("date_of_birth")) else None,
                                "age": int(row.get("age")) if pd.notna(row.get("age")) else None,
                                "phone_number": phone,
                                "address": str(row.get("address") or "").strip(),  # Add this line
                                "zonal_leader": str(row.get("zonal_leader") or "").strip(),  # Add this new field
                                "bank": str(row.get("bank") or "").strip(),  # Add this new field
                                "account_number": str(row.get("account_number") or "").strip(),  # Add this new field
                                "number_of_kids": int(row.get("number_of_kids")) if pd.notna(row.get("number_of_kids")) else None,
                                "last_updated": now
                            }

                            # Remove existing caregiver with same key (upsert)
                            cg_df = cg_df[cg_df["caregiver_key"] != key]
                            cg_df = pd.concat([cg_df, pd.DataFrame([new_row])], ignore_index=True)

                        save_data(cg_df, ch_df)
                        st.success("Caregiver data imported successfully!")

                    elif is_child_data:
                        # Process children data
                        for _, row in import_df.iterrows():
                            name = str(row.get("child_name") or "").strip()
                            if not name:
                                continue

                            # Find the caregiver key by name
                            caregiver_name = str(row.get("caregiver_name") or "").strip()
                            caregiver_row = cg_df[cg_df["caregiver_name"] == caregiver_name]

                            if caregiver_row.empty:
                                st.warning(f"No caregiver found for child '{name}'. Skipping.")
                                continue

                            caregiver_key = caregiver_row.iloc[0]["caregiver_key"]

                            # Get the child phone number from the row data
                            child_phone = str(row.get("child_phone_number") or "").strip()

                            now = datetime.utcnow().isoformat()

                            new_child = {
                                "caregiver_key": caregiver_key,
                                "caregiver_name": caregiver_name,
                                "child_name": name,
                                "child_gender": str(row.get("child_gender") or "").strip(),
                                "child_phone_number": child_phone,
                                "child_age": int(row.get("child_age")) if pd.notna(row.get("child_age")) else None,
                                "child_date_of_birth": pd.to_datetime(
                                    row.get("child_date_of_birth")).date() if pd.notna(
                                    row.get("child_date_of_birth")) else None,
                                "child_education_level": str(row.get("child_education_level") or "").strip(),
                                "child_school_name": str(row.get("child_school_name") or "").strip(),
                                "child_class_level": str(row.get("child_class_level") or "").strip(),
                                "child_profession": str(row.get("child_profession") or "").strip(),
                                "last_updated": now
                            }

                            # Remove existing child record for this child
                            ch_df = ch_df[~((ch_df["caregiver_key"] == caregiver_key) & (ch_df["child_name"] == name))]
                            ch_df = pd.concat([ch_df, pd.DataFrame([new_child])], ignore_index=True)

                        save_data(cg_df, ch_df)
                        st.success("Children data imported successfully!")
                    else:
                        st.error("Unknown data format. Please ensure the CSV has either caregiver or child columns.")
            else:
                # Handle Excel import
                import_xl = pd.ExcelFile(uploaded_file)
                sheet_names = import_xl.sheet_names
                selected_sheet = st.selectbox("Select sheet to import", options=sheet_names)
                import_df = pd.read_excel(import_xl, sheet_name=selected_sheet)
                st.write("Preview of imported data:")
                st.dataframe(import_df.head())

                # Determine if this is caregivers or children data
                is_caregiver_data = "caregiver_name" in import_df.columns and "caregiver_key" not in import_df.columns
                is_child_data = "child_name" in import_df.columns

                if st.button("Confirm Import"):
                    if is_caregiver_data:
                        # Process caregiver data
                        for _, row in import_df.iterrows():
                            name = str(row.get("caregiver_name") or "").strip()
                            phone = str(row.get("phone_number") or "").strip()

                            if not name:
                                continue

                            key = stable_key(name, phone)
                            now = datetime.utcnow().isoformat()

                            new_row = {
                                "caregiver_key": key,
                                "caregiver_name": name,
                                "gender": str(row.get("gender") or "").strip(),
                                "profession": str(row.get("profession") or "").strip(),
                                "date_of_birth": pd.to_datetime(row.get("date_of_birth"), errors='coerce').date() if pd.notna(row.get("date_of_birth")) else None,
                                "age": int(row.get("age")) if pd.notna(row.get("age")) else None,
                                "phone_number": phone,
                                "address": str(row.get("address") or "").strip(),
                                "zonal_leader": str(row.get("zonal_leader") or "").strip(),
                                "bank": str(row.get("bank") or "").strip(),
                                "account_number": str(row.get("account_number") or "").strip(),
                                "number_of_kids": int(row.get("number_of_kids")) if pd.notna(row.get("number_of_kids")) else None,
                                "last_updated": now
                            }
                            
                            # Remove existing caregiver with same key (upsert)
                            cg_df = cg_df[cg_df["caregiver_key"] != key]
                            cg_df = pd.concat([cg_df, pd.DataFrame([new_row])], ignore_index=True)
                        
                        save_data(cg_df, ch_df)
                        st.success("Caregiver data imported successfully!")
                    elif is_child_data:
                        # Process children data
                        for _, row in import_df.iterrows():
                            name = str(row.get("child_name") or "").strip()
                            if not name:
                                continue
                                
                            # Find the caregiver key by name
                            caregiver_name = str(row.get("caregiver_name") or "").strip()
                            caregiver_row = cg_df[cg_df["caregiver_name"] == caregiver_name]
                            
                            if caregiver_row.empty:
                                st.warning(f"No caregiver found for child '{name}'. Skipping.")
                                continue
                                
                            caregiver_key = caregiver_row.iloc[0]["caregiver_key"]
                            
                            now = datetime.utcnow().isoformat()
                            
                            new_child = {
                                "caregiver_key": caregiver_key,
                                "caregiver_name": caregiver_name,
                                "child_name": name,
                                "child_gender": str(row.get("child_gender") or "").strip(),  # Add this new field
                                "child_phone_number": child_phone,
                                "child_age": int(row.get("child_age")) if pd.notna(row.get("child_age")) else None,
                                "child_date_of_birth": pd.to_datetime(row.get("child_date_of_birth")).date() if pd.notna(row.get("child_date_of_birth")) else None,
                                "child_education_level": str(row.get("child_education_level") or "").strip(),
                                "child_profession": str(row.get("child_profession") or "").strip(),
                                "last_updated": now
                            }
                            
                            # Remove existing child record for this child
                            ch_df = ch_df[~((ch_df["caregiver_key"] == caregiver_key) & (ch_df["child_name"] == name))]
                            ch_df = pd.concat([ch_df, pd.DataFrame([new_child])], ignore_index=True)
                        
                        save_data(cg_df, ch_df)
                        st.success("Children data imported successfully!")
                    else:
                        st.error("Unknown data format. Please ensure the Excel sheet has either caregiver or child columns.")
        except Exception as e:
            st.error(f"Error importing file: {str(e)}")


# Add footer with app information
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p><strong>ISOILAJ SDI Caregiver Database Management System</strong></p>
    <p>Version 2.0 | Built by Ighere G. Nelson, C.E.O NelviusGrey Technologies | Last Updated: {}</p>
    <p>📧 Support: nelviusgrey@gmail.com | 📞 Help: +234-904-370-8371</p>
</div>
""".format(datetime.now().strftime("%Y-%m-%d")), unsafe_allow_html=True)

# Add keyboard shortcuts info
with st.expander("⌨️ Keyboard Shortcuts & Tips"):
    st.markdown("""
    **Navigation:**
    - `Ctrl + R` - Refresh the page
    - `Ctrl + F` - Search in browser
    - `Tab` - Navigate between form fields
    
    **Data Entry Tips:**
    - Use consistent formatting for phone numbers
    - Enter dates in YYYY-MM-DD format when possible
    - Use proper capitalization for names
    - Fill in all required fields marked with *
    
    **Search Tips:**
    - Search works across all text fields
    - Use partial names for broader results
    - Search is case-insensitive
    - Use phone numbers to find specific records
    """)

# Performance monitoring (optional - for development)
#if st.sidebar.checkbox("Show Performance Info", value=False):
   # st.sidebar.markdown("**Performance Metrics**")
   # st.sidebar.write(f"Caregivers loaded: {len(cg_df)}")
   # st.sidebar.write(f"Children loaded: {len(ch_df)}")
    #st.sidebar.write(f"Memory usage: {cg_df.memory_usage(deep=True).sum() + ch_df.memory_usage(deep=True).sum()} bytes")

st.caption("Note: An internal key links children to caregivers. You don't need to enter any ID.")



