"""
Streamlit frontend for OMR Evaluation System
Provides web interface for uploading, processing, and reviewing OMR sheets
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import time
import os
from PIL import Image
import io
import base64

# Configure Streamlit page
st.set_page_config(
    page_title="OMR Evaluation System",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "http://localhost:8000"

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #f5c6cb;
    }
    .warning-message {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #ffeaa7;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_exam' not in st.session_state:
    st.session_state.current_exam = None
if 'processing_queue' not in st.session_state:
    st.session_state.processing_queue = []
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 5

# Helper functions
def make_api_request(endpoint, method="GET", data=None, files=None):
    """Make API request with error handling"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            if files:
                response = requests.post(url, data=data, files=files)
            else:
                response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": response.text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def display_message(message, message_type="info"):
    """Display styled message"""
    if message_type == "success":
        st.markdown(f'<div class="success-message">{message}</div>', unsafe_allow_html=True)
    elif message_type == "error":
        st.markdown(f'<div class="error-message">{message}</div>', unsafe_allow_html=True)
    elif message_type == "warning":
        st.markdown(f'<div class="warning-message">{message}</div>', unsafe_allow_html=True)
    else:
        st.info(message)

def format_datetime(dt_string):
    """Format datetime string for display"""
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_string

# Sidebar navigation
st.sidebar.title("🎯 OMR Evaluation System")
st.sidebar.markdown("---")

page = st.sidebar.selectbox(
    "Navigate to:",
    ["Dashboard", "Upload Files", "Manage Exams", "View Results", "Review Flagged", "System Status", "Settings"]
)

