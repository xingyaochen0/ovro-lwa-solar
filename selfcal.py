from casatasks import clearcal, ft, bandpass, applycal, flagdata, tclean, flagmanager, uvsub, gaincal, split, imstat, \
    gencal
from casatools import table, measures, componentlist, msmetadata
import math
import sys, os, time
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.wcs import WCS
from astropy.io import fits
import matplotlib.pyplot as plt
import utils,flagging,calibration,deconvolve
import flux_scaling
import logging, glob
from file_handler import File_Handler
from primary_beam import analytic_beam as beam 
import primary_beam
from generate_calibrator_model import model_generation
import generate_calibrator_model
import timeit
tb = table()
me = measures()
cl = componentlist()
msmd = msmetadata()


def do_selfcal(msfile, num_phase_cal=3, num_apcal=5, applymode='calflag', logging_level='info',
               ms_keyword='di_selfcal_time',pol='I'):
    
    time1=timeit.default_timer()          
    logging.info('The plan is to do ' + str(num_phase_cal) + " rounds of phase selfcal")
    logging.info('The plan is to do ' + str(num_apcal) + " rounds of amplitude-phase selfcal")
    
    num_pol=2
    if pol=='XX,YY':
        num_pol=4

    max1 = np.zeros(num_pol)
    min1 = np.zeros(num_pol)
    
    for i in range(num_phase_cal):
        imagename = msfile[:-3] + "_self" + str(i)
        deconvolve.run_wsclean(msfile, imagename=imagename, pol=pol)
        
        
        good = utils.check_image_quality(imagename, max1, min1)
       
        print(good)
        logging.debug('Maximum pixel values are: ' + str(max1[0]) + "," + str(max1[1]))
        logging.debug('Minimum pixel values around peaks are: ' + str(min1[0]) + "," + str(min1[1]))
        if not good:
            logging.info('Dynamic range has reduced. Doing a round of flagging')
            flagdata(vis=msfile, mode='rflag', datacolumn='corrected')
            deconvolve.run_wsclean(msfile, imagename=imagename,pol=pol)
            
            
            good = utils.check_image_quality(imagename, max1, min1,reorder=False)
            
            print(good)
            logging.debug('Maximum pixel values are: ' + str(max1[0]) + "," + str(max1[1]))
            logging.debug('Minimum pixel values around peaks are: ' + str(min1[0]) + "," + str(min1[1]))
            if not good:
                logging.info('Flagging could not solve the issue. Restoring flags, applying last good solutions.')
                utils.restore_flag(msfile)
                logging.debug('Restoring flags')
                os.system("rm -rf " + imagename + "-*.fits")
                caltable = msfile[:-3] + "_self" + str(i - 1) + ".gcal"
                os.system("rm -rf " + caltable)
                imagename = msfile[:-3] + "_self" + str(i - 2)
                caltable = imagename + ".gcal"
                if os.path.isdir(caltable):
                    logging.info("Applying " + caltable)
                    applycal(vis=msfile, gaintable=caltable, calwt=[False], applymode=applymode)
                    os.system("cp -r " + caltable + " caltables/")
                else:
                    logging.warning("No caltable found. Setting corrected data to DATA")
                    clearcal(msfile)
                return good
        logging.debug("Finding gain solutions and writing in into " + imagename + ".gcal")
        gaincal(vis=msfile, caltable=imagename + ".gcal", uvrange=">10lambda",
                calmode='p', solmode='L1R', rmsthresh=[10, 8, 6])
        utils.put_keyword(imagename + ".gcal", ms_keyword, utils.get_keyword(msfile, ms_keyword))
        if logging_level == 'debug' or logging_level == 'DEBUG':
            utils.get_flagged_solution_num(imagename + ".gcal")
        logging.debug("Applying solutions")
        applycal(vis=msfile, gaintable=imagename + ".gcal", calwt=[False], applymode=applymode)

    logging.info("Phase self-calibration finished successfully")

    if num_phase_cal > 0:
        final_phase_caltable = imagename + ".gcal"
    else:
        final_phase_caltable = ''
    for i in range(num_phase_cal, num_phase_cal + num_apcal):
        imagename = msfile[:-3] + "_self" + str(i)
        deconvolve.run_wsclean(msfile, imagename=imagename,pol=pol)
        
        good = utils.check_image_quality(imagename, max1, min1)
        
        logging.debug('Maximum pixel values are: ' + str(max1[0]) + "," + str(max1[1]))
        logging.debug('Minimum pixel values around peaks are: ' + str(min1[0]) + "," + str(min1[1]))
        if not good:
            logging.info('Dynamic range has reduced. Doing a round of flagging')
            flagdata(vis=msfile, mode='rflag', datacolumn='corrected')
            deconvolve.run_wsclean(msfile, imagename=imagename,pol=pol)
            
            good = utils.check_image_quality(imagename, max1, min1, reorder=False)
            
            print(good)
            if not good:
                logging.info('Flagging could not solve the issue. Restoring flags, applying last good solutions.')
                utils.restore_flag(msfile)
                os.system("rm -rf " + imagename + "-*.fits")
                caltable = msfile[:-3] + "_self" + str(i - 1) + "_ap_over_p.gcal"
                os.system("rm -rf " + caltable)
                imagename = msfile[:-3] + "_self" + str(i - 2)
                caltable = imagename + "_ap_over_p.gcal"
                if os.path.isdir(caltable):
                    logging.info("Applying " + caltable + " and " + final_phase_caltable)
                    if num_phase_cal > 0:
                        applycal(vis=msfile, gaintable=[caltable, final_phase_caltable], calwt=[False, False],
                                 applymode=applymode)
                        os.system("cp -r " + final_phase_caltable + " caltables/")
                    else:
                        applycal(vis=msfile, gaintable=[caltable], calwt=[False, False], applymode=applymode)
                    os.system("cp -r " + caltable + " caltables/")

                else:
                    logging.warning("No good aplitude-phase selfcal solution found.")
                    if num_phase_cal > 0:
                        logging.info("Applying " + final_phase_caltable)
                        applycal(vis=msfile, gaintable=[final_phase_caltable], calwt=[False], applymode=applymode)
                        os.system("cp -r " + final_phase_caltable + " caltables/")
                    else:
                        logging.warning("No caltable found. Setting corrected data to DATA")
                        clearcal(msfile)
                return good
        caltable = imagename + "_ap_over_p.gcal"

        gaincal(vis=msfile, caltable=caltable, uvrange=">10lambda",
                calmode='ap', solnorm=True, normtype='median', solmode='L1R',
                rmsthresh=[10, 8, 6], gaintable=final_phase_caltable)
        utils.put_keyword(caltable, ms_keyword, utils.get_keyword(msfile, ms_keyword))
        if logging_level == 'debug' or logging_level == 'DEBUG':
            utils.get_flagged_solution_num(imagename + "_ap_over_p.gcal")
        applycal(vis=msfile, gaintable=[caltable, final_phase_caltable], calwt=[False, False], applymode=applymode)
        if i == num_phase_cal:
            flagdata(vis=msfile, mode='rflag', datacolumn='corrected')
    logging.debug('Flagging on the residual')
    flagdata(vis=msfile, mode='rflag', datacolumn='residual')
    if num_apcal>0:
    	os.system("cp -r " + caltable + " caltables/")
    os.system("cp -r " + final_phase_caltable + " caltables/")
    time2=timeit.default_timer()
    logging.info("Time taken for selfcal: "+str(time2-time1)+"seconds")
    return True


