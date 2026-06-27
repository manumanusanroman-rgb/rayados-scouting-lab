"""
process_opta_events.py v2
=========================
Anade 2 columnas: recuperaciones_zona_baja + entradas_ultimo_tercio
para distinguir RECUPERADOR PURO vs PRESIONADOR ALTO.
"""
from pathlib import Path
import zipfile
import json
import pandas as pd
from collections import defaultdict
import time

PROJECT_ROOT = Path(__file__).resolve().parent
ZIP_PATH = Path(r"C:\Users\msanr\Datos\EVENTING_LIGAS\testeo_ligas_norteamerica.zip")
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
SEASON = "2024-2025"

TYPE_PASS = 1
TYPE_TAKEON = 3
TYPE_TACKLE = 7
TYPE_INTERCEPTION = 8
TYPE_AERIAL = 44
TYPE_SHOT_MISS = 13
TYPE_SHOT_POST = 14
TYPE_SHOT_SAVED = 15
TYPE_SHOT_GOAL = 16
TYPE_RECOVERY = 49
SHOT_TYPES = {TYPE_SHOT_MISS, TYPE_SHOT_POST, TYPE_SHOT_SAVED, TYPE_SHOT_GOAL}

QUAL_HEAD = 15
QUAL_LEFT_FOOT = 17
QUAL_RIGHT_FOOT = 20
QUAL_FREE_KICK = 23
QUAL_PENALTY = 84
QUAL_FROM_CROSS = 328
QUAL_KEY_PASS = 210
QUAL_ASSIST = 29
QUAL_DISTANCE = 103
QUAL_BLOCKED = 146

ZONA_AREA_GRANDE = 83
ZONA_AREA_PEQUENA = 94
ZONA_ULTIMO_TERCIO = 67
ZONA_BAJA = 50


def has_qualifier(event, qid):
    return any(q.get("qualifierId") == qid for q in event.get("qualifier", []))


def get_qualifier_value(event, qid, default=None):
    for q in event.get("qualifier", []):
        if q.get("qualifierId") == qid:
            return q.get("value", default)
    return default


def list_match_files(zf, season=SEASON):
    prefix = f"testeo_ligas_norteamerica/Mexico_Liga_MX/{season}/partidos/"
    return [n for n in zf.namelist() if n.startswith(prefix) and n.endswith(".json")]


