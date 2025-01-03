import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv
import os
import requests
from tqdm import tqdm
import random
import csv
import datetime
import pickle
import argparse
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import base64

load_dotenv() 
BUS_TIME_KEY = os.getenv("BUS_TIME_KEY")
encoded_key = os.getenv('GOOGLE_CREDENTIALS_BASE64')
json_key = base64.b64decode(encoded_key).decode('utf-8')
with open('service_account_key.json', 'w') as key_file:
    key_file.write(json_key)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('service_account_key.json', scope)
client = gspread.authorize(creds)
sheet_id = '144aqQL8BLJGJNGnUU_UlyMVoMED_1CM-6SQjgO_xJBQ'


if not BUS_TIME_KEY:
    raise ValueError("API_KEY is not set in the environment variables.")

oba_url = "https://bustime.mta.info/api/where/stops-for-location.json"
oba_meta_url = "https://bustime.mta.info/api/where/routes-for-agency/MTA%20NYCT.xml"
siri_vm_url = "https://bustime.mta.info/api/siri/vehicle-monitoring.json"
siri_sm_url = 'https://bustime.mta.info/api/siri/stop-monitoring.json'

ntas = gpd.read_file("shapefiles/nynta2020_24d")

with open('static_data/location_dict.pickle', 'rb') as handle:
    location_dict = pickle.load(handle)

with open('static_data/NTA_dict.pickle', 'rb') as handle:
    NTA_dict = pickle.load(handle)

with open('static_data/stops.pickle', 'rb') as handle:
    list_of_stops = pickle.load(handle)

def get_stop_data(stop):
    params = {
    "key": BUS_TIME_KEY,         
    "version": "2",               
    "MonitoringRef": stop,    
    "VehicleMonitoringDetailLevel": "minimum", 
    }
    response = requests.get(siri_sm_url, params=params)
    data = response.json()
    if 'MonitoredStopVisit' in data['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]:
        df =  pd.json_normalize(response.json()['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit'])
    else:
        df = pd.DataFrame()  
    return df

def get_gap(stop):
    df = get_stop_data(stop)
    
    if df.empty:
        return pd.DataFrame()
    
    if 'MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime' not in df.columns:
        return pd.DataFrame()
    
    df.dropna(subset=['MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime'], inplace=True)
    
    if df.empty:
        return pd.DataFrame()
    df['gap'] =  pd.to_datetime(df['MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime']) - pd.to_datetime(df['MonitoredVehicleJourney.MonitoredCall.AimedArrivalTime'])
    df['gap'] = df['gap'].dt.total_seconds() / 60
    df['absolute_gap'] = df['gap'].abs()
    mean_gap = df['absolute_gap'].mean()
    stop_gap_df = pd.DataFrame({'stop': [stop], 'mean_gap': [mean_gap]})
    return stop_gap_df

def gap_for_stops(stop_list,size):
    df = pd.DataFrame()
    
    reduced_stop_list = random.sample(stop_list, size)
    for stop in tqdm(reduced_stop_list):
        try:
            stop_df = get_gap(stop)
            
            if not stop_df.empty:
                df = pd.concat([df, stop_df], ignore_index=True)

        except Exception as e:
            print(f"Error processing stop {stop}: {e}")
            continue

    return df

def agg_new_data(count:2000):
    df = gap_for_stops(list_of_stops,count)
    df['NTAName'] = df['stop'].map(location_dict)
    ag_df = df.groupby('NTAName')['mean_gap'].mean().reset_index(name='avg')
    ag_df['NTA2020'] = ag_df['NTAName'].map(NTA_dict)
    ag_df['date'] = datetime.datetime.now()

    return ag_df

def write_to_csv(data, file):
    with open(file, 'a') as f:
        writer_object = csv.writer(f)
        for row in data.iterrows():
            writer_object.writerow(row[1])
        f.close()

def wrtie_to_sheet(sheet_id,data,delete_old=False):
    sheet = client.open_by_key(sheet_id).sheet1
    data_length = len(data)
    data['date'] = data['date'].astype(str)
    data_to_append = data.values.tolist()
    sheet.append_rows(data_to_append, value_input_option="USER_ENTERED")
    print(f"{data_length} rows added to the sheet")
    if delete_old:
        sheet.delete_rows(2, data_length)

def main():
    parser = argparse.ArgumentParser(description='Get bus time data')
    parser.add_argument('count', help='Number of stops to get data for')
    parser.add_argument('--sheet', help='Write data to google sheet', action='store_true')
    
    args = parser.parse_args()
    count = int(args.count)
    data = agg_new_data(count)
    if args.sheet:
        wrtie_to_sheet(sheet_id,data,delete_old=True)
    else:
        write_to_csv(data, 'static_data/rolling_avg.csv')

if __name__ == "__main__":
    main()