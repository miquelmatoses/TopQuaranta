"""Pre-process geodata for the public /mapa page.

Reads the QGIS exports at `temp/geodata/*.json`, simplifies the
polygon geometries with Douglas-Peucker (tolerance 0.0005°, preserving
topology), splits the per-territori collections into one file each,
and writes the result to `web-react/public/geodata/`.

Run once after cloning the repo (or when the source GeoJSONs change):

    python scripts/simplify_geodata.py

The output fits under 5 MB total. Commit the generated files so the
production Caddy can serve them directly off disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import mapping, shape

# Where the raw QGIS exports live.
SRC = Path(__file__).resolve().parent.parent / "temp" / "geodata"
# Where the React SPA expects to fetch them from.
OUT = Path(__file__).resolve().parent.parent / "web-react" / "public" / "geodata"

TOLERANCE = 0.0005  # degrees — imperceptible at our zoom, ~7% of original size

# GeoJSON territori name → internal code used by Django + the API.
NAME_TO_CODE = {
    "Catalunya": "CAT",
    "País Valencià": "VAL",
    "Illes": "BAL",
    "Illes Balears": "BAL",
    "Andorra": "AND",
    "Catalunya del Nord": "CNO",
    "Franja de Ponent": "FRA",
    "L'Alguer": "ALG",
    "El Carxe": "CAR",
}


def simplify_feature(ft: dict) -> dict:
    g = shape(ft["geometry"]).simplify(TOLERANCE, preserve_topology=True)
    return {
        "type": "Feature",
        "properties": ft["properties"],
        "geometry": mapping(g),
    }


def write_fc(path: Path, features: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        f"  → {path.relative_to(OUT.parent.parent)}  ({path.stat().st_size / 1024:.1f} KB)"
    )


def process_paisos() -> None:
    print("paisos.json")
    data = json.loads((SRC / "paisos.json").read_text(encoding="utf-8"))
    out_feats: list[dict] = []
    for ft in data["features"]:
        territori_nom = ft["properties"].get("territori", "")
        codi = NAME_TO_CODE.get(territori_nom)
        if not codi:
            # Skip anything not in our 8 PPCC territories (ALT has no polygon).
            print(f"  skipping: {territori_nom}")
            continue
        simp = simplify_feature(ft)
        simp["properties"] = {"codi": codi, "nom": territori_nom}
        out_feats.append(simp)
    write_fc(OUT / "paisos.json", out_feats)


def process_comarques() -> None:
    print("comarques.json → per territori")
    data = json.loads((SRC / "comarques.json").read_text(encoding="utf-8"))
    by_codi: dict[str, list[dict]] = {}
    for ft in data["features"]:
        props = ft["properties"]
        codi = NAME_TO_CODE.get(props.get("territori", ""))
        if not codi:
            continue
        simp = simplify_feature(ft)
        simp["properties"] = {
            "codi": codi,
            "comarca": props.get("comarca", ""),
        }
        by_codi.setdefault(codi, []).append(simp)
    for codi, feats in sorted(by_codi.items()):
        write_fc(OUT / f"comarques-{codi}.json", feats)


def process_municipis() -> None:
    print("municipis.json → per territori")
    data = json.loads((SRC / "municipis.json").read_text(encoding="utf-8"))
    by_codi: dict[str, list[dict]] = {}
    for ft in data["features"]:
        props = ft["properties"]
        codi = NAME_TO_CODE.get(props.get("territori", ""))
        if not codi:
            continue
        simp = simplify_feature(ft)
        simp["properties"] = {
            "codi": codi,
            "comarca": props.get("comarca", ""),
            "municipi": props.get("municipi", ""),
            "codi_ine": props.get("codi_ine", ""),
        }
        by_codi.setdefault(codi, []).append(simp)
    for codi, feats in sorted(by_codi.items()):
        write_fc(OUT / f"municipis-{codi}.json", feats)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    process_paisos()
    process_comarques()
    process_municipis()
    print("Done.")


if __name__ == "__main__":
    main()