def process_match(zf, path, stats):
    try:
        data = json.loads(zf.read(path))
    except Exception as e:
        print(f"  [warn] no se pudo leer {path}: {e}")
        return 0
    eventos = data.get("liveData", {}).get("event", [])
    procesados = 0
    for ev in eventos:
        pid = ev.get("playerId")
        if not pid:
            continue
        pname = ev.get("playerName", "")
        tid = ev.get("typeId")
        outcome = ev.get("outcome", 0)
        x = ev.get("x", 0)
        s = stats[pid]
        s["nombre"] = pname
        s["eventos_total"] += 1
        procesados += 1
        if tid in SHOT_TYPES:
            es_penal = has_qualifier(ev, QUAL_PENALTY)
            es_falta = has_qualifier(ev, QUAL_FREE_KICK)
            es_cabeza = has_qualifier(ev, QUAL_HEAD)
            es_izq = has_qualifier(ev, QUAL_LEFT_FOOT)
            es_der = has_qualifier(ev, QUAL_RIGHT_FOOT)
            vino_cruce = has_qualifier(ev, QUAL_FROM_CROSS)
            tras_asist = has_qualifier(ev, QUAL_ASSIST)
            bloqueado = has_qualifier(ev, QUAL_BLOCKED)
            fue_gol = (tid == TYPE_SHOT_GOAL)
            a_puerta = tid in [TYPE_SHOT_SAVED, TYPE_SHOT_GOAL]
            if es_penal:
                s["penales_tirados"] += 1
                if fue_gol:
                    s["penales_metidos"] += 1
                continue
            s["tiros"] += 1
            if fue_gol:
                s["goles"] += 1
            if a_puerta:
                s["tiros_a_puerta"] += 1
            if x >= ZONA_AREA_PEQUENA:
                s["tiros_area_pequena"] += 1
                if fue_gol:
                    s["goles_area_pequena"] += 1
            elif x >= ZONA_AREA_GRANDE:
                s["tiros_area_grande"] += 1
                if fue_gol:
                    s["goles_area_grande"] += 1
            else:
                s["tiros_fuera_area"] += 1
                if fue_gol:
                    s["goles_fuera_area"] += 1
                if a_puerta:
                    s["tiros_fuera_a_puerta"] += 1
            if es_cabeza:
                s["tiros_cabeza"] += 1
                if fue_gol:
                    s["goles_cabeza"] += 1
            elif es_izq:
                s["tiros_pie_izq"] += 1
                if fue_gol:
                    s["goles_pie_izq"] += 1
            elif es_der:
                s["tiros_pie_der"] += 1
                if fue_gol:
                    s["goles_pie_der"] += 1
            if es_falta:
                s["tiros_falta_directa"] += 1
                if fue_gol:
                    s["goles_falta_directa"] += 1
            if vino_cruce:
                s["tiros_tras_cruce"] += 1
                if fue_gol:
                    s["goles_tras_cruce"] += 1
            if tras_asist:
                s["tiros_tras_asistencia"] += 1
            if bloqueado:
                s["tiros_bloqueados"] += 1
            dist = get_qualifier_value(ev, QUAL_DISTANCE)
            if dist is not None:
                try:
                    s["sum_distancia_tiro"] += float(dist)
                    s["count_distancia_tiro"] += 1
                except (ValueError, TypeError):
                    pass
        elif tid == TYPE_TAKEON:
            s["regates_intentados"] += 1
            if outcome == 1:
                s["regates_exitosos"] += 1
            if x >= ZONA_ULTIMO_TERCIO:
                s["regates_ultimo_tercio"] += 1
                if outcome == 1:
                    s["regates_ultimo_tercio_ok"] += 1
        elif tid == TYPE_PASS:
            if has_qualifier(ev, QUAL_KEY_PASS):
                s["pases_clave"] += 1
                if has_qualifier(ev, QUAL_FROM_CROSS):
                    s["pases_clave_desde_cruce"] += 1
            if has_qualifier(ev, QUAL_ASSIST):
                s["pases_asistencia"] += 1
        elif tid == TYPE_RECOVERY:
            s["recuperaciones_total"] += 1
            if x >= ZONA_ULTIMO_TERCIO:
                s["recuperaciones_ultimo_tercio"] += 1
            if x < ZONA_BAJA:
                s["recuperaciones_zona_baja"] += 1
        elif tid == TYPE_TACKLE:
            s["entradas_total"] += 1
            if outcome == 1:
                s["entradas_exitosas"] += 1
                if x >= ZONA_ULTIMO_TERCIO:
                    s["entradas_ultimo_tercio"] += 1
        elif tid == TYPE_INTERCEPTION:
            s["intercepciones_total"] += 1
            if x < ZONA_BAJA:
                s["intercepciones_zona_baja"] += 1
        elif tid == TYPE_AERIAL:
            s["aereos_total"] += 1
            if outcome == 1:
                s["aereos_ganados"] += 1
    return procesados


