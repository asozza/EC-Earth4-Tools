#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is a command line tool to plot graphics

Authors: Alessandro Sozza (CNR-ISAC)
Date: Sept 2024
"""

import os
import time
import psutil
import logging
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

from osprey.graphics.timeseries import timeseries_yearshift

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Function to get memory usage in MB
def get_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / (1024 ** 2)  # Convert bytes to megabytes (MB)


def drawing(figname):

    # shift between EOF and REF experiments
    timeseries_yearshift(expname1='FE01', startyear1=1990, endyear1=2139, expname2='lfr0', startyear2=1990, endyear2=2400, shift_threshold=300, varlabel='thetao', reader='post', timeoff=0, color='red', linestyle='-', label='EOF-T')
    timeseries_yearshift(expname1='FE02', startyear1=1990, endyear1=2089, expname2='lfr0', startyear2=1990, endyear2=2400, shift_threshold=300, varlabel='thetao', reader='post', timeoff=0, color='blue', linestyle='-', label='EOF-TS')

    plt.legend(
        bbox_to_anchor=(0.98, 0.98),  # x, y coordinates for legend placement
        loc='upper right',         # Location of the legend relative to bbox_to_anchor
        borderaxespad=0           # Padding between the legend and the plot
    )
    plt.title('Year shift of global mean temperature')

    # Save the combined figure
    plt.savefig(figname)

    return None


if __name__ == "__main__":
    
    # Start timer
    start_time = time.time()

    figname='fig8.png'
    drawing(figname)

    # End timer
    end_time = time.time()

    # Calculate total execution time
    execution_time = end_time - start_time

    # Get memory usage
    memory_usage = get_memory_usage()

    # Log execution time and memory load
    logging.info(f"Total execution time: {execution_time:.2f} seconds")
    logging.info(f"Memory load at the end: {memory_usage:.2f} MB")
