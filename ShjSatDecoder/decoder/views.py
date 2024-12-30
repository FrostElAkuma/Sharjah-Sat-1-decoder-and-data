import json
import re
import django
from django.shortcuts import render
from django.http import HttpResponse
import datetime
from django.utils import timezone
import pytz
import requests
from urllib.parse import urljoin
from .models import ObsHex, ObsStatus
from django.utils.dateparse import parse_datetime
import time
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.db.models import Avg, Count
from django.db.models.functions import TruncDay





# decoder/views.py

def fetch_observation_ids(api_url, norad_id, start_date, end_date):
    formatted_start_date = start_date.strftime('%Y-%m-%d')
    formatted_end_date = end_date.strftime('%Y-%m-%d')
    url = f"{api_url}?id=&status=good&ground_station=&start={formatted_start_date}&end={formatted_end_date}&satellite__norad_cat_id={norad_id}&transmitter_uuid=&transmitter_mode=&transmitter_type=&waterfall_status=&vetted_status=&vetted_user=&observer=&start__lt=&observation_id="
    #print(url)
    try:
        response = requests.get(url, headers = {'User-agent': 'your bot 0.1'})
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        print("API response (IDs):", data)  # Debug: print the entire response
        return [obs['id'] for obs in data]
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching observation IDs: {e}")
        return []

def fetch_observation_data(api_url, observation_id):
    try:
        observation_url = urljoin(api_url, f"{observation_id}/")
        print(observation_url)
        response = requests.get(observation_url, headers = {'User-agent': 'your bot 0.1'})
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching observation data: {e}")
        return None

def download_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.content
        print("Data from link:")
        print(data)
        print(type(data))
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while downloading ASCII data: {e}")
        return None

def decode_data_to_hex(data):
    # Convert the decoded data to hex
    hex_data = data.hex().upper()
    print("Data after converting to Hex:")
    print(hex_data)
    # Format the hex data with spaces between each byte
    formatted_hex_data = ' '.join([hex_data[i:i+2] for i in range(0, len(hex_data), 2)])
    return formatted_hex_data

def fetch_and_decode(request):
    if request.method == 'POST':
        api_url = "https://network.satnogs.org/api/observations/"
        norad_id = 55104
        #Getting data starting from the last date in the DB to the current date
        last_obs = ObsHex.objects.order_by('-Obs_date').first()
        if last_obs:
            start_date = last_obs.Obs_date 
            #we can add the below line of code if we want to start from the next day, but I will start from the last observed date just in case
            #+ datetime.timedelta(days=1)
        else:
            start_date = datetime.datetime(2024, 7, 20)

        end_date = timezone.now()

        delay_seconds = 5  # Adjust this value based on the API's rate limit
        current_date = start_date
        results = []

        while current_date <= end_date:
            next_date = current_date + datetime.timedelta(days=1)
            observation_ids = fetch_observation_ids(api_url, norad_id, current_date, next_date)
            current_date += datetime.timedelta(days=1)
            if observation_ids:
                for obs_id in observation_ids:
                    time.sleep(delay_seconds)
                    observation = fetch_observation_data(api_url, obs_id)
                    if observation and "demoddata" in observation and len(observation["demoddata"]) > 0:
                        ascii_file_url = observation["demoddata"][0]["payload_demod"]
                        ascii_data = download_data(ascii_file_url)
                        if ascii_data:
                            hex_data = decode_data_to_hex(ascii_data)
                            expected_start = "82 6C 64 AA 9E A6 E0 82 6C 60 AA 9E A6 61 03 F0 45 53 45 52 50 F6 00 00 00 00"
                            expected_end = "00"
                            hex_words = hex_data.split()
                            
                            if len(hex_words) == 272 and hex_data.startswith(expected_start) and hex_data.endswith(expected_end):
                                results.append({
                                    'observation_id': obs_id,
                                    'hex_data': hex_data,
                                    'download_link': ascii_file_url
                                })
                                # Check if the observation already exists
                                if ObsHex.objects.filter(Obs_ID=obs_id).exists():
                                    print(f"Observation ID {obs_id} already exists in the database.")
                                    continue

                                # Save hex data to the database
                                observation_date = parse_datetime(observation["start"])
                                obs_hex = ObsHex(Obs_ID=obs_id, Hex_Data=hex_data, Obs_date=observation_date)
                                obs_hex.save()

                                # Decode hex data and save to obs_status table
                                decoded_values = hex_to_decimal(hex_data)
                                if decoded_values:
                                    decoded_values.pop(1)
                                    sensor_status = decoded_values[0]
                                    reset_count = int(decoded_values[1].split(": ")[1])
                                    last_reset_cause = int(decoded_values[2].split(": ")[1])

                                    obs_status = ObsStatus(
                                        Obs_ID=obs_hex,
                                        sensor_status=sensor_status,
                                        reset_count=reset_count,
                                        last_reset_cause=last_reset_cause
                                    )
                                    obs_status.save()
                                
                            else:
                                error_message = f"Hex data for observation_id {obs_id} does not meet the required criteria: "
                                if len(hex_words) != 272:
                                    error_message += "Incorrect number of words. "
                                if not hex_data.startswith(expected_start):
                                    error_message += "Does not start with the expected sequence. "
                                if not hex_data.endswith(expected_end):
                                    error_message += "Does not end with the expected sequence."
                                results.append({
                                    'observation_id': obs_id,
                                    'error': error_message
                                })
                        else:
                            results.append({'observation_id': obs_id, 'error': 'Failed to download data'})
                        # Adding delay between requests to avoid hitting the API rate limit
                        time.sleep(delay_seconds)
            else:
                results.append({'error': f'No observations found between {current_date} and {next_date}'})
                time.sleep(delay_seconds)
            
        return render(request, 'fetch_decode_results.html', {'results': results})

    return render(request, 'decoder/decoder.html')



