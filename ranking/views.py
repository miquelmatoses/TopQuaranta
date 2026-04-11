from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection
from django.shortcuts import render


@staff_member_required
def ranking_provisional(request):
    territori = request.GET.get("territori", "CAT")
    if territori not in ("CAT", "VAL", "BAL"):
        territori = "CAT"

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT data FROM ranking_ingestadiari
            WHERE error = FALSE ORDER BY data DESC LIMIT 1
        """)
        row = cursor.fetchone()
        latest_date = row[0] if row else None

    tracks = []
    if latest_date:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.nom AS canco_nom,
                    a.nom AS artista_nom,
                    i.lastfm_playcount,
                    i.lastfm_listeners,
                    c.data_llancament
                FROM ranking_ingestadiari i
                JOIN music_canco c ON c.id = i.canco_id
                JOIN music_artista a ON a.id = c.artista_id
                JOIN music_artista_territoris at ON at.artista_id = a.id
                WHERE i.data = %s
                  AND i.error = FALSE
                  AND i.lastfm_playcount IS NOT NULL
                  AND at.territori_id = %s
                  AND c.verificada = TRUE
                GROUP BY c.id, c.nom, a.nom, i.lastfm_playcount,
                         i.lastfm_listeners, c.data_llancament
                ORDER BY i.lastfm_playcount DESC
                LIMIT 40
            """, [latest_date, territori])
            for pos, row in enumerate(cursor.fetchall(), 1):
                tracks.append({
                    "posicio": pos,
                    "canco_nom": row[0],
                    "artista_nom": row[1],
                    "playcount": row[2],
                    "listeners": row[3],
                    "data_llancament": row[4],
                })

    context = {
        "title": f"Ranking Provisional — {territori}",
        "territori": territori,
        "territoris": ["CAT", "VAL", "BAL"],
        "latest_date": latest_date,
        "tracks": tracks,
        "is_popup": False,
        "has_permission": True,
        "site_header": "TopQuaranta Admin",
    }
    return render(request, "ranking/ranking_provisional.html", context)