def do_fresh_selfcal(solar_ms, num_phase_cal=3, num_apcal=5, logging_level='info',pol='I'):
    """
    Do fresh self-calibration if no self-calibration tables are found
    :param solar_ms: input solar visibility
    :param num_phase_cal: (maximum) rounds of phase-only selfcalibration. Default to 3
    :param num_apcal: (maximum) rounds of ampitude and phase selfcalibration. Default to 5
    :param logging_level: type of logging, default to "info"
    :return: N/A
    """
    logging.info('Starting to do direction independent Stokes I selfcal')
    success = do_selfcal(solar_ms, num_phase_cal=num_phase_cal, num_apcal=num_apcal, logging_level=logging_level,pol=pol)
    if not success:
#TODO Understand why this step is needed
        logging.info('Starting fresh selfcal as DR decreased significantly')
        clearcal(solar_ms)
        success = do_selfcal(solar_ms, num_phase_cal=num_phase_cal, num_apcal=num_apcal, logging_level=logging_level,pol=pol)
    return


def DI_selfcal(solar_ms, solint_full_selfcal=14400, solint_partial_selfcal=3600,
               full_di_selfcal_rounds=[1,1], partial_di_selfcal_rounds=[1, 1], logging_level='info',pol='I'):
    """
    Directional-independent self-calibration (full sky)
    :param solar_ms: input solar visibility
    :param solint_full_selfcal: interval for doing full self-calibration in seconds. Default to 4 hours
    :param solint_partial_selfcal: interval for doing partial self-calibration in seconds. Default to 1 hour.
    :param full_di_selfcal_rounds: [rounds of phase-only selfcal, rounds of amp-phase selfcal]
            for full selfcalibration runs
    :param partial_di_selfcal_rounds: [rounds of phase-only selfcal, rounds of amp-phase selfcal]
            for partial selfcalibration runs
    :param logging_level: level of logging
    :return: N/A
    """

    solar_ms1 = solar_ms[:-3] + "_selfcalibrated.ms"
    if os.path.isdir(solar_ms1) == True:
        return solar_ms1
    
    sep = 100000000
    prior_selfcal = False
    caltables = []

    mstime = utils.get_time_from_name(solar_ms)
    mstime_str = utils.get_timestr_from_name(solar_ms)
    msfreq_str = utils.get_freqstr_from_name(solar_ms)

    caltables = glob.glob("caltables/*"+msfreq_str+"*.gcal")
    if len(caltables) != 0:
        prior_selfcal = True

    if prior_selfcal:
        dd_cal = glob.glob("caltables/*"+msfreq_str+"*sun_only*.gcal")
        di_cal = [cal for cal in caltables if cal not in dd_cal]
        print(di_cal)
        selfcal_time = utils.get_selfcal_time_to_apply(solar_ms, di_cal)
        print(selfcal_time)

        caltables = glob.glob("caltables/" + selfcal_time + "*"+msfreq_str+"*.gcal")
        dd_cal = glob.glob("caltables/" + selfcal_time +  "*"+msfreq_str+"*sun_only*.gcal")
        di_cal = [cal for cal in caltables if cal not in dd_cal]

        if len(di_cal) != 0:
            di_selfcal_time_str, success = utils.get_keyword(di_cal[0], 'di_selfcal_time', return_status=True)
            print(di_selfcal_time_str, success)
            if success:
                di_selfcal_time = utils.get_time_from_name(di_selfcal_time_str)

                sep = abs((di_selfcal_time - mstime).value * 86400)  ### in seconds

                applycal(solar_ms, gaintable=di_cal, calwt=[False] * len(di_cal))
                flagdata(vis=solar_ms, mode='rflag', datacolumn='corrected')

                if sep < solint_partial_selfcal:
                    logging.info('No direction independent Stokes I selfcal after applying ' + di_selfcal_time_str)
                    success = utils.put_keyword(solar_ms, 'di_selfcal_time', di_selfcal_time_str, return_status=True)


                elif sep > solint_partial_selfcal and sep < solint_full_selfcal:
                    # Partical selfcal does one additional round of ap self-calibration
                    success = utils.put_keyword(solar_ms, 'di_selfcal_time', mstime_str, return_status=True)
                    logging.info(
                        'Starting to do direction independent Stokes I selfcal after applying ' + di_selfcal_time_str)
                    success = do_selfcal(solar_ms, num_phase_cal=0,
                                         num_apcal=partial_di_selfcal_rounds[1], logging_level=logging_level,pol=pol)
                    datacolumn = 'corrected'

                else:
                    # Full selfcal does 5 additional rounds of ap self-calibration
                    success = utils.put_keyword(solar_ms, 'di_selfcal_time', mstime_str, return_status=True)
                    logging.info(
                        'Starting to do direction independent Stokes I selfcal after applying ' + di_selfcal_time_str)
                    success = do_selfcal(solar_ms, num_phase_cal=0,
                                         num_apcal=full_di_selfcal_rounds[1], logging_level=logging_level,pol=pol)
                    datacolumn = 'corrected'
                    if success == False:
                        clearcal(solar_ms)
                        success = do_selfcal(solar_ms, logging_level=logging_level,pol=pol)
            else:
                success = utils.put_keyword(solar_ms, 'di_selfcal_time', mstime_str, return_status=True)
                logging.info(
                    'Starting to do direction independent Stokes I selfcal as I failed to retrieve the keyword for DI selfcal')
                do_fresh_selfcal(solar_ms, num_phase_cal=full_di_selfcal_rounds[0],
                                 num_apcal=full_di_selfcal_rounds[1], logging_level=logging_level,pol=pol)
        else:
            success = utils.put_keyword(solar_ms, 'di_selfcal_time', mstime_str, return_status=True)
            logging.info(
                'Starting to do direction independent Stokes I selfcal as mysteriously I did not find a suitable caltable')
            do_fresh_selfcal(solar_ms, num_phase_cal=full_di_selfcal_rounds[0],
                             num_apcal=full_di_selfcal_rounds[1], logging_level=logging_level,pol=pol)
    else:
        success = utils.put_keyword(solar_ms, 'di_selfcal_time', mstime_str, return_status=True)
        logging.info('Starting to do direction independent Stokes I selfcal')
        do_fresh_selfcal(solar_ms, num_phase_cal=full_di_selfcal_rounds[0],
                         num_apcal=full_di_selfcal_rounds[1], logging_level=logging_level,pol=pol)
    
    time1=timeit.default_timer()
    logging.info('Doing a flux scaling using background strong sources')
    fc=flux_scaling.flux_scaling(vis=solar_ms,min_beam_val=0.1,pol=pol)
    fc.correct_flux_scaling()
    time2=timeit.default_timer()
    logging.info("Time taken for fluxscaling: "+str(time2-time1)+"seconds") 

    logging.info('Splitted the selfcalibrated MS into a file named ' + solar_ms[:-3] + "_selfcalibrated.ms")

    solar_ms_slfcaled = solar_ms[:-3] + "_selfcalibrated.ms"
    split(vis=solar_ms, outputvis=solar_ms_slfcaled, datacolumn='data')
    return solar_ms_slfcaled