# Create your views here.
def hex_to_decimal(hex_str):
    try:
        hex_values = hex_str.split()
        decimal_values = [int(h, 16) for h in hex_values]
        little_endian_values = []
        status_list = []  # To store the 13-bit status strings

        idx = 0
        while idx < len(decimal_values):
            if idx == 26:  # Word number 27 and 28 combined (13-bit binary representation)
                combined_value = ((decimal_values[idx + 1] << 8) | decimal_values[idx]) & 0x1FFF  # Mask to keep only 13 bits
                bin_value = bin(combined_value)[2:].zfill(13)  # Convert to binary and zero-fill to 13 bits
                little_endian_values.append(bin_value)
                # Create status labels for the 13 bits
                status_labels = [
                    "Operation Mode", "Antenna Status", "Beacon", "RTC", "IF Board",
                    "CAM 5mp", "CAM 2mp", "iXRD", "S-Band Transmitter", "UHV/VHF Modem",
                    "ADCS", "EPS", "Battery"
                ]
                
                # Generate status strings
                for i in range(12, -1, -1):  # Iterate over the 13 bits
                    bit_status = (combined_value >> i) & 1
                    status_list.append(f"{status_labels[12 - i]}: {'ok' if bit_status == 1 else 'error'}")

                little_endian_values.append(status_list)
                idx += 2
            elif idx == 28:  # Word number 29 and 30 combined (u2)
                u2_value = (decimal_values[idx + 1] << 8) | decimal_values[idx]
                little_endian_values.append(f"Reset count: {u2_value}")
                idx += 2
            elif idx == 30:  # Word number 31 (u1)
                little_endian_values.append(f"Last reset cause: {decimal_values[idx]}")
                idx += 1
            else:
                # Convert to little-endian formats
                #Length Calculation: Adding 7 before integer division by 8 ensures that we round up to the next whole number if there are any remaining bits.
                #Example: If decimal_values[idx] is 300, bit_length() is 9, and (9 + 7) // 8 is 2, meaning we need 2 bytes.
                #I commented the below lines for now because I don't need the other data I will only work with sensors status, reset count, and reason.
                #Uncomment the below 2 lines when needed
                #num_bytes = decimal_values[idx].to_bytes((decimal_values[idx].bit_length() + 7) // 8, byteorder='little')
                #little_endian_values.append(int.from_bytes(num_bytes, byteorder='big'))
                idx += 1

        return little_endian_values
    except ValueError:
        return None

def decoder_view(request):
    if request.method == 'POST':
        hex_input = request.POST.get('hex_input', '')
        print(hex_input)
        
        # Validate input format
        if not re.match(r'^([0-9a-fA-F]{2}\s){271}[0-9a-fA-F]{2}$', hex_input):
            error_message = "Input must be exactly 272 hexadecimal words separated by spaces."
            return render(request, 'decoder.html', {'error_message': error_message})
        
        # Validate that the hex data starts and ends with the correct values
        expected_start = "82 6C 64 AA 9E A6 E0 82 6C 60 AA 9E A6 61 03 F0 45 53 45 52 50 F6 00 00 00 00"
        expected_end = "00"
        hex_words = hex_input.split()
                        
        if len(hex_words) == 272 and hex_input.startswith(expected_start) and hex_input.endswith(expected_end):
            decoded_values = hex_to_decimal(hex_input)
            if decoded_values is None:
                error_message = "Invalid hexadecimal format."
                return render(request, 'decoder.html', {'error_message': error_message})
            
            # Separate status list from other decoded values
            status_list = decoded_values.pop(1)
            #to remove the binary number. Only needed when saving to DB
            decoded_values.pop(0)
            
            return render(request, 'decoder.html', {'decoded_values': decoded_values, 'status_list': status_list, 'hex_input': hex_input})
        else:
            error_message = f"Hex data for observation_id does not meet the required criteria: "
            if len(hex_words) != 272:
                error_message += f"Incorrect number of words. {len(hex_words)}"
            if not hex_input.startswith(expected_start):
                error_message += "Does not start with the expected sequence. "
            if not hex_input.endswith(expected_end):
                 error_message += "Does not end with the expected sequence."
                          
            return render(request, 'decoder.html', {'error_message': error_message})

    return render(request, 'decoder.html')
