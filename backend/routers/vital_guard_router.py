import datetime
import os
import random
import string
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Header, Request, status
from pydantic import BaseModel
from pymongo import MongoClient
import google.generativeai as genai

router = APIRouter(prefix="/api", tags=["vital-guard"])

# Database connection
mongo_uri = os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017")
db_name = os.environ.get("MONGODB_DB_NAME", "vitalguard")

try:
    client = MongoClient(mongo_uri)
    db = client[db_name]
    # Create indexes
    db.patients.create_index("patient_id", unique=True)
    db.vitals.create_index("vital_id", unique=True)
    db.medications.create_index("medication_id", unique=True)
    db.doctor_instructions.create_index("instruction_id", unique=True)
    db.nurse_tasks.create_index("task_id", unique=True)
    db.messages.create_index("message_id", unique=True)
    db.reports.create_index("report_id", unique=True)
    db.ai_summaries.create_index("summary_id", unique=True)
    db.discharge_reports.create_index("report_id", unique=True)
    
    # Auto-seed sample health record with evidence attached
    if db.patients.count_documents({}) == 0:
        patient_id = "sample-patient-123"
        db.patients.insert_one({
            "patient_id": patient_id,
            "patient_uid": "PT-SAMPLE123",
            "name": "John Doe",
            "age": 45,
            "gender": "Male",
            "room": "101",
            "condition": "Post-operative recovery",
            "diagnosis": "Appendectomy",
            "care_mode": "live_monitoring",
            "status": "stable",
            "admission_time": (datetime.datetime.utcnow() - datetime.timedelta(days=2)).isoformat() + "Z",
            "discharge_time": None,
            "active": 1,
            "notes": "Patient recovering well from surgery",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
        })
        db.vitals.insert_one({
            "vital_id": "vital-sample-123",
            "patient_id": patient_id,
            "heart_rate": 72,
            "systolic_bp": 120,
            "diastolic_bp": 80,
            "spo2": 98,
            "temperature": 37.0,
            "respiratory_rate": 16,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "attachment": {
                "file_name": "xray_chest_postop.png",
                "image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "attached_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
        })
        db.medications.insert_one({
            "medication_id": "med-sample-123",
            "patient_id": patient_id,
            "name": "Amoxicillin",
            "dosage": "500mg",
            "route": "oral",
            "frequency": "2x daily",
            "timing": "After food",
            "start_time": datetime.datetime.utcnow().isoformat() + "Z",
            "end_time": None,
            "status": "active",
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "attachment": {
                "file_name": "prescription_slip.png",
                "image_data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "attached_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
        })
except Exception as e:
    print(f"MongoDB connection/index error: {e}")
    db = None

# Helpers
def generate_id():
    return str(int(datetime.datetime.utcnow().timestamp() * 1000)) + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))

def generate_patient_uid():
    time_part = hex(int(datetime.datetime.utcnow().timestamp()))[2:].upper()
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"PT-{time_part}{random_part}"

def get_actor(request: Request, body_created_by: Optional[str] = None, body_created_role: Optional[str] = None):
    name = request.headers.get("x-user-name") or body_created_by or "unknown-user"
    role = request.headers.get("x-user-role") or body_created_role or "UNKNOWN"
    return {"name": str(name), "role": str(role)}

# Gemini Integration
def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

# Models
class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    room: str
    condition: str
    diagnosis: Optional[str] = None
    care_mode: str
    notes: Optional[str] = None
    assigned_doctor_uid: Optional[str] = None
    created_by_uid: Optional[str] = None

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    room: Optional[str] = None
    condition: Optional[str] = None
    diagnosis: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class VitalsCreate(BaseModel):
    heart_rate: float
    systolic_bp: float
    diastolic_bp: float
    spo2: float
    temperature: float
    respiratory_rate: float
    attachment: Optional[Dict[str, Any]] = None

