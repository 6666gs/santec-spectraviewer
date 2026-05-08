"""SpectraViewer Dash Web 应用。"""

import dash
import dash_bootstrap_components as dbc

from web.layout import layout
from web import callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title='SpectraViewer',
)
app.layout = layout
callbacks.register(app)