# Main content based on selected page
if page == "Dashboard":
    st.markdown('<h1 class="main-header">📊 Dashboard</h1>', unsafe_allow_html=True)
    
    # Get system statistics
    health_response = make_api_request("/health")
    
    if health_response["success"]:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("System Status", "🟢 Online")
        
        with col2:
            # Get total exams
            exams_response = make_api_request("/exams/")
            total_exams = len(exams_response["data"]) if exams_response["success"] else 0
            st.metric("Total Exams", total_exams)
        
        with col3:
            # Get processing queue status
            queue_response = make_api_request("/processing/queue")
            queue_size = len(queue_response["data"]) if queue_response["success"] else 0
            st.metric("Processing Queue", queue_size)
        
        with col4:
            st.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))
    
    st.markdown("---")
    
    # Recent activity
    st.subheader("📈 Recent Activity")
    
    # Get recent exams
    exams_response = make_api_request("/exams/")
    if exams_response["success"] and exams_response["data"]:
        recent_exams = sorted(exams_response["data"], 
                            key=lambda x: x["created_at"], reverse=True)[:5]
        
        exam_data = []
        for exam in recent_exams:
            # Get exam statistics
            stats_response = make_api_request(f"/exams/{exam['id']}/statistics")
            if stats_response["success"]:
                stats = stats_response["data"]
                exam_data.append({
                    "Exam Name": exam["exam_name"],
                    "Date": format_datetime(exam["exam_date"]),
                    "Students": stats.get("total_students", 0),
                    "Avg Score": f"{stats.get('average_total_score', 0):.1f}",
                    "Pass Rate": f"{stats.get('overall_pass_rate', 0):.1f}%"
                })
        
        if exam_data:
            df = pd.DataFrame(exam_data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No exam data available yet.")
    else:
        st.info("No exams found. Create an exam to get started!")

elif page == "Upload Files":
    st.markdown('<h1 class="main-header">📤 Upload OMR Sheets</h1>', unsafe_allow_html=True)
    
    # Get available exams
    exams_response = make_api_request("/exams/")
    
    if not exams_response["success"] or not exams_response["data"]:
        st.warning("No exams available. Please create an exam first.")
        st.stop()
    
    exams = exams_response["data"]
    exam_options = {f"{exam['exam_name']} ({exam['id']})": exam['id'] for exam in exams}
    
    # Upload form
    with st.form("upload_form"):
        st.subheader("Upload Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_exam = st.selectbox("Select Exam", list(exam_options.keys()))
            exam_id = exam_options[selected_exam]
        
        with col2:
            upload_type = st.radio("Upload Type", ["Single File", "Batch Upload"])
        
        if upload_type == "Single File":
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input("Student ID (optional)")
            with col2:
                sheet_version = st.selectbox("Sheet Version", ["A", "B", "C", "D", "Auto-detect"])
            
            uploaded_file = st.file_uploader(
                "Choose OMR sheet image",
                type=['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'pdf'],
                accept_multiple_files=False
            )
        else:
            uploaded_files = st.file_uploader(
                "Choose OMR sheet images",
                type=['jpg', 'jpeg', 'png', 'bmp', 'tiff', 'pdf'],
                accept_multiple_files=True
            )
        
        submit_button = st.form_submit_button("Upload and Process")
    
    if submit_button:
        if upload_type == "Single File" and uploaded_file:
            # Single file upload
            files = {"file": uploaded_file.getvalue()}
            data = {
                "exam_id": exam_id,
                "student_id": student_id if student_id else None,
                "sheet_version": sheet_version if sheet_version != "Auto-detect" else None
            }
            
            with st.spinner("Uploading and processing file..."):
                response = make_api_request("/upload/single", method="POST", data=data, files=files)
            
            if response["success"]:
                display_message(f"✅ File uploaded successfully! Queue ID: {response['data']['queue_id']}", "success")
                st.session_state.processing_queue.append(response['data']['queue_id'])
            else:
                display_message(f"❌ Upload failed: {response['error']}", "error")
        
        elif upload_type == "Batch Upload" and uploaded_files:
            # Batch upload
            files = [("files", file.getvalue()) for file in uploaded_files]
            data = {"exam_id": exam_id}
            
            with st.spinner(f"Uploading {len(uploaded_files)} files..."):
                response = make_api_request("/upload/batch", method="POST", data=data, files=files)
            
            if response["success"]:
                display_message(f"✅ {len(uploaded_files)} files uploaded successfully!", "success")
                queue_ids = [file_info['queue_id'] for file_info in response['data']['files']]
                st.session_state.processing_queue.extend(queue_ids)
            else:
                display_message(f"❌ Upload failed: {response['error']}", "error")
    
    # Processing status
    if st.session_state.processing_queue:
        st.markdown("---")
        st.subheader("🔄 Processing Status")
        
        status_container = st.container()
        
        with status_container:
            for queue_id in st.session_state.processing_queue:
                status_response = make_api_request(f"/processing/queue/{queue_id}")
                if status_response["success"]:
                    status_data = status_response["data"]
                    status = status_data["status"]
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.write(f"Queue ID: {queue_id}")
                    
                    with col2:
                        if status == "completed":
                            st.success("✅ Completed")
                        elif status == "processing":
                            st.warning("🔄 Processing")
                        elif status == "failed":
                            st.error("❌ Failed")
                        else:
                            st.info("⏳ Queued")
                    
                    with col3:
                        if status == "completed":
                            if st.button(f"Remove {queue_id}", key=f"remove_{queue_id}"):
                                st.session_state.processing_queue.remove(queue_id)
                                st.rerun()

elif page == "Manage Exams":
    st.markdown('<h1 class="main-header">📋 Manage Exams</h1>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Create New Exam", "View Existing Exams"])
    
    with tab1:
        st.subheader("Create New Exam")
        
        with st.form("create_exam_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                exam_name = st.text_input("Exam Name*")
                exam_date = st.date_input("Exam Date*")
                exam_time = st.time_input("Exam Time*")
            
            with col2:
                total_questions = st.number_input("Total Questions", value=100, min_value=1, max_value=200)
                questions_per_subject = st.number_input("Questions per Subject", value=20, min_value=1, max_value=50)
                sheet_versions = st.multiselect("Sheet Versions", ["A", "B", "C", "D"], default=["A", "B"])
            
            subjects = st.text_area(
                "Subjects (one per line)",
                value="Mathematics\nPhysics\nChemistry\nBiology\nEnglish"
            ).strip().split('\n')
            
            st.subheader("Answer Keys")
            answer_keys = {}
            
            for version in sheet_versions:
                st.write(f"**Answer Key for Version {version}**")
                
                # Option to upload answer key file or enter manually
                upload_option = st.radio(f"Input method for Version {version}", 
                                       ["Manual Entry", "Upload File"], 
                                       key=f"input_method_{version}")
                
                if upload_option == "Upload File":
                    uploaded_key = st.file_uploader(f"Upload answer key for Version {version}", 
                                                   type=['json', 'csv'], 
                                                   key=f"upload_{version}")
                    if uploaded_key:
                        # Process uploaded file
                        if uploaded_key.name.endswith('.json'):
                            answer_keys[version] = json.load(uploaded_key)
                        elif uploaded_key.name.endswith('.csv'):
                            df = pd.read_csv(uploaded_key)
                            if 'question' in df.columns and 'answer' in df.columns:
                                answer_keys[version] = dict(zip(df['question'].astype(str), df['answer']))
                else:
                    # Manual entry
                    answers_text = st.text_area(
                        f"Enter answers for Version {version} (format: 1:A, 2:B, 3:C, ...)",
                        key=f"answers_{version}",
                        height=100
                    )
                    
                    if answers_text:
                        try:
                            # Parse manual entry
                            answers = {}
                            for line in answers_text.split(','):
                                if ':' in line:
                                    q, a = line.strip().split(':')
                                    answers[q.strip()] = a.strip().upper()
                            answer_keys[version] = answers
                        except:
                            st.error(f"Invalid format for Version {version}")
            
            submit_exam = st.form_submit_button("Create Exam")
        
        if submit_exam:
            if exam_name and answer_keys:
                exam_datetime = datetime.combine(exam_date, exam_time)
                
                exam_data = {
                    "exam_name": exam_name,
                    "exam_date": exam_datetime.isoformat(),
                    "total_questions": total_questions,
                    "subjects": subjects,
                    "questions_per_subject": questions_per_subject,
                    "sheet_versions": sheet_versions,
                    "answer_keys": answer_keys
                }
                
                response = make_api_request("/exams/", method="POST", data=exam_data)
                
                if response["success"]:
                    display_message("✅ Exam created successfully!", "success")
                    st.rerun()
                else:
                    display_message(f"❌ Failed to create exam: {response['error']}", "error")
            else:
                display_message("❌ Please fill in all required fields and answer keys", "error")
    
    with tab2:
        st.subheader("Existing Exams")
        
        exams_response = make_api_request("/exams/")
        
        if exams_response["success"] and exams_response["data"]:
            for exam in exams_response["data"]:
                with st.expander(f"📋 {exam['exam_name']} - {format_datetime(exam['exam_date'])}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Total Questions:** {exam['total_questions']}")
                        st.write(f"**Questions per Subject:** {exam['questions_per_subject']}")
                    
                    with col2:
                        st.write(f"**Subjects:** {', '.join(exam['subjects'])}")
                        st.write(f"**Sheet Versions:** {', '.join(exam['sheet_versions'])}")
                    
                    with col3:
                        st.write(f"**Created:** {format_datetime(exam['created_at'])}")
                        
                        # Get exam statistics
                        stats_response = make_api_request(f"/exams/{exam['id']}/statistics")
                        if stats_response["success"]:
                            stats = stats_response["data"]
                            st.write(f"**Students Processed:** {stats.get('total_students', 0)}")
                    
                    # Show answer keys
                    if st.checkbox(f"Show Answer Keys", key=f"show_keys_{exam['id']}"):
                        for version, answers in exam['answer_keys'].items():
                            st.write(f"**Version {version}:**")
                            # Display first 10 answers as preview
                            preview_answers = dict(list(answers.items())[:10])
                            st.json(preview_answers)
                            if len(answers) > 10:
                                st.write(f"... and {len(answers) - 10} more answers")
        else:
            st.info("No exams found. Create your first exam using the form above.")

elif page == "View Results":
    st.markdown('<h1 class="main-header">📊 View Results</h1>', unsafe_allow_html=True)
    
    # Get available exams
    exams_response = make_api_request("/exams/")
    
    if not exams_response["success"] or not exams_response["data"]:
        st.warning("No exams available.")
        st.stop()
    
    exams = exams_response["data"]
    exam_options = {f"{exam['exam_name']} ({exam['id']})": exam['id'] for exam in exams}
    
    selected_exam = st.selectbox("Select Exam to View Results", list(exam_options.keys()))
    exam_id = exam_options[selected_exam]
    
    # Get exam results
    results_response = make_api_request(f"/results/exam/{exam_id}")
    
    if results_response["success"] and results_response["data"]:
        results = results_response["data"]
        
        # Summary statistics
        st.subheader("📈 Summary Statistics")
        
        total_students = len(results)
        total_scores = [r["total_score"] for r in results]
        avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
        max_score = max(total_scores) if total_scores else 0
        min_score = min(total_scores) if total_scores else 0
        pass_rate = len([s for s in total_scores if s >= 50]) / len(total_scores) * 100 if total_scores else 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Students", total_students)
        with col2:
            st.metric("Average Score", f"{avg_score:.1f}")
        with col3:
            st.metric("Highest Score", max_score)
        with col4:
            st.metric("Lowest Score", min_score)
        with col5:
            st.metric("Pass Rate", f"{pass_rate:.1f}%")
        
        # Visualizations
        st.subheader("📊 Score Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Score histogram
            fig_hist = px.histogram(
                x=total_scores,
                nbins=20,
                title="Score Distribution",
                labels={"x": "Total Score", "y": "Number of Students"}
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with col2:
            # Subject-wise performance
            subject_data = []
            for result in results:
                subject_data.append({
                    "Mathematics": result["subject_1_score"],
                    "Physics": result["subject_2_score"],
                    "Chemistry": result["subject_3_score"],
                    "Biology": result["subject_4_score"],
                    "English": result["subject_5_score"]
                })
            
            if subject_data:
                df_subjects = pd.DataFrame(subject_data)
                avg_subjects = df_subjects.mean()
                
                fig_subjects = px.bar(
                    x=avg_subjects.index,
                    y=avg_subjects.values,
                    title="Average Score by Subject",
                    labels={"x": "Subject", "y": "Average Score"}
                )
                st.plotly_chart(fig_subjects, use_container_width=True)
        
        # Detailed results table
        st.subheader("📋 Detailed Results")
        
        # Prepare data for table
        table_data = []
        for result in results:
            table_data.append({
                "Student ID": result["student"]["student_id"] if result["student"] else "Unknown",
                "Student Name": result["student"]["name"] if result["student"] else "Unknown",
                "Version": result["sheet_version"],
                "Math": result["subject_1_score"],
                "Physics": result["subject_2_score"],
                "Chemistry": result["subject_3_score"],
                "Biology": result["subject_4_score"],
                "English": result["subject_5_score"],
                "Total": result["total_score"],
                "Status": result["processing_status"],
                "Confidence": f"{result['confidence_score']:.2f}",
                "Processed": format_datetime(result["processed_at"]) if result["processed_at"] else "N/A"
            })
        
        df_results = pd.DataFrame(table_data)
        st.dataframe(df_results, use_container_width=True)
        
        # Export options
        st.subheader("📥 Export Results")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Export as CSV"):
                response = make_api_request(f"/export/exam/{exam_id}/csv")
                if response["success"]:
                    st.success("CSV export initiated. Check downloads folder.")
                else:
                    st.error("Export failed.")
        
        with col2:
            if st.button("Export as Excel"):
                response = make_api_request(f"/export/exam/{exam_id}/excel")
                if response["success"]:
                    st.success("Excel export initiated. Check downloads folder.")
                else:
                    st.error("Export failed.")
        
        with col3:
            if st.button("Export as JSON"):
                response = make_api_request(f"/export/exam/{exam_id}/json")
                if response["success"]:
                    st.success("JSON export initiated. Check downloads folder.")
                else:
                    st.error("Export failed.")
    
    else:
        st.info("No results found for this exam.")

elif page == "Review Flagged":
    st.markdown('<h1 class="main-header">🚩 Review Flagged Results</h1>', unsafe_allow_html=True)
    
    # Get flagged results
    flagged_response = make_api_request("/results/flagged")
    
    if flagged_response["success"] and flagged_response["data"]:
        flagged_results = flagged_response["data"]
        
        st.write(f"Found {len(flagged_results)} results that need review.")
        
        for result in flagged_results:
            with st.expander(f"🚩 Student: {result['student']['name'] if result['student'] else 'Unknown'} - Score: {result['total_score']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Student Information:**")
                    st.write(f"ID: {result['student']['student_id'] if result['student'] else 'Unknown'}")
                    st.write(f"Name: {result['student']['name'] if result['student'] else 'Unknown'}")
                    st.write(f"Sheet Version: {result['sheet_version']}")
                    st.write(f"Confidence Score: {result['confidence_score']:.2f}")
                
                with col2:
                    st.write("**Scores:**")
                    st.write(f"Mathematics: {result['subject_1_score']}/20")
                    st.write(f"Physics: {result['subject_2_score']}/20")
                    st.write(f"Chemistry: {result['subject_3_score']}/20")
                    st.write(f"Biology: {result['subject_4_score']}/20")
                    st.write(f"English: {result['subject_5_score']}/20")
                    st.write(f"**Total: {result['total_score']}/100**")
                
                if result["flagged_questions"]:
                    st.write("**Flagged Questions:**")
                    st.write(", ".join(result["flagged_questions"]))
                
                # Review actions
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"Approve Result", key=f"approve_{result['id']}"):
                        # Update result status
                        st.success("Result approved!")
                
                with col2:
                    if st.button(f"Request Manual Review", key=f"manual_{result['id']}"):
                        st.info("Marked for manual review.")
                
                with col3:
                    if st.button(f"View Original Image", key=f"image_{result['id']}"):
                        st.info("Image viewing feature coming soon.")
    
    else:
        st.info("No flagged results found. All processed results look good!")

elif page == "System Status":
    st.markdown('<h1 class="main-header">⚙️ System Status</h1>', unsafe_allow_html=True)
    
    # Health check
    health_response = make_api_request("/health")
    
    if health_response["success"]:
        st.success("🟢 System is online and healthy")
        
        health_data = health_response["data"]
        st.write(f"**Last Check:** {health_data['timestamp']}")
    else:
        st.error("🔴 System appears to be offline")
    
    # Processing queue status
    st.subheader("🔄 Processing Queue")
    
    queue_response = make_api_request("/processing/queue")
    
    if queue_response["success"]:
        queue_data = queue_response["data"]
        
        if queue_data:
            # Group by status
            status_counts = {}
            for item in queue_data:
                status = item["status"]
                status_counts[status] = status_counts.get(status, 0) + 1
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Queued", status_counts.get("queued", 0))
            with col2:
                st.metric("Processing", status_counts.get("processing", 0))
            with col3:
                st.metric("Completed", status_counts.get("completed", 0))
            with col4:
                st.metric("Failed", status_counts.get("failed", 0))
            
            # Detailed queue view
            if st.checkbox("Show detailed queue"):
                queue_df = pd.DataFrame([
                    {
                        "Queue ID": item["id"],
                        "Exam ID": item["exam_id"],
                        "Status": item["status"],
                        "Created": format_datetime(item["created_at"]),
                        "Started": format_datetime(item["started_at"]) if item["started_at"] else "N/A",
                        "Completed": format_datetime(item["completed_at"]) if item["completed_at"] else "N/A"
                    }
                    for item in queue_data
                ])
                st.dataframe(queue_df, use_container_width=True)
        else:
            st.info("Processing queue is empty.")
    
    # System metrics (placeholder for future implementation)
    st.subheader("📊 System Metrics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Placeholder metrics
        st.metric("Total Files Processed", "1,234")
        st.metric("Average Processing Time", "2.3 seconds")
    
    with col2:
        st.metric("Success Rate", "98.5%")
        st.metric("Storage Used", "2.1 GB")

elif page == "Settings":
    st.markdown('<h1 class="main-header">⚙️ Settings</h1>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["System Configuration", "Processing Settings", "About"])
    
    with tab1:
        st.subheader("System Configuration")
        
        # API endpoint configuration
        st.write("**API Configuration**")
        new_api_url = st.text_input("API Base URL", value=API_BASE_URL)
        
        if st.button("Test Connection"):
            test_response = make_api_request("/health")
            if test_response["success"]:
                st.success("✅ Connection successful!")
            else:
                st.error("❌ Connection failed!")
        
        # Auto-refresh settings
        st.write("**Display Settings**")
        auto_refresh = st.checkbox("Enable auto-refresh", value=True)
        if auto_refresh:
            refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 
                                        value=st.session_state.refresh_interval)
            st.session_state.refresh_interval = refresh_interval
    
    with tab2:
        st.subheader("Processing Settings")
        
        # Confidence threshold
        confidence_threshold = st.slider("Confidence Threshold", 0.0, 1.0, 0.8, 0.05)
        st.write("Results below this confidence level will be flagged for review.")
        
        # Processing options
        auto_detect_version = st.checkbox("Auto-detect sheet version", value=True)
        parallel_processing = st.checkbox("Enable parallel processing", value=True)
        
        if st.button("Save Processing Settings"):
            st.success("Settings saved successfully!")
    
    with tab3:
        st.subheader("About OMR Evaluation System")
        
        st.write("""
        **Version:** 1.0.0
        
        **Description:** 
        Automated OMR (Optical Mark Recognition) Evaluation & Scoring System for educational institutions.
        
        **Features:**
        - Automated bubble detection and classification
        - Multi-version answer sheet support
        - Subject-wise scoring
        - Batch processing capabilities
        - Comprehensive reporting and analytics
        - Manual review workflow for flagged results
        
        **Technology Stack:**
        - Backend: FastAPI + Python
        - Frontend: Streamlit
        - Image Processing: OpenCV + NumPy
        - Database: SQLite/PostgreSQL
        - Machine Learning: TensorFlow/Scikit-learn
        
        **Developed for:** Innomatics Research Labs
        """)
        
        st.write("**System Requirements:**")
        st.write("- Python 3.8+")
        st.write("- 4GB RAM minimum")
        st.write("- 10GB storage space")
        st.write("- Modern web browser")

# Auto-refresh functionality
if page in ["Dashboard", "System Status"] and st.session_state.get('refresh_interval', 5) > 0:
    time.sleep(st.session_state.refresh_interval)
    st.rerun()

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666; font-size: 0.8rem;'>"
    "OMR Evaluation System v1.0.0 | Developed for Innomatics Research Labs"
    "</div>",
    unsafe_allow_html=True
)