class MedicationCreate(BaseModel):
    name: str
    dosage: str
    route: str
    frequency: str
    timing: Optional[str] = None
    attachment: Optional[Dict[str, Any]] = None

class InstructionCreate(BaseModel):
    instruction_text: str
    priority: str
    due_time: Optional[str] = None
    created_by: str
    attachment: Optional[Dict[str, Any]] = None

class TaskCreate(BaseModel):
    task_text: str
    priority: str
    due_time: Optional[str] = None
    linked_instruction_id: Optional[str] = None

class MessageCreate(BaseModel):
    sender_role: str
    sender_name: str
    message_text: str

class ReportCreate(BaseModel):
    file_name: str
    report_type: str
    extracted_text: Optional[str] = None
    findings: Optional[str] = None
    image_data_url: Optional[str] = None

class AttachmentUpdate(BaseModel):
    file_name: str
    image_data_url: str

# PATIENTS ENDPOINTS
@router.get("/patients")
async def get_active_patients():
    if not db:
        return {"success": True, "data": []}
    patients = list(db.patients.find({"active": 1}, {"_id": 0}))
    patients.sort(key=lambda x: x.get("admission_time", ""), reverse=True)
    return {"success": True, "data": patients}

@router.get("/patients/role-scoped")
async def get_role_scoped_patients(role: str = "admin", user_id: Optional[str] = None):
    if not db:
        return {"success": True, "data": [], "count": 0}
        
    role_lower = role.lower()
    patients = list(db.patients.find({"active": 1}, {"_id": 0}))
    scoped_patients = []
    
    if role_lower in ["admin", "hospital"]:
        scoped_patients = patients
    elif role_lower == "investigator":
        scoped_patients = [p for p in patients if p.get("status") in ["critical", "attention"]]
    elif role_lower == "reviewer":
        scoped_patients = [p for p in patients if p.get("status") in ["stable", "attention"]]
    elif role_lower == "authority":
        for p in patients:
            anonymized = p.copy()
            name_parts = anonymized["name"].split()
            anonymized["name"] = name_parts[0][0] + "***" + ((" " + name_parts[-1][0] + "***") if len(name_parts) > 1 else "")
            anonymized["room"] = "REDACTED"
            anonymized["notes"] = "Anonymized for authority audit"
            scoped_patients.append(anonymized)
    elif role_lower in ["user", "patient"]:
        if user_id:
            scoped_patients = [p for p in patients if p.get("patient_id") == user_id or p.get("patient_uid") == user_id]
        else:
            scoped_patients = patients[:1]
    else:
        scoped_patients = patients

    scoped_patients.sort(key=lambda x: x.get("admission_time", ""), reverse=True)
    return {
        "success": True,
        "data": scoped_patients,
        "count": len(scoped_patients)
    }

@router.get("/patients/discharged")
async def get_discharged_patients():
    if not db:
        return {"success": True, "data": []}
    patients = list(db.patients.find({"active": 0}, {"_id": 0}))
    patients.sort(key=lambda x: x.get("discharge_time", ""), reverse=True)
    return {"success": True, "data": patients}

