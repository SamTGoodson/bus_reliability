import pandas as pd
import geopandas as gpd

from dash import Dash, html, Output, Input
import dash_bootstrap_components as dbc

import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash_extensions.javascript import arrow_function, assign
import plotly.figure_factory as ff

import json

from matplotlib import cm, colors

style_handle = assign("""function(feature, context){
    const {classes, colorscale, style, colorProp} = context.hideout;  // get props from hideout
    const value = feature.properties[colorProp];  // get value the determines the color
    for (let i = 0; i < classes.length; ++i) {
        if (value > classes[i]) {
            style.fillColor = colorscale[i];  // set the fill color according to the class
        }
    }
    return style;
}""")

def produce_rolling(df,window_size,min):
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['NTAName', 'date'])
    df['avg_imputed'] = df.groupby('NTAName')['avg'].transform(lambda x: x.fillna(x.mean()))
    df['rolling_avg'] = df.groupby('NTAName')['avg_imputed'].rolling(window=window_size, min_periods=min).mean().reset_index(level=0, drop=True)
    return df

def get_info(feature=None):
    header = [html.H4("On Time Rating")]
    if not feature:
        return header + [html.P("Hoover over a district")]
    return header + [html.B(feature["properties"]["NTAName"]), html.Br(),
                     "{} minutes off schedule".format(round(feature["properties"]["rolling_avg"],2))]

ntas = gpd.read_file("shapefiles/nynta2020_24d")
df = pd.read_csv('static_data/rolling_avg.csv')

rolling_df = produce_rolling(df,3,1)
most_recent_df = rolling_df.loc[rolling_df.groupby('NTAName')['date'].idxmax()]
rolling_map = ntas.merge(most_recent_df, left_on='NTAName', right_on='NTAName')
rolling_map.dropna(subset=['rolling_avg'],inplace=True)
rolling_map = rolling_map[['NTAName','rolling_avg','Shape_Leng','Shape_Area','geometry']]
rolling_map = rolling_map.to_crs(epsg=4326)

geojson_data = json.loads(rolling_map.to_json())


classes = [0, 1, 2, 3, 4, 5, 10, 20]
colorscale = ['#FFEDA0', '#FED976', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026']
style = dict(weight=2, opacity=1, color='white', dashArray='3', fillOpacity=0.7)

ctg = ["{}+".format(cls, classes[i + 1]) for i, cls in enumerate(classes[:-1])] + ["{}+".format(classes[-1])]
colorbar = dlx.categorical_colorbar(categories=ctg, colorscale=colorscale, width=300, height=30, position="bottomleft")



app = Dash(__name__)
server = app.server

info = html.Div(children=get_info(), id="info", className="info",
                style={
        "position": "absolute",
        "top": "10px",
        "right": "10px",
        "zIndex": "1000",
        "background-color": "white", 
        "padding": "10px",  
        "border": "1px solid #ccc", 
        "border-radius": "5px",  
        "box-shadow": "0 0 5px rgba(0, 0, 0, 0.2)" 
    })



app.layout = html.Div([
    html.Div([
        html.H1("NYC Bus On Time Rating", style={'font-family': 'Georgia', 'padding': '10px', 'textAlign': 'center'}),
        html.P("This map shows a rolling average of on-time arrivals for each NTA in NYC. The on-time rating is calculated as the average number of minutes each bus is off schedule in either direction."),
        html.P("Hover over a district to see the name and on-time rating."),
    ], style={'font-family': 'Georgia', 'padding': '10px', 'textAlign': 'center'}),

    html.Div([
        dl.Map(center=[40.7128, -74.0060], zoom=10, children=[
            dl.TileLayer(),
            dl.GeoJSON(data=geojson_data, style=style_handle, id='geojson',
                       zoomToBounds=True, zoomToBoundsOnClick=True,
                       hoverStyle=arrow_function(dict(weight=5, color='#666', dashArray='')),
                       hideout=dict(colorscale=colorscale, classes=classes, style=style, colorProp="rolling_avg")),
            colorbar, info
        ], style={'width': '100%', 'height': '75vh', 'padding-bottom': '20px', 'margin-bottom': '50px'})
    ])
])


@app.callback(Output("info", "children"), Input("geojson", "hoverData"))
def info_hover(feature):
    return get_info(feature)

if __name__ == '__main__':
    app.run_server(debug=True)
