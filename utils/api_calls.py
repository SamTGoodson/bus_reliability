import pandas as pd
from dotenv import load_dotenv
import os
import requests

load_dotenv() 
BUS_TIME_KEY = os.getenv("BUS_TIME_KEY")

oba_url = "https://bustime.mta.info/api/where/stops-for-location.json"
oba_meta_url = "https://bustime.mta.info/api/where/routes-for-agency/MTA%20NYCT.xml"
siri_vm_url = "https://bustime.mta.info/api/siri/vehicle-monitoring.json"
siri_sm_url = 'https://bustime.mta.info/api/siri/stop-monitoring.json'



def get_bus_data(route):
    params = {
        "key": BUS_TIME_KEY,
        "version": "2",
        "LineRef": route,
        "VehicleMonitoringDetailLevel": "minimum",
    }
    response = requests.get(siri_vm_url, params=params)

    data = response.json()
    if 'VehicleActivity' in data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]:
        df = pd.json_normalize(data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'][0]['VehicleActivity'])
    else:
        df = pd.DataFrame()  

    return df

def find_gap(route):
    df = get_bus_data(route)
    
    if df.empty:
        return pd.DataFrame()
    
    df.dropna(subset=['MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime'], inplace=True)
    df['gap'] = pd.to_datetime(df['MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime']) - pd.to_datetime(df['MonitoredVehicleJourney.MonitoredCall.AimedArrivalTime'])
    df['gap'] = df['gap'].dt.total_seconds() / 60
    mean_gap = df['gap'].mean()
    
    route_df = pd.DataFrame({'route': [route], 'mean_gap': [mean_gap]})
    return route_df

def gap_for_routes(route_list):
    df = pd.DataFrame()
    for route in route_list:
        route_df = find_gap(route)
        
        # Skip adding to the main DataFrame if the route has no data
        if not route_df.empty:
            df = pd.concat([df, route_df], ignore_index=True)
    return df

def get_stop_data(stop):
    params = {
    "key": BUS_TIME_KEY,         
    "version": "2",               
    "MonitoringRef": stop,    
    "VehicleMonitoringDetailLevel": "minimum", 
    }
    response = requests.get(siri_sm_url, params=params)
    response.json()
    response_df = pd.json_normalize(response.json()['Siri']['ServiceDelivery']['StopMonitoringDelivery'][0]['MonitoredStopVisit'])
    df = response_df[['RecordedAtTime',
             'MonitoredVehicleJourney.MonitoredCall.AimedArrivalTime',
       'MonitoredVehicleJourney.MonitoredCall.ExpectedArrivalTime',
    ]]
    df.columns = ['RecordedTime','AimedArrivalTime','ExpectedArrivalTime']
    return df

def get_gap(stop):
    df = get_stop_data(stop)
    df['gap'] = pd.to_datetime(df['ExpectedArrivalTime']) - pd.to_datetime(df['AimedArrivalTime'])
    df['gap'] = df['gap'].dt.total_seconds() / 60
    df['absolute_gap'] = df['gap'].abs()
    mean_gap = df['absolute_gap'].mean()
    stop_gap_df = pd.DataFrame({'stop': [stop], 'mean_gap': [mean_gap]})
    return stop_gap_df