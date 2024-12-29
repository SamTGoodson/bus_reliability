import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
import os

ntas = gpd.read_file("../shapefiles/nynta2020_24d")
df = pd.read_csv('static_data/rolling_avg.csv')

def produce_rolling(df,window_size,min):
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(by=['NTAName', 'date'])
    df['avg_imputed'] = df.groupby('NTAName')['avg'].transform(lambda x: x.fillna(x.mean()))
    df['rolling_avg'] = df.groupby('NTAName')['avg_imputed'].rolling(window=window_size, min_periods=min).mean().reset_index(level=0, drop=True)
    return df