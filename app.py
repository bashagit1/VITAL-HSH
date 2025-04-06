import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from email.mime.text import MIMEText
import smtplib
import matplotlib.pyplot as plt
from fpdf import FPDF
import base64
import os
from dotenv import load_dotenv

# ==================== LOAD ENVIRONMENT VARIABLES ====================
load_dotenv()
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# ==================== DATABASE INITIALIZATION ====================
conn = sqlite3.connect("hsh_vitals.db", check_same_thread=False)
c = conn.cursor()

# Create Patients Table
c.execute("""
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_name TEXT NOT NULL,
    check_date DATE NOT NULL,
    check_time TEXT NOT NULL,
    shift TEXT,
    systolic INTEGER,
    diastolic INTEGER,
    pulse INTEGER,
    spo2 INTEGER,
    temp REAL,
    glucose REAL,
    glucose_unit TEXT DEFAULT 'mg/dL',  -- Added column for glucose unit
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Create Users Table
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL
)
""")
conn.commit()

# Initialize default admin user if not already present
c.execute("SELECT * FROM users WHERE username = 'admin'")
if not c.fetchone():
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
              ("admin", "admin123", "admin"))
    conn.commit()

# ==================== EMAIL ALERT FUNCTION ====================
def send_critical_alert(patient_name, vital_type, value):
    try:
        msg = MIMEText(f"Critical Alert!\n\nPatient: {patient_name}\nVital: {vital_type}\nValue: {value}")
        msg['Subject'] = "Critical Alert Notification"
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = ADMIN_EMAIL
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, ADMIN_EMAIL, msg.as_string())
        st.success("Critical alert sent via email!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# ==================== HELPER FUNCTIONS FOR ALERTS ====================
def get_bp_alert(systolic, diastolic):
    if systolic > 140 or diastolic > 90:
        return "🚨 Critical (High BP)"
    elif systolic < 90 or diastolic < 60:
        return "⚠️ Low BP"
    return "✅ Normal"

def get_pulse_alert(pulse):
    if pulse > 100 or pulse < 60:
        return "🚨 Critical (Abnormal Pulse)"
    return "✅ Normal"

def get_spo2_alert(spo2):
    if spo2 < 90:
        return "🚨 Critical (Low SpO₂)"
    return "✅ Normal"

def get_temp_alert(temp):
    if temp >= 38 or temp <= 35:
        return "🚨 Critical (Abnormal Temp)"
    return "✅ Normal"

def get_glucose_alert(glucose, glucose_unit="mg/dL"):
    # Convert glucose to mmol/L if the unit is mg/dL
    if glucose_unit == "mg/dL":
        glucose_mmol = glucose / 18.5  # Conversion factor: 1 mg/dL = 1/18.5 mmol/L
    else:
        glucose_mmol = glucose  # Already in mmol/L

    # Define glucose thresholds (in mmol/L)
    if glucose_mmol < 2.8:
        return "🚨 Critical (Too Low)"
    elif glucose_mmol > 16.7:
        return "🚨 Critical (Too High)"
    elif 7.0 <= glucose_mmol <= 16.7:
        return "🚨 Diabetes"
    elif 5.6 < glucose_mmol <= 6.9:
        return "⚠️ Pre-Diabetes"
    return "✅ Normal"
# ==================== GET OVERALL STATUS ====================
def get_overall_status(entry):
    alerts = []
    systolic = entry.get('systolic', 0)
    diastolic = entry.get('diastolic', 0)
    pulse = entry.get('pulse', 0)
    spo2 = entry.get('spo2', 0)
    temp = entry.get('temp', 0)
    glucose = entry.get('glucose', 0)
    glucose_unit = entry.get('glucose_unit', "mg/dL")  # Default to mg/dL if not provided

    # Blood Pressure Alerts
    if systolic > 140 or diastolic > 90:
        alerts.append("High BP")
    if systolic < 90 or diastolic < 60:
        alerts.append("Low BP")

    # Pulse Alerts
    if pulse > 100 or pulse < 60:
        alerts.append("Abnormal Pulse")

    # SpO₂ Alerts
    if spo2 < 90:
        alerts.append("Low SpO₂")

    # Temperature Alerts
    if temp >= 38 or temp <= 35:
        alerts.append("Abnormal Temp")

    # Glucose Alerts (mmol/L)
    glucose_mmol = glucose / 18.5 if glucose_unit == "mg/dL" else glucose
    if glucose_mmol < 2.8:
        alerts.append("Glucose Too Low (Critical)")
    if glucose_mmol > 16.7:
        alerts.append("Glucose Too High (Critical)")
    if 7.0 <= glucose_mmol <= 16.7:
        alerts.append("Diabetes")
    if 5.6 < glucose_mmol <= 6.9:
        alerts.append("Pre-Diabetes")

    return ", ".join(alerts) if alerts else "Normal"

# ==================== DATA EXPORT FUNCTIONS ====================
def export_to_csv(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="filtered_data.csv">Download CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_to_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    # Add header
    pdf.cell(200, 10, txt="Patient Vitals Report", ln=True, align="C")
    pdf.ln(10)
    # Add table headers
    columns = list(df.columns)
    for col in columns:
        pdf.cell(40, 10, col, border=1)
    pdf.ln()
    # Add data rows
    for _, row in df.iterrows():
        for item in row:
            pdf.cell(40, 10, str(item), border=1)
        pdf.ln()
    # Save PDF
    pdf_file = "patient_report.pdf"
    pdf.output(pdf_file)
    with open(pdf_file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
        href = f'<a href="data:application/pdf;base64,{b64}" download="patient_report.pdf">Download PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

# ==================== PRINTABLE REPORT GENERATION ====================
def generate_printable_report(patient_name, entries):
    # Generate the rows for the table first
    table_rows = ''.join([
        f"<tr>"
        f"<td>{entry['check_date']}</td>"
        f"<td>{entry['check_time']}</td>"
        f"<td>{entry['shift']}</td>"
        f"<td>{entry['systolic']}/{entry['diastolic']}</td>"
        f"<td>{entry['pulse']}</td>"
        f"<td>{entry['spo2']}</td>"
        f"<td>{entry['temp']}</td>"
        f"<td>{entry['glucose']}</td>"
        f"<td>{get_overall_status(entry)}</td>"
        f"</tr>"
        for entry in entries
    ])
    
    # Construct the full HTML report
    report = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1, h2 {{ text-align: center; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid black; padding: 8px; text-align: center; }}
                th {{ background-color: #f4f4f4; }}
            </style>
        </head>
        <body>
            <h1>HSH Nursing Home</h1>
            <h2>Patient Report</h2>
            <p><strong>Patient Name:</strong> {patient_name}</p>
            <table>
                <tr>
                    <th>Date</th><th>Time</th><th>Shift</th><th>BP</th><th>Pulse</th><th>SpO₂</th><th>Temp</th><th>Glucose</th><th>Status</th>
                </tr>
                {table_rows}
            </table>
        </body>
    </html>
    """
    return report

# ==================== VISUALIZATION FUNCTIONS ====================
def plot_trends(entries):
    dates = [f"{entry['check_date']} {entry['check_time']}" for entry in entries]
    systolic = [entry['systolic'] for entry in entries]
    diastolic = [entry['diastolic'] for entry in entries]
    glucose = [entry['glucose'] for entry in entries]
    spo2 = [entry['spo2'] for entry in entries]
    fig, axes = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    # Blood Pressure Trends
    axes[0].plot(dates, systolic, label="Systolic BP", color="red", marker="o")
    axes[0].plot(dates, diastolic, label="Diastolic BP", color="blue", marker="o")
    axes[0].set_title("Blood Pressure Trends")
    axes[0].set_ylabel("BP (mmHg)")
    axes[0].legend()
    axes[0].tick_params(axis='x', rotation=45)
    # Glucose Trends
    axes[1].plot(dates, glucose, label="Glucose (mg/dL)", color="green", marker="o")
    axes[1].set_title("Glucose Trends")
    axes[1].set_ylabel("Glucose (mg/dL)")
    axes[1].tick_params(axis='x', rotation=45)
    # SpO₂ Trends
    axes[2].plot(dates, spo2, label="SpO₂ (%)", color="purple", marker="o")
    axes[2].set_title("SpO₂ Trends")
    axes[2].set_ylabel("SpO₂ (%)")
    axes[2].tick_params(axis='x', rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

# ==================== AUTHENTICATION ====================
def authenticate(username, password):
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    if user:
        return user[3]  # Return the role (admin or staff)
    return None

# Check if the user is logged in
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# ==================== LOGIN PAGE ====================
# ==================== FIXING ST.RERUN() ISSUE ====================
if "rerun_app" not in st.session_state:
    st.session_state.rerun_app = False

def show_login_page():
    st.title("🩺 HSH Vital Signs Monitoring")
    st.header("Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        role = authenticate(username, password)
        if role:
            st.session_state.logged_in = True
            st.session_state.user_role = role
            st.session_state.rerun_app = True  # Trigger rerun
            st.success("Login successful!")
        else:
            st.error("Invalid username or password!")

# Check for rerun flag outside the callback
if st.session_state.rerun_app:
    st.session_state.rerun_app = False  # Reset the flag
    st.rerun()


# ==================== LOGOUT FUNCTION ====================
def logout():
    st.session_state.logged_in = False
    st.session_state.user_role = None
    st.rerun()


# ==================== ROLE-BASED ACCESS CONTROL ====================
if not st.session_state.logged_in:
    show_login_page()
else:
    # Show logout button
    st.sidebar.button("Logout", on_click=logout)
    if st.session_state.user_role == "admin":
        st.sidebar.write("Logged in as Admin")
    elif st.session_state.user_role == "staff":
        st.sidebar.write("Logged in as Staff")

    # Define tabs only if the user is logged in
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Patient Vitals",
        "Patient History",
        "Monthly Reports",
        "Register Staff",
        "Admin Settings"
    ])

    # ==================== TAB 1: PATIENT VITALS ====================
    with tab1:
        st.header("Enter Patient Vitals")
        c.execute("SELECT DISTINCT patient_name FROM patients")
        patient_names = [row[0] for row in c.fetchall()]
        patient_names.insert(0, "Select or Add New Patient")
        selected_patient = st.selectbox("Select Patient", patient_names)
        if selected_patient == "Select or Add New Patient":
            patient_name = st.text_input("Enter New Patient Name", key="new_patient_name")
        else:
            patient_name = selected_patient
        col1, col2 = st.columns(2)
        with col1:
            check_date = st.date_input("Date", key="check_date")
        with col2:
            check_time = st.time_input("Time", key="check_time")
        shift = st.selectbox("Shift", ["Morning", "Afternoon", "Night"], key="shift")
        col3, col4 = st.columns(2)
        with col3:
            systolic = st.number_input("Systolic BP (mmHg)", min_value=0, key="systolic")
            pulse = st.number_input("Pulse (BPM)", min_value=0, key="pulse")
            temp = st.number_input("Temperature (°C)", min_value=0.0, step=0.1, key="temp")
        with col4:
            diastolic = st.number_input("Diastolic BP (mmHg)", min_value=0, key="diastolic")
            spo2 = st.number_input("SpO₂ (%)", min_value=0, key="spo2")
            glucose = st.number_input("Glucose (mg/dL)", min_value=0.0, step=0.1, key="glucose")
        if st.button("Save Vitals"):
            if not patient_name:
                st.error("Patient name is required!")
            else:
                check_time_str = check_time.strftime("%H:%M:%S")
                c.execute("""
                INSERT INTO patients (
                    patient_name, check_date, check_time, shift, systolic, diastolic, pulse, spo2, temp, glucose
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_name, check_date, check_time_str, shift, systolic, diastolic, pulse, spo2, temp, glucose
                ))
                conn.commit()
                st.success("Vitals saved successfully!")
                # Trigger email alerts for critical values
                if systolic > 140 or diastolic > 90:
                    send_critical_alert(patient_name, "BP", f"{systolic}/{diastolic}")
                if spo2 < 90:
                    send_critical_alert(patient_name, "SpO₂", spo2)
                if temp >= 38 or temp <= 35:
                    send_critical_alert(patient_name, "Temperature", temp)
                if glucose / 18 > 7.0:
                    send_critical_alert(patient_name, "Glucose", glucose)

    # ==================== TAB 2: PATIENT HISTORY ====================
    with tab2:
        if st.session_state.user_role == "admin":
            st.header("View Patient History")
            filter_patient = st.text_input("Search Patient", key="filter_patient")
            filter_date = st.date_input("Filter by Date", key="filter_date", value=None)
            filter_shift = st.selectbox(
                "Filter by Shift", ["All", "Morning", "Afternoon", "Night"], key="filter_shift"
            )
            query = "SELECT * FROM patients WHERE 1=1"
            params = []
            if filter_patient:
                query += " AND patient_name LIKE ?"
                params.append(f"%{filter_patient}%")
            if filter_date:
                query += " AND check_date = ?"
                params.append(filter_date)
            if filter_shift != "All":
                query += " AND shift = ?"
                params.append(filter_shift)
            c.execute(query, params)
            data = c.fetchall()
            columns = [desc[0] for desc in c.description]
            df = pd.DataFrame(data, columns=columns)
            if not df.empty:
                st.dataframe(df.style.applymap(
                    lambda x: "background-color: red" if isinstance(x, str) and "Critical" in x else None
                ))
                st.subheader("Export Data")
                if st.button("Export to CSV"):
                    export_to_csv(df)
                if st.button("Export to PDF"):
                    export_to_pdf(df)
                st.subheader("Vital Trends Over Time")
                plot_trends(df.to_dict(orient="records"))
            else:
                st.info("No data found for the selected filters.")
        else:
            st.error("Access Denied: Only admins can view patient history.")

    # ==================== TAB 3: MONTHLY REPORTS ====================
    with tab3:
        if st.session_state.user_role == "admin":
            st.header("Generate Monthly Report")
            patient_name = st.text_input("Enter Patient Name", key="monthly_patient_name")
            month_year = st.text_input("Enter Month/Year (MM-YYYY)", key="month_year")
            if st.button("Generate Report"):
                if not patient_name or not month_year:
                    st.error("Please enter both patient name and month/year!")
                else:
                    try:
                        month, year = map(int, month_year.split('-'))
                        if not (1 <= month <= 12) or not (1900 <= year <= 2100):
                            raise ValueError
                    except ValueError:
                        st.error("Invalid month/year format! Use MM-YYYY (e.g., 10-2023).")
                        st.stop()
                    start_date = f"{year}-{month:02d}-01"
                    end_date = f"{year}-{month:02d}-31"
                    c.execute("""
                    SELECT * FROM patients
                    WHERE patient_name = ? AND check_date BETWEEN ? AND ?
                    """, (patient_name, start_date, end_date))
                    data = c.fetchall()
                    columns = [desc[0] for desc in c.description]
                    df = pd.DataFrame(data, columns=columns)
                    if not df.empty:
                        daily_counts = df.groupby("check_date").size().reset_index(name="Number of Checks")
                        st.subheader(f"{patient_name}'s Monthly Report ({month:02d}/{year})")
                        st.dataframe(daily_counts)
                        entries = df.to_dict(orient="records")
                        report_html = generate_printable_report(patient_name, entries)
                        st.components.v1.html(report_html, height=800, scrolling=True)
                        st.download_button(
                            label="Download Printable Report",
                            data=report_html,
                            file_name=f"{patient_name}_report.html",
                            mime="text/html"
                        )
                    else:
                        st.info("No data found for the specified month/year.")
        else:
            st.error("Access Denied: Only admins can generate monthly reports.")

    # ==================== TAB 4: REGISTER STAFF ====================
# ==================== TAB 4: MANAGE STAFF ====================
    with tab4:
     if st.session_state.user_role == "admin":
        st.header("Register New Staff")
        new_username = st.text_input("Username", key="new_username_tab4")  # Unique key
        new_password = st.text_input("Password", type="password", key="new_password_tab4")  # Unique key
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password_tab4")  # Unique key

        if st.button("Register Staff", key="register_staff_button"):
            if not new_username or not new_password or not confirm_password:
                st.error("All fields are required!")
            elif new_password != confirm_password:
                st.error("Passwords do not match!")
            else:
                # Check if username already exists in the database
                c.execute("SELECT * FROM users WHERE username = ?", (new_username,))
                if c.fetchone():
                    st.error("Username already exists!")
                else:
                    # Insert new user into the database
                    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                              (new_username, new_password, "staff"))
                    conn.commit()
                    st.success("Staff registered successfully!")
     else:
        st.error("Access Denied: Only admins can register new staff.")  

# ==================== TAB 5: ADMIN SETTINGS ====================
# ==================== TAB 5: ADMIN SETTINGS ====================
    with tab5:
     if st.session_state.user_role == "admin":
        st.header("Admin Settings")
        st.subheader("Change Admin Credentials")

        current_password = st.text_input("Current Password", type="password", key="current_password_tab5")  # Unique key
        new_username = st.text_input("New Username (Optional)", key="new_username_tab5")  # Unique key
        new_password = st.text_input("New Password", type="password", key="new_password_tab5")  # Unique key
        confirm_password = st.text_input("Confirm New Password", type="password", key="confirm_password_tab5")  # Unique key

        if st.button("Update Credentials", key="update_credentials_button"):
            # Verify current password
            c.execute("SELECT * FROM users WHERE username = ? AND password = ?", ("admin", current_password))
            admin = c.fetchone()

            if not admin:
                st.error("Incorrect current password!")
            else:
                # Validate new credentials
                if new_password != confirm_password:
                    st.error("New password and confirmation do not match!")
                elif not new_password and not new_username:
                    st.error("Please provide either a new username or password!")
                else:
                    # Update the database
                    if new_username:
                        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, "admin"))
                        st.session_state.username = new_username  # Update session state
                    if new_password:
                        c.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, "admin"))

                    conn.commit()
                    st.success("Credentials updated successfully!")
     else:
        st.error("Access Denied: Only admins can change credentials.")