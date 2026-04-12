"""
Track verification classifier.

Uses a Random Forest trained on HistorialRevisio decisions.
Falls back to hand-tuned heuristics if <20 training examples.

Model saved to /home/topquaranta/app/music/ml_model.joblib
"""

import logging
import threading
import time
from pathlib import Path

from django.db.models import QuerySet

logger = logging.getLogger(__name__)

MODEL_PATH = Path("/home/topquaranta/app/music/ml_model.joblib")
LAST_RECALC_FILE = "/tmp/tq_last_ml_recalc"
MIN_NEW_DECISIONS = 5
MIN_TRAINING_SAMPLES = 20

FEATURE_NAMES = [
    "isrc_es",
    "isrc_digital",
    "isrc_international",
    "isrc_empty",
    "deezer_nb_fan",
    "deezer_nb_album",
    "deezer_nom_similitud",
    "nom_artista_len",
    "nb_decisions_artista",
    "ratio_rebuig_artista",
    "ratio_rebuig_isrc_prefix",
    "nb_collaboradors",
    "mes_llancament",
    "any_llancament",
    "nb_cancons_aprovades_artista",
]


def _isrc_category(isrc: str) -> tuple[int, int, int, int]:
    """Returns (es, digital, international, empty) as 0/1."""
    prefix = isrc[:2].upper() if len(isrc) >= 2 else ""
    if not prefix:
        return (0, 0, 0, 1)
    if prefix == "ES":
        return (1, 0, 0, 0)
    if prefix in ("QT", "QM", "QZ"):
        return (0, 1, 0, 0)
    return (0, 0, 1, 0)


def _get_rejection_ratio(artista_nom: str) -> tuple[int, float]:
    from music.models import HistorialRevisio
    total = HistorialRevisio.objects.filter(artista_nom=artista_nom).count()
    if total == 0:
        return (0, 0.5)
    rej = HistorialRevisio.objects.filter(
        artista_nom=artista_nom, decisio="rebutjada"
    ).count()
    return (total, rej / total)


def _get_isrc_prefix_rejection_ratio(isrc: str) -> float:
    from music.models import HistorialRevisio
    prefix = isrc[:2].upper() if len(isrc) >= 2 else ""
    if not prefix:
        return 0.5
    total = HistorialRevisio.objects.filter(isrc_prefix=prefix).count()
    if total < 3:
        return 0.5
    rej = HistorialRevisio.objects.filter(
        isrc_prefix=prefix, decisio="rebutjada"
    ).count()
    return rej / total


def _build_features(canco) -> list[float]:
    """Extract feature vector from a Canco."""
    artista = canco.artista
    isrc = canco.isrc or ""
    es, digital, intl, empty = _isrc_category(isrc)
    nb_decisions, ratio_reb = _get_rejection_ratio(artista.nom)
    nb_col = canco.artistes_col.count()
    from music.models import Canco
    nb_approved = Canco.objects.filter(
        artista=artista, verificada=True
    ).count()

    return [
        float(es),
        float(digital),
        float(intl),
        float(empty),
        float(artista.deezer_nb_fan or 0),
        float(artista.deezer_nb_album or 0),
        float(artista.deezer_nom_similitud if artista.deezer_nom_similitud is not None else 0.5),
        float(len(artista.nom)),
        float(nb_decisions),
        float(ratio_reb),
        float(_get_isrc_prefix_rejection_ratio(isrc)),
        float(nb_col),
        float(canco.data_llancament.month if canco.data_llancament else 0),
        float(canco.data_llancament.year if canco.data_llancament else 0),
        float(nb_approved),
    ]


