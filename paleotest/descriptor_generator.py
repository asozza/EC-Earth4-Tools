#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is a command line tool to create with CDO the descriptor file necessary to
perform a wide range of horizontal interpolation of initial conditions

Authors
Paolo Davini (CNR-ISAC, Nov 2023)
"""

import os
import re
import subprocess


# grid list
grids = ['TL63', 'TL95', 'TCO319', 'TCO399']

# this runs only on Atos if you have the rights to read this folder
OIFS_BC="/lus/h2resw01/fws1/mirror/lb/project/rdxdata/climate/climate.v015"


def get_info_grid(gridname):

    """Get the info on the grid to find the right ECMWF file"""

    kind = re.sub("[0-9]", "", gridname)[1:].upper()
    spectral = re.sub("[^0-9]", "", gridname)
    ecmwf_name = {
        'L': 'l_2',
        'CO': '_4',
        'Q': '_2'
    }

    return spectral, ecmwf_name[kind]


for grid in grids:

    grid = grid.upper()
    print('Processing ' + grid + '...')

    truncation, ecmwf_kind = get_info_grid(grid)
    REF_FILE='10_bats_glcc.grb'
    file_path = os.path.join(OIFS_BC, truncation + ecmwf_kind, REF_FILE)
    target_path = os.path.join('grids', grid + '.txt')
    #pippo = cdo.griddes(input=file_path, stdout=target_path)
    with open(target_path, 'w', encoding='utf8') as fff:
        subprocess.run(['cdo', 'griddes', file_path], stdout=fff, check=True)

