import plotly.express as px
import plotly.graph_objects as go
from utils.theme import get_colors
from utils.translations import t

def get_base_layout(**kwargs):
    """Returns a base layout for Plotly charts supporting Devanagari Hindi and Hinglish fonts."""
    layout = dict(
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(family="Noto Sans Devanagari, Nirmala UI, Inter, Arial, sans-serif", color="#1E293B"),
        title=dict(font=dict(color="#1E293B", family="Playfair Display, Georgia, Noto Sans Devanagari, serif", size=16)),
        xaxis=dict(
            showgrid=False, 
            zeroline=False, 
            title=dict(font=dict(color="#1E293B")),
            tickfont=dict(color="#64748B")
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor="#E2E8F0", 
            zeroline=False, 
            title=dict(font=dict(color="#1E293B")),
            tickfont=dict(color="#64748B")
        ),
        legend=dict(font=dict(color="#1E293B")),
        hoverlabel=dict(bgcolor="#FFFFFF", font=dict(color="#1E293B"), bordercolor="#2563EB"),
        hovermode="x unified"
    )
    if kwargs:
        layout.update(kwargs)
    return layout

def create_line_chart(df, x_col, y_col, title, color=None):
    if not color:
        color = get_colors().get('blue', '#2563EB')
    fig = px.line(df, x=x_col, y=y_col, title=t(title))
    fig.update_traces(line_color=color, line_width=3)
    fig.update_layout(**get_base_layout())
    return fig

def create_bar_chart(df, x_col, y_col, title, color=None, orientation='v'):
    if not color:
        color = get_colors().get('secondary', '#0D9488')
    fig = px.bar(df, x=x_col, y=y_col, title=t(title), orientation=orientation)
    fig.update_traces(marker_color=color, marker_line_width=0, textfont=dict(color="#FFFFFF", size=12))
    fig.update_layout(**get_base_layout())
    return fig
    
def create_donut_chart(df, names_col, values_col, title):
    colors_dict = get_colors()
    palette = [
        colors_dict.get('blue', '#2563EB'),
        colors_dict.get('secondary', '#0D9488'),
        colors_dict.get('orange', '#EA580C'),
        colors_dict.get('green', '#059669'),
        colors_dict.get('purple', '#7C3AED'),
    ]
    
    fig = px.pie(df, names=names_col, values=values_col, title=t(title), hole=0.6, color_discrete_sequence=palette)
    layout = get_base_layout()
    layout.pop("xaxis", None)
    layout.pop("yaxis", None)
    layout.pop("hovermode", None)
    fig.update_layout(**layout)
    return fig