@router.get("/patients/{id}")
async def get_patient_detail(id: str):
    if not db:
        raise HTTPException(status_code=404, detail="Database not initialized")
    patient = db.patients.find_one({"patient_id": id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    vitals = list(db.vitals.find({"patient_id": id}, {"_id": 0}))
    vitals.sort(key=lambda x: x.get("timestamp", ""))
    
    medications = list(db.medications.find({"patient_id": id, "status": "active"}, {"_id": 0}))
    
    instructions = list(db.doctor_instructions.find({"patient_id": id}, {"_id": 0}))
    instructions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    tasks = list(db.nurse_tasks.find({"patient_id": id}, {"_id": 0}))
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    messages = list(db.messages.find({"patient_id": id}, {"_id": 0}))
    messages.sort(key=lambda x: x.get("timestamp", ""))
    
    reports = list(db.reports.find({"patient_id": id}, {"_id": 0}))
    reports.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
    
    summaries = list(db.ai_summaries.find({"patient_id": id}, {"_id": 0}))
    summaries.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    latest_summary = summaries[0] if summaries else None

    return {
        "success": True,
        "data": {
            **patient,
            "vitals": vitals,
            "medications": medications,
            "instructions": instructions,
            "tasks": tasks,
            "messages": messages,
            "reports": reports,
            "aiSummary": latest_summary
        }
    }

@router.post("/patients")
async def create_patient(payload: PatientCreate, request: Request):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    actor = get_actor(request, payload.created_by_uid, "doctor")
    
    patient = {
        "patient_id": generate_id(),
        "patient_uid": generate_patient_uid(),
        "name": payload.name,
        "age": payload.age,
        "gender": payload.gender,
        "room": payload.room,
        "condition": payload.condition,
        "diagnosis": payload.diagnosis,
        "care_mode": payload.care_mode,
        "assigned_doctor_uid": payload.assigned_doctor_uid,
        "created_by_uid": payload.created_by_uid,
        "status": "stable",
        "admission_time": datetime.datetime.utcnow().isoformat() + "Z",
        "discharge_time": None,
        "active": 1,
        "notes": payload.notes,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    db.patients.insert_one(patient)
    patient.pop("_id", None)
    return {"success": True, "data": patient}

@router.put("/patients/{id}")
async def update_patient(id: str, payload: PatientUpdate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    update_data["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    db.patients.update_one({"patient_id": id}, {"$set": update_data})
    updated = db.patients.find_one({"patient_id": id}, {"_id": 0})
    if not updated:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"success": True, "data": updated}

# VITALS ENDPOINTS
@router.post("/patients/{id}/vitals")
async def add_vitals(id: str, payload: VitalsCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    vital = {
        "vital_id": generate_id(),
        "patient_id": id,
        "heart_rate": payload.heart_rate,
        "systolic_bp": payload.systolic_bp,
        "diastolic_bp": payload.diastolic_bp,
        "spo2": payload.spo2,
        "temperature": payload.temperature,
        "respiratory_rate": payload.respiratory_rate,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "attachment": payload.attachment
    }
    
    db.vitals.insert_one(vital)
    vital.pop("_id", None)
    
    patient = db.patients.find_one({"patient_id": id}, {"_id": 0})
    
    analysis = {"riskLevel": "attention", "analysis": "Real-time analysis mock", "recommendation": "Mock alert"}
    if get_gemini_client():
        try:
            model = genai.GenerativeModel('gemini-3.5-flash')
            prompt = f"""
            Analyze the following patient vitals and provide a risk assessment.
            Patient: {json.dumps(patient)}
            Vitals: {json.dumps(vital)}
            Return JSON matching schema: {{'riskLevel': 'stable'|'attention'|'critical', 'analysis': str, 'recommendation': str}}
            """
            response = model.generate_content(prompt)
            data = json.loads(response.text)
            analysis = data
        except Exception as e:
            print(f"Gemini vitals analysis failed: {e}")
            
    db.patients.update_one({"patient_id": id}, {
        "$set": {
            "status": analysis.get("riskLevel", "attention"),
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
    })
    
    return {"success": True, "data": vital, "analysis": analysis}

# MEDICATION ENDPOINTS
@router.post("/patients/{id}/medications")
async def add_medication(id: str, payload: MedicationCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    medication = {
        "medication_id": generate_id(),
        "patient_id": id,
        "name": payload.name,
        "dosage": payload.dosage,
        "route": payload.route,
        "frequency": payload.frequency,
        "timing": payload.timing,
        "start_time": datetime.datetime.utcnow().isoformat() + "Z",
        "end_time": None,
        "status": "active",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "attachment": payload.attachment
    }
    
    db.medications.insert_one(medication)
    medication.pop("_id", None)
    return {"success": True, "data": medication}

@router.delete("/medications/{id}")
async def delete_medication(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    db.medications.delete_one({"medication_id": id})
    return {"success": True, "message": "Medication deleted"}

# DOCTOR INSTRUCTIONS ENDPOINTS
@router.post("/patients/{id}/instructions")
async def add_instruction(id: str, payload: InstructionCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    instruction = {
        "instruction_id": generate_id(),
        "patient_id": id,
        "instruction_text": payload.instruction_text,
        "priority": payload.priority,
        "due_time": payload.due_time,
        "created_by": payload.created_by,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "completed": 0,
        "completed_at": None,
        "attachment": payload.attachment
    }
    
    db.doctor_instructions.insert_one(instruction)
    instruction.pop("_id", None)
    return {"success": True, "data": instruction}

@router.delete("/instructions/{id}")
async def delete_instruction(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    db.doctor_instructions.delete_one({"instruction_id": id})
    return {"success": True, "message": "Instruction deleted"}

# NURSE TASKS ENDPOINTS
@router.post("/patients/{id}/tasks")
async def add_task(id: str, payload: TaskCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    task = {
        "task_id": generate_id(),
        "patient_id": id,
        "task_text": payload.task_text,
        "priority": payload.priority,
        "due_time": payload.due_time,
        "linked_instruction_id": payload.linked_instruction_id,
        "status": "pending",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "completed_at": None,
        "completed_by": None
    }
    
    db.nurse_tasks.insert_one(task)
    task.pop("_id", None)
    return {"success": True, "data": task}

@router.put("/tasks/{id}/complete")
async def complete_task(id: str, body: Dict[str, Any]):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    completed_by = body.get("completed_by", "unknown-nurse")
    
    db.nurse_tasks.update_one({"task_id": id}, {
        "$set": {
            "status": "completed",
            "completed_at": datetime.datetime.utcnow().isoformat() + "Z",
            "completed_by": completed_by
        }
    })
    
    updated = db.nurse_tasks.find_one({"task_id": id}, {"_id": 0})
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": updated}

# MESSAGES ENDPOINTS
@router.post("/patients/{id}/messages")
async def add_message(id: str, payload: MessageCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    message = {
        "message_id": generate_id(),
        "patient_id": id,
        "sender_role": payload.sender_role,
        "sender_name": payload.sender_name,
        "message_text": payload.message_text,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    db.messages.insert_one(message)
    message.pop("_id", None)
    return {"success": True, "data": message}

# REPORTS ENDPOINTS
@router.post("/patients/{id}/reports")
async def add_report(id: str, payload: ReportCreate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    report = {
        "report_id": generate_id(),
        "patient_id": id,
        "file_name": payload.file_name,
        "report_type": payload.report_type,
        "extracted_text": payload.extracted_text,
        "findings": payload.findings,
        "image_data_url": payload.image_data_url,
        "uploaded_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    db.reports.insert_one(report)
    report.pop("_id", None)
    return {"success": True, "data": report}

@router.delete("/reports/{id}")
async def delete_report(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    db.reports.delete_one({"report_id": id})
    return {"success": True, "message": "Report deleted"}

# POST endpoint to update attachment on any health record type (vitals, medications, instructions)
@router.post("/records/{record_type}/{record_id}/attachment")
async def update_record_attachment(record_type: str, record_id: str, payload: AttachmentUpdate):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    collection_map = {
        "vitals": ("vital_id", db.vitals),
        "medications": ("medication_id", db.medications),
        "instructions": ("instruction_id", db.doctor_instructions)
    }
    
    if record_type not in collection_map:
        raise HTTPException(status_code=400, detail=f"Invalid record type: {record_type}")
        
    id_field, collection = collection_map[record_type]
    
    attachment_dict = {
        "file_name": payload.file_name,
        "image_data_url": payload.image_data_url,
        "attached_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    res = collection.update_one({id_field: record_id}, {"$set": {"attachment": attachment_dict}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
        
    updated_record = collection.find_one({id_field: record_id}, {"_id": 0})
    return {"success": True, "data": updated_record}

# AI SUMMARY ENDPOINTS
@router.post("/patients/{id}/summary")
async def get_ai_summary(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    patient = db.patients.find_one({"patient_id": id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    vitals = list(db.vitals.find({"patient_id": id}, {"_id": 0}))
    vitals.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    recent_vitals = vitals[:10]
    
    medications = list(db.medications.find({"patient_id": id, "status": "active"}, {"_id": 0}))
    instructions = list(db.doctor_instructions.find({"patient_id": id}, {"_id": 0}))
    tasks = list(db.nurse_tasks.find({"patient_id": id}, {"_id": 0}))
    reports = list(db.reports.find({"patient_id": id}, {"_id": 0}))
    
    patient_data = {
        **patient,
        "vitals": recent_vitals,
        "medications": medications,
        "instructions": instructions,
        "tasks": tasks,
        "reports": reports
    }
    
    summary = {
        "overview": f"{patient.get('name')} is a {patient.get('age')}-year-old {patient.get('gender')} currently categorized as {patient.get('status')}.",
        "keyPoints": ["Status: " + patient.get("status"), "Care mode: " + patient.get("care_mode")],
        "recentChanges": ["Simulated changes log"],
        "recommendations": ["Follow baseline care plan"]
    }
    
    if get_gemini_client():
        try:
            model = genai.GenerativeModel('gemini-3.5-flash')
            prompt = f"""
            You are a clinical assistant. Generate a structured patient summary in JSON:
            Patient Data: {json.dumps(patient_data)}
            Schema: {{'overview': str, 'keyPoints': [str], 'recentChanges': [str], 'recommendations': [str]}}
            """
            response = model.generate_content(prompt)
            summary = json.loads(response.text)
        except Exception as e:
            print(f"Gemini summary generation failed: {e}")
            
    summary_record = {
        "summary_id": generate_id(),
        "patient_id": id,
        "overview": summary.get("overview"),
        "key_points": json.dumps(summary.get("keyPoints")),
        "recent_changes": json.dumps(summary.get("recentChanges")),
        "recommendations": json.dumps(summary.get("recommendations")),
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    db.ai_summaries.insert_one(summary_record)
    return {"success": True, "data": summary}

# DISCHARGE ENDPOINTS
@router.post("/patients/{id}/discharge")
async def discharge_patient(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    
    discharge_time = datetime.datetime.utcnow().isoformat() + "Z"
    patient = db.patients.find_one({"patient_id": id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    vitals = list(db.vitals.find({"patient_id": id}, {"_id": 0}))
    vitals.sort(key=lambda x: x.get("timestamp", ""))
    medications = list(db.medications.find({"patient_id": id}, {"_id": 0}))
    instructions = list(db.doctor_instructions.find({"patient_id": id}, {"_id": 0}))
    tasks = list(db.nurse_tasks.find({"patient_id": id}, {"_id": 0}))
    messages = list(db.messages.find({"patient_id": id}, {"_id": 0}))
    reports = list(db.reports.find({"patient_id": id}, {"_id": 0}))
    
    patient_data = {
        **patient,
        "discharge_time": discharge_time,
        "vitals": vitals,
        "medications": medications,
        "instructions": instructions,
        "tasks": tasks,
        "messages": messages,
        "reports": reports
    }
    
    ai_summary = {
        "summary": "AI discharge course simulation.",
        "clinicalCourse": "The patient completed scheduled treatment.",
        "finalDiagnosis": patient.get("diagnosis") or "Not specified",
        "medicationsAtDischarge": ", ".join([m.get("name") for m in medications]),
        "followUpRecommendations": ["Follow up with clinical team"]
    }
    
    if get_gemini_client():
        try:
            model = genai.GenerativeModel('gemini-3.5-flash')
            prompt = f"""
            Generate a JSON discharge summary:
            Data: {json.dumps(patient_data)}
            Schema: {{'summary': str, 'clinicalCourse': str, 'finalDiagnosis': str, 'medicationsAtDischarge': str, 'followUpRecommendations': [str]}}
            """
            response = model.generate_content(prompt)
            ai_summary = json.loads(response.text)
        except Exception as e:
            print(f"Gemini discharge summary failed: {e}")
            
    admission_time = datetime.datetime.fromisoformat(patient.get("admission_time").replace("Z", "+00:00"))
    d_time = datetime.datetime.fromisoformat(discharge_time.replace("Z", "+00:00"))
    length_of_stay = max(1, (d_time - admission_time).days)
    
    discharge_report = {
        "patient_id": id,
        "patient_name": patient.get("name"),
        "age": patient.get("age"),
        "gender": patient.get("gender"),
        "room": patient.get("room"),
        "admission_time": patient.get("admission_time"),
        "discharge_time": discharge_time,
        "length_of_stay": length_of_stay,
        "diagnosis": patient.get("diagnosis"),
        "condition": patient.get("condition"),
        "final_status": patient.get("status"),
        "care_mode": patient.get("care_mode"),
        "vitals_summary": {
            "total_readings": len(vitals),
            "first_reading": vitals[0] if vitals else None,
            "last_reading": vitals[-1] if vitals else None
        },
        "medications": [
            {"name": m.get("name"), "dosage": m.get("dosage"), "frequency": m.get("frequency"), "route": m.get("route")}
            for m in medications
        ],
        "instructions_completed": len([i for i in instructions if i.get("completed")]),
        "instructions_total": len(instructions),
        "tasks_completed": len([t for t in tasks if t.get("status") == "completed"]),
        "tasks_total": len(tasks),
        "reports_uploaded": len(reports),
        "ai_discharge_summary": ai_summary,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    report_record = {
        "report_id": generate_id(),
        "patient_id": id,
        "report_data": json.dumps(discharge_report),
        "generated_at": discharge_time
    }
    
    db.discharge_reports.insert_one(report_record)
    db.patients.update_one({"patient_id": id}, {
        "$set": {
            "active": 0,
            "discharge_time": discharge_time,
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
    })
    
    return {"success": True, "data": discharge_report}

@router.get("/patients/{id}/discharge-report")
async def get_discharge_report(id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Database not connected")
    reports = list(db.discharge_reports.find({"patient_id": id}, {"_id": 0}))
    if not reports:
        raise HTTPException(status_code=404, detail="Discharge report not found")
    reports.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return {"success": True, "data": json.loads(reports[0].get("report_data"))}

# BLOCKCHAIN MOCKS/ENDPOINTS
@router.post("/blockchain/records")
async def store_blockchain_record(body: Dict[str, Any]):
    return {
        "success": True,
        "data": {
            "patientId": body.get("patientId"),
            "recordHash": "0x" + "".join(random.choices(string.hexdigits.lower(), k=64)),
            "transactionHash": "0x" + "".join(random.choices(string.hexdigits.lower(), k=64))
        }
    }

@router.post("/blockchain/verify")
async def verify_blockchain_record(body: Dict[str, Any]):
    return {
        "success": True,
        "data": {
            "patientId": body.get("patientId"),
            "recordHash": "0x" + "".join(random.choices(string.hexdigits.lower(), k=64)),
            "exists": True
        }
    }

@router.post("/blockchain/consent")
async def grant_blockchain_consent(body: Dict[str, Any]):
    return {
        "success": True,
        "data": {
            "patientId": body.get("patientId"),
            "transactionHash": "0x" + "".join(random.choices(string.hexdigits.lower(), k=64))
        }
    }

@router.get("/health")
async def vitalguard_health():
    return {
        "success": True,
        "message": "VitalGuard AI Python Backend is running",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
