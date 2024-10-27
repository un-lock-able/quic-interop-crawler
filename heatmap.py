from time2filename import time2filename
import matplotlib.pyplot as plt
import json
import argparse
import logging
import os.path
from collections import defaultdict
import numpy as np


def read_from_manifest(dir):
    manifest_filename = os.path.join(dir, "manifest.json")
    if os.path.exists(manifest_filename):
        with open(manifest_filename) as fl:
            stored = json.load(fl)
    else:
        stored = list()
    return stored


def get_argparser():
    parser = argparse.ArgumentParser(description="Crawl the quic interop data")
    parser.add_argument(
        "-c", "--config", type=str, required=True, help="Path to config file"
    )
    parser.add_argument("--debug", action="store_true")
    return parser


def draw_heatmap(data):
    quic_impls = sorted(list(data.keys()))
    logging.debug(f"QUIC impls: {quic_impls}")
    size = (len(quic_impls), len(quic_impls))
    avg = np.zeros(size)
    var = np.zeros(size)

    for server, server_data in data.items():
        for client, tests in server_data.items():
            if tests:
                logging.debug(
                    f"server {server} client {client} test: {tests}, avg: {np.average(tests)}, std: {np.std(tests)}"
                )
                avg[quic_impls.index(server)][quic_impls.index(client)] = np.average(
                    tests
                )
                var[quic_impls.index(server)][quic_impls.index(client)] = np.std(tests)
            else:
                logging.debug(f"server {server} client {client} test empty")

    # in heatmap, the first dimension is on y, the second dimension is on x.
    # we want client to be lay on y.
    avg = avg.transpose()
    var = var.transpose()

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    axes[0].set_title("Average")
    heatmap1 = axes[0].imshow(avg, cmap="viridis", aspect="auto", vmin=1)

    axes[0].set_xticks(np.arange(len(quic_impls)), labels=quic_impls)
    axes[0].set_yticks(np.arange(len(quic_impls)), labels=quic_impls)
    axes[0].tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    plt.setp(
        axes[0].get_xticklabels(), rotation=-30, ha="right", rotation_mode="anchor"
    )

    axes[0].set_xlabel("Server")
    axes[0].set_ylabel("Client")
    axes[0].xaxis.set_label_position("top")

    axes[0].spines[:].set_visible(False)

    axes[0].set_xticks(np.arange(len(quic_impls) + 1) - 0.5, minor=True)
    axes[0].set_yticks(np.arange(len(quic_impls) + 1) - 0.5, minor=True)
    axes[0].grid(which="minor", color="w", linestyle="-", linewidth=2)
    axes[0].tick_params(which="minor", bottom=False, left=False)
    cbar1 = plt.colorbar(heatmap1, ax=axes[0])
    cbar1.cmap.set_under("white")

    axes[1].set_title("Variance")
    heatmap2 = axes[1].imshow(var, cmap="viridis", aspect="auto", norm="log")
    axes[1].set_xticks(np.arange(len(quic_impls)), labels=quic_impls)
    axes[1].set_yticks(np.arange(len(quic_impls)), labels=quic_impls)
    axes[1].tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)
    plt.setp(
        axes[1].get_xticklabels(), rotation=-30, ha="right", rotation_mode="anchor"
    )

    axes[1].set_xlabel("Server")
    axes[1].set_ylabel("Client")
    axes[1].xaxis.set_label_position("top")

    axes[1].spines[:].set_visible(False)

    axes[1].set_xticks(np.arange(len(quic_impls) + 1) - 0.5, minor=True)
    axes[1].set_yticks(np.arange(len(quic_impls) + 1) - 0.5, minor=True)
    axes[1].grid(which="minor", color="w", linestyle="-", linewidth=2)
    axes[1].tick_params(which="minor", bottom=False, left=False)
    cbar2 = plt.colorbar(heatmap2, ax=axes[1])

    fig.tight_layout()

    return fig


def draw_figure(data_dir, figure_dir, time):
    data_file_name = os.path.join(data_dir, time2filename(time))
    if not os.path.exists(data_file_name):
        logging.error(f"File {data_file_name} does not exist")
        return False

    with open(data_file_name) as fl:
        data = json.load(fl)

    goodput_fig = draw_heatmap(data["goodput"])
    goodput_fig.suptitle(f"{time} Goodput")
    # plt.show()
    crosstraffic_fig = draw_heatmap(data["crosstraffic"])
    crosstraffic_fig.suptitle(f"{time} Crosstraffic")
    # plt.show()

    goodput_fig.savefig(
        os.path.join(figure_dir, "goodput", f"{time2filename(time)}.png")
    )
    crosstraffic_fig.savefig(
        os.path.join(figure_dir, "crosstraffic", f"{time2filename(time)}.png")
    )

    plt.close(goodput_fig)
    plt.close(crosstraffic_fig)
    return True


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

    os.makedirs(config["data_dir"], exist_ok=True)
    # os.makedirs(config["figure_dir"], exist_ok=True)
    os.makedirs(os.path.join(config["figure_dir"], "goodput"), exist_ok=True)
    os.makedirs(os.path.join(config["figure_dir"], "crosstraffic"), exist_ok=True)

    stored_time = read_from_manifest(config["data_dir"])
    figured_time = read_from_manifest(config["figure_dir"])

    for time in stored_time:
        if time not in figured_time:
            logging.info(f"Draw for {time}")
            if draw_figure(config["data_dir"], config["figure_dir"], time):
                figured_time.append(time)
            with open(os.path.join(config["figure_dir"], "manifest.json"), "w") as fl:
                json.dump(figured_time, fl)


if __name__ == "__main__":
    main()