def _build_features_from_historial(rec) -> list[float]:
    """Extract feature vector from an HistorialRevisio record."""
    from music.models import HistorialRevisio
    isrc = rec.canco_isrc or ""
    es, digital, intl, empty = _isrc_category(isrc)
    prefix = isrc[:2].upper() if len(isrc) >= 2 else ""

    # Rejection ratios from historial (excluding this record to avoid leak)
    others = HistorialRevisio.objects.filter(artista_nom=rec.artista_nom).exclude(pk=rec.pk)
    total_others = others.count()
    if total_others > 0:
        rej_others = others.filter(decisio="rebutjada").count()
        ratio_reb = rej_others / total_others
    else:
        ratio_reb = 0.5

    prefix_others = HistorialRevisio.objects.filter(isrc_prefix=prefix).exclude(pk=rec.pk)
    total_prefix = prefix_others.count()
    if total_prefix >= 3:
        ratio_prefix = prefix_others.filter(decisio="rebutjada").count() / total_prefix
    else:
        ratio_prefix = 0.5

    return [
        float(es),
        float(digital),
        float(intl),
        float(empty),
        float(rec.artista_deezer_nb_fan or 0),
        float(rec.artista_deezer_nb_album or 0),
        float(rec.artista_nom_similitud if rec.artista_nom_similitud is not None else 0.5),
        float(len(rec.artista_nom)),
        float(total_others),
        float(ratio_reb),
        float(ratio_prefix),
        0.0,  # nb_collaboradors not available in historial
        float(rec.data_llancament.month if rec.data_llancament else 0),
        float(rec.data_llancament.year if rec.data_llancament else 0),
        0.0,  # nb_cancons_aprovades not available in historial
    ]


def _build_dataset() -> tuple[list, list]:
    """Build X, y from HistorialRevisio."""
    from music.models import HistorialRevisio
    X = []
    y = []
    for rec in HistorialRevisio.objects.all():
        features = _build_features_from_historial(rec)
        X.append(features)
        y.append(1 if rec.decisio == "aprovada" else 0)
    return X, y


def entrenar_model() -> bool:
    """
    Train RandomForestClassifier from HistorialRevisio.
    Saves model to MODEL_PATH. Returns True if trained.
    """
    from sklearn.ensemble import RandomForestClassifier
    import joblib

    X, y = _build_dataset()
    if len(X) < MIN_TRAINING_SAMPLES:
        logger.info("Not enough training data (%d < %d)", len(X), MIN_TRAINING_SAMPLES)
        return False

    clf = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)

    importances = dict(zip(FEATURE_NAMES, clf.feature_importances_))
    sorted_imp = sorted(importances.items(), key=lambda x: -x[1])
    logger.info("RF model trained with %d samples. Feature importances: %s",
                len(X), sorted_imp[:5])
    return True


def pre_classificar(canco) -> dict:
    """
    Classify a Canco using the RF model if available,
    or heuristic fallback if not.
    """
    if MODEL_PATH.exists():
        try:
            import joblib
            clf = joblib.load(MODEL_PATH)
            features = _build_features(canco)
            proba = clf.predict_proba([features])[0]
            # proba[1] = probability of approval (class 1)
            confianca = float(proba[1]) if len(proba) > 1 else float(proba[0])
            if confianca >= 0.7:
                classe = "A"
            elif confianca >= 0.4:
                classe = "B"
            else:
                classe = "C"
            feature_imp = sorted(
                zip(FEATURE_NAMES, clf.feature_importances_),
                key=lambda x: -x[1],
            )
            raons = [f"{n}={v:.2f}" for n, v in feature_imp[:3]]
            return {"classe": classe, "confiança": round(confianca, 2), "raons": raons}
        except Exception as exc:
            logger.warning("RF model error, falling back to heuristic: %s", exc)

    return _heuristic_classificar(canco)


