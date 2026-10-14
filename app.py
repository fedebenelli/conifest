"""Webapp interactiva: envolvente de fases P-T según composición.

Streamlit + Plotly sobre yaeos (PengRobinson78 + QMR), misma formulación
que ``script.py`` sin el último componente (C50-C80A), que queda fuera
del modelo.

Ejecutar localmente::

    streamlit run app.py
    # -> http://localhost:8501
"""

import time

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import envelope_model as em

st.set_page_config(page_title="Envolvente de fases", page_icon="🌡️", layout="wide")

# ---------------------------------------------------------------------------
# Configuración de grupos: Gases (con CO2), Intermedios, Pesados
# ---------------------------------------------------------------------------
GROUP_MAP = {
    "Gases": em.GROUPS["Gases"],
    "Intermedios": em.GROUPS["Intermedios"],
    "Pesados": em.GROUPS["Pesados"],
}

# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def build_env_figure(res):
    """P [bar] vs T [K] con ramas líquido/vapor y punto crítico."""
    fig = go.Figure()
    labels = {"liquid": "Burbuja", "vapor": "Rocío"}
    colors = {"liquid": "#1f6fb2", "vapor": "#e07b39"}
    t, p, kinds = res["temperatures"], res["pressures"], res["kinds"]

    # Posiciones dinámicas de las etiquetas de región
    liquid_x, liquid_y = None, None
    vapor_x, vapor_y = None, None

    for kind in ("liquid", "vapor"):
        mask = kinds == kind
        if not mask.any():
            continue
        xs = [float(a) if m else None for a, m in zip(t, mask)]
        ys = [float(a) if m else None for a, m in zip(p, mask)]
        valid = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]

        if not valid:
            continue

        # Graficar la línea (glow + línea principal)
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

        # Calcular posición de anotación de región
        if kind == "liquid":
            # Regla 1: presión más alta de la línea de burbuja + 10 bar
            max_p_point = max(valid, key=lambda p: p[1])
            y_liq = max_p_point[1] + 10

            # Regla 2: temperatura del punto crítico - 80 K, o máximo T de la curva
            if len(res.get("critical_t", [])) > 0:
                x_liq = float(res["critical_t"][0]) - 80
            else:
                x_liq = max(valid, key=lambda p: p[0])[0] - 80

            # Regla 3: si presiones extremadamente altas (>1000), arriba a la derecha
            if max_p_point[1] > 1000:
                liquid_x = max(valid, key=lambda p: p[0])[0] + 30
                liquid_y = 330
            else:
                liquid_x = max(210, x_liq)
                liquid_y = min(340, y_liq)
        else:
            rightmost = max(valid, key=lambda p: p[0])
            x_right = rightmost[0] + 50
            y_bottom = rightmost[1] * 0.3
            vapor_x = min(890, x_right)
            vapor_y = max(10, y_bottom)

    # Añadir las anotaciones de región
    if liquid_x is not None and liquid_y is not None:
        fig.add_annotation(
            x=liquid_x, y=liquid_y,
            text="<b>Líquido</b>",
            showarrow=False,
            font=dict(size=16, color="#1f6fb2"),
            opacity=0.6,
        )
    if vapor_x is not None and vapor_y is not None:
        fig.add_annotation(
            x=vapor_x, y=vapor_y,
            text="<b>Gas</b>",
            showarrow=False,
            font=dict(size=16, color="#e07b39"),
            opacity=0.6,
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
    defaults = [100.0 * em.normalize(em.sliders_default)[i] for i in vis]
    colors = [em.GROUP_COLORS[em.GROUPS_INV[i]] for i in vis]
    groups = [em.GROUPS_INV[i] for i in vis]

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
    """Ajusta los componentes del grupo para que su participación sea ``share``."""
    idx = GROUP_MAP[key]
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
# UI de Streamlit
# ---------------------------------------------------------------------------
def _detect_mobile():
    """Detecta si la pantalla es móvil usando JavaScript inyectado."""
    is_mobile = st.components.v1.html(
        """
        <script>
        const isMobile = window.innerWidth < 768;
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: isMobile
        }, '*');
        </script>
        """,
        height=0,
    )
    # Fallback: si no hay valor del JS, asumir desktop
    if is_mobile is None:
        return False
    return bool(is_mobile)


def main():
    st.markdown("# 🌡️ Envolvente de fases interactiva")
    st.markdown(
        "Peng-Robinson 78 + regla QMR · yaeos · "
        "ajusta los sliders, el cálculo se actualiza al soltar."
    )

    # Mapeo inverso de componente a grupo para colores
    GROUPS_INV = em.GROUPS_INV

    # Estado inicial
    if "applied_raw" not in st.session_state:
        st.session_state.applied_raw = list(em.sliders_default)
    if "pending_raw" not in st.session_state:
        st.session_state.pending_raw = list(em.sliders_default)
    if "last_apply_time" not in st.session_state:
        st.session_state.last_apply_time = 0.0

    # Valores por defecto de cada grupo
    default_shares = {
        g: 100.0 * sum(em.sliders_default[i] for i in idxs) / sum(em.sliders_default)
        for g, idxs in GROUP_MAP.items()
    }

    # Detectar tamaño de pantalla
    is_mobile = _detect_mobile()

    # -----------------------------------------------------------------------
    # Sliders (comunes a ambos layouts)
    # -----------------------------------------------------------------------
    st.markdown("### Composición de la mezcla")

    if is_mobile:
        # Móvil: sliders apilados verticalmente
        grp_vals = {}
        for g in GROUP_MAP:
            grp_vals[g] = st.slider(
                f"{g}", 0.0, 100.0, default_shares[g], 0.1,
                key=f"slider-{g}",
                help=f"Incluye: {', '.join(em.names[i] for i in GROUP_MAP[g])}",
            )
    else:
        # Escritorio: sliders en fila horizontal
        slider_cols = st.columns(3)
        grp_vals = {}
        for i, g in enumerate(GROUP_MAP):
            with slider_cols[i]:
                grp_vals[g] = st.slider(
                    f"{g}", 0.0, 100.0, default_shares[g], 0.1,
                    key=f"slider-{g}",
                    help=f"Incluye: {', '.join(em.names[i] for i in GROUP_MAP[g])}",
                )

    if st.button("Restaurar por defecto", use_container_width=True):
        st.session_state.applied_raw = list(em.sliders_default)
        st.session_state.pending_raw = list(em.sliders_default)
        st.rerun()

    # -----------------------------------------------------------------------
    # Detección de "slider soltado": aplica el cálculo con debounce
    # -----------------------------------------------------------------------
    current_shares = tuple(grp_vals[g] for g in GROUP_MAP)

    if "last_shares" not in st.session_state:
        st.session_state.last_shares = current_shares

    # Si los sliders cambiaron, guardar como pendientes
    if current_shares != st.session_state.last_shares:
        st.session_state.last_shares = current_shares

        # Calcular nueva composición desde los sliders de grupo
        new_raw = list(em.sliders_default)
        for g in GROUP_MAP:
            new_raw = adjust_group(new_raw, g, grp_vals[g] / 100.0)

        st.session_state.pending_raw = new_raw

    # Aplicar si hubo cambio (inmediato, sin botón)
    if st.session_state.pending_raw is not None and \
       st.session_state.pending_raw != st.session_state.applied_raw:
        st.session_state.applied_raw = st.session_state.pending_raw
        st.session_state.pending_raw = None

    # -----------------------------------------------------------------------
    # Layout según tamaño de pantalla
    # -----------------------------------------------------------------------
    # Calcular composición en tiempo real para el gráfico de barras
    raw_display = list(em.sliders_default)
    for g in GROUP_MAP:
        raw_display = adjust_group(raw_display, g, grp_vals[g] / 100.0)

    z_display = em.normalize(raw_display)
    if z_display is None:
        z_display = np.zeros(em.nc)

    # Calcular envolvente
    applied = st.session_state.applied_raw
    env = em.compute_envelope(applied)

    if is_mobile:
        # Móvil: diagrama de fases arriba, barras abajo
        if env is not None:
            st.plotly_chart(build_env_figure(env), use_container_width=True)
        else:
            st.warning("No fue posible calcular la envolvente para esta composición.")

        st.plotly_chart(build_comp_figure(z_display), use_container_width=True)
    else:
        # Escritorio: sliders+barras a la izquierda, diagrama a la derecha
        col_left, col_right = st.columns([1, 2])

        with col_left:
            st.plotly_chart(build_comp_figure(z_display), use_container_width=True)

        with col_right:
            if env is not None:
                st.plotly_chart(build_env_figure(env), use_container_width=True)
            else:
                st.warning("No fue posible calcular la envolvente para esta composición.")


if __name__ == "__main__":
    main()
