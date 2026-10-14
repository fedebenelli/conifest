"""Webapp interactiva: envolvente de fases P-T según composición.

Streamlit + Plotly sobre yaeos (PengRobinson78 + QMR), misma formulación
que ``script.py`` sin el último componente (C50-C80A), que queda fuera
del modelo.

Ejecutar localmente::

    streamlit run app.py
    # -> http://localhost:8501
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import envelope_model as em

st.set_page_config(page_title="Envolvente de fases", page_icon="🌡️", layout="wide")

Z_DEFAULT = em.normalize(em.sliders_default)
COMP_GROUP = {i: g for g, idxs in em.GROUPS.items() for i in idxs}


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def build_env_figure(res):
    """P [bar] vs T [K] con ramas líquido/vapor y punto crítico."""
    fig = go.Figure()
    labels = {"liquid": "Líquido", "vapor": "Vapor"}
    colors = {"liquid": "#1f6fb2", "vapor": "#e07b39"}
    t, p, kinds = res["temperatures"], res["pressures"], res["kinds"]
    for kind in ("liquid", "vapor"):
        mask = kinds == kind
        if not mask.any():
            continue
        xs = [float(a) if m else None for a, m in zip(t, mask)]
        ys = [float(a) if m else None for a, m in zip(p, mask)]
        fig.add_trace(
            go.Scatter(
                x=xs, y=ys, mode="lines",
                line=dict(color=colors[kind], width=8),
                opacity=0.15, hoverinfo="skip", showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=xs, y=ys, mode="lines", name=labels[kind],
                line=dict(color=colors[kind], width=2.5),
                hovertemplate=(
                    "T = %{x:.1f} K<br>P = %{y:.2f} bar"
                    f"<extra>{labels[kind]}</extra>"
                ),
            )
        )
    if len(res["critical_t"]):
        fig.add_trace(
            go.Scatter(
                x=res["critical_t"], y=res["critical_p"], mode="markers",
                name="Punto crítico",
                marker=dict(color="#0f141b", size=12, symbol="diamond",
                           line=dict(color="#ffffff", width=2)),
                hovertemplate=(
                    "Tc = %{x:.1f} K<br>Pc = %{y:.1f} bar<extra>Crítico</extra>"
                ),
            )
        )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Temperatura [K]",
        yaxis_title="Presión [bar]",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                   font=dict(size=11, color="#64748b")),
        margin=dict(l=48, r=16, t=56, b=44),
        hovermode="closest",
        font=dict(family="Inter, system-ui, sans-serif", color="#1e293b"),
    )
    fig.update_xaxes(range=[200, 900], gridcolor="rgba(148,163,184,0.15)",
                     showgrid=True, zeroline=False,
                     linecolor="rgba(148,163,184,0.3)")
    fig.update_yaxes(range=[0, 350], gridcolor="rgba(148,163,184,0.15)",
                     showgrid=True, zeroline=False,
                     linecolor="rgba(148,163,184,0.3)")
    return fig


def build_comp_figure(z):
    """Barras de la composición actual por componente, coloreadas por grupo."""
    vis = em.VISIBLE
    xs = [em.names[i] for i in vis]
    vals = [100.0 * z[i] for i in vis]
    defaults = [100.0 * Z_DEFAULT[i] for i in vis]
    colors = [em.GROUP_COLORS[COMP_GROUP[i]] for i in vis]
    groups = [COMP_GROUP[i] for i in vis]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=xs, y=vals, marker_color=colors, name="Actual",
            marker_line_width=0,
            customdata=np.array([groups, defaults]).T,
            hovertemplate=(
                "<b>%{x}</b> · %{customdata[0]}<br>"
                "Actual: %{y:.4f} %<br>"
                "Defecto: %{customdata[1]:.4f} %"
                "<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=xs, y=defaults, marker_color="rgba(30,41,59,0.4)",
            width=0.12, name="Por defecto",
            hovertemplate="Defecto: %{y:.4f} %<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        barmode="overlay", bargap=0.25,
        yaxis_title="Fracción molar [%]",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0,
                   font=dict(size=11, color="#64748b")),
        margin=dict(l=48, r=16, t=48, b=36),
        height=320,
        font=dict(family="Inter, system-ui, sans-serif", color="#1e293b"),
    )
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.15)", showgrid=True,
                     zeroline=False, linecolor="rgba(148,163,184,0.3)")
    fig.update_xaxes(zeroline=False, linecolor="rgba(148,163,184,0.3)")
    return fig


# ---------------------------------------------------------------------------
# Lógica de composición
# ---------------------------------------------------------------------------
def _fill_from_defaults(raw, idx, target=None):
    dsum = sum(em.sliders_default[i] for i in idx)
    if dsum > 0:
        base = target if target is not None else dsum
        for i in idx:
            raw[i] = base * em.sliders_default[i] / dsum
    else:
        base = target if target is not None else 0.0
        for i in idx:
            raw[i] = base / len(idx)


def adjust_group(raw, key, share):
    idx = [em.VISIBLE.index(i) for i in em.GROUPS[key]]
    share = min(max(share, 0.0), 0.99999)
    group_sum = sum(raw[i] for i in idx)
    others = sum(raw) - group_sum

    if share >= 0.99999:
        for j in range(len(raw)):
            if j not in idx:
                raw[j] = 0.0
        if group_sum <= 0:
            _fill_from_defaults(raw, idx)
        return [min(max(v, 0.0), 1.0) for v in raw]

    target = share * others / (1.0 - share)
    if group_sum > 0:
        factor = target / group_sum
        for i in idx:
            raw[i] *= factor
    else:
        _fill_from_defaults(raw, idx, target)
    return [min(max(v, 0.0), 1.0) for v in raw]


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def main():
    st.markdown("# 🌡️ Envolvente de fases interactiva")
    st.markdown(
        "Peng-Robinson 78 + regla QMR · yaeos · ajusta los sliders y pulsa **Aplicar**."
    )

    # Estado persistente
    if "raw" not in st.session_state:
        st.session_state["raw"] = list(em.sliders_default)
    if "pending" not in st.session_state:
        st.session_state["pending"] = list(em.sliders_default)

    raw = st.session_state["pending"]

    col_sidebar, col_main = st.columns([1, 2])

    with col_sidebar:
        st.markdown("### Composición de la mezcla")

        # Sliders de grupo
        st.markdown("**Participación de grupos (%)**")
        grp_vals = {}
        for g in em.GROUP_ORDER:
            share0 = em.group_shares(em.sliders_default)[g]
            grp_vals[g] = st.slider(
                f"{g}", 0.0, 100.0, share0, 0.1, key=f"grp-{g}"
            )

        st.markdown("---")
        st.markdown("### Componentes individuales")

        # Sliders individuales
        ind_vals = {}
        for i in em.VISIBLE:
            ind_vals[em.names[i]] = st.slider(
                em.names[i], 0.0, 1.0, em.sliders_default[i], 0.0001,
                key=f"ind-{i}"
            )

        st.markdown("---")

        # Botones
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Aplicar cambios", type="primary", use_container_width=True):
                # Leer valores de sliders individuales
                new_raw = list(em.sliders_default)
                for i in em.VISIBLE:
                    new_raw[i] = ind_vals[em.names[i]]

                # Aplicar sliders de grupo
                for g in em.GROUP_ORDER:
                    new_raw = adjust_group(new_raw, g, grp_vals[g] / 100.0)

                st.session_state["raw"] = new_raw
                st.session_state["pending"] = new_raw
                st.rerun()

        with col_btn2:
            if st.button("Restaurar por defecto", use_container_width=True):
                st.session_state["raw"] = list(em.sliders_default)
                st.session_state["pending"] = list(em.sliders_default)
                st.rerun()

        # Mostrar figura de composición
        z_display = em.normalize(raw)
        if z_display is None:
            z_display = np.zeros(em.nc)
        st.plotly_chart(build_comp_figure(z_display), use_container_width=True)

    with col_main:
        # Usar composición aplicada (o por defecto si no se ha aplicado)
        applied = st.session_state["raw"]
        env = em.compute_envelope(applied)

        if env is None:
            st.warning(
                "No fue posible calcular la envolvente para esta composición. "
                "Prueba con una mezcla más cercana a la defecto."
            )
        else:
            st.plotly_chart(build_env_figure(env), use_container_width=True)


if __name__ == "__main__":
    main()
