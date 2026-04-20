from flask import Flask, request, jsonify
from flask_cors import CORS
import face_recognition
import numpy as np
import base64
import cv2
import os
import pandas as pd
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2
import time

app = Flask(__name__)
CORS(app)

KNOWN_FACES = []
KNOWN_NAMES = []
KNOWN_SRNS = []

# 📍 PES EC Campus Location
PES_LAT = 12.9346
PES_LON = 77.6050
ALLOWED_RADIUS_KM = 12.0

# Attendance CSV file
ATTENDANCE_FILE = "attendance.csv"

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in km using Haversine formula"""
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def is_within_location(lat, lon):
    """Check if user is within allowed radius"""
    distance = calculate_distance(lat, lon, PES_LAT, PES_LON)
    print(f"📍 Distance from PES EC Campus: {distance:.2f} km")
    return distance <= ALLOWED_RADIUS_KM, distance

def run_rars_attendance():
    """Run RARS assembly program from rars folder"""
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        assembly_file = os.path.join(base_dir, "rars", "attendance.asm")
        
        if os.path.exists(assembly_file):
            rars_jar = os.path.join(base_dir, "rars", "rars.jar")
            if os.path.exists(rars_jar):
                import subprocess
                result = subprocess.run(
                    ["java", "-jar", rars_jar, "ae", assembly_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                output = result.stdout
                rars_data = {}
                lines = output.split('\n')
                for line in lines:
                    if 'Sum:' in line:
                        parts = line.split('Sum:')
                        if len(parts) > 1:
                            rars_data['sum'] = int(parts[1].strip())
                    elif 'Average:' in line:
                        parts = line.split('Average:')
                        if len(parts) > 1:
                            rars_data['average'] = int(parts[1].strip())
                    elif 'Max Roll No:' in line:
                        parts = line.split('Max Roll No:')
                        if len(parts) > 1:
                            rars_data['max_roll'] = int(parts[1].strip())
                    elif 'Total Students:' in line:
                        parts = line.split('Total Students:')
                        if len(parts) > 1:
                            rars_data['total_students'] = int(parts[1].strip())
                if rars_data:
                    return rars_data
        
        # Simulated RARS data
        return {
            'total_students': 4,
            'sum': 418,
            'average': 104,
            'max_roll': 110
        }
    except Exception as e:
        print(f"⚠️ RARS Error: {e}")
        return None

def mark_attendance_in_csv(name, srn):
    """Mark attendance - only updates DATE and TIME for the student"""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), ATTENDANCE_FILE)
        
        print(f"📁 CSV Path: {csv_path}")
        
        # Define the correct columns
        correct_columns = ['NAMES', 'SRN', 'DATE', 'TIME']
        
        # Check if CSV exists
        if not os.path.exists(csv_path):
            # Create new CSV with correct headers
            df = pd.DataFrame(columns=correct_columns)
            df.to_csv(csv_path, index=False)
            print(f"✅ Created new CSV file with columns: {correct_columns}")
            return False, "Attendance file created. Please add student data and restart."
        
        # Read existing data
        try:
            df = pd.read_csv(csv_path)
            
            # Fix: Remove any unnamed columns
            unnamed_cols = [col for col in df.columns if 'Unnamed' in col]
            if unnamed_cols:
                print(f"⚠️ Removing unnamed columns: {unnamed_cols}")
                df = df.drop(columns=unnamed_cols)
            
            # Fix: Ensure correct columns exist
            for col in correct_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Keep only the correct columns
            df = df[correct_columns]
            
        except PermissionError:
            return False, "❌ CSV file is open. Please close Excel and try again."
        except Exception as e:
            print(f"⚠️ Error reading CSV: {e}")
            # Recreate the dataframe
            df = pd.DataFrame(columns=correct_columns)
        
        # Check if student exists (case-insensitive)
        df['NAMES'] = df['NAMES'].astype(str).str.strip()
        name_match = df['NAMES'].str.lower() == name.lower()
        
        if not name_match.any():
            return False, f"❌ Student '{name}' not found in database. Please contact admin."
        
        # Get today's date and time in proper format
        today_date = datetime.now().strftime('%Y-%m-%d')  # YYYY-MM-DD format (Excel friendly)
        current_time = datetime.now().strftime('%H:%M:%S')
        
        print(f"📅 Today's date: {today_date}")
        print(f"⏰ Current time: {current_time}")
        
        # Check if attendance already marked today
        student_idx = name_match.idxmax() if name_match.any() else None
        if student_idx is not None:
            existing_date = df.loc[student_idx, 'DATE']
            if pd.notna(existing_date) and existing_date != '' and existing_date == today_date:
                existing_time = df.loc[student_idx, 'TIME']
                return False, f"⚠️ Attendance already marked for {name} today at {existing_time}"
        
        # Update DATE and TIME for the student
        df.loc[student_idx, 'DATE'] = today_date
        df.loc[student_idx, 'TIME'] = current_time
        
        # Save to CSV with retry mechanism
        saved = False
        for attempt in range(3):
            try:
                df.to_csv(csv_path, index=False)
                saved = True
                break
            except PermissionError:
                if attempt < 2:
                    print(f"⚠️ Permission denied, retrying... (attempt {attempt + 1}/3)")
                    time.sleep(0.5)
                    continue
                else:
                    return False, "❌ CSV file is locked. Please close Excel if it's open."
        
        if not saved:
            return False, "❌ Could not save to CSV."
        
        print(f"✅ Attendance marked for {name} (SRN: {srn}) on {today_date} at {current_time}")
        
        return True, f"✅ Attendance marked successfully for {name} at {current_time}"
        
    except Exception as e:
        print(f"❌ CSV Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"❌ Error: {str(e)}"

def load_faces():
    """Load faces from known_faces folder and map to CSV data"""
    print("🔄 Loading faces...")
    
    # Clear existing data
    global KNOWN_FACES, KNOWN_NAMES, KNOWN_SRNS
    KNOWN_FACES = []
    KNOWN_NAMES = []
    KNOWN_SRNS = []
    
    # First, load faces from known_faces folder
    faces_folder = os.path.join(os.path.dirname(__file__), "known_faces")
    
    if not os.path.exists(faces_folder):
        print(f"❌ Faces folder not found: {faces_folder}")
        os.makedirs(faces_folder)
        print(f"✅ Created folder: {faces_folder}")
        print("📌 Please add student photos (JPG/PNG) to this folder")
        return
    
    # Load all faces from the folder
    face_files = []
    for file in os.listdir(faces_folder):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            face_files.append(file)
            print(f"📂 Found face file: {file}")
    
    if len(face_files) == 0:
        print("❌ No face images found in known_faces folder!")
        print("📌 Please add photos like: snidhi.jpg, usha.jpg")
        return
    
    # Load each face
    for file in face_files:
        name = os.path.splitext(file)[0]
        path = os.path.join(faces_folder, file)
        
        try:
            print(f"📂 Loading face: {file}")
            image = face_recognition.load_image_file(path)
            
            # Resize for better performance
            small = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)
            encodings = face_recognition.face_encodings(small)
            
            if len(encodings) == 0:
                print(f"⚠️ No face detected in: {file}")
                continue
            
            KNOWN_FACES.append(encodings[0])
            KNOWN_NAMES.append(name.lower())  # Store names in lowercase for consistency
            print(f"✅ Loaded face: {name}")
            
        except Exception as e:
            print(f"❌ Error loading {file}: {e}")
    
    # Now load SRNs from CSV if available
    csv_path = os.path.join(os.path.dirname(__file__), ATTENDANCE_FILE)
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            
            # Fix: Remove unnamed columns
            unnamed_cols = [col for col in df.columns if 'Unnamed' in col]
            if unnamed_cols:
                df = df.drop(columns=unnamed_cols)
            
            # Ensure correct columns
            if 'NAMES' in df.columns and 'SRN' in df.columns:
                # Create case-insensitive mapping
                name_to_srn = {}
                for _, row in df.iterrows():
                    student_name = str(row['NAMES']).strip().lower()
                    if student_name and student_name != 'nan':
                        name_to_srn[student_name] = str(row['SRN'])
                
                for i, name in enumerate(KNOWN_NAMES):
                    if name in name_to_srn:
                        KNOWN_SRNS.append(name_to_srn[name])
                        print(f"📋 Found SRN {name_to_srn[name]} for {name}")
                    else:
                        KNOWN_SRNS.append("N/A")
                        print(f"⚠️ No SRN found in CSV for {name}")
            else:
                print("⚠️ CSV missing NAMES or SRN columns")
                for _ in KNOWN_NAMES:
                    KNOWN_SRNS.append("N/A")
        except Exception as e:
            print(f"⚠️ Error reading CSV: {e}")
            for _ in KNOWN_NAMES:
                KNOWN_SRNS.append("N/A")
    else:
        print(f"⚠️ CSV file not found: {csv_path}")
        print("📌 Creating new CSV file with loaded names...")
        
        if len(KNOWN_NAMES) > 0:
            df = pd.DataFrame({
                'NAMES': [name.upper() for name in KNOWN_NAMES],
                'SRN': [''] * len(KNOWN_NAMES),
                'DATE': [''] * len(KNOWN_NAMES),
                'TIME': [''] * len(KNOWN_NAMES)
            })
            df.to_csv(csv_path, index=False)
            print(f"✅ Created CSV with {len(KNOWN_NAMES)} students")
            for _ in KNOWN_NAMES:
                KNOWN_SRNS.append("")
    
    print(f"✅ Total faces loaded: {len(KNOWN_NAMES)}")
    print(f"📋 Names: {KNOWN_NAMES}")
    
    if len(KNOWN_FACES) == 0:
        print("❌ WARNING: No faces loaded! Attendance will not work.")
        print("📌 Please add clear front-facing photos to backend/known_faces/")

# Load faces on startup
load_faces()

@app.route('/check_location', methods=['POST'])
def check_location():
    """Check your current location"""
    try:
        data = request.get_json(force=True)
        lat = float(data['lat'])
        lon = float(data['lon'])
        
        distance = calculate_distance(lat, lon, PES_LAT, PES_LON)
        within = distance <= ALLOWED_RADIUS_KM
        
        return jsonify({
            "success": True,
            "distance_km": round(distance, 2),
            "allowed_radius_km": ALLOWED_RADIUS_KM,
            "within_campus": within,
            "message": f"You are {round(distance, 2)} km from PES EC Campus"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    """Main endpoint for marking attendance"""
    try:
        data = request.get_json(force=True)
        
        if not data or 'image' not in data:
            return jsonify({"status": "error", "message": "No image data"}), 400
        
        image_data = data['image']
        lat = float(data['lat'])
        lon = float(data['lon'])
        
        print(f"\n{'='*50}")
        print(f"📍 User location: {lat}, {lon}")
        
        # Location check
        within_campus, distance = is_within_location(lat, lon)
        
        if not within_campus:
            return jsonify({
                "status": "error", 
                "message": f"❌ You are {distance:.2f} km from campus. Must be within {ALLOWED_RADIUS_KM} km."
            }), 200
        
        # Decode image
        try:
            img_bytes = base64.b64decode(image_data.split(',')[1])
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            return jsonify({"status": "error", "message": "Invalid image data"}), 200
        
        # Face recognition
        print(f"📋 Known faces in system: {len(KNOWN_FACES)}")
        
        if len(KNOWN_FACES) == 0:
            return jsonify({
                "status": "error", 
                "message": "❌ No faces registered in system. Please contact admin."
            }), 200
        
        # Get face encodings
        face_locations = face_recognition.face_locations(rgb)
        print(f"👤 Faces detected: {len(face_locations)}")
        
        if len(face_locations) == 0:
            return jsonify({
                "status": "error", 
                "message": "❌ No face detected. Please ensure your face is clearly visible."
            }), 200
        
        if len(face_locations) > 1:
            return jsonify({
                "status": "error", 
                "message": f"❌ {len(face_locations)} faces detected. Only one person allowed."
            }), 200
        
        encodings = face_recognition.face_encodings(rgb, face_locations)
        
        if len(encodings) == 0:
            return jsonify({
                "status": "error", 
                "message": "❌ Could not process face. Please try again."
            }), 200
        
        face_encoding = encodings[0]
        matches = face_recognition.compare_faces(KNOWN_FACES, face_encoding, tolerance=0.5)
        
        if True in matches:
            index = matches.index(True)
            name = KNOWN_NAMES[index]
            srn = KNOWN_SRNS[index] if index < len(KNOWN_SRNS) else "N/A"
            
            print(f"✅ Face recognized: {name} (SRN: {srn})")
            
            # Run RARS
            rars_data = run_rars_attendance()
            
            # Mark attendance
            success, message = mark_attendance_in_csv(name.upper(), srn)
            
            if success:
                response_data = {
                    "status": "success", 
                    "name": name.upper(),
                    "srn": srn,
                    "message": message,
                    "distance": round(distance, 2)
                }
                
                if rars_data:
                    response_data["stats"] = {
                        "total_students": rars_data.get('total_students', 'N/A'),
                        "sum_rollnos": rars_data.get('sum', 'N/A'),
                        "avg_roll": rars_data.get('average', 'N/A'),
                        "max_roll": rars_data.get('max_roll', 'N/A')
                    }
                
                return jsonify(response_data), 200
            else:
                return jsonify({"status": "error", "message": message}), 200
        else:
            print(f"❌ No match found. Available: {KNOWN_NAMES}")
            return jsonify({
                "status": "error", 
                "message": "❌ Face not recognized. Please contact admin to register."
            }), 200
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

@app.route('/fix_csv', methods=['GET'])
def fix_csv():
    """Endpoint to fix CSV file format"""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), ATTENDANCE_FILE)
        
        if os.path.exists(csv_path):
            # Read and fix the CSV
            df = pd.read_csv(csv_path)
            
            # Remove unnamed columns
            unnamed_cols = [col for col in df.columns if 'Unnamed' in col]
            if unnamed_cols:
                df = df.drop(columns=unnamed_cols)
            
            # Ensure correct columns
            correct_columns = ['NAMES', 'SRN', 'DATE', 'TIME']
            for col in correct_columns:
                if col not in df.columns:
                    df[col] = ''
            
            df = df[correct_columns]
            
            # Save fixed CSV
            df.to_csv(csv_path, index=False)
            
            return jsonify({
                "status": "success",
                "message": "CSV file fixed!",
                "columns": list(df.columns),
                "data": df.to_dict('records')
            })
        else:
            return jsonify({"status": "error", "message": "CSV file not found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/reload_faces', methods=['POST'])
def reload_faces():
    """Reload faces without restarting server"""
    load_faces()
    return jsonify({
        "status": "success", 
        "message": f"Reloaded {len(KNOWN_NAMES)} faces",
        "names": KNOWN_NAMES
    })

@app.route('/get_students', methods=['GET'])
def get_students():
    """Get list of all students"""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), ATTENDANCE_FILE)
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            # Remove unnamed columns
            unnamed_cols = [col for col in df.columns if 'Unnamed' in col]
            if unnamed_cols:
                df = df.drop(columns=unnamed_cols)
            students = df.to_dict('records')
            return jsonify({"status": "success", "students": students})
        else:
            return jsonify({"status": "error", "message": "No attendance file found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/test_faces', methods=['GET'])
def test_faces():
    """Test endpoint to check loaded faces"""
    return jsonify({
        "total_faces": len(KNOWN_FACES),
        "names": KNOWN_NAMES,
        "srns": KNOWN_SRNS
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 PES University EC Campus - Biometric Attendance System")
    print("=" * 60)
    print(f"📍 Campus Radius: {ALLOWED_RADIUS_KM} km")
    print(f"📁 Known Faces: backend/known_faces/")
    print(f"📊 Attendance File: backend/attendance.csv")
    print("=" * 60)
    print("📌 Admin Setup:")
    print("   1. Add photos to backend/known_faces/ (e.g., snidhi.jpg)")
    print("   2. Add entries to backend/attendance.csv:")
    print("      NAMES,SRN,DATE,TIME")
    print("      SNIDHI,159,,")
    print("      USHA,175,,")
    print("=" * 60)
    print("⚠️  IMPORTANT: Close attendance.csv if open in Excel!")
    print("📅 Date format: YYYY-MM-DD (Excel friendly)")
    print("=" * 60)
    print("🌐 Server running at: http://127.0.0.1:5000")
    print("🔧 Fix CSV: http://127.0.0.1:5000/fix_csv")
    print("🎯 Test faces: http://127.0.0.1:5000/test_faces")
    print("=" * 60)
    app.run(debug=True, host='127.0.0.1', port=5000)