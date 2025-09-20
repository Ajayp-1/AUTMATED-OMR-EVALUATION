"""
Startup script for OMR Evaluation System
Runs both FastAPI backend and Streamlit frontend
"""
import subprocess
import sys
import time
import os
import threading
from pathlib import Path

def run_backend():
    """Run FastAPI backend server"""
    print("🚀 Starting FastAPI backend server...")
    try:
        # Change to the project directory
        os.chdir(Path(__file__).parent)
        
        # Run FastAPI with uvicorn
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.backend.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("🛑 Backend server stopped")
    except Exception as e:
        print(f"❌ Error starting backend: {e}")

def run_frontend():
    """Run Streamlit frontend"""
    print("🎨 Starting Streamlit frontend...")
    try:
        # Wait a bit for backend to start
        time.sleep(3)
        
        # Change to the project directory
        os.chdir(Path(__file__).parent)
        
        # Run Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "app/frontend/main.py", 
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ])
    except KeyboardInterrupt:
        print("🛑 Frontend server stopped")
    except Exception as e:
        print(f"❌ Error starting frontend: {e}")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn', 
        'streamlit': 'streamlit', 
        'opencv-python': 'cv2',
        'numpy': 'numpy', 
        'pandas': 'pandas', 
        'sqlalchemy': 'sqlalchemy', 
        'plotly': 'plotly'
    }
    
    missing_packages = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Please install missing packages using:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = [
        "uploads",
        "processed", 
        "config",
        "logs",
        "data"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 Created directory: {directory}")

def main():
    """Main function to start the system"""
    print("=" * 60)
    print("🎯 OMR EVALUATION SYSTEM STARTUP")
    print("=" * 60)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ All dependencies are installed")
    
    # Create directories
    print("\n📁 Creating necessary directories...")
    create_directories()
    
    # Start servers
    print("\n🚀 Starting servers...")
    print("   Backend API: http://localhost:8000")
    print("   Frontend UI: http://localhost:8501")
    print("   API Docs: http://localhost:8000/docs")
    print("\n⚠️  Press Ctrl+C to stop both servers")
    print("=" * 60)
    
    try:
        # Start backend in a separate thread
        backend_thread = threading.Thread(target=run_backend, daemon=True)
        backend_thread.start()
        
        # Start frontend in main thread
        run_frontend()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down OMR Evaluation System...")
        print("✅ System stopped successfully")

if __name__ == "__main__":
    main()