import pandas as pd
import geopandas as gpd
import os
from dotenv import load_dotenv
import base64
import pytz

from dash import Dash, html, Output, Input, dash_table
import dash_bootstrap_components as dbc

import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash_extensions.javascript import arrow_function, assign
import json

from oauth2client.service_account import ServiceAccountCredentials
import gspread

from utils.sort_and_join import month_dict, produce_rolling, make_table, join_tables,clean_spreadsheet
from utils.style import style_handle, get_info

load_dotenv()
encoded_key = os.getenv('GOOGLE_CREDENTIALS_BASE64')
json_key = base64.b64decode(encoded_key).decode('utf-8')
with open('service_account_key.json', 'w') as key_file:
    key_file.write(json_key)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('service_account_key.json', scope)
client = gspread.authorize(creds)
sheet_id = '144aqQL8BLJGJNGnUU_UlyMVoMED_1CM-6SQjgO_xJBQ'
sheet = client.open_by_key(sheet_id).sheet1 
data = sheet.get_all_records()
df = pd.DataFrame(data)
df = clean_spreadsheet(df)

ntas = gpd.read_file("shapefiles/nynta2020_24d")
#df = pd.read_csv('static_data/rolling_avg.csv')
local_tz = pytz.timezone('America/New_York')
df['date'] = pd.to_datetime(df['date'])
df['date'] = df['date'].dt.tz_localize('UTC').dt.tz_convert(local_tz)
scrape_date = df['date'].max().strftime('on %m/%d/%Y at %H:%M')

with open("shapefiles/segments.geojson", "r") as f:
    bus_geojson = json.load(f)

oct_speed = pd.read_csv('static_data/raw_oct_speed.csv')
nov_speed = pd.read_csv('static_data/raw_nov_speed.csv')


rolling_df = produce_rolling(df,4,1)
most_recent_df = rolling_df.loc[rolling_df.groupby('NTAName')['date'].idxmax()]
rolling_map = ntas.merge(most_recent_df, left_on='NTAName', right_on='NTAName')
rolling_map.dropna(subset=['rolling_avg'],inplace=True)
rolling_map = rolling_map[['NTAName','rolling_avg','Shape_Leng','Shape_Area','geometry']]
rolling_map = rolling_map.to_crs(epsg=4326)

geojson_data = json.loads(rolling_map.to_json())


classes = [0, 1, 2, 3, 4, 5, 7, 9,11,13, 15,17]
colorscale = ['#FFEDA0', '#FED976', '#FEB24C', '#FD8D3C', '#FC4E2A', '#E31A1C', '#BD0026', '#800026',
              '#660022', '#440016', '#33000F', '#20000A']
style = dict(weight=2, opacity=1, color='white', dashArray='3', fillOpacity=0.7)

ctg = ["{}+".format(cls, classes[i + 1]) for i, cls in enumerate(classes[:-1])] + ["{}+".format(classes[-1])]
colorbar = dlx.categorical_colorbar(categories=ctg, colorscale=colorscale, width=300, height=30, position="bottomleft")

table_data = join_tables(oct_speed,nov_speed,month_dict)
table_rows = table_data.to_dict('records')
table_columns = [{"name": col, "id": col} for col in table_data.columns]

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
        html.H1("NYC Bus Speed and Reliability", style={'font-family': 'Georgia', 'padding': '10px', 'textAlign': 'center'}),
        html.P("The map below shows two metrics for bus performance in NYC. The color of the tiles represents a rolling average of on-time arrivals for each Neighborhood Tabulation Area (NTA) in NYC. This was calculated by averaging the absolute difference in minutes between expected arrival and actual arrival for all stops in the NTA. The green lines represent the slowest segments of bus routes in NYC during Wednesday AM and PM rush hour."),
        html.P("The on-time data is collected from the MTA's Bus Time API and is queried everyday at rush hour. Bus speeds are collected from the NYC Open Data and are updated monthly. See table below map for average speeds by borough."),
        html.P("Hover over a tile to see the NTA name and the average minutes off schedule. Click on a tile to zoom in and see the NTA boundaries."),
        html.P(f"On-time data last queried {scrape_date}", style={'font-style': 'italic'}),
    ], style={'font-family': 'Georgia', 'padding': '10px', 'textAlign': 'center'}),

    html.Div([
        dl.Map(center=[40.7128, -74.0060], zoom=10, children=[
            dl.TileLayer(),
            dl.GeoJSON(data=geojson_data, style=style_handle, id='geojson',
                       zoomToBounds=True, zoomToBoundsOnClick=True,
                       hoverStyle=arrow_function(dict(weight=5, color='#666', dashArray='')),
                       hideout=dict(colorscale=colorscale, classes=classes, style=style, colorProp="rolling_avg")),
            dl.GeoJSON(data=bus_geojson,
                       options=dict(style=dict(color="#00FF00", weight=3, opacity=1))),
            colorbar, info
        ], style={'width': '100%', 'height': '75vh', 'padding-bottom': '20px', 'margin-bottom': '50px'})
    ]),
    html.Div([
        html.P("The table below shows the average speed of buses in each borough during Wednesday AM and PM rush hour. The data is collected from the NYC Open Data and is updated monthly. We are still waiting on December numbers, this will probably be the most immediately revealing of congestion pricing success but we may not know until February."), 
    ])
    ,
    html.Div([
        html.H2("Avg. Bus Speed by Borough", style={'font-family': 'Georgia', 'textAlign': 'center', 'margin-top': '20px'}),
        dash_table.DataTable(
            data=table_rows,
            columns=table_columns,
            style_table={'width': '80%', 'margin': '0 auto'},
            style_cell={'textAlign': 'center', 'font-family': 'Georgia', 'padding': '5px'},
            style_header={'fontWeight': 'bold', 'backgroundColor': '#f4f4f4'}
        )
    ])
])


@app.callback(Output("info", "children"), Input("geojson", "hoverData"))
def info_hover(feature):
    return get_info(feature)

if __name__ == '__main__':
    app.run_server(debug=True)