def DD_selfcal(solar_ms, solint_full_selfcal=1800, solint_partial_selfcal=600,
               full_dd_selfcal_rounds=[3, 5], partial_dd_selfcal_rounds=[1, 1],
               logging_level='info',pol='I'):
    """
    Directional-dependent self-calibration on the Sun only
    :param solar_ms: input solar visibility
    :param solint_full_selfcal: interval for doing full self-calibration in seconds. Default to 30 min
    :param solint_partial_selfcal: interval for doing partial self-calibration in seconds. Default to 10 min.
    :param full_dd_selfcal_rounds: [rounds of phase-only selfcal, rounds of amp-phase selfcal]
            for full selfcalibration runs
    :param partial_dd_selfcal_rounds: [rounds of phase-only selfcal, rounds of amp-phase selfcal]
            for partial selfcalibration runs
    :param logging_level: level of logging
    :return: N/A
    """

    solar_ms1 = solar_ms[:-3] + "_sun_selfcalibrated.ms"
    if os.path.isdir(solar_ms1):
        return solar_ms1

    
    mstime = utils.get_time_from_name(solar_ms)
    mstime_str = utils.get_timestr_from_name(solar_ms)
    msfreq_str = utils.get_freqstr_from_name(solar_ms)
    
    selfcal_time = utils.get_selfcal_time_to_apply(solar_ms, glob.glob("caltables/*"+msfreq_str+"*.gcal"))
    
    sep = 100000000
    prior_selfcal = False

    caltables = glob.glob("caltables/" + selfcal_time + "*" + msfreq_str + "*sun_only*.gcal")

    if len(caltables) != 0:
        prior_selfcal = True

    if prior_selfcal:
        dd_selfcal_time_str, success = utils.get_keyword(caltables[0], 'dd_selfcal_time', return_status=True)

        if success:
            dd_selfcal_time = utils.get_time_from_name(dd_selfcal_time_str)

            sep = abs((dd_selfcal_time - mstime).value * 86400)  ### in seconds

            applycal(solar_ms, gaintable=caltables, calwt=[False] * len(caltables), applymode='calonly')
            flagdata(vis=solar_ms, mode='rflag', datacolumn='corrected')

            if sep < solint_partial_selfcal:
                logging.info('No direction dependent Stokes I selfcal after applying ' + dd_selfcal_time_str)
                success = utils.put_keyword(solar_ms, 'dd_selfcal_time', dd_selfcal_time_str, return_status=True)

            elif sep > solint_partial_selfcal and sep < solint_full_selfcal:
                success = utils.put_keyword(solar_ms, 'dd_selfcal_time', mstime_str, return_status=True)
                logging.info(
                    'Starting to do direction dependent Stokes I selfcal after applying ' + dd_selfcal_time_str)
                success = do_selfcal(solar_ms, num_phase_cal=partial_dd_selfcal_rounds[0],
                                     num_apcal=partial_dd_selfcal_rounds[1], applymode='calonly',
                                     logging_level=logging_level, ms_keyword='dd_selfcal_time',pol=pol)
                datacolumn = 'corrected'


            else:
                success = utils.put_keyword(solar_ms, 'dd_selfcal_time', mstime_str, return_status=True)
                logging.info(
                    'Starting to do direction dependent Stokes I selfcal after applying ' + dd_selfcal_time_str)
                success = do_selfcal(solar_ms, num_phase_cal=full_dd_selfcal_rounds[0],
                                     num_apcal=full_dd_selfcal_rounds[1], applymode='calonly',
                                     logging_level=logging_level, ms_keyword='dd_selfcal_time',pol=pol)
                datacolumn = 'corrected'
        else:
            success = utils.put_keyword(solar_ms, 'dd_selfcal_time', mstime_str, return_status=True)
            logging.info(
                'Starting to do direction dependent Stokes I selfcal as I failed to retrieve the keyword for DD selfcal')
            success = do_selfcal(solar_ms, num_phase_cal=full_dd_selfcal_rounds[0],
                                 num_apcal=full_dd_selfcal_rounds[1], applymode='calonly',
                                 logging_level=logging_level, ms_keyword='dd_selfcal_time',pol=pol)



    else:
        success = utils.put_keyword(solar_ms, 'dd_selfcal_time', mstime_str, return_status=True)
        logging.info('Starting to do direction dependent Stokes I selfcal')
        success = do_selfcal(solar_ms, num_phase_cal=full_dd_selfcal_rounds[0], num_apcal=full_dd_selfcal_rounds[1],
                             applymode='calonly', logging_level=logging_level,
                             ms_keyword='dd_selfcal_time',pol=pol)

    logging.info('Splitted the selfcalibrated MS into a file named ' + solar_ms[:-3] + "_sun_selfcalibrated.ms")

    split(vis=solar_ms, outputvis=solar_ms[:-3] + "_sun_selfcalibrated.ms")
    solar_ms = solar_ms[:-3] + "_sun_selfcalibrated.ms"
    return solar_ms
