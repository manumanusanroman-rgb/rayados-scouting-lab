"""
enrich_with_squad.py
=====================
Enriquece players_scouting.csv y rayados_squad.csv usando squad.json de Opta.
v2: usa matchName como clave principal del lookup (era el bug del v1).
"""
from pathlib import Path
import zipfile
import json
import pandas as pd
import unicodedata

PROJECT_ROOT = Path(__file__).resolve().parent
ZIP_PATH = Path(r"C:\Users\msanr\Datos\EVENTING_LIGAS\testeo_ligas_norteamerica.zip")
DATA_DIR = PROJECT_ROOT / "data"
SEASON = "2024-2025"


def norm_name(s):
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def map_nationality_to_code(nat):
    if not nat or pd.isna(nat):
        return "MEX"
    mapping = {
        "Mexico": "MEX", "Argentina": "ARG", "Brazil": "BRA", "Brasil": "BRA",
        "Spain": "ESP", "Colombia": "COL", "Uruguay": "URU", "Chile": "CHI",
        "Paraguay": "PAR", "Ecuador": "ECU", "Venezuela": "VEN",
        "United States": "USA", "Peru": "PER", "Costa Rica": "CRC",
        "Honduras": "HON", "Panama": "PAN", "France": "FRA",
        "Montenegro": "MNE", "Portugal": "POR", "Germany": "GER",
        "Italy": "ITA", "Netherlands": "NED", "Croatia": "CRO",
        "Serbia": "SRB", "Senegal": "SEN", "Ghana": "GHA",
        "Nigeria": "NGA", "Morocco": "MAR", "Algeria": "ALG",
        "Japan": "JPN", "South Korea": "KOR", "Canada": "CAN",
        "Jamaica": "JAM", "Bolivia": "BOL", "El Salvador": "SLV",
        "Guatemala": "GUA", "Curacao": "CUW", "England": "ENG",
        "Belgium": "BEL", "Switzerland": "SUI", "Poland": "POL",
        "Turkey": "TUR", "Australia": "AUS",
    }
    if nat in mapping:
        return mapping[nat]
    return nat[:3].upper()


def build_lookup_from_squad(zf, season=SEASON):
    prefix = f"testeo_ligas_norteamerica/Mexico_Liga_MX/{season}/equipos/"
    squad_files = [n for n in zf.namelist()
                   if n.startswith(prefix) and n.endswith("/jsons/squad.json")]
    lookup_by_match = {}   # CLAVE PRINCIPAL: matchName normalizado
    lookup_by_full = {}    # SECUNDARIA: fullName normalizado
    lookup_by_last = {}    # TERCIARIA: solo apellido
    teams_processed = 0
    for path in squad_files:
        try:
            data = json.loads(zf.read(path))
            for team_block in data.get("squad", []):
                for person in team_block.get("person", []):
                    if person.get("type") != "player":
                        continue
                    pid = person.get("id")
                    if not pid:
                        continue
                    fn = person.get("firstName", "")
                    ln = person.get("lastName", "")
                    match_name = person.get("matchName", "")
                    known = person.get("knownName")
                    full_name = known if known else f"{fn} {ln}".strip()
                    nat = person.get("nationality", "")
                    nat2 = person.get("secondNationality", "")
                    info = {
                        "full_name": full_name,
                        "first_name": fn,
                        "last_name": ln,
                        "match_name": match_name,
                        "nationality_code": map_nationality_to_code(nat),
                        "nationality_name": nat,
                        "second_nationality_code": map_nationality_to_code(nat2) if nat2 else "",
                        "placeOfBirth": person.get("placeOfBirth", ""),
                        "shirtNumber": person.get("shirtNumber"),
                        "startDate": person.get("startDate", ""),
                        "endDate": person.get("endDate", ""),
                        "active": person.get("active", ""),
                        "position_opta": person.get("position", ""),
                    }
                    # PRIMARIA: matchName ("É. Aguirre" -> "e. aguirre")
                    mn_norm = norm_name(match_name)
                    if mn_norm and mn_norm not in lookup_by_match:
                        lookup_by_match[mn_norm] = info
                    # SECUNDARIA: nombre completo
                    full_norm = norm_name(full_name)
                    if full_norm and full_norm not in lookup_by_full:
                        lookup_by_full[full_norm] = info
                    # TERCIARIA: solo apellido (puede colisionar, no critico)
                    ln_norm = norm_name(ln)
                    if ln_norm and ln_norm not in lookup_by_last:
                        lookup_by_last[ln_norm] = info
            teams_processed += 1
        except Exception as e:
            print(f"  [warn] error en {path}: {e}")
    print(f"  Procesados {teams_processed} squad.json")
    print(f"  Lookup matchName: {len(lookup_by_match)} entries")
    print(f"  Lookup fullName:  {len(lookup_by_full)} entries")
    print(f"  Lookup lastName:  {len(lookup_by_last)} entries")
    return lookup_by_match, lookup_by_full, lookup_by_last


