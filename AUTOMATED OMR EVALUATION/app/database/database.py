"""
Database configuration and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./omr_evaluation.db")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database with default data"""
    create_tables()
    
    # Add default system configurations
    db = SessionLocal()
    try:
        from .models import SystemConfig
        
        default_configs = [
            {
                "config_key": "bubble_detection_threshold",
                "config_value": "0.6",
                "description": "Threshold for bubble detection confidence"
            },
            {
                "config_key": "skew_correction_enabled",
                "config_value": "true",
                "description": "Enable automatic skew correction"
            },
            {
                "config_key": "max_processing_threads",
                "config_value": "4",
                "description": "Maximum number of processing threads"
            },
            {
                "config_key": "supported_image_formats",
                "config_value": "jpg,jpeg,png,pdf",
                "description": "Supported image file formats"
            },
            {
                "config_key": "max_file_size_mb",
                "config_value": "50",
                "description": "Maximum file size in MB"
            }
        ]
        
        for config in default_configs:
            existing = db.query(SystemConfig).filter(
                SystemConfig.config_key == config["config_key"]
            ).first()
            
            if not existing:
                db_config = SystemConfig(**config)
                db.add(db_config)
        
        db.commit()
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully!")