def main():
    print("=" * 70)
    print("PROCESAMIENTO EVENTOS CRUDOS OPTA v2")
    print("=" * 70)
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"No encuentro {ZIP_PATH}")
    def empty_stats():
        return defaultdict(float)
    stats = defaultdict(empty_stats)
    t0 = time.time()
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        match_files = list_match_files(zf)
        print(f"\nEncontrados {len(match_files)} partidos\n")
        total_eventos = 0
        for i, path in enumerate(match_files, 1):
            n_eventos = process_match(zf, path, stats)
            total_eventos += n_eventos
            if i % 50 == 0 or i == len(match_files):
                elapsed = time.time() - t0
                print(f"  {i}/{len(match_files)} ({total_eventos} eventos, {elapsed:.1f}s)")
    print(f"\nProcesados {total_eventos:,} eventos en {len(stats)} jugadores")
    print("\nGenerando DataFrame...")
    rows = []
    for pid, s in stats.items():
        if s["eventos_total"] < 10:
            continue
        row = {
            "player_id": pid,
            "nombre": s["nombre"],
            "eventos_total": int(s["eventos_total"]),
            "tiros": int(s["tiros"]),
            "tiros_a_puerta": int(s["tiros_a_puerta"]),
            "goles": int(s["goles"]),
            "penales_tirados": int(s["penales_tirados"]),
            "penales_metidos": int(s["penales_metidos"]),
            "tiros_fuera_area": int(s["tiros_fuera_area"]),
            "tiros_fuera_a_puerta": int(s["tiros_fuera_a_puerta"]),
            "goles_fuera_area": int(s["goles_fuera_area"]),
            "tiros_area_grande": int(s["tiros_area_grande"]),
            "goles_area_grande": int(s["goles_area_grande"]),
            "tiros_area_pequena": int(s["tiros_area_pequena"]),
            "goles_area_pequena": int(s["goles_area_pequena"]),
            "tiros_cabeza": int(s["tiros_cabeza"]),
            "goles_cabeza": int(s["goles_cabeza"]),
            "tiros_pie_izq": int(s["tiros_pie_izq"]),
            "goles_pie_izq": int(s["goles_pie_izq"]),
            "tiros_pie_der": int(s["tiros_pie_der"]),
            "goles_pie_der": int(s["goles_pie_der"]),
            "tiros_falta_directa": int(s["tiros_falta_directa"]),
            "goles_falta_directa": int(s["goles_falta_directa"]),
            "tiros_tras_cruce": int(s["tiros_tras_cruce"]),
            "goles_tras_cruce": int(s["goles_tras_cruce"]),
            "tiros_bloqueados": int(s["tiros_bloqueados"]),
            "regates_intentados": int(s["regates_intentados"]),
            "regates_exitosos": int(s["regates_exitosos"]),
            "regates_ultimo_tercio": int(s["regates_ultimo_tercio"]),
            "regates_ultimo_tercio_ok": int(s["regates_ultimo_tercio_ok"]),
            "pases_clave": int(s["pases_clave"]),
            "pases_clave_desde_cruce": int(s["pases_clave_desde_cruce"]),
            "pases_asistencia": int(s["pases_asistencia"]),
            "recuperaciones_total": int(s["recuperaciones_total"]),
            "recuperaciones_ultimo_tercio": int(s["recuperaciones_ultimo_tercio"]),
            "recuperaciones_zona_baja": int(s["recuperaciones_zona_baja"]),
            "entradas_total": int(s["entradas_total"]),
            "entradas_exitosas": int(s["entradas_exitosas"]),
            "entradas_ultimo_tercio": int(s["entradas_ultimo_tercio"]),
            "intercepciones_total": int(s["intercepciones_total"]),
            "intercepciones_zona_baja": int(s["intercepciones_zona_baja"]),
            "aereos_total": int(s["aereos_total"]),
            "aereos_ganados": int(s["aereos_ganados"]),
        }
        if s["count_distancia_tiro"] > 0:
            row["distancia_promedio_tiro"] = round(s["sum_distancia_tiro"] / s["count_distancia_tiro"], 1)
        else:
            row["distancia_promedio_tiro"] = 0
        if row["tiros_fuera_area"] > 0:
            row["acierto_tiros_fuera_pct"] = round(row["goles_fuera_area"] / row["tiros_fuera_area"] * 100, 1)
            row["puerta_tiros_fuera_pct"] = round(row["tiros_fuera_a_puerta"] / row["tiros_fuera_area"] * 100, 1)
        else:
            row["acierto_tiros_fuera_pct"] = 0
            row["puerta_tiros_fuera_pct"] = 0
        if row["goles"] > 0:
            row["pct_goles_desde_fuera"] = round(row["goles_fuera_area"] / row["goles"] * 100, 1)
        else:
            row["pct_goles_desde_fuera"] = 0
        if row["tiros"] > 0:
            row["pct_tiros_desde_fuera"] = round(row["tiros_fuera_area"] / row["tiros"] * 100, 1)
            row["pct_tiros_pie_izq"] = round(row["tiros_pie_izq"] / row["tiros"] * 100, 1)
            row["pct_tiros_pie_der"] = round(row["tiros_pie_der"] / row["tiros"] * 100, 1)
            row["pct_tiros_cabeza"] = round(row["tiros_cabeza"] / row["tiros"] * 100, 1)
        else:
            row["pct_tiros_desde_fuera"] = row["pct_tiros_pie_izq"] = row["pct_tiros_pie_der"] = row["pct_tiros_cabeza"] = 0
        if row["regates_intentados"] > 0:
            row["pct_regates_exito"] = round(row["regates_exitosos"] / row["regates_intentados"] * 100, 1)
        else:
            row["pct_regates_exito"] = 0
        if row["aereos_total"] > 0:
            row["pct_aereos_ganados"] = round(row["aereos_ganados"] / row["aereos_total"] * 100, 1)
        else:
            row["pct_aereos_ganados"] = 0
        if row["entradas_total"] > 0:
            row["pct_entradas_exitosas"] = round(row["entradas_exitosas"] / row["entradas_total"] * 100, 1)
        else:
            row["pct_entradas_exitosas"] = 0
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("eventos_total", ascending=False)
    output_path = DATA_DIR / "player_events_stats.csv"
    df.to_csv(output_path, index=False)
    print(f"\nLISTO en {time.time()-t0:.1f}s")
    print(f"Archivo: {output_path}")
    print(f"Jugadores: {len(df)}")


if __name__ == "__main__":
    main()