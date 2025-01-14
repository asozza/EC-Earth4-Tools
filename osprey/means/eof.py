#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EOF module

Author: Alessandro Sozza (CNR-ISAC) 
Date: May 2024
"""

import os
import glob
import subprocess
import logging
import numpy as np
import xarray as xr
import cftime

from osprey.utils.folders import folders
from osprey.utils.time import get_leg, get_decimal_year, get_forecast_year
from osprey.utils.utils import remove_existing_file
from osprey.means.means import spacemean, timemean
from osprey.utils import catalogue
from osprey.utils.utils import remove_existing_filelist

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _forecast_xarray(foreyear, use_cftime=True):
    """Get the xarray for the forecast time"""

    fdate = cftime.DatetimeGregorian(foreyear, 1, 16, 12, 0, 0, has_year_zero=False)

    if use_cftime == False:
        fdate = get_decimal_year([fdate])[0]
    
    xf = xr.DataArray(data = np.array([fdate]), dims = ['time'], coords = {'time': np.array([fdate])},
                      attrs = {'stardand_name': 'time', 'long_name': 'Time axis', 'bounds': 'time_counter_bnds', 'axis': 'T'})

    return xf

def _time_xarray(startyear, endyear):
    """Reconstruct the time array of restarts"""

    dates=[]
    for year in range(startyear,endyear+1):
        x = cftime.DatetimeGregorian(year, 1, 1, 0, 0, 0, has_year_zero=False)
        dates.append(x)
    tdata = xr.DataArray(data = np.array(dates), dims = ['time_counter'], coords = {'time_counter': np.array(dates)}, 
                         attrs = {'stardand_name': 'time', 'axis': 'T'})

    return tdata

##########################################################################################
# Pre-processing options for EOF reader

def _grid_mapping(grid):
    """
    Generate grid-specific renaming conventions for NEMO data.

    Args:
    - grid: str
        Grid type. Choose from 'T', 'U', 'V', 'W'.

    Returns:
    - Dictionary with renaming conventions for the specified grid.
    """

    grid_lower = grid.lower()
    if grid in {'T', 'U', 'V', 'W'}:
        return {
            "x": f"x_grid_{grid}",
            "y": f"y_grid_{grid}",
            "lat": f"nav_lat_grid_{grid}",
            "lon": f"nav_lon_grid_{grid}",
            "z": f"depth{grid_lower}"
        }
    else:
        raise ValueError(f"Unsupported grid type: {grid}")


def process_data(data, ftype, dim='3D', grid='T'):
    """
    Function for preprocessing or postprocessing 2D/3D data.

    Parameters:
    - data: xarray.DataArray or xarray.Dataset
        Input data to be processed.
    - ftype: str
        Operation type. Choose from:
        'pattern' - Preprocessing for EOF pattern.
        'series' - Preprocessing for EOF timeseries.
        'post' - Post-processing for variable field.
    - dim: str, optional (default='3D')
        Dimensionality of the dataset. Choose from '2D' or '3D'.
    - grid: str, optional (default='T')
        Grid type. Choose from 'T', 'U', 'V', 'W'.
        
    Returns:
    - Processed data (xarray.DataArray or xarray.Dataset)
    """

    if dim not in {'2D', '3D'}:
        raise ValueError(f"Invalid dim '{dim}'. Choose '2D' or '3D'.")

    if grid not in {'T', 'U', 'V', 'W'}:
        raise ValueError(f"Invalid grid '{grid}'. Choose from 'T', 'U', 'V', 'W'.")

    grid_mappings = _grid_mapping(grid)

    if ftype == 'pattern':
        # Preprocessing routine for EOF pattern
        data = data.rename_dims({grid_mappings['x']: 'x', grid_mappings['y']: 'y'})
        data = data.rename({grid_mappings['lat']: 'lat', grid_mappings['lon']: 'lon'})
        data = data.rename({'time_counter': 'time'})
        data = data.drop_vars({'time_counter_bnds'}, errors='ignore')
        if dim == '3D':
            data = data.rename({grid_mappings['z']: 'z'})
            data = data.drop_vars({f"{grid_mappings['z']}_bnds"}, errors='ignore')


    elif ftype == 'series':
        # Preprocessing routine for EOF timeseries
        data = data.rename({'time_counter': 'time'})
        data = data.isel(lon=0, lat=0)
        data = data.drop_vars({'time_counter_bnds', 'lon', 'lat'}, errors='ignore')
        if dim == '3D':
            data = data.isel(zaxis_Reduced=0)
            data = data.drop_vars({'zaxis_Reduced'}, errors='ignore')

    elif ftype == 'post':
        # Post-processing routine for variable field
        data = data.rename({'time': 'time_counter'})
        if dim == '3D':
            data = data.rename({'z': 'nav_lev'})

    else:
        raise ValueError(f"Invalid mode '{ftype}'. Choose from 'pattern', 'series', or 'post'.")

    return data


##########################################################################################

def project_eofs(expname, varname, endleg, yearspan, yearleap, mode='full'):
    """ 
    Function to project a field in the future using EOFs. 
    
    Different options are available:
    - projection using the full set of EOFs (mode=full)
    - projection using only the first EOF (mode=first)
    - projection using EOFs up to a percentage of the full (mode=frac)
    - reconstruction of the original field using EOFs (mode=reco)
    
    """

    startleg = endleg - yearspan + 1
    startyear = 1990 + startleg - 2
    endyear = 1990 + endleg - 2
    neofs = endyear - startyear + 1

    logging.info(f"Start/end year: {startyear}-{endyear}")
    logging.info(f"Time window: {neofs}")

    info = catalogue.observables('nemo')[varname]
    dirs = folders(expname)

    # forecast year
    foreyear = get_forecast_year(endyear, yearleap)
    xf = _forecast_xarray(foreyear, use_cftime=False)
    yf = _forecast_xarray(foreyear, use_cftime=True)

    # prepare patterns for EOFs
    filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_pattern.nc")
    pattern = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='pattern', dim=info['dim'], grid=info['grid']))
    field = pattern.isel(time=0)*0

    # Full set of EOFs
    if mode == 'full':

        for i in range(neofs):
            filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_series_{str(i).zfill(5)}.nc")
            logging.warning(f"Reading filename: {filename}")
            timeseries = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='series', dim=info['dim'], grid=info['grid']))        
            new_time = get_decimal_year(timeseries['time'].values)
            timeseries['time'] = new_time
            p = timeseries.polyfit(dim='time', deg=1, skipna=True)
            m, q = p[f"{varname}_polyfit_coefficients"].values
            print(f"m={m}, q={q}")
            theta = xr.polyval(xf, p[f"{varname}_polyfit_coefficients"])
            print(f"theta={theta.values}")
            basis = pattern.isel(time=i)
            field += theta * basis
            field['time'] = yf

    # First EOF
    elif mode == 'first':

        filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_series_00000.nc")    
        timeseries = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='series', dim=info['dim'], grid=info['grid']))        
        new_time = get_decimal_year(timeseries['time'].values)
        timeseries['time'] = new_time
        p = timeseries.polyfit(dim='time', deg=1, skipna = True)
        m, q = p[f"{varname}_polyfit_coefficients"].values
        print(f"m={m}, q={q}")
        theta = xr.polyval(xf, p[f"{varname}_polyfit_coefficients"])
        print(f"theta={theta.values}")
        basis = pattern.isel(time=0)
        field += theta * basis
        field['time'] = yf

    # Reconstruct the last frame (for dry-runs)
    elif mode == 'reco':

        for i in range(neofs):            
            filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_series_{str(i).zfill(5)}.nc")
            timeseries = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='series', dim=info['dim'], grid=info['grid']))
            theta = timeseries[varname].isel(time=-1)
            basis = pattern.isel(time=i)
            field += theta * basis

        field = field.drop_vars({'time'})

    # EOFs up to a percentage of the full
    elif mode == 'frac':
        
        threshold_percentage = 0.9

        weights = []
        cdo_command = f"cdo info -div {varname}_variance.nc -timsum {varname}_variance.nc"
        output = subprocess.check_output(cdo_command, shell=True, text=True)
        for line in output.splitlines():
            if "Mean" in line:
                mean_value = float(line.split(":")[3].strip())
                weights.append(mean_value)
        weights = np.array(weights)
        cumulative_weights = np.cumsum(weights) / np.sum(weights)

        # Find the index where cumulative sum exceeds the threshold percentage
        feofs = np.searchsorted(cumulative_weights, threshold_percentage) + 1

        for i in range(feofs):
            filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_series_{str(i).zfill(5)}.nc")
            timeseries = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='series', dim=info['dim'], grid=info['grid']))
            p = timeseries.polyfit(dim='time', deg=1, skipna=True)
            theta = xr.polyval(xf, p[f"{varname}_polyfit_coefficients"])
            basis = pattern.isel(time=i)
            field += theta * basis

    # add mode='weighted' weight the yearleap based on the distance from equilibrium.

    # add linear regression fit modes: point-to-poit, global- & basin- based
    elif mode == 'fit':

        filename = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}.nc")
        data = xr.open_mfdataset(filename, use_cftime=True, preprocess=lambda data: process_data(data, ftype='pattern', dim=info['dim'], grid=info['grid']))
        p = data[varname].polyfit(dim='time', deg=1, skipna=True)
        field = xr.polyval(xf, p.polyfit_coefficients)

    # fit dimensions before writing on file
    if info['dim'] == '3D':
        field = field.transpose("time", "z", "y", "x")
    if info['dim'] == '2D':
        field = field.transpose("time", "y", "x")

    infile = os.path.join(dirs['tmp'], str(endleg).zfill(3), f"{varname}_eof.nc")
    remove_existing_filelist(infile)
    field.to_netcdf(infile, mode='w', unlimited_dims={'time': True})

    return field