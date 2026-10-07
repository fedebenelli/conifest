"""Webapp interactiva: envolvente de fases P-T según composición.

Dash + Plotly sobre yaeos ( PengRobinson78 + QMR ), misma formulación
que ``script.py``.

Ejecutar localmente::

    python app.py
    # -> http://localhost:8050  (o $PORT)
"""

import os

import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback, dcc, ctx, html, no_update

import envelope_model as em

# ---------------------------------------------------------------------------
# Derivados de la composición por defecto
# ---------------------------------------------------------------------------
Z_DEFAULT = em.normalize(em.sliders_default)  # normalizada, 15 componentes
COMP_GROUP = {i: g for g, idxs in em.GROUPS.items() for i in idxs}

GROUP_SLUG = {g: g.lower() for g in em.GROUP_ORDER}

# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------


def build_env_figure(res):
    """P [bar] vs T [K] con ramas líquido/vapor y punto crítico."""
    fig = go.Figure()
    labels = {"liquid": "Líquido", "vapor": "Vapor"}
    colors = {"liquid": "#1f77b4", "vapor": "#e8833a"}
    t, p, kinds = res["temperatures"], res["pressures"], res["kinds"]
    for kind in ("liquid", "vapor"):
        mask = kinds == kind
        if not mask.any():
            continue
        xs = [float(a) if m else None for a, m in zip(t, mask)]
        ys = [float(a) if m else None for a, m in zip(p, mask)]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines",
                name=labels[kind],
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
                x=res["critical_t"],
                y=res["critical_p"],
                mode="markers",
                name="Punto crítico",
                marker=dict(color="black", size=10, symbol="diamond"),
                hovertemplate=(
                    "Tc = %{x:.1f} K<br>Pc = %{y:.1f} bar<extra>Crítico</extra>"
                ),
            )
        )
    fig.update_layout(
        template="plotly_white",
        xaxis_title="Temperatura [K]",
        yaxis_title="Presión [bar]",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=48, r=16, t=56, b=44),
        height=520,
        hovermode="closest",
    )
    fig.update_xaxes(gridcolor="#ececec", showgrid=True)
    fig.update_yaxes(gridcolor="#ececec", showgrid=True)
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
            x=xs,
            y=vals,
            marker_color=colors,
            name="Actual",
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
            x=xs,
            y=defaults,
            marker_color="#222222",
            width=0.12,
            name="Por defecto",
            hovertemplate="Defecto: %{y:.4f} %<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        barmode="overlay",
        bargap=0.25,
        yaxis_title="Fracción molar [%]",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0),
        margin=dict(l=48, r=16, t=48, b=36),
        height=320,
    )
    fig.update_yaxes(gridcolor="#ececec", showgrid=True)
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
    else:  # sin referencia: reparto uniforme
        base = target if target is not None else 0.0
        for i in idx:
            raw[i] = base / len(idx)


