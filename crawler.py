import json
import argparse
import requests
import os.path
import re
import logging
import concurrent.futures
from time2filename import time2filename
from itertools import product

REGEX_PATTERN = re.compile(r"Goodput: (.+) kbps")
# PROXY_CONFIG = {"http": "127.0.0.1:7890", "https": "127.0.0.1:7890"}
PROXY_CONFIG = {}


class GoodputNotFound(BaseException):
    def __init__(self, *args):
        super().__init__(self, *args)


class RequestFailed(BaseException):
    def __init__(self, *args):
        super().__init__(self, *args)


def get_argparser():
    parser = argparse.ArgumentParser(description="Crawl the quic interop data")
    parser.add_argument(
        "-c", "--config", type=str, required=True, help="Path to config file"
    )
    parser.add_argument("--debug", action="store_true")
    return parser


def get_available_times(base_url):
    response = requests.get(f"{base_url}/logs.json", proxies=PROXY_CONFIG)
    if response.status_code == 200:
        return json.loads(response.text)

    raise (RequestFailed)


def match_for_result(text):
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


def request_for_output(url):
    logging.debug(f"Request output.txt at {url}")
    if os.path.exists(url):
        # is a file path.
        with open(url) as fl:
            return match_for_result(fl.read())
    
    response = requests.get(url, proxies=PROXY_CONFIG)
    if response.status_code == 200:
        return match_for_result(response.text)

    raise RequestFailed


def get_goodput(base_url_with_time, client, server):
    # in the url, the format is server_client/goodput/num/output.txt
    goodput = list()
    for idx in range(1, 6):
        try:
            single_goodput = request_for_output(
                f"{base_url_with_time}/{server}_{client}/goodput/{idx}/output.txt"
            )
        except (RequestFailed, GoodputNotFound):
            # if this test failed, there should be no more tests
            logging.info(
                f"Client {client}, Server {server}, Goodput test faild at idx {idx}"
            )
            break

        logging.info(
            f"Client {client}, Server {server}, idx {idx}, goodput {single_goodput} kbps"
        )
        goodput.append(single_goodput)

    return goodput


def get_crosstraffic(base_url_with_time, client, server):
    crosstraffic = list()
    for idx in range(1, 6):
        try:
            single_crosstraffic = request_for_output(
                f"{base_url_with_time}/{server}_{client}/crosstraffic/{idx}/output.txt"
            )
        except (RequestFailed, GoodputNotFound):
            # if this test failed, there should be no more tests
            logging.info(
                f"Client {client}, Server {server}, Crosstraffic test faild at idx {idx}"
            )
            break

        logging.info(
            f"Client {client}, Server {server}, idx {idx}, crosstraffic {single_crosstraffic} kbps"
        )
        crosstraffic.append(single_crosstraffic)

    return crosstraffic


def get_new_data_single_server(base_url, time, server, quic_impls):
    goodput = dict()
    crosstraffic = dict()
    for client in quic_impls:
        logging.info(f"Client: {client}, Server: {server}")
        goodput[client] = get_goodput(f"{base_url}/{time}", client, server)
        crosstraffic[client] = get_crosstraffic(f"{base_url}/{time}", client, server)
    return (goodput, crosstraffic)


def get_new_data(base_url, time, quic_impls):
    goodput = dict()
    crosstraffic = dict()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(
                get_new_data_single_server, base_url, time, server, quic_impls
            ): server
            for server in quic_impls
        }

        for future in concurrent.futures.as_completed(futures):
            server_name = futures[future]
            goodput[server_name], crosstraffic[server_name] = future.result()

    return {"goodput": goodput, "crosstraffic": crosstraffic}


def web_main(config):
    # quic_impls are the names that appears in both client and server
    quic_impls = list(set(config["clients"]) & set(config["servers"]))
    logging.debug(f"QUIC impls with both client and server: {quic_impls}")

    ### THIS ONLY FOR TESTING
    # quic_impls = ["quiche", "lsquic"]

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
    # available_times = ["2024-10-27T08:32"]

    for time in available_times:
        if time not in stored_time:
            logging.info(f"Crawl for time {time}")
            new_data = get_new_data(config["base_url"], time, quic_impls)
            with open(os.path.join(data_file_dir, time2filename(time)), "w") as fl:
                json.dump(new_data, fl)
            stored_time.append(time)
            with open(manifest_file_name, "w") as fl:
                json.dump(stored_time, fl)


def local_main(config):
    for impl in config["impls"]:
        goodput = dict()
        cca_name = impl["cca"]
        quic_impl = impl["quic_impls"]
        for server in quic_impl:
            goodput[server] = dict()
            for client in quic_impl:
                goodput[server][client] = get_goodput(
                    f"{config["base_url"]}/{cca_name}", client, server
                )
        with open(os.path.join(config["data_dir"], f"{cca_name}.json"), "w") as fl:
            json.dump({"goodput": goodput}, fl)


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

    if config["local"]:
        local_main(config)
    else:
        web_main(config)


if __name__ == "__main__":
    main()
