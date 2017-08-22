"""An Amazon Alexa skill for retrieving wind data from a NOAA bouy."""
import statistics
import time

import numpy
import requests

from flask import Flask, render_template
from flask_ask import Ask, statement, question


app = Flask(__name__)
ask = Ask(app, '/wind-checker')

STATION_MAP = {
    'baltimore': '8574680',
    'scott key bridge': '8574728',
    'tolchester beach': '8573364',
    'kiptopeke': '8632200',
    'solomons island': '8577330 '
}


def get_wind_data(station):
    """
    Query a NOAA bouy to fetch wind data for the specified station.

    :rtype: ``dict``
    :return: Wind data for the most recent three hours. Each data point will
             have the following fields:
             ``d`` - numerical direction (e.g., 290.56)
             ``dr`` - text direction, up to half-winds (e.g., WNW)
             ``f`` - ?
             ``g`` - gust speed, in knots
             ``s`` - wind speed, in knots
             ``t`` - time stamp (e.g., 2017-08-19 14:12)
    """
    date = time.strftime("%Y%m%d")
    url = "https://tidesandcurrents.noaa.gov/api/datagetter"
    params = {'product': 'wind',
              'begin_date': int(date)-1,
              'end_date': date,
              'station': STATION_MAP.get(station.lower()),
              'time_zone': 'LST_LDT',
              'units': 'english',
              'format': 'json'}
    r = requests.get(url, params=params)
    return r.json().get('data')[-30:]  # Most recent 3 hrs


def process_wind_data(wind_data):
    """
    Summarize most recent values from provided wind data.

    :type wind_data: ``dict``
    :param wind_data: Wind data to process, see ``get_wind_data`` for expected
                      format.

    :rtype: ``dict``
    :return: A wind data summary with the following keys:
             ``max_speed`` - Max wind speed, in knots
             ``min_speed`` - Min wind speed, in knots
             ``average_speed`` - Average wind speed, in knots
             ``max_gust`` - Max gust speed, in knots
             ``min_gust`` - Min gust speed, in knots
             ``average_gust`` - Average gust speed, in knots
             ``trend`` - Wind speed trend: increasing, steady, or decreasing
             ``average_direction`` - Average wind direction
             ``latest_timestamp`` - Timestamp from the most recent reading
             ``latest_speed`` - Most recent wind speed reading, in knots
             ``latest_gust`` - Most recent gust speed reading, in knots
             ``latest_direction`` - Most recent wind speed direction
    """
    directions, gusts, speeds = [], [], []
    for w in wind_data:
        directions.append(float(w['d']))
        gusts.append(float(w['g']))
        speeds.append(float(w['s']))

    # Calculate the trend
    t = []
    t.append(range(len(speeds)))
    t.append([1 for ele in range(len(speeds))])
    s = numpy.matrix(speeds).T
    t = numpy.matrix(t).T
    betas = (t.T*t).I*t.T*s

    latest = wind_data.pop()
    return {'max_speed': max(speeds),
            'min_speed': min(speeds),
            'average_speed': statistics.mean(speeds),
            'max_gust': max(gusts),
            'min_gusts': min(gusts),
            'average_gusts': statistics.mean(gusts),
            'average_directions': statistics.mean(directions),
            'speed_trend': betas,
            'latest_timestamp': latest['t'],
            'latest_speed': latest['s'],
            'latest_gust': latest['g'],
            'latest_direction': latest['dr']}


def _humanize(direction):
    """Convert wind direction representaion such as 'N' into 'north'."""
    if direction == 'N':
        return 'north'
    elif direction == 'NNE':
        return 'north-northeast'
    elif direction == 'NE':
        return 'northeast'
    elif direction == 'E':
        return 'east'
    elif direction == 'SE':
        return 'southeast'
    elif direction == 'SSE':
        return 'south-southeast'
    elif direction == 'S':
        return 'south'
    elif direction == 'SSW':
        return 'south-southwest'
    elif direction == 'SW':
        return 'southwest'
    elif direction == 'W':
        return 'west'
    elif direction == 'NW':
        return 'northwest'
    elif direction == 'NNW':
        return 'north-northwest'
    return direction


@ask.intent('AvailableStationsIntent')
def available_stations():
    """Return a list of stations available/registered with this skill."""
    stations = ', '.join(sorted(STATION_MAP.keys()))
    list_stations_text = render_template('list_stations', stations=stations)
    list_stations_reprompt_text = render_template('list_stations_reprompt')
    return question(list_stations_text).reprompt(list_stations_reprompt_text)


@ask.launch
def launch():
    """Start the skill with a welcome message."""
    welcome_text = render_template('welcome')
    help_text = render_template('help')
    return question(welcome_text).reprompt(help_text)


@ask.intent('StationIntent', mapping={'station': 'station'},
            default={'station': 'Baltimore'})
def run_skill(station):
    """Run the skill."""
    print("Got station %s" % station)
    if station.lower() not in STATION_MAP:
        no_match_text = render_template('no_match', station=station)
        return question(no_match_text)
    wind_data = process_wind_data(get_wind_data(station))
    location = station
    timestamp = wind_data['latest_timestamp'][-5:]
    direction = _humanize(wind_data['latest_direction'])
    speed = wind_data['latest_speed']
    gust = wind_data['latest_gust']
    ntrend = wind_data['speed_trend'].item(0)
    if -0.05 <= ntrend <= 0.05:
        trend = 'steady'
    elif ntrend < -0.05:
        trend = 'decreasing'
    else:
        trend = 'increasing'
    wind_msg = ("%s at %s shows wind blowing from %s at %s knots, "
                "gusting to %s, generally %s." % (location, timestamp,
                                                  direction, speed,
                                                  gust, trend))
    return statement(wind_msg)
    # return statement(wind_msg).simple_card(
    #     title=wind_msg,
    #     content=_get_card_content(wind_data))


@ask.intent('AMAZON.HelpIntent')
def help():
    help_text = render_template('help')
    list_stations_reprompt_text = render_template('list_stations_reprompt')
    return question(help_text).reprompt(list_stations_reprompt_text)


@ask.intent('AMAZON.StopIntent')
def stop():
    bye_text = render_template('bye')
    return statement(bye_text)


@ask.intent('AMAZON.CancelIntent')
def cancel():
    bye_text = render_template('bye')
    return statement(bye_text)


if __name__ == '__main__':
    app.run(debug=True)
    # pass
