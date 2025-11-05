# db.py
from typing import List, Optional, Tuple
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import os
from pathlib import Path
from PIL import Image

from models import SessionLocal, Player, Match, PlayerStats, init_db, engine

# Carpeta donde guardaremos fotos
FOTOS_DIR = Path("fotos")
FOTOS_DIR.mkdir(exist_ok=True)

# Crear tablas si no existen
init_db()

# Migración segura: añadir columnas home_score / away_score si faltan
def ensure_match_score_columns():
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info('matches')"))
        cols = [row[1] for row in result.fetchall()]
        to_add = []
        if "home_score" not in cols:
            to_add.append("ALTER TABLE matches ADD COLUMN home_score INTEGER")
        if "away_score" not in cols:
            to_add.append("ALTER TABLE matches ADD COLUMN away_score INTEGER")
        for sql in to_add:
            conn.execute(text(sql))
    if to_add:
        print("Migración: se agregaron columnas de marcador a matches:", [c.split()[-1] for c in to_add])

ensure_match_score_columns()

@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------- Players ----------
def create_player(nombre: str, dorsal: Optional[int] = None, posicion: Optional[str] = None, foto_path: Optional[str] = None) -> Player:
    with get_session() as session:
        player = Player(nombre=nombre, dorsal=dorsal, posicion=posicion, foto_path=foto_path)
        session.add(player)
        session.flush()
        session.refresh(player)
        return player

def get_players() -> List[Player]:
    with get_session() as session:
        return session.query(Player).order_by(Player.nombre).all()

def get_player(player_id: int) -> Optional[Player]:
    with get_session() as session:
        return session.get(Player, player_id)

def update_player(player_id: int, **kwargs) -> Optional[Player]:
    with get_session() as session:
        player = session.get(Player, player_id)
        if not player:
            return None
        for k, v in kwargs.items():
            if hasattr(player, k):
                setattr(player, k, v)
        session.add(player)
        session.flush()
        session.refresh(player)
        return player

def delete_player(player_id: int) -> bool:
    with get_session() as session:
        player = session.query(Player).filter(Player.id == player_id).first()
        if player:
            session.delete(player)
            return True
        return False


# ---------- Matches ----------
def create_match(fecha: str, rival: Optional[str] = None, local: bool = True,
                 home_score: Optional[int] = None, away_score: Optional[int] = None) -> Match:
    with get_session() as session:
        m = Match(fecha=fecha, rival=rival, local=local, home_score=home_score, away_score=away_score)
        session.add(m)
        session.flush()
        session.refresh(m)
        return m

def get_matches() -> List[Match]:
    with get_session() as session:
        return session.query(Match).order_by(Match.fecha.desc()).all()

def get_match(match_id: int) -> Optional[Match]:
    with get_session() as session:
        return session.get(Match, match_id)


# ---------- PlayerStats ----------
def add_player_stats(player_id: int, match_id: int, goles: int = 0, asistencias: int = 0,
                     minutos: Optional[int] = None, partidos_jugados: Optional[int] = None) -> PlayerStats:
    """
    Compatibilidad: acepta 'minutos' (legacy) o 'partidos_jugados' (nuevo).
    """
    with get_session() as session:
        player = session.get(Player, player_id)
        match = session.get(Match, match_id)
        if player is None:
            raise ValueError("Player no encontrado")
        if match is None:
            raise ValueError("Match no encontrado")

        pj = None
        if partidos_jugados is not None:
            pj = int(partidos_jugados)
        elif minutos is not None:
            pj = int(minutos)

        ps = PlayerStats(player_id=player_id, match_id=match_id,
                         goles=int(goles), asistencias=int(asistencias),
                         partidos_jugados=pj)
        session.add(ps)
        session.flush()
        session.refresh(ps)
        return ps

def get_stats_by_player(player_id: int) -> List[PlayerStats]:
    with get_session() as session:
        return session.query(PlayerStats).filter(PlayerStats.player_id == player_id).all()

def get_stats_by_match(match_id: int) -> List[PlayerStats]:
    with get_session() as session:
        return session.query(PlayerStats).filter(PlayerStats.match_id == match_id).all()


# ---------- Agregaciones ----------
def get_player_totals(player_id: int) -> Tuple[int, int, int, int]:
    """
    Retorna (total_goles, total_asistencias, suma_goles_asistencias, partidos_jugados).
    partidos_jugados = count de filas PlayerStats para ese jugador.
    """
    with get_session() as session:
        row = session.query(
            func.coalesce(func.sum(PlayerStats.goles), 0),
            func.coalesce(func.sum(PlayerStats.asistencias), 0),
            func.coalesce(func.count(PlayerStats.id), 0)
        ).filter(PlayerStats.player_id == player_id).one()
        goles = int(row[0])
        asistencias = int(row[1])
        partidos = int(row[2])
        return goles, asistencias, goles + asistencias, partidos

def get_top_scorers(limit: int = 5) -> List[Tuple[int, str, int]]:
    with get_session() as session:
        q = session.query(
            Player.id,
            Player.nombre,
            func.coalesce(func.sum(PlayerStats.goles), 0).label("total_goles")
        ).join(PlayerStats, Player.id == PlayerStats.player_id, isouter=True) \
         .group_by(Player.id) \
         .order_by(func.sum(PlayerStats.goles).desc()) \
         .limit(limit)
        return [(row[0], row[1], int(row[2] or 0)) for row in q.all()]