"""
def visualize_data(request):
    # Retrieve data from the database
    obs_status_entries = ObsStatus.objects.select_related('Obs_ID').order_by('Obs_ID_id').all()
    count = ObsStatus.objects.count() 
    print("count of observations is")
    print(count)
    # Prepare data for the charts
    reset_counts = [entry.reset_count for entry in obs_status_entries]
    last_reset_causes = [entry.last_reset_cause for entry in obs_status_entries]
    reset_dates = [entry.Obs_ID.Obs_date.strftime('%Y-%m-%d') for entry in obs_status_entries]  # Format dates as strings

    
    # Convert sensor statuses to a pie chart format (example)
    sensor_status_summary = {}
    for entry in obs_status_entries:
        status_labels = entry.sensor_status.split(', ')  # Assuming statuses are comma-separated
        for label in status_labels:
            if label not in sensor_status_summary:
                sensor_status_summary[label] = 0
            sensor_status_summary[label] += 1

    context = {
        'reset_counts': json.dumps(reset_counts, cls=DjangoJSONEncoder),
        'reset_dates': json.dumps(reset_dates, cls=DjangoJSONEncoder),
        'last_reset_causes': json.dumps(last_reset_causes, cls=DjangoJSONEncoder),
        'sensor_status_summary_labels': json.dumps(list(sensor_status_summary.keys()), cls=DjangoJSONEncoder),
        'sensor_status_summary_values': json.dumps(list(sensor_status_summary.values()), cls=DjangoJSONEncoder),
    }
    
    return render(request, 'visualize_data.html', context)
    """
def visualize_data(request):
    # Get sorting parameters from the request
    sort_field = request.GET.get('sort', 'Obs_ID_id')  # Default to sorting by Obs_ID_id
    sort_direction = request.GET.get('direction', 'asc')

    if sort_direction == 'desc':
        sort_field = f"-{sort_field}"

    # Retrieve the date filter parameters from the request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Filter based on date range if provided
    obs_status_entries = ObsStatus.objects.select_related('Obs_ID')

    if start_date:
        obs_status_entries = obs_status_entries.filter(Obs_ID__Obs_date__gte=start_date)
    if end_date:
        obs_status_entries = obs_status_entries.filter(Obs_ID__Obs_date__lte=end_date)

    # Apply sorting to the filtered data
    obs_status_entries = obs_status_entries.order_by(sort_field)

    # Prepare data for the charts
    reset_counts = [entry.reset_count for entry in obs_status_entries]
    last_reset_causes = [entry.last_reset_cause for entry in obs_status_entries]
    reset_dates = [entry.Obs_ID.Obs_date.strftime('%Y-%m-%d') for entry in obs_status_entries]

    # Process sensor statuses for summary
    sensor_status_summary = {}
    for entry in obs_status_entries:
        status_labels = entry.sensor_status.split(', ')
        for label in status_labels:
            sensor_status_summary[label] = sensor_status_summary.get(label, 0) + 1

    context = {
        'reset_counts': json.dumps(reset_counts, cls=DjangoJSONEncoder),
        'reset_dates': json.dumps(reset_dates, cls=DjangoJSONEncoder),
        'last_reset_causes': json.dumps(last_reset_causes, cls=DjangoJSONEncoder),
        'sensor_status_summary_labels': json.dumps(list(sensor_status_summary.keys()), cls=DjangoJSONEncoder),
        'sensor_status_summary_values': json.dumps(list(sensor_status_summary.values()), cls=DjangoJSONEncoder),
    }

    return render(request, 'visualize_data.html', context)

def trend_analysis(request):
    # Retrieve the date filter parameters from the request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Filter based on date range if provided
    trends = ObsStatus.objects.annotate(date=TruncDay('Obs_ID__Obs_date')).values('date').annotate(
        avg_reset_count=Avg('reset_count'),
        reset_count_count=Count('reset_count')
    ).order_by('date')

    if start_date:
        trends = trends.filter(date__gte=start_date)
    if end_date:
        trends = trends.filter(date__lte=end_date)

    # Pass the trends data to the template
    context = {
        'trends': trends,
    }
    return render(request, 'trend_analysis.html', context)



