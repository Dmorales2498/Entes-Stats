# app.py
import streamlit as st
from pathlib import Path
from PIL import Image
import os

# app.py (imports desde db) — incluir estas funciones
from db import (
    create_player, get_players, ensure_fotos_dir,
    create_match, get_matches, add_player_stats,
    get_player_totals, get_top_scorers, get_top_assisters, get_top_contributions,
    delete_player, update_player_photo,
    get_stats_by_player, get_stat_by_id, update_player_stats, delete_player_stats,get_team_record,get_match_history,get_player_totals
)


st.set_page_config(page_title="Entes Stats", layout="wide")

# ----- Autenticación mínima por roles (admin / viewer) -----
def get_secrets_passwords():
    try:
        secrets = st.secrets
    except Exception:
        secrets = None

    admin_pw = None
    viewers_pw = []

    if secrets and "ADMIN_PASSWORD" in secrets:
        admin_pw = secrets["ADMIN_PASSWORD"]
        if "VIEWER_PASSWORDS" in secrets:
            v = secrets["VIEWER_PASSWORDS"]
            if isinstance(v, list):
                viewers_pw = v
            else:
                viewers_pw = [s.strip() for s in v.split(",") if s.strip()]
    else:
        admin_pw = os.environ.get("ADMIN_PASSWORD")
        v = os.environ.get("VIEWER_PASSWORDS", "")
        viewers_pw = [s.strip() for s in v.split(",") if s.strip()]

    return admin_pw, viewers_pw

ADMIN_PW, VIEWER_PWS = get_secrets_passwords()

if "authenticated" not in st.session_state or not st.session_state.get("authenticated"):
    st.sidebar.header("Iniciar sesión")
    username_input = st.sidebar.text_input("Usuario", key="login_user")
    password_input = st.sidebar.text_input("Contraseña", type="password", key="login_pw")
    if st.sidebar.button("Entrar"):
        role = None
        if ADMIN_PW and password_input == ADMIN_PW:
            role = "admin"
        elif VIEWER_PWS and password_input in VIEWER_PWS:
            role = "viewer"
        else:
            st.sidebar.error("Credenciales incorrectas.")
        if role:
            st.session_state["authenticated"] = True
            st.session_state["role"] = role
            st.session_state["username"] = username_input or ("admin" if role == "admin" else "viewer")
            st.rerun()
