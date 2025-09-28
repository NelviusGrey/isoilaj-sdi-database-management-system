# ISOILAJ SDI – Caregivers & Children Database Management System

A custom-built Streamlit application developed to help NGOs and CBOs collect, manage, and analyze caregiver and child data efficiently. This system was originally designed for ISOILAJ Social Development Initiative (SDI) to support beneficiary tracking, monitoring, and reporting across multiple communities.

---

## ✨ Features

- **Caregiver & Child Registry**
  - Register caregivers and their children in a structured Excel database.
  - Auto-generate stable IDs for linking caregivers and children.
  - Smart age calculation from date of birth.

- **Data Validation & Integrity**
  - Handles missing values, duplicate entries, and child–caregiver links.
  - Automatic migration of missing child phone numbers.

- **Edit & Update**
  - Search, filter, and update existing caregiver/child records.
  - Dynamic Streamlit forms with pre-filled data.

- **Search & Filters**
  - Quick name search and advanced filters by gender, age group, profession, education level, zonal leader, and more.

- **Backup & Storage**
  - Excel file with two sheets (caregivers & children).
  - Timestamped backup creation for data security.

- **Analytics & Insights** (powered by Plotly)
  - Caregiver and child demographics.
  - Education, profession, and age distributions.
  - Caregiver–child relationship analysis.
  - Family size, sibling age gaps, and gender ratios.
  - Registration trends over time.
  - Geographic insights from address data.

- **Unverified Caregivers**
  - Integrated workflow for tracking verification status.

---

## 🛠️ Tech Stack

- **Frontend/UI:** [Streamlit](https://streamlit.io/)  
- **Backend & Data Handling:** Python, Pandas  
- **Visualization:** Plotly Express & Graph Objects  
- **Storage:** Excel (via OpenPyXL), CSV export  
- **Other:** Logging, PIL for image handling, modular code structure  

