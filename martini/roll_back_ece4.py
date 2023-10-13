#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This is a simple tool to roll back a restart for EC-Earth4 experiment to a given leg
If you want to restore the model to a specific date, just run this tool defining 
at which leg you want to go. It is important to define the directory where the data is, 
so please check the RUNDIR variable here below

There is also the option of creating a backup (--backup) and to rerun from this backup
if something went south (--rurun)

Paolo Davini, CNR-ISAC (Oct 2023)
"""

import argparse
import os
import glob
import sys
import shutil
import yaml
from dateutil.relativedelta import relativedelta

# important: the folder where the experiments are
RUNDIR="/ec/res4/scratch/ccpd/ece4"


def parse_args():
    """Command line parser for nemo-restart"""

    parser = argparse.ArgumentParser(description="Command Line Parser for nemo-restart")

    # add positional argument (mandatory)
    parser.add_argument("expname", metavar="EXPNAME", help="Experiment name")
    parser.add_argument("leg", metavar="LEG", help="The leg you want roll back to restart your experiment", type=str)

    # optional to activate nemo rebuild
    parser.add_argument("--rerun", action="store_true", help="Restore the a backup (if available)")
    parser.add_argument("--backup", action="store_true", help="Before running, create a backup of the entire folder. It might be slow!")


    parsed = parser.parse_args()

    return parsed

if __name__ == "__main__":
    
    # parser
    args = parse_args()
    expname = args.expname
    leg = args.leg
    rerun = args.rerun

    # define directories
    dirs = {
        'exp': os.path.join(RUNDIR, expname),
        'backup': os.path.join(RUNDIR, expname + "-backup")
    }

    # if I have been asked to rerun everything, copy from the backup
    if args.rerun:
        if os.path.isdir(dirs['backup']):
            print('Rerunning required, copying backup to exp folder, it can be VERY LONG...')
            shutil.copytree(dirs['backup'], dirs['exp'], symlinks=True)
        else:
            sys.exit('Cannot exploit the backup, you need to create it before with --backup')

    # if a backup has been asked, create it if necessary
    if args.backup:
        if os.path.isdir(dirs['backup']):
            print('Backup directory found, no need to recreate it!')
        else:
            print('Creating a backup, it can be VERY LONG...')
            shutil.copytree(dirs['exp'], dirs['backup'], symlinks=True)

    # cleaning
    # create list of files to be remove in the run folder
    browser = ['rstas.nc', 'rstos.nc',  'srf000*.????', 'restart*.nc', 'rcf']
    for file in browser:
        filelist = sorted(glob.glob(os.path.join(dirs['exp'], file)))
        for file in filelist:
            if os.path.isfile(file):
                print('Removing' + file)
                os.remove(file)

    # update the leginfo rolling back to the require leg
    legfile = os.path.join(dirs['exp'], 'leginfo.yml')
    with open(legfile, 'r', encoding='utf-8') as file:
        leginfo = yaml.load(file, Loader=yaml.FullLoader)

    # get some time information
    info = leginfo['base.context']['experiment']['schedule']['leg']
    deltayear = int(leg) - info['num']
    newdate = info['start'] + relativedelta(years=deltayear)
    orgdate = info['start']

    # modify the file only if it is necessary
    if int(leg) < info['num']:

        #print(info['start'] + relativedelta(years=deltayear))

        leginfo['base.context']['experiment']['schedule']['leg']['num'] = int(leg)
        leginfo['base.context']['experiment']['schedule']['leg']['start'] = newdate

        print("Updating the leginfo to leg number " + leg)
        with open(legfile, 'w', encoding='utf8') as outfile:
            yaml.dump(leginfo, outfile, default_flow_style=False)

    elif int(leg) == info['num']:
        print("Nothing to do on the leginfo.yaml")
    else:
        raise ValueError("I cannot go forward in time...")

    # copying from the restart folder required for the leg you asked
    browser = ['rstas.nc', 'rstos.nc',  'srf000*.????', 'rcf', '*restart*']
    for file in browser:
        filelist = sorted(glob.glob(os.path.join(dirs['exp'],  'restart', leg.zfill(3), file)))
        for file in filelist:
            basefile = os.path.basename(file)
            targetfile = os.path.join(dirs['exp'], basefile)
            if not os.path.isfile(targetfile):
                # copy rcf and oasis file
                if basefile in ['rstas.nc', 'rstos.nc', 'rcf']:
                    print("Copying restart", file)
                    shutil.copy(file, targetfile)
                # link oifs files
                elif 'srf' in basefile:
                    print("Linking IFS restart", file)
                    os.symlink(file, targetfile)
                # link and rename nemo files
                elif 'restart' in basefile:
                    newfile = os.path.join(dirs['exp'], '_'.join(basefile.split('_')[2:]))
                    print("Linking NEMO restart", file)
                    os.symlink(file, newfile)

    # removing old output to avoid mess
    browser = list(range(newdate.year, orgdate.year))
    for year in browser:
        filelist = sorted(glob.glob(os.path.join(dirs['exp'],  'output', '*', '*' + str(year) + '*')))
        for file in filelist:
            if os.path.isfile(file):
                print('Removing output file', file)
                os.remove(file)
