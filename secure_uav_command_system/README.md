# Multimodal Biometric Command Authorization System

A secure command authorization system that integrates **face recognition**, **dynamic spoken phrase verification**, and **gesture-based commands** to authenticate and authorize sensitive actions.

The system combines **biometric verification with cryptographic protection using AES-256 (Advanced Encryption Standard – 256 bit) and RSA (Rivest–Shamir–Adleman)** to provide a multi-layer authentication mechanism.

This project demonstrates how **computer vision, gesture recognition, speech challenges, and encryption techniques** can work together to build a secure command authorization system.

---

# Features

• Username and password authentication
• Face recognition based identity verification using **FaceNet**
• Dynamic spoken phrase verification for button commands
• Gesture-based command execution
• Multi-factor authentication workflow
• Secure command logging system
• AES-256 encryption for sensitive data protection
• RSA encryption for secure key exchange

---

# System Workflow

1. **Initial Login**

The user logs into the system using a valid **username and password**.

---

2. **Face Authentication**

After login, the user must press the **Authenticate** button to verify their identity using **FaceNet-based face recognition**.

---

3. **Command Execution**

Once authenticated, the user can execute commands using two methods:

**Button Commands**

* The system generates a **dynamic phrase** that the user must speak.
* The phrase currently appears in the **VS Code terminal** rather than the web dashboard.
* The spoken phrase is verified before executing the command.

**Gesture Commands**

* Commands can also be triggered using **hand gestures**.
* Gesture commands **do not require voice verification**.

---

4. **Command Logging**

Every executed command is recorded in the **system log** for auditing and tracking purposes.

---

5. **Encryption Layer**

Sensitive operations and data are protected using:

• **AES-256 encryption** for secure data storage
• **RSA encryption** for secure key exchange

---

# Face Enrollment

Before authentication can work, a face must first be registered.

Run the enrollment script:

python enroll_face.py

This captures and stores the face data required for the recognition system.

For security reasons, the repository **does not include any face images**.
Users must enroll their own face before using the system.

---

# Technologies Used

### Programming

Python

### Computer Vision

OpenCV (Open Source Computer Vision Library)

### Face Recognition

FaceNet (via DeepFace)

### Web Framework

Flask (Python Web Framework)

### Machine Learning

NumPy (Numerical Python)

### Cryptography

AES-256 (Advanced Encryption Standard – 256 bit)
RSA (Rivest–Shamir–Adleman)

---

# Installation

Clone the repository:

git clone https://github.com/yourusername/repository-name.git

Navigate into the project folder:

cd repository-name

Install dependencies:

pip install -r requirements.txt

---

# Running the Application

The system requires **two terminals** because the gesture recognition service uses dependencies that conflict with the main application environment.

---

## Terminal 1 — Main Application

Activate the virtual environment:

venv\Scripts\activate

Run the main application:

python app.py

---

## Terminal 2 — Gesture Service

If you are still inside the main application's virtual environment, deactivate it first:

deactivate

Navigate to the gesture service folder:

cd gesture_service

Activate the gesture service virtual environment:

venv\Scripts\activate

Run the gesture server:

python gesture_server.py

---

# Security Model

The system uses multiple security layers:

1. **Password Authentication**
2. **Face Recognition Verification**
3. **Dynamic Phrase Voice Challenge**
4. **Gesture-Based Command Control**
5. **AES-256 Data Encryption**
6. **RSA Secure Key Exchange**

This layered design improves security and reduces the risk of unauthorized command execution.

---

# Future Improvements

• Display dynamic voice phrases directly on the dashboard
• Implement face liveness detection
• Add multi-user face enrollment support
• Improve gesture recognition accuracy
• Deploy the system as a cloud-based authentication service
