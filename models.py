# models.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property
import os

# Asegurar carpeta data
os.makedirs("data", exist_ok=True)

# Soportar DATABASE_URL (env var o st.secrets) para migrar a Postgres si se desea
DATABASE_URL = os.environ.get("DATABASE_URL")
try:
    import streamlit as _st
    if not DATABASE_URL and "DATABASE_URL" in _st.secrets:
        DATABASE_URL = _st.secrets["DATABASE_URL"]
except Exception:
    pass

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///data/stats.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)

Base = declarative_base()

# Session factory: expire_on_commit=False para que los objetos sigan accesibles en Streamlit
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False
)


class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    dorsal = Column(Integer)
    posicion = Column(String)
    foto_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stats = relationship("PlayerStats", back_populates="player", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Player id={self.id} nombre={self.nombre} dorsal={self.dorsal}>"


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String, nullable=False)  # ISO: YYYY-MM-DD
    rival = Column(String)
    local = Column(Boolean, default=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stats = relationship("PlayerStats", back_populates="match", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Match id={self.id} fecha={self.fecha} rival={self.rival} score={self.home_score}-{self.away_score}>"


class PlayerStats(Base):
    __tablename__ = "player_stats"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    goles = Column(Integer, default=0)
    asistencias = Column(Integer, default=0)
    partidos_jugados = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    player = relationship("Player", back_populates="stats")
    match = relationship("Match", back_populates="stats")

    @hybrid_property
    def participaciones(self):
        return (self.goles or 0) + (self.asistencias or 0)

    def __repr__(self):
        return f"<PlayerStats id={self.id} player_id={self.player_id} match_id={self.match_id} goles={self.goles} asist={self.asistencias}>"


def init_db():
    Base.metadata.create_all(bind=engine)
    print("Base de datos creada (o ya existente) en:", DATABASE_URL)


if __name__ == "__main__":
    init_db()
