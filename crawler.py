import json
import argparse
import requests
import os.path
import itertools
import re
from collections import defaultdict
import logging
from datetime import datetime

REGEX_PATTERN = re.compile(r"Goodput: (.+) kbps")
PROXY_CONFIG = {"http": "127.0.0.1:7890", "https": "127.0.0.1:7890"}


class GoodputNotFound(BaseException):
    def __init__(self, *args):
        super().__init__(self, *args)


class RequestFailed(BaseException):
    def __init__(self, *args):
        super().__init__(self, *args)

def time2filename(time: str) -> str:
    parsed_time = datetime.strptime(time, "%Y-%m-%dT%H:%M")
    return parsed_time.strftime("%Y-%m-%dT%H%M.json")


def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl the quic interop data")
    parser.add_argument(
        "-c", "--config", type=str, required=True, help="Path to config file"
    )
    parser.add_argument("--debug", action="store_true")
    return parser


def get_available_times(base_url: str) -> list[str]:
    response = requests.get(f"{base_url}/logs.json", proxies=PROXY_CONFIG)
    if response.status_code == 200:
        return json.loads(response.text)

    raise (RequestFailed)


def match_for_result(text: str) -> int:
    lines = text.splitlines()
    last_line = lines[-1]
    logging.debug(f"Last line: {last_line}")

    matched = REGEX_PATTERN.findall(last_line)
    logging.debug(f"Matched: {matched}")
    if matched:
        try:
            return int(matched[0])
        except ValueError:
            raise GoodputNotFound
    else:
        raise GoodputNotFound


def request_for_output(url: str) -> str:
    logging.debug(f"Request output.txt at {url}")
    response = requests.get(url, proxies=PROXY_CONFIG)
    if response.status_code == 200:
        return match_for_result(response.text)

    raise RequestFailed


def get_goodput(base_url_with_time: str, client: str, server: str) -> list[int]:
    # in the url, the format is server_client/goodput/num/output.txt
    goodput = list()
    for idx in range(1, 6):
        try:
            single_goodput = request_for_output(
                f"{base_url_with_time}/{server}_{client}/goodput/{idx}/output.txt"
            )
        except (RequestFailed, GoodputNotFound):
            # if this test failed, there should be no more tests
            logging.info(f"Googput test faild at idx {idx}")
            break

        logging.info(f"idx {idx}, goodput {single_goodput} kbps")
        goodput.append(single_goodput)

    return goodput


def get_crosstraffic(base_url_with_time: str, client: str, server: str) -> list[int]:
    crosstraffic = list()
    for idx in range(1, 6):
        try:
            single_crosstraffic = request_for_output(
                f"{base_url_with_time}/{server}_{client}/crosstraffic/{idx}/output.txt"
            )
        except (RequestFailed, GoodputNotFound):
            # if this test failed, there should be no more tests
            logging.info(f"Crosstraffic test faild at idx {idx}")
            break

        logging.info(f"idx {idx}, crosstraffic {single_crosstraffic} kbps")
        crosstraffic.append(single_crosstraffic)

    return crosstraffic

def get_new_data(base_url: str, time: str, quic_impls: list[str]) -> dict:
    goodput = defaultdict(lambda: defaultdict(dict))
    crosstraffic = defaultdict(lambda: defaultdict(dict))
    for client, server in itertools.product(quic_impls, quic_impls):
        logging.info(f"Client: {client}, Server: {server}")
        goodput[server][client] = get_goodput(f"{base_url}/{time}", client, server)
        crosstraffic[server][client] = get_crosstraffic(
            f"{base_url}/{time}", client, server
        )

    return {"goodput": goodput, "crosstraffic": crosstraffic}


def main():
    parser = get_argparser()
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    config_file_name = args.config
    with open(config_file_name) as fl:
        config = json.load(fl)

    # quic_impls are the names that appears in both client and server
    quic_impls = list(set(config["clients"]) & set(config["servers"]))
    logging.debug(f"QUIC impls with both client and server: {quic_impls}")

    ### THIS ONLY FOR TESTING
    # quic_impls = ['quiche', 'lsquic']

    data_file_dir = config["data_dir"]

    manifest_file_name = os.path.join(data_file_dir, "manifest.json")
    if os.path.exists(manifest_file_name):
        with open(manifest_file_name) as fl:
            stored_time = json.load(fl)
    else:
        stored_time = list()

    try:
        available_times = get_available_times(config["base_url"])
    except RequestFailed:
        exit(0)

    ### THIS IS ONLY FOR TESING
    # available_times = ['2024-10-22T16:35']

    for time in available_times:
        if time not in stored_time:
            logging.info(f"Crawl for time {time}")
            new_data = get_new_data(config["base_url"], time, quic_impls)
            with open(os.path.join(data_file_dir, time2filename(time)), 'w') as fl:
                json.dump(new_data, fl)
            stored_time.append(time)
            with open(manifest_file_name, 'w') as fl:
                json.dump(stored_time, fl)


if __name__ == "__main__":
    main()