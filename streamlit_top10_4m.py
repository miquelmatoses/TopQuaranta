# -*- coding: utf-8 -*-
import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

st.set_page_config(page_title="Evolució Top10 · Score vs Popularitat", layout="wide")

st.title("Evolució (4 mesos) · Popularitat diària vs Score setmanal")

territori = st.text_input("Territori", value="pv")

DB_NAME = os.getenv("PGDATABASE", "topquaranta")
DB_USER = os.getenv("PGUSER", "topquaranta")
DB_PASS = os.getenv("PGPASSWORD", "topquaranta")
DB_HOST = os.getenv("PGHOST", "localhost")
DB_PORT = os.getenv("PGPORT", "5432")

SQL = r"""
-- NOTES:
-- - Setmana basada en dilluns: date_trunc('week', data)
--   Si la teua setmana oficial comença diumenge, usa: date_trunc('week', data + interval '1 day')

WITH top_candidates AS (
    -- Cançons que han estat al Top10 almenys una vegada als últims 120 dies
    SELECT DISTINCT territori, id_canco, titol
    FROM ranking_setmanal
    WHERE territori = %(territori)s
      AND data >= CURRENT_DATE - INTERVAL '120 days'
      AND posicio <= 10
),

-- Popularitat DIÀRIA de TOT l'univers (per fer el rànquing per popularitat setmanal)
daily_universe AS (
    SELECT 
        date_trunc('week', data)::date AS week_start,
        territori,
        id_canco,
        max(titol) AS titol,
        avg(popularitat)::numeric AS pop_mitjana_setmana
    FROM ranking_diari
    WHERE territori = %(territori)s
      AND data >= CURRENT_DATE - INTERVAL '120 days'
    GROUP BY 1,2,3
),

-- Rànquing setmanal per popularitat (totes les cançons)
weekly_pop_rank_all AS (
    SELECT
        week_start,
        territori,
        id_canco,
        titol,
        pop_mitjana_setmana,
        DENSE_RANK() OVER (
            PARTITION BY territori, week_start
            ORDER BY pop_mitjana_setmana DESC NULLS LAST
        ) AS rank_pop_setmanal
    FROM daily_universe
),

-- Ens quedem només amb les candidates (per a visualitzar clar)
weekly_pop_rank_top AS (
    SELECT a.*
    FROM weekly_pop_rank_all a
    JOIN top_candidates t
      ON t.territori = a.territori
     AND t.id_canco  = a.id_canco
),

-- Score/posició setmanal provinents del rànquing oficial
weekly_score AS (
    SELECT 
        data AS week_start,
        territori,
        id_canco,
        titol,
        score_setmanal,
        posicio AS posicio_setmanal
    FROM ranking_setmanal
    WHERE territori = %(territori)s
      AND data >= CURRENT_DATE - INTERVAL '120 days'
)

SELECT
    p.week_start,
    p.territori,
    p.id_canco,
    p.titol,
    p.pop_mitjana_setmana,
    p.rank_pop_setmanal,
    COALESCE(s.score_setmanal, 0)    AS score_setmanal,     -- si no ix a setmanal: score = 0
    s.posicio_setmanal               AS posicio_setmanal    -- si no ix: NULL (no posició)
FROM weekly_pop_rank_top p
LEFT JOIN weekly_score s
  ON s.territori = p.territori
 AND s.id_canco  = p.id_canco
 AND s.week_start= p.week_start
ORDER BY id_canco, week_start;
"""


@st.cache_data(ttl=600)
def load_df(territori):
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
    df = pd.read_sql(SQL, conn, params={"territori": territori})
    conn.close()
    return df


df = load_df(territori)

if df.empty:
    st.warning("No hi ha dades per a este territori.")
    st.stop()

# Dades ordenades setmanalment
df = df.sort_values(["id_canco", "week_start"]).reset_index(drop=True)

# Selecció de cançons (per defecte fins a 10)
tracks = df[["id_canco", "titol"]].drop_duplicates().sort_values("titol")
seleccio = st.multiselect(
    "Cançons a mostrar (multi):",
    options=tracks["id_canco"].tolist(),
    default=tracks["id_canco"].tolist()[:10],
    format_func=lambda x: tracks.loc[tracks["id_canco"] == x, "titol"].iloc[0],
)
if not seleccio:
    st.info("Selecciona almenys una cançó.")
    st.stop()

df_sel = df[df["id_canco"].isin(seleccio)].copy()

vista = st.radio(
    "Vista",
    options=[
        "Popularitat (mitjana setmanal) vs Score",
        "Posicions: Algoritme vs Popularitat",
    ],
    index=0,
)

nice = {
    "pop_mitjana_setmana": "Popularitat (mitjana setmanal)",
    "score_setmanal": "Score setmanal",
    "posicio_setmanal": "Posició (algoritme)",
    "rank_pop_setmanal": "Posició per popularitat (setmanal)",
}
import plotly.express as px

if vista == "Popularitat (mitjana setmanal) vs Score":
    # Gràfic 1: Popularitat setmanal (multi-línia)
    fig_pop = px.line(
        df_sel,
        x="week_start",
        y="pop_mitjana_setmana",
        color=df_sel["titol"],
        markers=True,
        title="Popularitat (mitjana setmanal) — últims 4 mesos",
        hover_data={"id_canco": False},
    )
    fig_pop.update_layout(
        xaxis_title="Setmana",
        yaxis_title=nice["pop_mitjana_setmana"],
        legend_title_text="Cançó",
    )
    st.plotly_chart(fig_pop, use_container_width=True)

    # Gràfic 2: Score setmanal (multi-línia; score=0 quan no ix)
    fig_score = px.line(
        df_sel,
        x="week_start",
        y="score_setmanal",
        color=df_sel["titol"],
        markers=True,
        title="Score setmanal (0 quan la cançó no ix a setmanal)",
        hover_data={"id_canco": False},
    )
    fig_score.update_layout(
        xaxis_title="Setmana",
        yaxis_title=nice["score_setmanal"],
        legend_title_text="Cançó",
    )
    st.plotly_chart(fig_score, use_container_width=True)

else:
    # Vista de POSICIONS (1 és el millor): invertim eix Y
    # Gràfic A: posició de l'algoritme (només quan existix)
    fig_alg = px.line(
        df_sel.dropna(subset=["posicio_setmanal"]),
        x="week_start",
        y="posicio_setmanal",
        color=df_sel.dropna(subset=["posicio_setmanal"])["titol"],
        markers=True,
        title="Posició setmanal (algoritme)",
    )
    fig_alg.update_layout(
        xaxis_title="Setmana",
        yaxis_title=nice["posicio_setmanal"],
        legend_title_text="Cançó",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_alg, use_container_width=True)

    # Gràfic B: posició per popularitat setmanal (calculada amb pop mitjana)
    fig_poppos = px.line(
        df_sel,
        x="week_start",
        y="rank_pop_setmanal",
        color=df_sel["titol"],
        markers=True,
        title="Posició si ordenàrem per Popularitat (mitjana setmanal)",
    )
    fig_poppos.update_layout(
        xaxis_title="Setmana",
        yaxis_title=nice["rank_pop_setmanal"],
        legend_title_text="Cançó",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_poppos, use_container_width=True)