def _heuristic_classificar(canco) -> dict:
    """Fallback heuristic classifier."""
    from music.models import HistorialRevisio

    raons = []
    score = 0.5
    artista = canco.artista
    isrc = canco.isrc or ""

    isrc_prefix = isrc[:2].upper() if len(isrc) >= 2 else ""
    if isrc_prefix == "ES":
        score += 0.3
        raons.append("ISRC espanyol")
    elif isrc_prefix in ("QT", "QM", "QZ"):
        score -= 0.25
        raons.append(f"ISRC distrib. digital ({isrc_prefix})")
    elif isrc_prefix:
        score -= 0.3
        raons.append(f"ISRC internacional ({isrc_prefix})")

    nom_len = len(artista.nom)
    if nom_len <= 3:
        score -= 0.3
        raons.append(f"Nom molt curt ({nom_len})")
    elif nom_len <= 6:
        score -= 0.25
        raons.append(f"Nom curt ({nom_len})")

    if artista.deezer_nb_fan is not None:
        if artista.deezer_nb_fan > 100000:
            score -= 0.35
        elif artista.deezer_nb_fan > 50000:
            score -= 0.25
        elif artista.deezer_nb_fan < 1000:
            score += 0.1

    if artista.deezer_nb_album is not None:
        if artista.deezer_nb_album > 30:
            score -= 0.25
        elif artista.deezer_nb_album > 20:
            score -= 0.15

    if artista.deezer_nom_similitud is not None:
        if artista.deezer_nom_similitud < 0.5:
            score -= 0.3
        elif artista.deezer_nom_similitud >= 0.95:
            score += 0.15

    total_hist = HistorialRevisio.objects.filter(artista_nom=artista.nom).count()
    if total_hist >= 3:
        rebutjades = HistorialRevisio.objects.filter(
            artista_nom=artista.nom, decisio="rebutjada"
        ).count()
        ratio = rebutjades / total_hist
        if ratio > 0.8:
            score -= 0.35
        elif ratio > 0.5:
            score -= 0.2
        elif ratio < 0.2:
            score += 0.2

    score = max(0.0, min(1.0, score))
    if score >= 0.65:
        classe = "A"
    elif score >= 0.35:
        classe = "B"
    else:
        classe = "C"

    return {"classe": classe, "confiança": round(score, 2), "raons": raons}


def classificar_i_guardar(canco) -> None:
    """Compute ML classification and save to the canco's db fields."""
    result = pre_classificar(canco)
    canco.ml_classe = result["classe"]
    canco.ml_confianca = result["confiança"]
    canco.save(update_fields=["ml_classe", "ml_confianca"])


def recalcular_ml(qs: QuerySet | None = None, limit: int | None = None) -> int:
    """
    Recalculate ml_classe and ml_confianca for unverified cancons.
    Retrains the RF model first if enough data.
    """
    from music.models import Canco

    # Retrain before recalculating
    entrenar_model()

    if qs is None:
        qs = Canco.objects.filter(verificada=False).select_related("artista")

    if limit:
        qs = qs[:limit]

    updated = 0
    for canco in qs.iterator() if not limit else qs:
        result = pre_classificar(canco)
        canco.ml_classe = result["classe"]
        canco.ml_confianca = result["confiança"]
        try:
            canco.save(update_fields=["ml_classe", "ml_confianca"])
            updated += 1
        except Exception:
            pass

    try:
        with open(LAST_RECALC_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass

    logger.info("ML recalculated for %d cancons", updated)
    return updated


def recalcular_ml_si_cal() -> None:
    """
    Trigger ML recalc in a background thread if ≥5 new decisions since last recalc.
    """
    from music.models import HistorialRevisio

    last_recalc = 0.0
    try:
        with open(LAST_RECALC_FILE) as f:
            last_recalc = float(f.read().strip())
    except (OSError, ValueError):
        pass

    from datetime import datetime, timezone

    last_dt = datetime.fromtimestamp(last_recalc, tz=timezone.utc)
    new_decisions = HistorialRevisio.objects.filter(created_at__gt=last_dt).count()

    if new_decisions < MIN_NEW_DECISIONS:
        return

    logger.info(
        "ML recalc triggered in background: %d new decisions since last recalc",
        new_decisions,
    )
    thread = threading.Thread(target=recalcular_ml, daemon=True, name="ml-recalc")
    thread.start()