def adjust_group(raw, key, share):
    """Ajusta los individuales del grupo para que su participación sea ``share`` (0-1)."""
    idx = [em.VISIBLE.index(i) for i in em.GROUPS[key]]
    share = min(max(share, 0.0), 0.99999)
    group_sum = sum(raw[i] for i in idx)
    others = sum(raw) - group_sum

    if share >= 0.99999:  # dejar solo este grupo
        for j in range(len(raw)):
            if j not in idx:
                raw[j] = 0.0
        if group_sum <= 0:
            _fill_from_defaults(raw, idx)
        return [min(max(v, 0.0), 1.0) for v in raw]

    target = share * (others + em.ASPHALTENE_FIXED) / (1.0 - share)
    if group_sum > 0:
        factor = target / group_sum
        for i in idx:
            raw[i] *= factor
    else:
        _fill_from_defaults(raw, idx, target)
    return [min(max(v, 0.0), 1.0) for v in raw]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def group_card(group):
    slug = GROUP_SLUG[group]
    color = em.GROUP_COLORS[group]
    share0 = em.group_shares(em.sliders_default)[group]

    header = dbc.Button(
        [
            html.Span(
                style={
                    "display": "inline-block",
                    "width": "12px",
                    "height": "12px",
                    "borderRadius": "3px",
                    "backgroundColor": color,
                },
            ),
            html.Span(group, className="fw-semibold"),
            html.Span(
                f"{share0:.1f} %",
                id=f"share-{slug}",
                className="badge border ms-auto",
                style={"color": "#495057", "backgroundColor": "#f8f9fa"},
            ),
            html.Span("▾", className="text-muted"),
        ],
        id=f"toggle-{slug}",
        color="link",
        className="w-100 text-start d-flex align-items-center gap-2 text-decoration-none py-2",
        n_clicks=0,
    )

    master = html.Div(
        [
            html.Label("Participación del grupo", className="text-muted small mb-0"),
            dcc.Slider(
                id=f"grp-{group}",
                min=0,
                max=100,
                step=0.1,
                value=share0,
                marks={0: "0 %", 25: "25 %", 50: "50 %", 75: "75 %", 100: "100 %"},
                tooltip={"placement": "bottom"},
                updatemode="drag",
            ),
        ],
        className="mb-1",
    )

    individual = []
    for comp in em.GROUPS[group]:
        individual.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(
                                style={
                                    "display": "inline-block",
                                    "width": "8px",
                                    "height": "8px",
                                    "borderRadius": "2px",
                                    "backgroundColor": color,
                                },
                            ),
                            html.Span(em.names[comp], className="small fw-semibold"),
                        ],
                        className="d-flex align-items-center gap-1",
                    ),
                    dcc.Slider(
                        id=f"ind-{comp}",
                        min=0,
                        max=1,
                        step=0.0001,
                        value=em.sliders_default[comp],
                        marks={0: "0", 0.5: "0.5", 1: "1"},
                        tooltip={"placement": "bottom"},
                        updatemode="drag",
                        className="mb-2",
                    ),
                ],
            )
        )

    return dbc.Card(
        [
            dbc.CardHeader(header, className="p-0 px-2"),
            dbc.CardBody(
                [
                    master,
                    html.Hr(className="my-2"),
                    html.Div("Componentes", className="text-muted small mb-1"),
                    dbc.Collapse(individual, id=f"collapse-{slug}", is_open=True),
                ],
                className="py-2",
            ),
        ],
        className="mb-3 shadow-sm",
    )


app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="Envolvente de fases",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # para gunicorn / despliegues WSGI

app.layout = dbc.Container(
    [
        dcc.Location(id="url"),
        html.Div(
            [
                html.H3("Envolvente de fases interactiva", className="mb-0 mt-2"),
                html.P(
                    "Peng-Robinson 78 + regla QMR · yaeos · arrastra los sliders "
                    "y observa cómo cambia la envolvente P-T.",
                    className="text-muted mb-2",
                ),
            ]
        ),
        dbc.Row(
            [
                # ---------------- Sidebar: composición ----------------
                dbc.Col(
                    [
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    "Composición de la mezcla",
                                    className="fw-semibold",
                                ),
                                dbc.CardBody(
                                    [
                                        dcc.Graph(
                                            id="comp-graph",
                                            figure=build_comp_figure(Z_DEFAULT),
                                            config={
                                                "displayModeBar": False,
                                                "responsive": True,
                                                "scrollZoom": False,
                                            },
                                            style={"height": "320px"},
                                        ),
                                        html.P(
                                            "Barra negra = composición por defecto del "
                                            "script. Asfaltenos (C50-C80A): valor fijo "
                                            "1e-6, sin slider.",
                                            className="text-muted small mb-2",
                                        ),
                                        dbc.Button(
                                            "Restaurar composición por defecto",
                                            id="reset",
                                            color="secondary",
                                            outline=True,
                                            size="sm",
                                            className="w-100",
                                            n_clicks=0,
                                        ),
                                    ],
                                    className="pt-1",
                                ),
                            ],
                            className="mb-3 shadow-sm",
                        ),
                        *[group_card(g) for g in em.GROUP_ORDER],
                    ],
                    lg=4,
                    md=12,
                    className="order-2 order-lg-1 pb-4",
                ),
                # ---------------- Gráfica envolvente ----------------
                dbc.Col(
                    [
                        html.Div(id="status"),
                        dbc.Card(
                            [
                                dbc.CardHeader(
                                    "Envolvente P-T · P vs T",
                                    className="fw-semibold",
                                ),
                                dbc.CardBody(
                                    dcc.Graph(
                                        id="env-graph",
                                        figure=build_env_figure(
                                            em.compute_envelope(em.sliders_default)
                                        ),
                                        config={
                                            "displayModeBar": "hover",
                                            "responsive": True,
                                            "scrollZoom": False,
                                            "doubleClick": "reset",
                                        },
                                        style={"height": "520px"},
                                    ),
                                    className="p-2",
                                ),
                            ],
                            className="shadow-sm",
                        ),
                    ],
                    lg=8,
                    md=12,
                    className="order-1 order-lg-2 pb-3",
                ),
            ],
            className="g-3",
        ),
    ],
    fluid=True,
    className="px-3 px-md-4",
)