def enrich_csv(csv_path, lookup_match, lookup_full, lookup_last):
    if not csv_path.exists():
        print(f"  [skip] no existe {csv_path.name}")
        return 0
    df = pd.read_csv(csv_path)
    print(f"  Cargado {csv_path.name}: {len(df)} filas")
    enriched_count = 0
    name_col = None
    for candidate in ["nombre", "jugador"]:
        if candidate in df.columns:
            name_col = candidate
            break
    if name_col is None:
        print(f"  [error] no encontre columna de nombre")
        return 0
    new_cols = ["nombre_completo", "nacionalidad_nombre", "segunda_nacionalidad",
                "lugar_nacimiento", "dorsal_opta", "fecha_inicio_club",
                "fecha_fin_club", "activo_en_club", "posicion_opta"]
    for col in new_cols:
        if col not in df.columns:
            df[col] = ""
    matched_by = {"match": 0, "full": 0, "last": 0}
    for idx, row in df.iterrows():
        opta_name = row[name_col]
        if pd.isna(opta_name) or not opta_name:
            continue
        opta_norm = norm_name(opta_name)
        info = None
        # 1) matchName (mas probable)
        if opta_norm in lookup_match:
            info = lookup_match[opta_norm]
            matched_by["match"] += 1
        # 2) fullName
        elif opta_norm in lookup_full:
            info = lookup_full[opta_norm]
            matched_by["full"] += 1
        # 3) lastName (ultimo recurso)
        else:
            parts = opta_norm.split()
            if parts:
                last = parts[-1]
                if last in lookup_last:
                    info = lookup_last[last]
                    matched_by["last"] += 1
        if info is None:
            continue
        df.at[idx, "nombre_completo"] = info["full_name"]
        df.at[idx, "nacionalidad"] = info["nationality_code"]
        df.at[idx, "nacionalidad_nombre"] = info["nationality_name"]
        df.at[idx, "segunda_nacionalidad"] = info["second_nationality_code"]
        df.at[idx, "lugar_nacimiento"] = info["placeOfBirth"]
        df.at[idx, "dorsal_opta"] = info["shirtNumber"] if info["shirtNumber"] is not None else ""
        df.at[idx, "fecha_inicio_club"] = info["startDate"]
        df.at[idx, "fecha_fin_club"] = info["endDate"]
        df.at[idx, "activo_en_club"] = info["active"]
        df.at[idx, "posicion_opta"] = info["position_opta"]
        enriched_count += 1
    df.to_csv(csv_path, index=False)
    print(f"  Enriquecidos {enriched_count}/{len(df)} jugadores")
    print(f"  Desglose: matchName={matched_by['match']}, fullName={matched_by['full']}, lastName={matched_by['last']}")
    return enriched_count


def main():
    print("=" * 70)
    print("ENRIQUECIMIENTO DESDE squad.json (v2 - matchName fix)")
    print("=" * 70)
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"No encuentro {ZIP_PATH}")
    print("\n[1/3] Leyendo squad.json de todos los equipos Liga MX...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        lookup_match, lookup_full, lookup_last = build_lookup_from_squad(zf)
    print("\n[2/3] Enriqueciendo rayados_squad.csv...")
    n1 = enrich_csv(DATA_DIR / "rayados_squad.csv", lookup_match, lookup_full, lookup_last)
    print("\n[3/3] Enriqueciendo players_scouting.csv...")
    n2 = enrich_csv(DATA_DIR / "players_scouting.csv", lookup_match, lookup_full, lookup_last)
    print("\n" + "=" * 70)
    print(f"LISTO. Enriquecidos {n1} de Rayados + {n2} del pool.")
    print("=" * 70)


if __name__ == "__main__":
    main()