from datetime import datetime


def time2filename(time):
    parsed_time = datetime.strptime(time, "%Y-%m-%dT%H:%M")
    return parsed_time.strftime("%Y-%m-%dT%H%M.json")