# ---------------------------------------------------------------------------
# Callback principal: sliders -> composición -> envolvente + barras
# ---------------------------------------------------------------------------
GROUP_KEYS = em.GROUP_ORDER
N_IND = len(em.VISIBLE)

_ind_inputs = [Input(f"ind-{i}", "value") for i in em.VISIBLE]
_grp_inputs = [Input(f"grp-{g}", "value") for g in GROUP_KEYS]


@callback(
    Output("env-graph", "figure"),
    Output("comp-graph", "figure"),
    Output("status", "children"),
    *[Output(f"ind-{i}", "value") for i in em.VISIBLE],
    *[Output(f"grp-{g}", "value") for g in GROUP_KEYS],
    *[Output(f"share-{GROUP_SLUG[g]}", "children") for g in GROUP_KEYS],
    *_ind_inputs,
    *_grp_inputs,
    Input("reset", "n_clicks"),
)
def update(*args):
    ind_vals = args[:N_IND]
    grp_vals = args[N_IND:N_IND + len(GROUP_KEYS)]
    triggered = ctx.triggered_id

    raw = [
        float(v) if v is not None else d
        for v, d in zip(ind_vals, em.sliders_default)
    ]
    if triggered == "reset":
        raw = list(em.sliders_default)
    elif triggered is not None and str(triggered).startswith("grp-"):
        key = str(triggered)[len("grp-"):]
        if key in GROUP_KEYS and grp_vals[GROUP_KEYS.index(key)] is not None:
            raw = adjust_group(raw, key, float(grp_vals[GROUP_KEYS.index(key)]) / 100.0)

    shares = em.group_shares(raw)
    z = em.normalize(raw)
    if z is None:
        z = np.zeros(em.nc)

    env = em.compute_envelope(raw)
    if env is None:
        env_fig = no_update
        status = dbc.Alert(
            "No fue posible calcular la envolvente para esta composición. "
            "Prueba con una mezcla más cercana a la defecto "
            "(restaurar valores) o con menos componentes en cero.",
            color="warning",
            className="py-2",
        )
    else:
        env_fig = build_env_figure(env)
        status = None

    return (
        env_fig,
        build_comp_figure(z),
        status,
        *raw,
        *[shares[g] for g in GROUP_KEYS],
        *[f"{shares[g]:.1f} %" for g in GROUP_KEYS],
    )


# ---------------------------------------------------------------------------
# Acordeones de grupo: abiertos en escritorio, plegados en móvil
# ---------------------------------------------------------------------------
_collapse_outputs = [Output(f"collapse-{GROUP_SLUG[g]}", "is_open") for g in GROUP_KEYS]
_collapse_inputs = [Input("url", "pathname")] + [
    Input(f"toggle-{GROUP_SLUG[g]}", "n_clicks") for g in GROUP_KEYS
]
_collapse_states = [State(f"collapse-{GROUP_SLUG[g]}", "is_open") for g in GROUP_KEYS]

app.clientside_callback(
    """
    function(pathname, ...rest) {
        const n = %(n)d;
        const states = rest.slice(n, 2 * n);
        const trig = dash_clientside.callback_context.triggered.map(
            t => t.prop_id.split('.')[0]
        );
        const first = trig.length > 0 ? trig[0] : undefined;
        // Primera carga (sin trigger, "." o cambio de URL): según ancho de pantalla
        if (first === undefined || first === '' || first === 'url') {
            const open = window.innerWidth > 768;
            return Array(n).fill(open);
        }
        const toggles = %(toggles)s;
        const idx = toggles.indexOf(first);
        const out = states.slice();
        if (idx >= 0) {
            out[idx] = !states[idx];
        }
        return out;
    }
    """
    % {
        "n": len(GROUP_KEYS),
        "toggles": str([f"toggle-{GROUP_SLUG[g]}" for g in GROUP_KEYS]),
    },
    *_collapse_outputs,
    *_collapse_inputs,
    *_collapse_states,
)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)

