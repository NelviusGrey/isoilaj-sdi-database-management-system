
"""Reusable form components"""
import streamlit as st
from datetime import datetime

class CaregiverForm:
    def __init__(self, form_key: str = "new"):
        self.form_key = form_key
    
    def render(self, initial_data: dict = None):
        """Render caregiver form with validation"""
        with st.form(f"caregiver_form_{self.form_key}"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input(
                    "Caregiver Name *", 
                    value=initial_data.get("caregiver_name", "") if initial_data else "",
                    help="Enter the full name of the caregiver"
                )
                
                gender = st.selectbox(
                    "Gender", 
                    options=["", "male", "female"],
                    index=self._get_gender_index(initial_data.get("gender") if initial_data else "")
                )
                
                profession = st.text_input(
                    "Profession",
                    value=initial_data.get("profession", "") if initial_data else ""
                )
            
            with col2:
                dob = st.date_input(
                    "Date of Birth",
                    value=initial_data.get("date_of_birth") if initial_data else None,
                    min_value=datetime(1900, 1, 1),
                    max_value=datetime.now()
                )
                
                age = st.number_input(
                    "Age",
                    min_value=0,
                    max_value=120,
                    value=self._calculate_age(dob) if dob else 0
                )
                
                phone = st.text_input(
                    "Phone Number",
                    value=initial_data.get("phone_number", "") if initial_data else "",
                    help="Enter phone number with country code if international"
                )
            
            # Additional fields
            address = st.text_area(
                "Address",
                value=initial_data.get("address", "") if initial_data else "",
                height=100
            )
            
            zonal_leader = st.text_input(
                "Zonal Leader",
                value=initial_data.get("zonal_leader", "") if initial_data else ""
            )
            
            return {
                "name": name,
                "gender": gender,
                "profession": profession,
                "dob": dob,
                "age": age,
                "phone": phone,
                "address": address,
                "zonal_leader": zonal_leader
            }
    
    def _get_gender_index(self, gender_value: str):
        """Get index for gender selection box"""
        gender_map = {"male": 1, "female": 2}
        return gender_map.get(gender_value, 0)
    
    def _calculate_age(self, dob):
        """Calculate age from date of birth"""
        if not dob:
            return 0
        today = datetime.now()
        age = today.year - dob.year
        if today.month < dob.month or (today.month == dob.month and today.day < dob.day):
            age -= 1
        return age
