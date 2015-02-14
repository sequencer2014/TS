#!/usr/bin/env python
# Copyright (C) 2014 Ion Torrent Systems, Inc. All Rights Reserved
import os
import errno

from django.db.models import Sum

from iondb.rundb.models import DMFileStat, FileServer, Chip
from iondb.rundb.data import dmactions_types
from iondb.rundb.data import dm_utils
from celery.utils.log import get_task_logger

logger = get_task_logger('data_management')
logid = {'logid':"%s" % ('tasks')}

def calculate_diskspace_by_path(dmfilestats, fs_path):
    '''
    Calculates dmfilestats diskspace on given path.
    Assumptions:
        BaseCalling Input: Proton fullchip onboard results are located in expDir
        BaseCalling Input: Proton fullchip shared for single Experiment, count only once for multiple Results
        Intermediate Files: PGM and thumbnail almost all Intermediate files are in report dir
        Intermediate Files: Proton fullchip about 2% in expDir, the rest in report
    '''
    
    ret = {}

    expDir_objs = dmfilestats.filter(result__experiment__expDir__startswith=fs_path).order_by('-pk')
    reportDir_objs = dmfilestats.filter(result__reportstorage__dirPath__startswith=fs_path).order_by('-pk')

    for dmtype in dmactions_types.FILESET_TYPES:

        # find proton fullchip data
        proton_chips = Chip.objects.filter(instrumentType='proton').values_list('name',flat=True)
        proton_filestats = dmfilestats.filter(result__experiment__chipType__in = proton_chips).exclude(result__metaData__contains = 'thumb')

        if dmtype == dmactions_types.SIG:
            values = expDir_objs.filter(dmfileset__type=dmtype).values('result__experiment__pk', 'diskspace').distinct()
            ret[dmtype] = sum(v['diskspace'] for v in values if v['diskspace'])
                
        if dmtype == dmactions_types.OUT:
            ret[dmtype] = reportDir_objs.filter(dmfileset__type=dmtype).aggregate(sum=Sum('diskspace'))['sum'] or 0
        
        if dmtype == dmactions_types.BASE:
            # Proton fullchip sets are in exp folder            
            values = expDir_objs.filter(dmfileset__type=dmtype, pk__in=proton_filestats).values('result__experiment__pk', 'diskspace').distinct()
            proton_diskspace = sum(v['diskspace'] for v in values if v['diskspace'])
            
            # PGM and thumbnail Basecalling Input are in report folder
            objs = reportDir_objs.filter(dmfileset__type=dmtype).exclude(pk__in=proton_filestats)
            diskspace = objs.aggregate(sum=Sum('diskspace'))['sum'] or 0
            
            ret[dmtype] = proton_diskspace + diskspace
        
        if dmtype == dmactions_types.INTR:
            # Proton fullchip sets about 2% in expDir, the rest in report folder
            values = expDir_objs.filter(dmfileset__type=dmtype, pk__in=proton_filestats).values('result__experiment__pk', 'diskspace').distinct()
            proton_diskspace = sum(0.02*v['diskspace'] for v in values if v['diskspace'])
            
            values = reportDir_objs.filter(dmfileset__type=dmtype, pk__in=proton_filestats).values('result__experiment__pk', 'diskspace').distinct()
            proton_diskspace += sum(0.98*v['diskspace'] for v in values if v['diskspace'])
            
            # PGM and thumbnail Intermediate Files are in report folder
            objs = reportDir_objs.filter(dmfileset__type=dmtype).exclude(pk__in=proton_filestats)
            diskspace = objs.aggregate(sum=Sum('diskspace'))['sum'] or 0
            
            ret[dmtype] = proton_diskspace + diskspace

    return ret


def get_usefull_stats():
    
    dmfilestats = DMFileStat.objects.filter(action_state__in=['L','S','N','A'])
    stats = {}
    for fs in FileServer.objects.all():
        if os.path.exists(fs.filesPrefix):
            stats[fs.filesPrefix] = {}
            stats[fs.filesPrefix]['Total'] = calculate_diskspace_by_path(dmfilestats, fs.filesPrefix)
            
            # get sets marked Keep
            keepers = dmfilestats.filter(preserve_data=True) | dmfilestats.filter(dmfileset__type=dmactions_types.SIG, result__experiment__storage_options="KI")
            stats[fs.filesPrefix]['Keep'] = calculate_diskspace_by_path(keepers, fs.filesPrefix)

    return stats


def get_keepers_diskspace(fs_path):
    ''' Returns how much space on fs_path is taken up by data marked Keep '''
    dmfilestats = DMFileStat.objects.filter(action_state__in=['L','S','N','A'])
    keepers = dmfilestats.filter(preserve_data=True) | dmfilestats.filter(dmfileset__type=dmactions_types.SIG, result__experiment__storage_options="KI")
    keepers_diskspace = calculate_diskspace_by_path(keepers, fs_path)
    return keepers_diskspace


def update_diskspace(dmfilestat, cached = None):
    '''Update diskspace field in dmfilestat object'''
    try:
        # search both results directory and raw data directory
        search_dirs = [dmfilestat.result.get_report_dir(), dmfilestat.result.experiment.expDir]

        if not cached:
            cached = dm_utils.get_walk_filelist(search_dirs, list_dir=dmfilestat.result.get_report_dir())

        total_size = 0

        #Create a list of files eligible to process
        is_thumbnail = dmfilestat.result.isThumbnail
        for start_dir in search_dirs:
            to_process = []
            if os.path.isdir(start_dir):
                to_process, _ = dm_utils._file_selector(start_dir,
                                                     dmfilestat.dmfileset.include,
                                                     dmfilestat.dmfileset.exclude,
                                                     [],
                                                     is_thumbnail,
                                                     add_linked_sigproc=True,
                                                     cached = cached)

                #process files in list
                for path in to_process[1:]:
                    try:
                        #logger.debug("%d %s %s" % (j, 'diskspace', path), extra = logid)
                        if not os.path.islink(path):
                            total_size += os.lstat(path)[6]

                    except Exception as inst:
                        if inst.errno == errno.ENOENT:
                            pass
                        else:
                            errmsg = "update_diskspace %s" % (inst)
                            logger.error(errmsg, extra = logid)

        diskspace = float(total_size)/(1024*1024)
    except:
        diskspace = None
        raise
    finally:
        dmfilestat.diskspace = diskspace
        dmfilestat.save()
    return diskspace

    