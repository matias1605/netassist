"""Diseño de la interfaz Streamlit: mismo estilo que la web (paleta teal/navy, tarjetas y mascota Nexo).

Solo presentación: no toca la lógica de NetAssist (RAG, cadena, casos ni validaciones).
"""

import base64

NEXO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">
<g stroke="#1b2c44" stroke-width="3" stroke-linecap="round">
<line x1="60" y1="22" x2="60" y2="10"/>
<circle cx="60" cy="8" r="5" fill="#ffcf4a" stroke-width="2.5"/>
<rect x="14" y="44" width="10" height="22" rx="4" fill="#3fbfb1"/>
<rect x="96" y="44" width="10" height="22" rx="4" fill="#3fbfb1"/>
<rect x="22" y="22" width="76" height="64" rx="20" fill="#e9f1f8"/>
<rect x="36" y="88" width="48" height="26" rx="11" fill="#3fbfb1"/>
<rect x="22" y="90" width="12" height="20" rx="6" fill="#3fbfb1"/>
<rect x="86" y="90" width="12" height="20" rx="6" fill="#3fbfb1"/>
<circle cx="60" cy="101" r="4" fill="#ffcf4a" stroke-width="2"/>
</g>
<rect x="31" y="32" width="58" height="42" rx="13" fill="#12243b"/>
<ellipse cx="47" cy="51" rx="6" ry="7.5" fill="#59f0de"/>
<ellipse cx="73" cy="51" rx="6" ry="7.5" fill="#59f0de"/>
<circle cx="49" cy="48" r="2" fill="#fff"/>
<circle cx="75" cy="48" r="2" fill="#fff"/>
<ellipse cx="38" cy="63" rx="4.5" ry="2.6" fill="#ff8fa3" opacity=".55"/>
<ellipse cx="82" cy="63" rx="4.5" ry="2.6" fill="#ff8fa3" opacity=".55"/>
<path d="M52 63 Q60 70 68 63" fill="none" stroke="#59f0de" stroke-width="3" stroke-linecap="round"/>
</svg>"""

NEXO_URI = "data:image/svg+xml;base64," + base64.b64encode(NEXO_SVG.encode("utf-8")).decode("ascii")

_CSS = """
<style>
  :root {
    --navy: #0f1a2b; --blue: #14958a; --blue-dark: #0f7a71; --teal-soft: #e6f6f4;
    --ink: #1d2b3b; --muted: #6b7a8c; --line: #e3e9f0; --canvas: #f2f5f8;
  }
  /* Panel izquierdo: navegación como en la web */
  [data-testid="stSidebar"] { background: var(--navy); border-right: 0; min-width: 236px; }
  [data-testid="stSidebar"] > div:first-child { background: var(--navy); }
  [data-testid="stSidebarHeader"] { display: none; }
  [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapsedControl"] button { color: #c9d4e2; }
  [data-testid="stSidebarContent"] { padding: 0; }
  [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding: 22px 12px 18px; }
  .sb { display: flex; flex-direction: column; gap: 6px; min-height: calc(100vh - 40px); color: #c9d4e2; }
  .sb a { text-decoration: none; }
  .sb-brand { display: flex; align-items: center; gap: 12px; padding: 0 8px 18px; margin-bottom: 8px; border-bottom: 1px solid #1f2f47; color: inherit; }
  .sb-mark { display: grid; place-items: center; flex: 0 0 auto; width: 40px; height: 40px; border-radius: 12px; border: 1px solid #1f6b66; background: #12353a; color: #3fd3c3; font-weight: 800; font-size: 19px; }
  .sb-mark i { font-style: normal; color: #59f0de; }
  .sb-brand strong, .sb-brand small { display: block; }
  .sb-brand strong { color: #fff; font-size: 20px; letter-spacing: -.02em; }
  .sb-brand small { margin-top: 3px; color: #7d8ca2; font-size: 10px; letter-spacing: .14em; text-transform: uppercase; }
  .sb-label { margin: 14px 8px 8px; color: #66768d; font-size: 10px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
  .sb-nav a { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; padding: 14px; border: 1px solid transparent; border-radius: 12px; color: #dfe7f1; font-size: 14px; font-weight: 600; }
  .sb-nav a:hover { background: #15243b; color: #fff; }
  .sb-nav a.activo { color: #fff; background: #172a40; border-color: #24405a; }
  .sb-ico { display: inline-grid; place-items: center; width: 20px; color: #8fa0b6; font-size: 15px; }
  .sb-nav a.activo .sb-ico { color: #3fd3c3; }
  .sb-dot { width: 7px; height: 7px; margin-left: auto; border-radius: 50%; background: #3fd3c3; }
  .sb-foot { margin-top: auto; padding: 14px 8px 0; }
  .sb-foot p { margin: 0 0 4px; color: #7d8ca2; font-size: 11.5px; }
  .sb-foot span { color: #e8eef6; font-size: 12.5px; font-weight: 600; }
  .stApp, [data-testid="stAppViewContainer"] { background: var(--canvas); color: var(--ink); }
  [data-testid="stHeader"] { background: transparent; }
  .stMain .block-container { max-width: 1160px; padding: 56px clamp(16px, 3vw, 38px) 170px; }

  /* Tipografía */
  h1 { color: var(--navy); font-weight: 700 !important; letter-spacing: -.03em; line-height: 1.12; }
  h2, h3 { color: var(--navy); font-weight: 700 !important; letter-spacing: -.02em; }
  [data-testid="stCaptionContainer"], .stCaption { color: #5f7083; }
  .stMarkdown a { color: var(--blue-dark); }

  /* Campos */
  .stMain label p { color: var(--ink); font-weight: 650; font-size: 13px; }
  .stMain [data-baseweb="input"], .stMain [data-baseweb="base-input"],
  .stMain [data-baseweb="select"] > div, .stMain [data-baseweb="textarea"] {
    background: #fff; border-color: #d3dde8; border-radius: 10px;
  }
  .stMain [data-baseweb="input"]:focus-within, .stMain [data-baseweb="select"] > div:focus-within,
  .stMain [data-baseweb="textarea"]:focus-within {
    border-color: #7fcfc6; box-shadow: 0 0 0 3px rgb(20 149 138 / 12%);
  }
  .stMain textarea, .stMain input { color: var(--ink); background: #fff; }
  .stMain [data-baseweb="input"] > div, .stMain [data-baseweb="base-input"] { background: #fff; }
  [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
  }

  /* Botones */
  .stMain .stButton > button, .stMain .stDownloadButton > button {
    min-height: 38px; padding: 0 14px; border-radius: 9px; font-weight: 650; font-size: 13px;
    color: #405268; background: #fff; border: 1px solid var(--line); transition: background .15s, border-color .15s;
  }
  .stMain .stButton > button:hover, .stMain .stDownloadButton > button:hover { background: var(--teal-soft); border-color: #7fcfc6; color: var(--blue-dark); }
  .stMain .stButton > button[kind="primary"] { color: #fff; background: var(--blue); border-color: var(--blue); }
  .stMain .stButton > button[kind="primary"]:hover { background: var(--blue-dark); border-color: var(--blue-dark); color: #fff; }
  .stMain .stButton > button:disabled { opacity: .5; }
  .stMain :is(button, summary, a):focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }

  /* Laboratorio: encabezado y tarjetas como en la web */
  .lab-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin: 8px 0 6px; }
  .lab-eyebrow { margin: 0; color: var(--blue-dark); font-size: 11px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
  .lab-titulo { margin: 6px 0 10px; color: var(--navy); font-size: clamp(28px, 3.4vw, 40px); line-height: 1.12; letter-spacing: -.03em; font-weight: 700; }
  .lab-lead { margin: 0 0 8px; color: #5f7083; font-size: 15px; line-height: 1.6; }
  .lab-sello { flex: 0 0 auto; padding: 14px 20px; border: 1px solid var(--line); border-radius: 12px; background: #fff; }
  .lab-sello strong, .lab-sello span { display: block; }
  .lab-sello strong { color: var(--navy); font-size: 12px; letter-spacing: .1em; text-transform: uppercase; }
  .lab-sello span { margin-top: 6px; color: var(--muted); font-size: 10px; letter-spacing: .14em; text-transform: uppercase; }
  .st-key-lab-form, .st-key-lab-practica {
    padding: 28px; background: #fff; border: 1px solid var(--line); border-radius: 18px;
    box-shadow: 0 6px 22px rgb(24 48 77 / 5%); gap: 16px;
  }
  .card-head { display: flex; align-items: center; gap: 16px; }
  .card-head h2 { margin: 0; padding: 0; color: var(--navy); font-size: 21px; letter-spacing: -.02em; font-weight: 700; }
  .card-head p { margin: 4px 0 0; color: #5f7083; font-size: 12.5px; }
  .card-num { display: grid; place-items: center; flex: 0 0 auto; width: 48px; height: 48px; border: 1px solid #cfe9e5; border-radius: 12px; color: var(--blue-dark); background: var(--teal-soft); font-size: 14px; }
  .form-sec { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 6px 0 0; color: #7b8a9b; font-size: 10px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }
  .form-sec span:last-child { letter-spacing: .04em; text-transform: none; font-weight: 500; }
  .stMain [data-baseweb="tab-list"] { gap: 26px; border-bottom: 1px solid var(--line); }
  .stMain [data-baseweb="tab"] { padding: 10px 0 14px; color: #6b7a8c; font-weight: 500; background: none; }
  .stMain [data-baseweb="tab"][aria-selected="true"] { color: var(--blue-dark); font-weight: 700; }
  .stMain [data-baseweb="tab-highlight"] { background: var(--blue); height: 2px; }
  .stMain [data-baseweb="tab-border"] { background: transparent; }
  [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"]):not([class*="st-key-"]) {
    background: #fff; border-color: var(--line); border-radius: 16px; box-shadow: 0 6px 22px rgb(24 48 77 / 4%);
  }
  .stMain [data-testid="stExpander"] { background: #fff; border: 1px solid var(--line); border-radius: 12px; }
  .stMain [data-testid="stExpander"] summary { color: var(--blue-dark); font-weight: 600; }
  [data-testid="stAlert"] { border-radius: 10px; }
  .stMain pre { border-radius: 9px; }
  .stMain hr { border-color: var(--line); }

  /* Burbuja flotante: Nexo con su globo cuando el chat está cerrado */
  .st-key-boton-burbuja-cerrada, .st-key-boton-burbuja-abierta {
    position: fixed; right: 22px; bottom: 18px; z-index: 1001; width: auto !important;
  }
  .st-key-boton-burbuja-cerrada button {
    position: relative; width: 104px; height: 104px; padding: 0; border: none; border-radius: 24px;
    background: url("__NEXO__") center / contain no-repeat transparent;
    filter: drop-shadow(0 10px 18px rgb(15 26 43 / 22%)); transition: transform .2s;
  }
  .st-key-boton-burbuja-cerrada button:hover, .st-key-boton-burbuja-cerrada button:focus:not(:active) {
    background: url("__NEXO__") center / contain no-repeat transparent; border: none; transform: translateY(-3px) scale(1.03);
  }
  .st-key-boton-burbuja-cerrada button p { display: none; }
  .st-key-boton-burbuja-cerrada button::before {
    content: "¿Necesitas ayuda?\\A Pregúntale a NetAssist"; white-space: pre; position: absolute; right: 92px; bottom: 34px;
    padding: 12px 16px; border: 1px solid var(--line); border-radius: 16px 16px 4px 16px;
    color: #3f5167; background: #fff; font-size: 12.5px; line-height: 1.4; text-align: left;
    box-shadow: 0 10px 28px rgb(15 26 43 / 14%); filter: none;
  }
  .st-key-boton-burbuja-abierta button {
    width: 56px; height: 56px; border: none; border-radius: 50%; color: #fff; font-size: 24px;
    background: linear-gradient(135deg, #17a597, #0f7a71); box-shadow: 0 6px 18px rgb(20 149 138 / 35%);
  }
  .st-key-boton-burbuja-abierta button:hover { background: var(--blue-dark); color: #fff; border: none; }
  .st-key-boton-burbuja-abierta button:focus:not(:active) { color: #fff; border: none; }

  /* Ventana del chat */
  .st-key-ventana-chat {
    position: fixed; right: 24px; bottom: 88px; z-index: 1000;
    width: min(580px, calc(100vw - 32px)) !important; max-height: calc(100vh - 112px); overflow-y: auto;
    background: #f4f8fa; border-radius: 24px; padding: 0; gap: 0; border: 1px solid rgb(15 26 43 / 8%);
    box-shadow: 0 30px 80px rgb(10 25 45 / 26%), 0 4px 14px rgb(10 25 45 / 8%);
  }
  .st-key-cabecera-chat {
    position: relative; overflow: hidden; padding: 16px 16px 16px 20px; border-radius: 24px 24px 0 0;
    background: radial-gradient(circle at 100% 0, rgb(63 211 195 / 35%), transparent 55%),
                linear-gradient(135deg, #0f1a2b 0%, #14304a 60%, #0f6f68 130%);
  }
  .st-key-cabecera-chat p { color: #fff; margin: 0; line-height: 1.3; font-size: 20px; letter-spacing: -.02em; }
  .st-key-cabecera-chat .nx-cab { display: flex; align-items: center; gap: 12px; }
  .st-key-cabecera-chat .nx-cab img { width: 46px; height: 46px; border-radius: 14px; padding: 3px; background: #fff; }
  .st-key-cabecera-chat .nx-cab strong { display: flex; align-items: center; gap: 10px; font-size: 21px; font-weight: 700; color: #fff; }
  .st-key-cabecera-chat .nx-cab small { display: block; margin-top: 4px; color: #9fb3c8; font-size: 12px; }
  .st-key-cabecera-chat .nx-en-linea {
    display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px 3px 7px; border-radius: 999px;
    color: #bff7ef; background: rgb(255 255 255 / 10%); font-size: 11px; font-weight: 600;
  }
  .st-key-cabecera-chat .nx-en-linea i { width: 7px; height: 7px; border-radius: 50%; background: #3ee6a0; box-shadow: 0 0 0 3px rgb(62 230 160 / 22%); }
  .st-key-cabecera-chat button {
    background: rgba(255, 255, 255, .12); color: #fff; border: 1px solid rgba(255, 255, 255, .45);
    border-radius: 999px; padding: 2px 12px; min-height: 0; font-size: 13px;
  }
  .st-key-cabecera-chat button:hover { background: rgba(255, 255, 255, .25); color: #fff; border-color: #fff; }
  .st-key-cuerpo-chat {
    padding: 16px 14px 6px;
    background: radial-gradient(rgb(20 149 138 / 9%) 1px, transparent 1px) 0 0 / 18px 18px, linear-gradient(180deg, #f4f8fa, #eef4f7);
  }
  .st-key-cuerpo-chat [data-testid="stChatMessage"] {
    padding: 12px 15px; margin-bottom: 10px; border-radius: 6px 18px 18px 18px; gap: 10px;
    background: #fff; border: 1px solid #e2eaf1; box-shadow: 0 2px 10px rgb(15 26 43 / 5%);
  }
  .st-key-cuerpo-chat [data-testid="stChatMessage"]:has(.msg-usuario) {
    flex-direction: row-reverse; margin-left: 40px; border-color: transparent; border-radius: 18px 6px 18px 18px;
    background: linear-gradient(135deg, #17a597, #0f7a71); box-shadow: 0 6px 16px rgb(20 149 138 / 25%);
  }
  .st-key-cuerpo-chat [data-testid="stChatMessage"]:has(.msg-usuario) :is(p, li, strong, em) { color: #fff; }
  .st-key-cuerpo-chat [data-testid="stChatMessage"]:has(.msg-usuario) [data-testid^="stChatMessageAvatar"] { display: none; }
  .st-key-cuerpo-chat [data-testid="stChatMessage"]:not(:has(.msg-usuario)) { margin-right: 12px; }
  .st-key-cuerpo-chat [data-testid^="stChatMessageAvatar"] img { border-radius: 12px; background: #fff; padding: 2px; }
  .st-key-cuerpo-chat .stElementContainer:has(.msg-usuario) { display: none; }
  .st-key-cuerpo-chat [data-testid="stChatMessageContent"] { min-width: 0; }
  .st-key-cuerpo-chat [data-testid="stChatMessageContent"] p { font-size: 14px; line-height: 1.6; }
  .st-key-cuerpo-chat code:not(pre code) { padding: 2px 5px; border-radius: 5px; background: #e8edf4; color: #26364a; }
  .st-key-cuerpo-chat pre { background: #111b2a; border: 1px solid #223249; border-radius: 9px; }
  .st-key-cuerpo-chat [data-testid="stImage"], .st-key-cuerpo-chat [data-testid="stImageContainer"] { margin-left: auto; margin-right: auto; }
  .st-key-cuerpo-chat img { border-radius: 10px; }
  .st-key-cuerpo-chat iframe { display: block; margin: 0 auto; }
  .st-key-pie-chat { padding: 12px 16px 14px; border-top: 1px solid var(--line); background: #fff; border-radius: 0 0 24px 24px; }
  .st-key-pie-chat [data-testid="stChatInput"] > div { border-radius: 18px; border-color: #d9e1eb; background: #f7fafc; }
  .st-key-pie-chat [data-testid="stChatInput"] > div:focus-within { border-color: #7fcfc6; box-shadow: 0 0 0 4px rgb(20 149 138 / 12%); }
  .st-key-pie-chat [data-testid="stChatInputSubmitButton"] { color: #fff; background: linear-gradient(135deg, #17a597, #0f7a71); border-radius: 12px; }

  @media (max-width: 640px) {
    .st-key-ventana-chat { right: 8px; bottom: 80px; }
    .st-key-boton-burbuja-cerrada, .st-key-boton-burbuja-abierta { right: 12px; bottom: 12px; }
    .st-key-boton-burbuja-cerrada button::before { display: none; }
    .st-key-lab-form, .st-key-lab-practica { padding: 18px 14px; } .lab-sello { display: none; }
  }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
""".replace("__NEXO__", NEXO_URI)


def estilos() -> str:
    return _CSS


def panel_izquierdo(contacto: str) -> str:
    """Navegación lateral, igual que la de la web."""
    return (
        '<div class="sb">'
        '<a class="sb-brand" href="#laboratorio-de-redes-y-conectividad-i"><span class="sb-mark">N<i>.</i></span>'
        "<span><strong>NetAssist</strong><small>Laboratorio de redes</small></span></a>"
        '<nav class="sb-nav"><p class="sb-label">Espacio de trabajo</p>'
        '<a href="#laboratorio-de-redes-y-conectividad-i"><span class="sb-ico">◈</span>Presentación</a>'
        '<a class="activo" href="#tu-proxima-red-empieza-aqui"><span class="sb-ico">▦</span>Laboratorio<span class="sb-dot"></span></a>'
        '<a href="#practicas"><span class="sb-ico">▤</span>Mis prácticas</a></nav>'
        f'<div class="sb-foot"><p>¿Necesitas ayuda?</p><span>{contacto}</span></div></div>'
    )


def cabecera_chat() -> str:
    return (
        f'<div class="nx-cab"><img src="{NEXO_URI}" alt="">'
        '<div><strong>NetAssist <span class="nx-en-linea"><i></i>En línea</span></strong>'
        "<small>Soporte de redes Cisco IOS</small></div></div>"
    )


ENCABEZADO_LAB = (
    '<header class="lab-heading"><div>'
    '<p class="lab-eyebrow">Aprende · Configura · Comprueba</p>'
    '<h2 class="lab-titulo">Tu próxima red empieza aquí.</h2>'
    '<p class="lab-lead">Organiza una práctica Cisco y entiende cada paso con tu asistente. '
    'VLAN y puertos de acceso · Solo datos ficticios · Un switch, sin IP, trunk ni enrutamiento entre VLAN.</p>'
    '</div><div class="lab-sello"><strong>Cisco IOS</strong><span>VLAN + acceso</span></div></header>'
)


def card_head(numero: str, titulo: str, ayuda: str) -> str:
    return (
        f'<header class="card-head"><span class="card-num">{numero}</span>'
        f"<div><h2>{titulo}</h2><p>{ayuda}</p></div></header>"
    )


def form_sec(izquierda: str, derecha: str) -> str:
    return f'<p class="form-sec"><span>{izquierda}</span><span>{derecha}</span></p>'
