import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
import os
from shapely.geometry import Point,LineString
import json

ntas = gpd.read_file("shapefiles/nynta2020_24d")
df = pd.read_csv('static_data/rolling_avg.csv')

month_dict = {
    1 : 'January',
    2 : 'February',
    3 : 'March',
    4 : 'April',
    5 : 'May',
    6 : 'June',
    7 : 'July',
    8 : 'August',
    9 : 'September',
    10 : 'October',
    11 : 'November',
    12 : 'December'
}

def produce_rolling(df,window_size,min):
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['NTAName', 'date'])
    df['avg_imputed'] = df.groupby('NTAName')['avg'].transform(lambda x: x.fillna(x.mean()))
    df['rolling_avg'] = df.groupby('NTAName')['avg_imputed'].rolling(window=window_size, min_periods=min).mean().reset_index(level=0, drop=True)
    return df

def extract_segment(route, stop, next_stop):
    """
    Extracts the segment of the route between the stop and next_stop.
    """
    if not route or not stop or not next_stop:
        return None
    
    line_segments = list(route.geoms) if route.geom_type == 'MultiLineString' else [route]
    
    for segment in line_segments:
        if segment.distance(stop) < 1e-6 and segment.distance(next_stop) < 1e-6:
            return segment 
            
    
    return LineString([stop, next_stop])

def make_slow_routes(df,count,geo_stop_dict,geo_next_stop_dict):
    route_speed = df.groupby(['route_id','timepoint_stop_name','next_timepoint_stop_name'])['average_road_speed'].mean().reset_index()
    slowest_routes = route_speed.sort_values('average_road_speed',ascending=True).head(count)

    slowest_routes['stop_geo'] = slowest_routes['timepoint_stop_name'].map(geo_stop_dict)
    slowest_routes['next_stop_geo'] = slowest_routes['next_timepoint_stop_name'].map(geo_next_stop_dict)

    return slowest_routes

def make_gpd(df,bus_routes):
    df = df.merge(bus_routes, left_on='route_id', right_on='route_id',how='left')
    df['stop_point'] = df['stop_geo'].apply(lambda x: Point(x['coordinates']))
    df['next_stop_point'] = df['next_stop_geo'].apply(lambda x: Point(x['coordinates']))
    
    df['segment_geometry'] = df.apply(lambda row: extract_segment(row['geometry'], row['stop_point'], row['next_stop_point']), axis=1)
    short_df = df[['route_id','timepoint_stop_name','next_timepoint_stop_name','average_road_speed','segment_geometry']]
    gdf = gpd.GeoDataFrame(short_df, geometry='segment_geometry')
    return gdf

def make_table(df,month_dict):
    df['month_name'] = df['month'].map(month_dict)
    month = df['month_name'].unique()[0]
    boroughs = df.groupby('borough')['average_road_speed'].mean().reset_index(name='raw_speed')
    whole_city = df['average_road_speed'].mean()
    table = pd.DataFrame({'borough': 'NYC Whole', 'raw_speed': whole_city}, index=[0])
    boroughs = pd.concat([boroughs, table], ignore_index=True)
    boroughs[f'{month}_avg_speed'] = boroughs['raw_speed'].round(1)
    return boroughs

def join_tables(df1,df2,month_dict):
    tb1 = make_table(df1,month_dict)
    tb2 = make_table(df2,month_dict)
    tables = tb1.merge(tb2,on='borough')
    drop_cols = [col for col in tables.columns if 'raw_speed' in col]
    tables.drop(columns=drop_cols,inplace=True)
    return tables