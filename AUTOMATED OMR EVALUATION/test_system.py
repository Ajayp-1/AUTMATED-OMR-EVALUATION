#!/usr/bin/env python3
"""
Test script to verify system integration and basic functionality
"""

import os
import sys
import json
import requests
import time
from pathlib import Path

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    try:
        import cv2
        import numpy as np
        import pandas as pd
        import streamlit as st
        import fastapi
        import sqlalchemy
        import uvicorn
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_directory_structure():
    """Test if all required directories exist"""
    print("Testing directory structure...")
    required_dirs = [
        "app/core",
        "app/database", 
        "app/backend",
        "app/frontend",
        "config",
        "data",
        "uploads",
        "processed",
        "logs"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - Missing")
            all_exist = False
    
    return all_exist

def test_config_files():
    """Test if configuration files are valid"""
    print("Testing configuration files...")
    
    # Test answer keys
    try:
        with open("config/answer_keys.json", "r") as f:
            answer_keys = json.load(f)
        
        # Verify structure
        required_versions = ["A", "B", "C", "D"]
        for version in required_versions:
            if version in answer_keys:
                if len(answer_keys[version]) == 100:
                    print(f"✅ Answer key version {version} - 100 questions")
                else:
                    print(f"❌ Answer key version {version} - {len(answer_keys[version])} questions (expected 100)")
            else:
                print(f"❌ Answer key version {version} - Missing")
        
    except Exception as e:
        print(f"❌ Answer keys error: {e}")
        return False
    
    # Test exam config
    try:
        with open("config/exam_config.json", "r") as f:
            exam_config = json.load(f)
        print("✅ Exam configuration loaded")
    except Exception as e:
        print(f"❌ Exam config error: {e}")
        return False
    
    return True

def test_database_models():
    """Test database model creation"""
    print("Testing database models...")
    try:
        sys.path.append("app")
        from database.models import Student, Exam, ExamResult
        from database.database import init_database, get_db
        
        # Initialize database
        init_database()
        print("✅ Database initialized")
        
        # Test session creation
        session = next(get_db())
        session.close()
        print("✅ Database session created")
        
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_core_modules():
    """Test core OMR processing modules"""
    print("Testing core modules...")
    try:
        sys.path.append("app")
        from core.image_processor import ImageProcessor
        from core.bubble_detector import BubbleDetector
        from core.omr_processor import OMRProcessor
        
        # Test instantiation
        img_processor = ImageProcessor()
        bubble_detector = BubbleDetector()
        omr_processor = OMRProcessor()
        
        print("✅ Core modules instantiated")
        return True
    except Exception as e:
        print(f"❌ Core modules error: {e}")
        return False

def test_api_startup():
    """Test if FastAPI can start (without actually starting it)"""
    print("Testing API configuration...")
    try:
        # Change to app directory to handle relative imports
        original_cwd = os.getcwd()
        os.chdir("app")
        sys.path.insert(0, os.getcwd())
        
        from backend.main import app
        print("✅ FastAPI app configured")
        
        # Restore original directory
        os.chdir(original_cwd)
        return True
    except Exception as e:
        print(f"❌ API configuration error: {e}")
        # Restore original directory even on error
        try:
            os.chdir(original_cwd)
        except:
            pass
        return False

def test_sample_data():
    """Test sample data loading"""
    print("Testing sample data...")
    try:
        import pandas as pd
        students_df = pd.read_csv("data/sample_students.csv")
        print(f"✅ Sample students loaded: {len(students_df)} records")
        
        # Verify required columns
        required_cols = ["student_id", "name", "email", "phone", "batch"]
        missing_cols = [col for col in required_cols if col not in students_df.columns]
        if missing_cols:
            print(f"❌ Missing columns in sample data: {missing_cols}")
            return False
        
        print("✅ Sample data structure valid")
        return True
    except Exception as e:
        print(f"❌ Sample data error: {e}")
        return False

def run_all_tests():
    """Run all tests and provide summary"""
    print("=" * 50)
    print("AUTOMATED OMR SYSTEM - INTEGRATION TEST")
    print("=" * 50)
    
    tests = [
        ("Import Dependencies", test_imports),
        ("Directory Structure", test_directory_structure),
        ("Configuration Files", test_config_files),
        ("Database Models", test_database_models),
        ("Core Modules", test_core_modules),
        ("API Configuration", test_api_startup),
        ("Sample Data", test_sample_data)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to run.")
        print("\nTo start the system, run:")
        print("python run_system.py")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        print("Make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)