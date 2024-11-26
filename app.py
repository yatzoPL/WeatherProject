from flask import Flask, jsonify
from flask_cors import CORS
import requests
import json
from typing import Dict, Optional
from time import time
from openai import OpenAI
from dotenv import load_dotenv
from prompts import (
    WEATHER_DESCRIPTION_PROMPT,
    FORECAST_DESCRIPTION_PROMPT,
    DAILY_DESCRIPTION_PROMPT
)

load_dotenv()
client = OpenAI()

app = Flask(__name__)
CORS(app)

class WeatherAPI:
   def __init__(self):
       self.base_url = "https://api.open-meteo.com/v1/forecast"
       self.geocoding_url = "https://nominatim.openstreetmap.org/reverse"
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

   def _generate_weather_description(self, weather_data: Dict) -> str:
       try:
           current = weather_data["current_weather"]
           prompt = WEATHER_DESCRIPTION_PROMPT.format(
               temperature=current['temperature'],
               temperature_unit=current['temperature_unit'],
               wind_speed=current['wind_speed'],
               wind_speed_unit=current['wind_speed_unit'],
               humidity=current['humidity'],
               humidity_unit=current['humidity_unit'],
               clouds=current['clouds'],
               clouds_unit=current['clouds_unit']
           )
           response = client.chat.completions.create(
               model="gpt-3.5-turbo",
               messages=[{"role": "user", "content": prompt}],
               max_tokens=200,
               temperature=0.7
           )
           return response.choices[0].message.content.strip()
       except Exception as e:
           print(f"Error generating description: {e}")
           return "Weather description unavailable"

   def _generate_forecast_description(self, forecast_data: Dict) -> str:
       try:
           prompt = FORECAST_DESCRIPTION_PROMPT.format(
               temp_min=min(d['temperature_min'] for d in forecast_data['forecast']),
               temp_max=max(d['temperature_max'] for d in forecast_data['forecast']),
               precip_min=min(d['precipitation'] for d in forecast_data['forecast']),
               precip_max=max(d['precipitation'] for d in forecast_data['forecast']),
               # Add missing variables
               wind_min=min(d['wind_speed'] for d in forecast_data['forecast']),
               wind_max=max(d['wind_speed'] for d in forecast_data['forecast']),
               humidity_min=min(d['humidity'] for d in forecast_data['forecast']),
               humidity_max=max(d['humidity'] for d in forecast_data['forecast']),
               cloud_min=min(d['clouds'] for d in forecast_data['forecast']),
               cloud_max=max(d['clouds'] for d in forecast_data['forecast']),
               daylight_min=min(d['daylight_duration'] for d in forecast_data['forecast']),
               daylight_max=max(d['daylight_duration'] for d in forecast_data['forecast'])
           )
           response = client.chat.completions.create(
               model="gpt-3.5-turbo",
               messages=[{"role": "user", "content": prompt}],
               max_tokens=400,
               temperature=0.7
           )
           return response.choices[0].message.content.strip()
       except Exception as e:
           print(f"Error generating forecast description: {e}")
           return "Nie udało się wygenerować podsumowania prognozy."

   def _generate_daily_description(self, day_data: Dict) -> str:
       try:
           prompt = DAILY_DESCRIPTION_PROMPT.format(
               temp_max=day_data['temperature_max'],
               temp_min=day_data['temperature_min'],
               precipitation=day_data['precipitation'],
               wind_speed=day_data['wind_speed'],
               humidity=day_data['humidity'],
               clouds=day_data['clouds']
           )
           response = client.chat.completions.create(
               model="gpt-3.5-turbo",
               messages=[{"role": "user", "content": prompt}],
               max_tokens=150,
               temperature=0.7
           )
           return response.choices[0].message.content.strip()
       except Exception as e:
           print(f"Error generating daily description: {e}")
           return "Description unavailable"

   def get_location_name(self, latitude: float, longitude: float) -> str:
       try:
           params = {
               "lat": latitude,
               "lon": longitude,
               "format": "json"
           }
           headers = {
               "User-Agent": "WeatherAPIExercise/1.0"
           }
           
           response = requests.get(
               self.geocoding_url,
               params=params,
               headers=headers,
               timeout=5
           )
           response.raise_for_status()
           location_data = response.json()
           
           # Extract city name or address components
           address = location_data.get("address", {})
           city = (
               address.get("city") or 
               address.get("town") or 
               address.get("village") or 
               address.get("suburb") or 
               "Unknown location"
           )
           return city
           
       except Exception as e:
           print(f"Error getting location name: {e}")
           return "Unknown location"

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
                   "longitude": longitude,
                   "city": self.get_location_name(latitude, longitude)
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

           processed_data["description"] = self._generate_weather_description(processed_data)

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
               "daily": [
                   "temperature_2m_max",
                   "temperature_2m_min",
                   "precipitation_sum",
                   "daylight_duration",
                   "wind_speed_10m_max",
                   "relative_humidity_2m_max",
                   "cloud_cover_max"
               ],
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
                   "wind_speed_unit": weather_forecast["daily_units"]["wind_speed_10m_max"],
                   "humidity_unit": weather_forecast["daily_units"]["relative_humidity_2m_max"],
                   "clouds_unit": weather_forecast["daily_units"]["cloud_cover_max"]
               },
               "forecast": [
                   {
                       "date": weather_forecast["daily"]["time"][i],
                       "temperature_max": weather_forecast["daily"]["temperature_2m_max"][i],
                       "temperature_min": weather_forecast["daily"]["temperature_2m_min"][i],
                       "precipitation": weather_forecast["daily"]["precipitation_sum"][i],
                       "daylight_duration": weather_forecast["daily"]["daylight_duration"][i],
                       "wind_speed": weather_forecast["daily"]["wind_speed_10m_max"][i],
                       "humidity": weather_forecast["daily"]["relative_humidity_2m_max"][i],
                       "clouds": weather_forecast["daily"]["cloud_cover_max"][i]
                   }
                   for i in range(1, min(len(weather_forecast["daily"]["time"]), days + 1))
               ]
           }

           # Generate individual descriptions for each day
           for day in processed_data["forecast"]:
               day["description"] = self._generate_daily_description(day)

           # Add the overall forecast summary
           processed_data["summary"] = self._generate_forecast_description(processed_data)

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