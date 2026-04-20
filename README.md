# Microprocessor-and-Computer-Architecture-MINI-PROJECT
 mini project titled "Biometric Classroom Attendance System" for  MPCA course. The project includes RISC-V assembly programming using the RARS simulator
Project Overview:
The system is a web-based application that uses face recognition to mark student attendance. A student opens the website, allows camera access, and captures their face. The system compares the captured image with pre-stored student images and identifies the person. Attendance is marked only if:

1. The face matches a stored student image
2. The student has not already marked attendance on the same day (duplicate prevention)
3.  The location is within campus (using browser geolocation)

Technical Stack:

* Frontend: HTML, CSS, JavaScript (for UI, camera access, time & location validation)
* Backend: Python using OpenCV and face_recognition library (for face detection and matching)
* Data Storage: CSV file to store attendance records (Name, Date, Time, Status)
* Assembly Part: RISC-V program using RARS to process attendance data (count students, sum roll numbers, average, highest roll number)

Additional Details:

* Student images are stored in a folder and used for face comparison
* Backend receives captured image from frontend and returns the identified student
* Attendance is appended to CSV only if not already marked for that day
* The system is a prototype and not fully production-level
