from flask import Flask, jsonify
from flask_cors import CORS
import requests
import json
from typing import Dict, Optional
from time import time

app = Flask(__name__)
CORS(app)

class WeatherAPI:
   def __init__(self):
       self.base_url = "https://api.open-meteo.com/v1/forecast"
       self.cache_file = "weather_cache.json"
       self.cache_duration = 1800
       self.cache = self.load_cache()

   def load_cache(self):
       try:
           with open(self.cache_file, 'r') as f:
               return json.load(f)
       except FileNotFoundError:
           return {}

   def save_cache(self):
       with open(self.cache_file, 'w') as f:
           json.dump(self.cache, f)

   def get_weather(self, latitude: float, longitude: float) -> Optional[Dict]:
       cache_key = f"current_{latitude}_{longitude}"

       if cache_key in self.cache:
           cached_data = self.cache[cache_key]
           if time() - cached_data['timestamp'] < self.cache_duration:
               print("Pobieram dane z cache")
               return cached_data['data']

       try:
           params = {
               "latitude": latitude,
               "longitude": longitude,
               "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,surface_pressure,cloud_cover",
               "timezone": "auto"
           }

           headers = {
               "Accept": "application/json",
               "User-Agent": "WeatherAPIExercise/1.0"
           }

           response = requests.get(
               self.base_url,
               params=params,
               headers=headers,
               timeout=5
           )

           response.raise_for_status()
           raw_data = response.json()

           processed_data = {
               "location": {
                   "latitude": latitude,
                   "longitude": longitude
               },
               "current_weather": {
                   "temperature": raw_data["current"]["temperature_2m"],
                   "temperature_unit": raw_data["current_units"]["temperature_2m"],
                   "wind_speed": raw_data["current"]["wind_speed_10m"],
                   "wind_speed_unit": raw_data["current_units"]["wind_speed_10m"],
                   "humidity": raw_data["current"]["relative_humidity_2m"],
                   "humidity_unit": raw_data["current_units"]["relative_humidity_2m"],
                   "pressure": raw_data["current"]["surface_pressure"],
                   "pressure_unit": raw_data["current_units"]["surface_pressure"],
                   "clouds": raw_data["current"]["cloud_cover"],
                   "clouds_unit": raw_data["current_units"]["cloud_cover"]
               }
           }

           self.cache[cache_key] = {
               'timestamp': time(),
               'data': processed_data
           }
           self.save_cache()

           print("Pobieram dane z API i zapisuję je w cache")
           return processed_data

       except requests.exceptions.Timeout:
           print("Błąd: Przekroczono czas oczekiwania na odpowiedź")
           return None
       except requests.exceptions.RequestException as e:
           print(f"Błąd podczas wykonywania zapytania: {e}")
           return None
       except json.JSONDecodeError:
           print("Błąd: Otrzymano nieprawidłowy format JSON")
           return None
       except KeyError as e:
           print(f"Błąd: Brak oczekiwanego klucza w odpowiedzi: {e}")
           return None

   def get_forecast(self, latitude: float, longitude: float, days: int) -> Optional[Dict]:
       cache_key = f"forecast_{latitude}_{longitude}_{days}"

       if cache_key in self.cache:
           cached_data = self.cache[cache_key]
           if time() - cached_data['timestamp'] < self.cache_duration:
               print("Pobieram prognozę z cache")
               return cached_data['data']

       try:
           params = {
               "latitude": latitude,
               "longitude": longitude,
               "forecast_days": days,
               "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,daylight_duration",
               "timezone": "auto"
           }

           headers = {
               "Accept": "application/json",
               "User-Agent": "WeatherAPIExercise/1.0"
           }

           response = requests.get(
               self.base_url,
               params=params,
               headers=headers,
               timeout=5
           )

           response.raise_for_status()
           weather_forecast = response.json()

           processed_data = {
               "location": {
                   "latitude": latitude,
                   "longitude": longitude
               },
               "units": {
                   "temperature_max_unit": weather_forecast["daily_units"]["temperature_2m_max"],
                   "temperature_min_unit": weather_forecast["daily_units"]["temperature_2m_min"],
                   "precipitation_sum_unit": weather_forecast["daily_units"]["precipitation_sum"],
                   "daylight_duration_unit": weather_forecast["daily_units"]["daylight_duration"],
               },
               "forecast": [
                   {
                       "date": weather_forecast["daily"]["time"][i],
                       "temperature_max": weather_forecast["daily"]["temperature_2m_max"][i],
                       "temperature_min": weather_forecast["daily"]["temperature_2m_min"][i],
                       "precipitation": weather_forecast["daily"]["precipitation_sum"][i],
                       "daylight_duration": weather_forecast["daily"]["daylight_duration"][i],
                   }
                   for i in range(days)
               ]
           }

           self.cache[cache_key] = {
               'timestamp': time(),
               'data': processed_data
           }
           self.save_cache()

           print("Pobieram prognozę z API i zapisuję do cache")
           return processed_data

       except requests.exceptions.Timeout:
           print("Błąd: Przekroczono czas oczekiwania na odpowiedź")
           return None
       except requests.exceptions.RequestException as e:
           print(f"Błąd podczas wykonywania zapytania: {e}")
           return None
       except json.JSONDecodeError:
           print("Błąd: Otrzymano nieprawidłowy format JSON")
           return None
       except KeyError as e:
           print(f"Błąd: Brak oczekiwanego klucza w odpowiedzi: {e}")
           return None

# Inicjalizacja API
weather_api = WeatherAPI()

@app.route('/weather/<float:lat>/<float:lon>')
def get_weather(lat, lon):
   result = weather_api.get_weather(lat, lon)
   if result is None:
       return jsonify({"error": "Nie udało się pobrać danych"}), 500
   return jsonify(result)

@app.route('/forecast/<float:lat>/<float:lon>/<int:days>')
def get_forecast(lat, lon, days):
   result = weather_api.get_forecast(lat, lon, days)
   if result is None:
       return jsonify({"error": "Nie udało się pobrać prognozy"}), 500
   return jsonify(result)

if __name__ == '__main__':
   app.run(debug=True)