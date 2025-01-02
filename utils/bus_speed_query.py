import pandas as pd
from dotenv import load_dotenv
import os
import requests
import tqdm
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from datetime import datetime

load_dotenv() 
BUS_TIME_KEY = os.getenv("BUS_TIME_KEY")
api_token = os.getenv('NYC_OPEN_DATA_TOKEN')

url = 'https://data.ny.gov/resource/58t6-89vi.json'

credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_path, scope)
client = gspread.authorize(creds)
sheet_id = '1IniME82yEoZmGNQRLJVAuBMicw5aj_tvE_wu3iBvHLk'
sheet = client.open_by_key(sheet_id).sheet1 

def set_df_date_time():
    col_c_values = sheet.col_values(2)
    last_row = len(col_c_values) 
    date = sheet.acell(f'C{last_row}').value
    return date

def get_df_largest_date(sheet):
    col_c_values = sheet.col_values(2)
    last_row = len(col_c_values) 
    date = sheet.acell(f'C{last_row}').value
    parsed_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    formatted_date = parsed_date.strftime('%Y-%m-%d')
    return formatted_date


def check_for_new_date():
    params = {
    '$$app_token': api_token,
    '$limit': 1,
    '$order': 'timestamp DESC'
    }
    response = requests.get(url, params=params)
    df = pd.DataFrame(response.json())
    date = df['timestamp'].max()
    parsed_date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%f')
    formatted_date = parsed_date.strftime('%Y-%m-%d')
    return formatted_date

def query_new_data(date):
    date = set_df_date_time()
    parsed_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    form_date = parsed_date.strftime('%Y-%m-%dT%H:%M:%S.000')
    
    params = {
    '$$app_token': api_token,
    '$limit': 100000,
    '$where': f"timestamp > '{form_date}' AND day_of_week = 'Wednesday' AND ((hour_of_day > 7 AND hour_of_day < 11) OR (hour_of_day > 16 AND hour_of_day < 20))"
    }   
    response = requests.get(url, params=params)
    df = pd.DataFrame(response.json())
    return df

def get_new_data():
    df_date = get_df_largest_date(sheet)
    new_data = check_for_new_date()
    if new_data > df_date:
        df = query_new_data(df_date)
        return df
    else:
        print('No new data available')

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
    new_data = get_new_data()
    if new_data is not None:
        wrtie_to_sheet(sheet_id,new_data,delete_old=True)
    else:
        print('No new data available')

if __name__ == '__main__':
    main()