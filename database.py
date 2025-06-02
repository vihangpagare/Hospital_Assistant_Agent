"""
database.py

Contains DatabaseManager: creates/initializes the SQLite schema,
populates sample data, and exposes methods for querying/updating.
"""
import sqlite3
from datetime import datetime, timedelta, date
import random
from typing import List, Dict, Any, Optional


class DatabaseManager:
    def __init__(self, db_path: str = "healthcare_assistant.db"):
        self.db_path = db_path
        self.conn = self._create_database()

    def _create_database(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Patients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Patients (
            patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth DATE NOT NULL,
            gender TEXT 
                CHECK(gender IN ('Male','Female','Other','Prefer not to say')),
            contact_number TEXT,
            email TEXT,
            address TEXT,
            emergency_contact_name TEXT,
            emergency_contact_number TEXT,
            insurance_id TEXT,
            registration_date DATE DEFAULT CURRENT_DATE
        )
        ''')

        # Appointments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_date DATE NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME,
            purpose TEXT,
            status TEXT 
                CHECK(status IN ('Scheduled','Completed','Cancelled','No-show')),
            notes TEXT,
            FOREIGN KEY(patient_id) REFERENCES Patients(patient_id)
        )
        ''')

        # MedicalRecords table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS MedicalRecords (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            diagnosis TEXT,
            treatment TEXT,
            prescription TEXT,
            test_results TEXT,
            notes TEXT,
            record_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(patient_id) REFERENCES Patients(patient_id)
        )
        ''')

        # DoctorAvailability (weekly template)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS DoctorAvailability (
            doctor_name TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            PRIMARY KEY(doctor_name, day_of_week, start_time)
        )
        ''')

        # DoctorAvailabilitySlots (materialized for next 30 days)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS DoctorAvailabilitySlots (
            doctor_name TEXT NOT NULL,
            slot_date DATE NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_booked INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(doctor_name, slot_date, start_time)
        )
        ''')

        conn.commit()
        self._populate_database(conn)
        return conn

    def _populate_database(self, conn):
        cursor = conn.cursor()

        # 1) Seed Patients
        patients = [
            ('John', 'Doe', '1985-07-12', 'Male', '1234567890', 'john.doe@email.com',
             '123 Main St, New York, NY', 'Jane Doe', '0987654321', 'INS12345'),
            ('Jane', 'Smith', '1990-09-25', 'Female', '0987654321', 'jane.smith@email.com',
             '456 Park Ave, New York, NY', 'John Smith', '1234567890', 'INS54321'),
            ('Michael', 'Johnson', '1978-03-15', 'Male', '5556667777', 'michael.johnson@email.com',
             '789 Broadway, New York, NY', 'Sarah Johnson', '7778889999', 'INS67890'),
            ('Sophia', 'Garcia', '1992-04-18', 'Female', '1112223333', 'sophia.garcia@email.com',
             '123 Oak St, New City, NY', 'Miguel Garcia', '1112224444', 'INS78901')
        ]
        cursor.executemany('''
        INSERT OR IGNORE INTO Patients (
            first_name, last_name, date_of_birth, gender,
            contact_number, email, address,
            emergency_contact_name, emergency_contact_number, insurance_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', patients)

        # 2) Seed DoctorAvailability (template Monday–Friday)
        doctors = ['Dr. Sarah Johnson', 'Dr. James Williams', 'Dr. Emma Davis', 'Dr. Robert Miller']
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        availability = []
        for doc in doctors:
            for day in days:
                availability.append((doc, day, '09:00', '12:00'))
                availability.append((doc, day, '13:00', '17:00'))
        cursor.executemany('''
        INSERT OR IGNORE INTO DoctorAvailability 
        (doctor_name, day_of_week, start_time, end_time)
        VALUES (?, ?, ?, ?)
        ''', availability)

        # 3) Materialize DoctorAvailabilitySlots for next 30 days
        today = date.today()
        for offset in range(0, 30):
            slot_day = today + timedelta(days=offset)
            day_name = slot_day.strftime("%A")
            cursor.execute(
                "SELECT doctor_name, start_time, end_time FROM DoctorAvailability WHERE day_of_week = ?",
                (day_name,)
            )
            rows = cursor.fetchall()
            for (doctor_name, start_time, end_time) in rows:
                start_dt = datetime.combine(slot_day, datetime.strptime(start_time, "%H:%M").time())
                end_dt = datetime.combine(slot_day, datetime.strptime(end_time, "%H:%M").time())
                t = start_dt
                while t + timedelta(minutes=30) <= end_dt:
                    st = t.strftime("%H:%M")
                    et = (t + timedelta(minutes=30)).strftime("%H:%M")
                    cursor.execute('''
                    INSERT OR IGNORE INTO DoctorAvailabilitySlots 
                    (doctor_name, slot_date, start_time, end_time)
                    VALUES (?, ?, ?, ?)
                    ''', (doctor_name, slot_day.isoformat(), st, et))
                    t += timedelta(minutes=30)

        # 4) Seed some random Appointments for demonstration
        diagnoses = ['Hypertension', 'Type 2 Diabetes', 'Asthma', 'Allergic Rhinitis', 'Migraine', 'Osteoarthritis']
        treatments = ['Medication management', 'Lifestyle modifications', 'Physical therapy', 'Breathing exercises']
        medications = ['Lisinopril 10mg daily', 'Metformin 500mg twice daily', 'Albuterol inhaler as needed']
        test_results = ['Blood pressure 130/85', 'HbA1c 7.2%', 'Pulmonary function test: mild obstruction']

        # Seed Appointments and MedicalRecords
        # First insert some appointments (past + future) for patient IDs 1–4
        doctors_list = doctors
        appointments = []
        for i in range(10):
            patient_id = random.randint(1, 4)
            doctor = random.choice(doctors_list)
            days_offset = random.randint(-10, 30)
            appt_date = (today + timedelta(days=days_offset)).strftime('%Y-%m-%d')
            hour = random.randint(9, 16)
            minute = random.choice([0, 15, 30, 45])
            start_time = f"{hour:02d}:{minute:02d}"
            end_time = f"{hour:02d}:{(minute+30) % 60:02d}"
            if days_offset < 0:
                status = random.choice(['Completed', 'Cancelled', 'No-show'])
            else:
                status = 'Scheduled'
            purpose = random.choice(['Annual checkup', 'Follow-up', 'Consultation', 'Vaccination'])
            notes = f"Patient {patient_id} {purpose.lower()} with {doctor}"
            appointments.append((patient_id, doctor, appt_date, start_time, end_time, purpose, status, notes))

        cursor.executemany('''
        INSERT OR IGNORE INTO Appointments (
            patient_id, doctor_name, appointment_date, start_time, end_time,
            purpose, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', appointments)

        # 5) Seed some MedicalRecords
        medical_records = []
        for i in range(8):
            patient_id = random.randint(1, 4)
            diagnosis = random.choice(diagnoses)
            treatment = random.choice(treatments)
            prescription = random.choice(medications)
            test_result = random.choice(test_results)
            days_offset = random.randint(-365, -1)
            record_date = (today + timedelta(days=days_offset)).strftime('%Y-%m-%d %H:%M:%S')
            notes = f"Patient reported moderate symptoms. Follow-up in {random.randint(1, 6)} weeks."
            medical_records.append((patient_id, diagnosis, treatment, prescription, test_result, notes, record_date))

        cursor.executemany('''
        INSERT OR IGNORE INTO MedicalRecords (
            patient_id, diagnosis, treatment, prescription, test_results, notes, record_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', medical_records)

        conn.commit()

    # ─────── PUBLIC METHODS ────────────────────────────────────────────────────────
    def get_patient_by_name(self, first_name: str, last_name: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT patient_id, first_name, last_name, contact_number, email
               FROM Patients
               WHERE first_name LIKE ? AND last_name LIKE ?
               """,
            (f"%{first_name}%", f"%{last_name}%")
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_upcoming_appointments(self, patient_id: int) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        today_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            """SELECT appointment_id, doctor_name, appointment_date, start_time, purpose
               FROM Appointments
               WHERE patient_id = ? AND appointment_date >= ? AND status = 'Scheduled'
               ORDER BY appointment_date, start_time
            """,
            (patient_id, today_str)
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_past_appointments(self, patient_id: int) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        today_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(
            """SELECT appointment_id, doctor_name, appointment_date, start_time, status, purpose, notes
               FROM Appointments
               WHERE patient_id = ? AND
                     (appointment_date < ? OR status IN ('Completed', 'Cancelled', 'No-show'))
               ORDER BY appointment_date DESC
            """,
            (patient_id, today_str)
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_medical_history(self, patient_id: int) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT diagnosis, treatment, prescription, test_results, record_date, notes
               FROM MedicalRecords
               WHERE patient_id = ?
               ORDER BY record_date DESC
            """,
            (patient_id,)
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_doctor_available_slots(self, doctor_name: str, date_str: str) -> List[str]:
        """
        Return all unbooked 30-minute start_times for a doctor on a given date.
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT start_time 
            FROM DoctorAvailabilitySlots
            WHERE doctor_name = ? AND slot_date = ? AND is_booked = 0
            ORDER BY start_time
        ''', (doctor_name, date_str))
        return [row[0] for row in cursor.fetchall()]

    def book_appointment(self, patient_id: int, doctor_name: str,
                         date_str: str, time_str: str, purpose: str) -> Dict[str, Any]:
        """
        Book an appointment (30 minutes). Returns appointment details and marks slot as booked.
        """
        cursor = self.conn.cursor()
        end_time_dt = (datetime.strptime(time_str, "%H:%M") + timedelta(minutes=30)).strftime("%H:%M")
        cursor.execute(
            """INSERT INTO Appointments 
               (patient_id, doctor_name, appointment_date, start_time, end_time, purpose, status)
               VALUES (?, ?, ?, ?, ?, ?, 'Scheduled')
            """,
            (patient_id, doctor_name, date_str, time_str, end_time_dt, purpose)
        )
        appointment_id = cursor.lastrowid

        # Mark slot as booked
        cursor.execute('''
            UPDATE DoctorAvailabilitySlots
            SET is_booked = 1
            WHERE doctor_name = ? AND slot_date = ? AND start_time = ?
        ''', (doctor_name, date_str, time_str))

        self.conn.commit()
        return {
            "appointment_id": appointment_id,
            "status": "confirmed",
            "doctor": doctor_name,
            "date": date_str,
            "time": time_str
        }

    def cancel_appointment(self, appointment_id: int) -> Dict[str, Any]:
        """
        Cancel an appointment and free up its slot.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT doctor_name, appointment_date, start_time, status FROM Appointments WHERE appointment_id = ?",
            (appointment_id,)
        )
        row = cursor.fetchone()
        if not row or row[3] != 'Scheduled':
            return {"status": "failed", "message": "Cannot cancel appointment"}

        doctor_name, date_str, time_str, _ = row
        cursor.execute(
            "UPDATE Appointments SET status = 'Cancelled' WHERE appointment_id = ?",
            (appointment_id,)
        )
        # Free the slot
        cursor.execute('''
            UPDATE DoctorAvailabilitySlots
            SET is_booked = 0
            WHERE doctor_name = ? AND slot_date = ? AND start_time = ?
        ''', (doctor_name, date_str, time_str))
        self.conn.commit()
        return {"status": "success", "message": "Appointment successfully cancelled"}

    def reschedule_appointment(self, appointment_id: int,
                               new_date: str, new_time: str) -> Dict[str, Any]:
        """
        Reschedule an existing appointment. Frees old slot and books new one.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT doctor_name, appointment_date, start_time, status FROM Appointments WHERE appointment_id = ?",
            (appointment_id,)
        )
        row = cursor.fetchone()
        if not row or row[3] != 'Scheduled':
            return {"status": "failed", "message": "Cannot reschedule appointment"}

        doctor_name, old_date, old_time, _ = row
        new_end = (datetime.strptime(new_time, "%H:%M") + timedelta(minutes=30)).strftime("%H:%M")

        # Update the appointment
        cursor.execute('''
            UPDATE Appointments
            SET appointment_date = ?, start_time = ?, end_time = ?
            WHERE appointment_id = ?
        ''', (new_date, new_time, new_end, appointment_id))

        # Free old slot
        cursor.execute('''
            UPDATE DoctorAvailabilitySlots
            SET is_booked = 0
            WHERE doctor_name = ? AND slot_date = ? AND start_time = ?
        ''', (doctor_name, old_date, old_time))

        # Book new slot
        cursor.execute('''
            UPDATE DoctorAvailabilitySlots
            SET is_booked = 1
            WHERE doctor_name = ? AND slot_date = ? AND start_time = ?
        ''', (doctor_name, new_date, new_time))

        self.conn.commit()
        return {
            "status": "success",
            "message": "Appointment successfully rescheduled",
            "doctor": doctor_name,
            "new_date": new_date,
            "new_time": new_time
        }

    def get_next_appointment(self, patient_id: int) -> Optional[Dict[str, Any]]:
        """
        Return the next scheduled appointment for the patient,
        or None if there are no upcoming appointments.
        """
        cursor = self.conn.cursor()
        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT appointment_id, doctor_name, appointment_date, start_time
            FROM Appointments
            WHERE patient_id = ?
              AND appointment_date >= ?
              AND status = 'Scheduled'
            ORDER BY appointment_date ASC, start_time ASC
            LIMIT 1
            """,
            (patient_id, today_str)
        )
        row = cursor.fetchone()
        if not row:
            return None
        cols = [col[0] for col in cursor.description]
        return dict(zip(cols, row))

    def get_available_doctors(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT doctor_name FROM DoctorAvailability")
        return [row[0] for row in cursor.fetchall()]