def get_top_assisters(limit: int = 5) -> List[Tuple[int, str, int]]:
    with get_session() as session:
        q = session.query(
            Player.id,
            Player.nombre,
            func.coalesce(func.sum(PlayerStats.asistencias), 0).label("total_asistencias")
        ).join(PlayerStats, Player.id == PlayerStats.player_id, isouter=True) \
         .group_by(Player.id) \
         .order_by(func.sum(PlayerStats.asistencias).desc()) \
         .limit(limit)
        return [(row[0], row[1], int(row[2] or 0)) for row in q.all()]

def get_top_contributions(limit: int = 5) -> List[Tuple[int, str, int]]:
    with get_session() as session:
        q = session.query(
            Player.id,
            Player.nombre,
            (func.coalesce(func.sum(PlayerStats.goles), 0) + func.coalesce(func.sum(PlayerStats.asistencias), 0)).label("total_contrib")
        ).join(PlayerStats, Player.id == PlayerStats.player_id, isouter=True) \
         .group_by(Player.id) \
         .order_by((func.coalesce(func.sum(PlayerStats.goles), 0) + func.coalesce(func.sum(PlayerStats.asistencias), 0)).desc()) \
         .limit(limit)
        return [(row[0], row[1], int(row[2] or 0)) for row in q.all()]


# ---------- Foto: guardar/actualizar ----------
def update_player_photo(player_id: int, file_buffer) -> str:
    """
    Guarda la foto usando el ID del jugador y actualiza player.foto_path.
    file_buffer: st.uploaded_file (file-like)
    Retorna la ruta relativa guardada (ej: 'fotos/3_andres_iniesta.jpg')
    """
    from models import Player as ModelPlayer
    with get_session() as session:
        player = session.get(ModelPlayer, player_id)
        if not player:
            raise ValueError("Jugador no encontrado")

        safe_name = "".join(c for c in (player.nombre or f"player_{player_id}") if c.isalnum() or c in (" ", "_")).strip().replace(" ", "_")
        filename = f"{player_id}_{safe_name}.jpg"
        save_path = FOTOS_DIR / filename

        img = Image.open(file_buffer)
        rgb = img.convert("RGB")
        rgb.save(save_path, format="JPEG", quality=85)

        player.foto_path = str(save_path)
        session.add(player)
        session.flush()
        return str(save_path)


# util
def ensure_fotos_dir():
    FOTOS_DIR.mkdir(exist_ok=True)
    return str(FOTOS_DIR)

# db.py - añadir al final o después de las agregaciones

from typing import Dict
from datetime import datetime

def _entes_scores_from_match(m: Match) -> Dict[str, Optional[int]]:
    """
    Devuelve diccionario con los goles de Entes FC y del rival para el match m.
    Interpreta 'local' True = Entes FC es local (home_score), else Entes FC es visitante (away_score).
    Si home_score/away_score es None -> devuelve None para esos goles.
    """
    if m.home_score is None and m.away_score is None:
        return {"entes": None, "opponent": None}
    if m.local:
        return {"entes": m.home_score, "opponent": m.away_score}
    else:
        return {"entes": m.away_score, "opponent": m.home_score}

def get_match_history(limit: Optional[int] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    """
    Retorna lista de matches (más recientes primero) con resultado relativo a Entes FC.
    start_date / end_date aceptan strings 'YYYY-MM-DD' (inclusive).
    Cada item: {id, fecha, rival, local (True si Entes FC local), entes_goals, opp_goals, result}
    result: "W" (victoria Entes), "D" (empate), "L" (derrota), "PENDING" (si falta marcador)
    """
    with get_session() as session:
        q = session.query(Match).order_by(Match.fecha.desc())
        if start_date:
            q = q.filter(Match.fecha >= str(start_date))
        if end_date:
            q = q.filter(Match.fecha <= str(end_date))
        if limit:
            rows = q.limit(limit).all()
        else:
            rows = q.all()

        out = []
        for m in rows:
            scores = _entes_scores_from_match(m)
            entes = scores["entes"]
            opp = scores["opponent"]
            if entes is None or opp is None:
                result = "PENDING"
            else:
                if entes > opp:
                    result = "W"
                elif entes == opp:
                    result = "D"
                else:
                    result = "L"
            out.append({
                "id": m.id,
                "fecha": m.fecha,
                "rival": m.rival or "",
                "local": bool(m.local),
                "entes_goals": entes,
                "opponent_goals": opp,
                "result": result,
                "home_score": m.home_score,
                "away_score": m.away_score
            })
        return out

def get_team_record(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, int]:
    """
    Calcula el registro global de Entes FC en el rango de fechas opcional.
    Retorna diccionario: {'played','wins','draws','losses','goals_for','goals_against','goal_diff','points'}
    """
    history = get_match_history(start_date=start_date, end_date=end_date)
    played = wins = draws = losses = gf = ga = 0
    for m in history:
        if m["entes_goals"] is None or m["opponent_goals"] is None:
            continue  # partido sin marcador -> no cuenta como jugado
        played += 1
        gf += int(m["entes_goals"])
        ga += int(m["opponent_goals"])
        if m["entes_goals"] > m["opponent_goals"]:
            wins += 1
        elif m["entes_goals"] == m["opponent_goals"]:
            draws += 1
        else:
            losses += 1
    points = wins * 3 + draws
    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": gf,
        "goals_against": ga,
        "goal_diff": gf - ga,
        "points": points
    }