else:
    role = st.session_state.get("role", "viewer")
    user = st.session_state.get("username", "usuario")
    with st.sidebar.expander("Sesión"):
        st.write(f"Conectado como **{user}** — rol: **{role}**")
        if st.button("Salir"):
            for k in ["authenticated", "role", "username"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

st.title("⚽ Entes Stats — Temporada 2025/26")

# Mostrar flash_message si existe
if "flash_message" in st.session_state:
    st.success(st.session_state["flash_message"])
    del st.session_state["flash_message"]

# Definir páginas visibles según rol
role = st.session_state.get("role", None)
if role == "admin":
    PAGES = ["Inicio", "Crear jugador", "Crear partido", "Añadir estadísticas", "Reportes", "Eliminar jugador","Editar estadísticas"]
elif role == "viewer":
    PAGES = ["Inicio", "Reportes"]
else:
    PAGES = []

page = st.sidebar.selectbox("Navegar", PAGES) if PAGES else None

ensure_fotos_dir()

# ---------- Inicio ----------
if page == "Inicio":
    st.header("Jugadores registrados")
    players = get_players()
    if not players:
        st.info("No hay jugadores aún. Ve a 'Crear jugador' para añadir uno.")
    else:
        for p in players:
            col1, col2 = st.columns([1, 3])
            with col1:
                if p.foto_path:
                    foto_path = Path(p.foto_path)
                    if foto_path.exists():
                        st.image(str(foto_path), width=120, caption=p.nombre)
                    else:
                        st.markdown("📷")
                else:
                    st.markdown("📷")
            with col2:
                st.write(f"**{p.nombre}**  | Dorsal: {p.dorsal or '-'} | Posición: {p.posicion or '-'}")
                if role == "admin":
                    if st.button("📸 Cambiar foto", key=f"btn_photo_{p.id}"):
                        st.session_state[f"show_uploader_{p.id}"] = True
                        st.rerun()

                    if st.session_state.get(f"show_uploader_{p.id}", False):
                        up = st.file_uploader(f"Sube foto para {p.nombre}", type=["png", "jpg", "jpeg"], key=f"uploader_{p.id}")
                        if up is not None:
                            try:
                                new_path = update_player_photo(p.id, up)
                                st.session_state["flash_message"] = f"Foto actualizada para {p.nombre}"
                                st.session_state.pop(f"show_uploader_{p.id}", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo guardar la foto: {e}")

# ---------- Crear jugador ----------
elif page == "Crear jugador":
    if role != "admin":
        st.warning("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.header("Crear nuevo jugador")
    with st.form("player_form"):
        nombre = st.text_input("Nombre", "")
        dorsal = st.number_input("Dorsal (opcional)", min_value=0, step=1, value=0)
        posicion = st.selectbox("Posición", ["", "Portero", "Defensa", "Mediocampo", "Delantero"])
        foto = st.file_uploader("Foto del jugador (opcional)", type=["png", "jpg", "jpeg"])

        submit = st.form_submit_button("Crear jugador")
        if submit:
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                dorsal_val = int(dorsal) if dorsal > 0 else None
                player = create_player(nombre=nombre.strip(), dorsal=dorsal_val, posicion=posicion or None, foto_path=None)
                if foto is not None:
                    try:
                        update_player_photo(player.id, foto)
                    except Exception:
                        st.warning("La imagen no pudo guardarse, pero el jugador fue creado.")
                st.session_state["flash_message"] = f"Jugador creado: {player.nombre} (id={player.id})"
                st.rerun()

# ---------- Crear partido ----------
elif page == "Crear partido":
    if role != "admin":
        st.warning("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.header("Crear partido")
    with st.form("match_form"):
        fecha = st.date_input("Fecha del partido")
        rival = st.text_input("Rival")
        local = st.checkbox("Local (si está sin marcar, se asume 'visitante')", value=True)
        st.markdown("**Marcador (opcional)**")
        col1, col2 = st.columns(2)
        with col1:
            home_score = st.number_input("Goles (local)", min_value=0, value=0, step=1)
        with col2:
            away_score = st.number_input("Goles (visitante)", min_value=0, value=0, step=1)
        submit = st.form_submit_button("Crear partido")
        if submit:
            hs = int(home_score) if home_score > 0 else None
            aw = int(away_score) if away_score > 0 else None
            m = create_match(fecha=str(fecha), rival=rival.strip() or None, local=bool(local), home_score=hs, away_score=aw)
            display_score = f" — {hs}-{aw}" if (hs is not None or aw is not None) else ""
            st.success(f"Partido creado: {m.fecha} vs {m.rival or '---'}{display_score} (id={m.id})")

# ---------- Añadir estadísticas ----------
elif page == "Añadir estadísticas":
    if role != "admin":
        st.warning("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.header("Añadir estadísticas por jugador y partido")
    players = get_players()
    matches = get_matches()
    if not players or not matches:
        st.info("Necesitas al menos 1 jugador y 1 partido. Ve a 'Crear jugador' y 'Crear partido'.")
    else:
        with st.form("stats_form"):
            player_sel = st.selectbox("Jugador", options=[(p.id, p.nombre) for p in players], format_func=lambda x: x[1])
            match_sel = st.selectbox("Partido", options=[(m.id, m.fecha + (" - " + (m.rival or "")) ) for m in matches], format_func=lambda x: x[1])
            goles = st.number_input("Goles", min_value=0, value=0, step=1)
            asistencias = st.number_input("Asistencias", min_value=0, value=0, step=1)
            partidos_jugados = st.number_input("Partidos jugados (opcional)", min_value=0, value=0, step=1)
            submit = st.form_submit_button("Guardar estadísticas")
            if submit:
                player_id = player_sel[0] if isinstance(player_sel, tuple) else player_sel
                match_id = match_sel[0] if isinstance(match_sel, tuple) else match_sel
                try:
                    pj_val = int(partidos_jugados) if partidos_jugados > 0 else None
                    ps = add_player_stats(player_id=player_id, match_id=match_id, goles=int(goles), asistencias=int(asistencias), partidos_jugados=pj_val)
                    st.session_state["flash_message"] = f"Estadísticas guardadas (id={ps.id})"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar estadísticas: {e}")

# ---------- Reportes ----------
# app.py - reemplaza la sección Reportes por esto

elif page == "Reportes":
    st.header("Reportes y rankings")

    st.subheader("Top goleadores")
    top_goles = get_top_scorers(limit=10)
    if not top_goles:
        st.info("No hay estadísticas aún.")
    else:
        for idx, (pid, nombre, goles) in enumerate(top_goles, start=1):
            st.write(f"{idx}. {nombre} — {goles} goles")

    st.markdown("---")
    st.subheader("Top asistidores")
    top_asist = get_top_assisters(limit=10)
    if not top_asist:
        st.info("No hay estadísticas aún.")
    else:
        for idx, (pid, nombre, asist) in enumerate(top_asist, start=1):
            st.write(f"{idx}. {nombre} — {asist} asistencias")

    st.markdown("---")
    st.subheader("Top (Goles + Asistencias)")
    top_contrib = get_top_contributions(limit=10)
    if not top_contrib:
        st.info("No hay estadísticas aún.")
    else:
        for idx, (pid, nombre, total) in enumerate(top_contrib, start=1):
            st.write(f"{idx}. {nombre} — {total} participaciones")

    st.markdown("---")
    st.subheader("Buscar totales por jugador")
    players = get_players()
    sel = st.selectbox("Seleccione jugador", options=[(p.id, p.nombre) for p in players], format_func=lambda x: x[1])
    if sel:
        pid = sel[0] if isinstance(sel, tuple) else sel
        goles, asist, tot, partidos,pjs_sum = get_player_totals(pid)
        st.write(f"Goles: **{goles}**")
        st.write(f"Asistencias: **{asist}**")
        st.write(f"Total (Goles + Asist): **{tot}**")
        st.write(f"Suma campo 'partidos_jugados' en registros: **{pjs_sum}**")

    st.markdown("---")
    st.subheader("Histórico de partidos — Entes FC")

    # filtros
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        limit = st.number_input("Mostrar últimos N partidos (0 = todos)", min_value=0, value=10, step=1)
    with col2:
        start_date = st.text_input("Desde (YYYY-MM-DD)", value="")
    with col3:
        end_date = st.text_input("Hasta (YYYY-MM-DD)", value="")

    ld = int(limit) if limit and limit > 0 else None
    sd = start_date.strip() if start_date.strip() else None
    ed = end_date.strip() if end_date.strip() else None

    # mostrar registro del equipo en el periodo
    record = get_team_record(start_date=sd, end_date=ed)
    st.write("**Registro del equipo (Entes FC)**")
    st.write(f"Partidos jugados: **{record['played']}** | Victorias: **{record['wins']}** | Empates: **{record['draws']}** | Derrotas: **{record['losses']}**")
    st.write(f"Goles a favor: **{record['goals_for']}** | Goles en contra: **{record['goals_against']}** | Dif: **{record['goal_diff']}** | Puntos: **{record['points']}**")

    st.markdown("**Lista de partidos** (más recientes arriba)")
    history = get_match_history(limit=ld, start_date=sd, end_date=ed)
    if not history:
        st.info("No hay partidos registrados con marcador en ese rango.")
    else:
        # construir tabla simple
        rows = []
        for m in history:
            # human label result
            res_map = {"W": "Victoria", "D": "Empate", "L": "Derrota", "PENDING": "Pendiente"}
            rows.append({
                "Fecha": m["fecha"],
                "Rival": m["rival"],
                "Local (Entes)": "Sí" if m["local"] else "No",
                "Entes": m["entes_goals"] if m["entes_goals"] is not None else "-",
                "Rival_goles": m["opponent_goals"] if m["opponent_goals"] is not None else "-",
                "Resultado": res_map.get(m["result"], m["result"])
            })
        import pandas as pd
        df = pd.DataFrame(rows)
        st.dataframe(df)


# ---------- Eliminar jugador ----------
elif page == "Eliminar jugador":
    if role != "admin":
        st.warning("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.header("Eliminar jugador")
    players = get_players()
    if not players:
        st.info("No hay jugadores.")
    else:
        selected = st.selectbox("Selecciona el jugador a eliminar:", [f"{p.id} — {p.nombre}" for p in players])
        if st.button("Eliminar jugador"):
            player_id = int(selected.split(" — ")[0])
            player_name = next((p.nombre for p in players if p.id == player_id), None)
            delete_player(player_id)
            st.session_state["flash_message"] = f"Jugador eliminado: {player_name}"
            st.rerun()

# ---------- Editar estadísticas (nueva página) ----------
elif page == "Editar estadísticas":
    if role != "admin":
        st.warning("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.header("Editar / Eliminar estadísticas")

    # 1) Seleccionar jugador para listar sus stats
    players = get_players()
    if not players:
        st.info("No hay jugadores registrados.")
    else:
        player_opt = st.selectbox("Selecciona jugador para ver sus estadísticas", options=[(p.id, p.nombre) for p in players], format_func=lambda x: x[1])
        player_id = player_opt[0] if isinstance(player_opt, tuple) else player_opt

        # 2) Mostrar lista de stats del jugador (ID, partido, goles, asist)
        stats = get_stats_by_player(player_id)
        if not stats:
            st.info("Este jugador no tiene estadísticas registradas.")
        else:
            # construir lista legible y permitir seleccionar por id
            options = []
            for s in stats:
                # buscar info del partido para mostrar fecha/rival
                match = None
                try:
                    match = get_match(s.match_id)
                except Exception:
                    match = None
                match_label = f"Match {s.match_id}"
                if match:
                    match_label = f"{match.fecha} vs {match.rival or '---'} (id {match.id})"
                label = f"id:{s.id} | {match_label} | G:{s.goles} A:{s.asistencias} PJS:{s.partidos_jugados or '-'}"
                options.append((s.id, label))

            sel = st.selectbox("Selecciona estadística a editar", options=options, format_func=lambda x: x[1])

            stat_id = sel[0] if isinstance(sel, tuple) else sel
            stat_obj = get_stat_by_id(stat_id)

            if stat_obj is None:
                st.error("No se encontró la estadística seleccionada.")
            else:
                st.subheader("Editar valores")
                with st.form("edit_stat_form"):
                    new_goles = st.number_input("Goles", min_value=0, value=int(stat_obj.goles or 0), step=1)
                    new_asist = st.number_input("Asistencias", min_value=0, value=int(stat_obj.asistencias or 0), step=1)
                    new_pjs = st.number_input("Partidos jugados (opcional)", min_value=0, value=int(stat_obj.partidos_jugados or 0) if stat_obj.partidos_jugados is not None else 0, step=1)
                    btn_save = st.form_submit_button("Guardar cambios")
                    btn_delete = st.form_submit_button("Eliminar esta estadística")

                    if btn_save:
                        try:
                            pj_val = int(new_pjs) if new_pjs > 0 else None
                            updated = update_player_stats(stat_id, goles=new_goles, asistencias=new_asist, partidos_jugados=pj_val)
                            if updated:
                                st.success("Estadística actualizada correctamente.")
                                st.session_state["flash_message"] = "Estadística actualizada."
                                st.rerun()
                            else:
                                st.error("No se pudo actualizar (registro no encontrado).")
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")

                    if btn_delete:
                        confirm = st.radio("¿Estás seguro? Selecciona 'Sí' para confirmar eliminación.", ("No", "Sí"))
                        if confirm == "Sí":
                            try:
                                ok = delete_player_stats(stat_id)
                                if ok:
                                    st.success("Estadística eliminada.")
                                    st.session_state["flash_message"] = "Estadística eliminada."
                                    st.rerun()
                                else:
                                    st.error("No se pudo eliminar (registro no encontrado).")
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")

