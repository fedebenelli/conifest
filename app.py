"""Webapp interactiva: envolvente de fases P-T según composición.

Gradio + Plotly sobre yaeos (PengRobinson78 + QMR), misma formulación
que ``script.py`` sin el último componente (C50-C80A), que queda fuera
del modelo.

Ejecutar localmente::

    python app.py
    # -> http://localhost:7860
"""

import numpy as np
import plotly.graph_objects as go
import gradio as gr

import envelope_model as em

# ---------------------------------------------------------------------------
# Derivados de la composición por defecto
# ---------------------------------------------------------------------------
Z_DEFAULT = em.normalize(em.sliders_default)
COMP_GROUP = {i: g for g, idxs in em.GROUPS.items() for i in idxs}
GROUP_SLUG = {g: g.lower() for g in em.GROUP_ORDER}


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
    """Reparte valores dentro de ``idx`` proporcionalmente a los defecto."""
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
    """Ajusta los individuales del grupo para que su participación sea ``share`` (0-1)."""
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
# Callback principal
# ---------------------------------------------------------------------------
def update(ind_vals, grp_vals, reset_clicked):
    """Recibe todos los valores de sliders y devuelve figuras + nuevos valores."""
    raw = [
        float(v) if v is not None else d
        for v, d in zip(ind_vals, em.sliders_default)
    ]

    # Si se pulsó reset, restaurar defaults
    if reset_clicked:
        raw = list(em.sliders_default)
    else:
        # Aplicar sliders de grupo
        for i, g in enumerate(em.GROUP_ORDER):
            if grp_vals[i] is not None:
                raw = adjust_group(raw, g, float(grp_vals[i]) / 100.0)

    shares = em.group_shares(raw)
    z = em.normalize(raw)
    if z is None:
        z = np.zeros(em.nc)

    env = em.compute_envelope(raw)
    if env is None:
        env_fig = go.Figure()
        env_fig.add_annotation(
            text="No fue posible calcular la envolvente para esta composición.<br>"
                 "Prueba con una mezcla más cercana a la defecto o con menos componentes en cero.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="#b45309"),
        )
        env_fig.update_layout(
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=20, b=20),
        )
        status = "⚠️ Composición inválida"
    else:
        env_fig = build_env_figure(env)
        status = None

    comp_fig = build_comp_figure(z)

    # Nuevos valores para sliders individuales y de grupo
    new_ind = list(raw)
    new_grp = [shares[g] for g in em.GROUP_ORDER]

    # Retornar aplanado: 2 figs + status + 14 individuales + 4 grupo = 21
    return env_fig, comp_fig, status, *new_ind, *new_grp


# ---------------------------------------------------------------------------
# Layout Gradio
# ---------------------------------------------------------------------------
def create_demo():
    with gr.Blocks(title="Envolvente de fases") as demo:
        gr.Markdown(
            "# 🌡️ Envolvente de fases interactiva\n"
            "Peng-Robinson 78 + regla QMR · yaeos · arrastra los sliders "
            "y observa cómo cambia la envolvente P-T."
        )

        with gr.Row():
            # ---------------- Sidebar: composición ----------------
            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### Composición de la mezcla")
                comp_plot = gr.Plot(value=build_comp_figure(Z_DEFAULT), label="Composición")

                gr.Markdown("**Barra negra** = composición por defecto del script.")

                # Sliders de grupo
                grp_sliders = []
                for g in em.GROUP_ORDER:
                    share0 = em.group_shares(em.sliders_default)[g]
                    s = gr.Slider(
                        minimum=0, maximum=100, value=share0, step=0.1,
                        label=f"{g} — participación en la mezcla (%)",
                        info=f"Slider maestro del grupo {g}",
                    )
                    grp_sliders.append(s)

                gr.Markdown("---")
                gr.Markdown("### Componentes individuales")

                # Sliders individuales
                ind_sliders = []
                for i in em.VISIBLE:
                    s = gr.Slider(
                        minimum=0, maximum=1, value=em.sliders_default[i], step=0.0001,
                        label=em.names[i],
                        info=f"{COMP_GROUP[i]} — fracción molar",
                    )
                    ind_sliders.append(s)

                reset_btn = gr.Button("Restaurar composición por defecto", variant="secondary")

            # ---------------- Gráfica envolvente ----------------
            with gr.Column(scale=2, min_width=500):
                status_box = gr.Textbox(label="Estado", visible=False, interactive=False)
                env_plot = gr.Plot(
                    value=build_env_figure(em.compute_envelope(em.sliders_default)),
                    label="Envolvente P-T",
                )

        # -------------------------------------------------------------------
        # Conectar callbacks
        # -------------------------------------------------------------------
        all_inputs = ind_sliders + grp_sliders + [reset_btn]

        def on_change(*args):
            ind_vals = args[:len(ind_sliders)]
            grp_vals = args[len(ind_sliders):len(ind_sliders) + len(grp_sliders)]
            try:
                reset_clicked = args[-1] is not None and float(args[-1]) > 0
            except (TypeError, ValueError):
                reset_clicked = False
            return update(ind_vals, grp_vals, reset_clicked)

        for s in ind_sliders + grp_sliders:
            s.change(
                fn=on_change,
                inputs=all_inputs,
                outputs=[env_plot, comp_plot, status_box] + ind_sliders + grp_sliders,
            )

        reset_btn.click(
            fn=lambda: update(list(em.sliders_default), None, True),
            inputs=None,
            outputs=[env_plot, comp_plot, status_box] + ind_sliders + grp_sliders,
        )

    return demo


if __name__ == "__main__":
    import os
    demo = create_demo()
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port, theme=gr.themes.Soft())
