from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# ✅ Load Supabase connection URL
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")
if not SUPABASE_DB_URL:
    raise ValueError("❌ SUPABASE_DB_URL is missing in your .env file!")

# ✅ Use psycopg3 dialect explicitly
DATABASE_URL = SUPABASE_DB_URL.replace("postgresql://", "postgresql+psycopg://")

# ✅ Create SQLAlchemy engine and session
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -----------------------------
# 📄 Documents Table
# -----------------------------
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    user_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    signer_name = Column(String(255), nullable=True)
    signature_url = Column(Text, nullable=True)
    signature_hash = Column(String(255), nullable=True)

# -----------------------------
# ⚙️ User Settings Table
# -----------------------------
class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), nullable=True)
    openai_model = Column(String(255), default="gpt-4o-mini")
    theme = Column(String(50), default="dark")
    api_key = Column(Text, nullable=True)
    supabase_url = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

# -----------------------------
# 🚀 Initialize Database
# -----------------------------
def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized")
    except Exception as e:
        print("⚠️ Database not ready yet, continuing startup:", e)

