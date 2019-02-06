#!/usr/bin/python
# Copyright (C) 2013 Ion Torrent Systems, Inc. All Rights Reserved
# vim: tabstop=4 shiftwidth=4 softtabstop=4 noexpandtab
# Ion Plugin - Ion Variant Caller

import os
import time
import json
import sys
import subprocess
import glob
import sqlite3
import traceback
def printtime(message, *args):
    if args:
        message = message % args
    print "[ " + time.strftime('%a %Y-%m-%d %X %Z') + " ] " + message
    sys.stdout.flush()
    sys.stderr.flush()


def run_command(command,description):
    printtime(' ')
    printtime('Task    : ' + description)
    printtime('Command : ' + command)
    printtime(' ')
    return subprocess.call(command,shell=True)


WINDOW = 300

def _execute(path, query, limit, offset):
    """Function to execute queries against a local sqlite database"""

    page_str = " LIMIT {limit} OFFSET {offset}".format(limit=limit, offset=offset)

    if os.path.exists(os.path.join(path,"alleles.db")):
        dbPath = os.path.join(path,'alleles.db')
        connection = sqlite3.connect(dbPath)

        cursorobj = connection.cursor()
        try:
                cursorobj.execute(query + page_str)
                result = cursorobj.fetchall()

                #now find the total number of records that match the query
                cursorobj.execute(query.replace("SELECT *", "SELECT COUNT(*)") )
                count =  cursorobj.fetchall()
        except Exception as e:
                raise e
        connection.close()
        return count, result
    else:
        raise Exception("Unable to open database file")

def db_columns(bucket):
    """returns the keys of columns from database"""
    path = bucket["request_get"].get("path", '')
    dbPath = os.path.join(path, 'alleles.db')
    if path and os.path.exists(dbPath):
            connection = sqlite3.connect(dbPath)
            cursorobj = connection.cursor()
            try:
                cursorobj.execute('select * from variants')
                # The first two columns are '"id" INTEGER PRIMARY KEY, "ChromSort" UNSIGNED BIG INT,
                column_offset = 2
                db_columns_list = [col_description[0] for col_description in cursorobj.description[column_offset:]]
            except Exception as e:
                raise e
            connection.close()
            return db_columns_list
    else:
        raise(ValueError('Empty path in the bucket.'))
     

def query(bucket):
    """returns a list of rows from database"""

    where = bucket["request_get"].get("where", False)
    #get the search filter JSON, then use that to build the SQL where statements
    where_list = []
    if where:
        where = json.loads(where)
        for key,value in where.iteritems():

                if isinstance(value,list):
                    for i,v in enumerate(value):
                        if i == 0:
                            where_local = "("
                        where_local += '"{key}" = "{value}"'.format(key=key,value=v)
                        if i+1 < len(value):
                            where_local += ' OR '
                        else:
                            where_local += ")"
                    where_list.append(where_local)
                elif key in ["Position", "Frequency", "Coverage"]:
                    where_list.append('"{key}" {value}'.format(key=key, value=value))
                elif key in ["Allele Name", "Gene ID", "Region Name"]:
                    where_list.append('"{key}" LIKE "%{value}%"'.format(key=key, value=value))

    if where_list:
        where_str = "WHERE "
        for i,w in enumerate(where_list):
            if i == 0:
                where_str += w
            else:
                where_str += " AND " + w
    else:
        where_str = ""

    limit = bucket["request_get"].get("limit", "20")
    offset = bucket["request_get"].get("offset", "0")
    #pass the path in from the JS, it is in startplugin.json - runinfo -> results_dir
    path = bucket["request_get"].get("path", "")

    #now do filtering 1 column and direction at a time
    column = bucket["request_get"].get("column", False)
    direction = bucket["request_get"].get("direction", "ASC")

    #TODO do the WHERE filtering
    #TODO just use string.format to make all the SQL, the built in parameterasation feature isn't good enough
    if column:
        q= 'SELECT * FROM variants {where} ORDER BY "{column}" {direction}'.format(
                        column=column, direction=direction, where=where_str)
        #lower case position is a special field that has a combination of chrm and the Position (int)
        if column == "position":
            #order by the by the ChromSort, then the position
            q= 'SELECT * FROM variants {where} ORDER BY "ChromSort" {direction}, "Position" {direction}'.format(
                direction=direction, where=where_str)
        count, rows = _execute(path, q, limit, offset)
    else:
        q = 'SELECT * FROM variants {where} ORDER BY "id"'.format(
                where=where_str)
        count, rows = _execute(path, q, limit, offset)

    #make the first item the total count of items
    data = {}
    data["total"] = [count[0][0]]
    data["items"] = []
    for row in rows:
        data["items"].append(row)
    return data


def start(path, plugin_path, temp_path, barcode):
    """
    Start an SGE job, and wait for it to return
    """

    #only import drmaa on the head nodes
    import drmaa

    #TODO: this is not robust and fails to init the session sometimes
    #code 11: Initialization failed due to existing DRMAA session.
    #AlreadyActiveSessionException: code 11: Initialization failed due to existing DRMAA session.

    os.environ["SGE_ROOT"] = "/var/lib/gridengine"
    os.environ["SGE_CELL"] = "iontorrent"
    os.environ["SGE_CLUSTER_NAME"] = "p6444"
    os.environ["SGE_QMASTER_PORT"] = "6444"
    os.environ["SGE_EXECD_PORT"] = "6445"
    os.environ["SGE_ENABLED"] = "True"
    os.environ["DRMAA_LIBRARY_PATH"] = "/usr/lib/libdrmaa.so.1.0"

    # create a single drmaa session
    _session = drmaa.Session()
    try:
        _session.initialize()
    except:
        _session.exit()
        #maybe need to return False?
        return False

    # Prepare drmaa Job - SGE/gridengine only
    jt = _session.createJobTemplate()
    jt.nativeSpecification = " -q %s" % ("plugin.q")

    jt.workingDirectory = path
    jt.outputPath = ":" + os.path.join(temp_path, "TVC_drmaa_stdout.txt")
    jt.joinFiles = True # Merge stdout and stderr

    jt.remoteCommand = "python"
    script = os.path.join(plugin_path, "extend.py")
    jt.args = [script, path, temp_path, barcode]

    # Submit the job to drmaa
    jobid = _session.runJob(jt)

    _session.deleteJobTemplate(jt)
    _session.exit()
    return jobid

def split(bucket):
    if "request_post" in bucket:
        #On the POST request do the splicing

        post = bucket["request_post"]

        #step one find out if this is a barcoded run http://ionwest.itw/report/39313/metal/barcodeList.txt

        path = post.get("startplugin", {}).get("runinfo", {}).get("results_dir", "")

        plugin_path = post.get("startplugin", {}).get("runinfo", {}).get("plugin_dir", "")

        variants = post.get("variants", {})

        barcode = post.get("barcode", False)

        #if it is a barcode make the dir inside of the barcodes dir
        if barcode:
            path = os.path.join(path, barcode)

        #TODO This don't show previously generated data
        if path:
            #Create a temp path to shuffle the data around inside of
            temp_path = "split_" + str(int(time.time()))

            #make the temp dir is it is there
            if not os.path.exists(os.path.join(path, temp_path)):
                os.mkdir(os.path.join(path, temp_path))

            #Write out the variants to a JSON file
            temp_json = os.path.join( path, temp_path, "variants.json")

            with open(temp_json, "w+") as temp:
                temp.write(json.dumps(variants))

            with open(os.path.join(path, "split_status.json" ), "w+") as status:
                status.write(json.dumps({"split_status":"Queued"}))

            job = start(path, plugin_path, temp_path, barcode)

            #TODO if two jobs are sent in, the UI is stupid and will think the first one done is the one it wants
            #TODO add the job id in the status as well, and check the right job is done.

            if job:
                #TODO : write the job id to the dir, just to try to allow one than on split to happen at once.
                return {"started" : temp_path , "job" : job }
            else:
                with open(os.path.join(path, "split_status.json" ), "w+") as status:
                    status.write(json.dumps({"split_status":"failed"}))
                return {"failed" : "Job not started SGE error"}
        else:
            return {"failed" : "Bad data POSTed"}

    else:
        return {"failed" : "This expects a POST request"}

def vcf_split(input_vcf, output_vcf, chr, position, window=300):

    #todo check boundaries later
    left = int(position) - (window / 2 )
    right = int(position) + (window / 2 )

    return ["vcftools", "--vcf", input_vcf, "--out", output_vcf, "--recode", "--keep-INFO-all", "--chr", chr,
            "--from-bp", str(left) , "--to-bp", str(right)]

def bam_split(input_bam, output_bam, chr, position, window=300):

    #todo check boundaries later
    left = int(position) - (window / 2 )
    right = int(position) + (window / 2 )
    location = chr + ":" + str(left) + "-" + str(right)

    return ["samtools", "view", "-h", "-b", input_bam, location, "-o", output_bam]

def bam_index(input_bam):
    """make the bam index"""
    return ["samtools", "index", input_bam]

def status_update(path, status, extra_info_dict = {}):
    status_dict = dict([(key, value) for key, value in extra_info_dict.iteritems()])
    status_dict['split_status'] = str(status)
    with open(os.path.join(path, "split_status.json"), "w+") as f:
        f.write(json.dumps(status_dict))

def clean_position_name(chrom, pos, position_names, window, my_id):
    """try to clean up chr names"""

    #left = int(pos) - (window / 2 )
    #right = int(pos) + (window / 2 )

    name = chrom.replace("|","PIPE")
    name += "_" + str(pos)
    name += "_padding_" + str(window)

    #now check to make sure that the name isn't already taken
    if name in position_names:
        name += "_" + str(my_id)

    #maybe like this later
    #chr#(start-padding)(end+padding) where end=start+length(ref).

    return name

def add_to_zip_list(to_zip_list, source_path, dest_dir = None, dest_basename = None):
    if dest_basename is None:
        dest_basename = os.path.basename(source_path)
    if dest_dir is None:
        dest_path = dest_basename
    else:
        dest_path = os.path.join(dest_dir, dest_basename)
    to_zip_list.append((source_path, dest_path))

def simulate_vc_plugin(path_to_result, barcode):
    '''
    Simulate the variantCaller plugin and get the files for the barcode.
    '''
    # Use variant_caller_plugin to get information
    if barcode in ['', False, None, 'nonbarcoded']:
        plugin_dir = path_to_result
        my_barcode = None
    else:
        plugin_dir = os.path.realpath(os.path.join(path_to_result, ".."))
        my_barcode = barcode

    # Get startplugin_json
    with open(os.path.join(plugin_dir, 'startplugin.json'), 'rb') as f_json:
        startplugin_json = json.load(f_json, parse_float=str)
    # Get the directory of the plugin
    dirname = startplugin_json['runinfo']['plugin_dir']
    # Add the path of the plugin 
    sys.path.append(dirname)
    # Now I can import variant_caller_plugin.py
    import variant_caller_plugin as vc_plugin
   
    if my_barcode is None:
        my_barcode = vc_plugin.NONBARCODED
    vc_plugin.STARTPLUGIN_JSON = startplugin_json
    vc_plugin.TSP_FILEPATH_PLUGIN_DIR = plugin_dir
    vc_plugin.DIRNAME = dirname

    # Read barcodes.json
    with open(os.path.join(vc_plugin.TSP_FILEPATH_PLUGIN_DIR, 'barcodes.json'), 'rb') as f_json:
        vc_plugin.BARCODES_JSON = json.load(f_json)
    barcoded_run, configured_run, start_mode, multisample = vc_plugin.get_plugin_mode()

    # tvcutils
    vc_plugin.TVCUTILS = os.path.join(os.path.join(vc_plugin.DIRNAME, 'bin'), 'tvcutils')
    if not os.path.exists(vc_plugin.TVCUTILS):
        vc_plugin.TVCUTILS = 'tvcutils'
        
    # I do almost exactly the same thing as the plugin does for getting configuration and options.    
    configurations, process_status = vc_plugin.get_configurations(barcoded_run, configured_run, start_mode, multisample)
    # Get the configuration of the barcode
    my_configutation = None
    my_bam_dict = None
    for config in configurations.itervalues():
        for bam in config['bams']:
            if bam['name'] == my_barcode:
                my_configutation = config
                my_bam_dict = bam
                break
        if (my_configutation is not None) and (my_bam_dict is not None):
            break
    if (my_configutation is None) or (my_bam_dict is None):
        raise(ValueError('Fail to get the barcode.'))
    
    # Get options
    my_configutation['options'] = vc_plugin.ConfigureOptionsManager(my_configutation)

    # Get the bam file
    try_bams = [os.path.basename(my_bam_dict['file'])[:-4] + '.realigned.bam', os.path.basename(my_bam_dict['file'])]
    my_bam_dict['untrimmed_bam'] = None
    for try_bam in try_bams:
        try_bam_path = os.path.join(vc_plugin.TSP_FILEPATH_PLUGIN_DIR, try_bam)
        if os.path.exists(try_bam_path):
            my_bam_dict['untrimmed_bam'] = try_bam_path
            break
        try_bam_path = os.path.join(path_to_result, try_bam)
        if os.path.exists(try_bam_path):
            my_bam_dict['untrimmed_bam'] = try_bam_path
            break        
        
    if my_bam_dict['untrimmed_bam'] is None:
        raise(IOError('Can not find the bam file.'))
    # Identify the directory for the barcode 
    if barcoded_run:
        my_bam_dict['results_directory'] = os.path.join(vc_plugin.TSP_FILEPATH_PLUGIN_DIR, my_bam_dict['name'])
    else:
        my_bam_dict['results_directory'] = vc_plugin.TSP_FILEPATH_PLUGIN_DIR
    # Determine the 'vc_pipeline_directory' and post processed bam
    if multisample:
        my_bam_dict['vc_pipeline_directory'] = os.path.join(vc_plugin.TSP_FILEPATH_PLUGIN_DIR, my_configutation['name'])
        my_bam_dict['post_processed_bam'] = os.path.join(my_bam_dict['vc_pipeline_directory'], 'multisample_processed.bam')
    else:
        my_bam_dict['vc_pipeline_directory'] = my_bam_dict['results_directory']
        assert(my_bam_dict['untrimmed_bam'].endswith('.bam'))
        my_bam_dict['post_processed_bam'] = os.path.join(my_bam_dict['vc_pipeline_directory'], os.path.basename(my_bam_dict['untrimmed_bam'])[:-4] + '_processed.bam')

    if not os.path.exists(my_bam_dict['post_processed_bam']):
        my_bam_dict['post_processed_bam'] = None

    return vc_plugin, my_configutation, my_bam_dict 

def get_config_names(bucket):
    variantCallerConfigurations_path = '/results/plugins/scratch/variantCallerConfigurations.txt'
    # load all configurations
    try:
        with open(variantCallerConfigurations_path, 'r') as f_configs:
            all_contents = f_configs.read()
    except IOError:
        all_contents = ''
    if all_contents == '':
        all_configs = {}
    else:
        # load stringify content
        all_configs = json.loads(all_contents)
    return all_configs.keys()

def save_adjusted_param_to_configuration(bucket):
    '''
    Save the adjusted parameters to the configuration.
    '''
    try:
        try:
            barcode = bucket["request_get"].get('barcode', None)
            save_to_config_name = bucket["request_get"]['config_name']
            adjusted_tvc_params = bucket["request_get"]['adjusted_params']
            if barcode is None:
                path_to_detail_report = bucket["request_get"]['plugin_result_path']
            else:
                path_to_detail_report = os.path.join(bucket["request_get"]['plugin_result_path'], barcode)
        except:
             return {'Error': 'invalid requests'}
        
        # I hard code the path to variantCallerConfigurations here.
        variantCallerConfigurations_path = '/results/plugins/scratch/variantCallerConfigurations.txt'
    
        # Simulate what the plugin does
        try:
            vc_plugin, my_configutation, my_bam_dict = simulate_vc_plugin(path_to_detail_report, barcode)
        except:
            return {'Error': 'Fail to get the configuration of the plugin result %s.' %path_to_detail_report}
       
        # Get the configuration of the barcode
        my_pluginconfig = my_configutation['json']['pluginconfig']
        my_pluginconfig['meta']['name'] = 'Custom'
        my_pluginconfig['meta']['configuration'] = 'custom'
        my_pluginconfig['meta']['configuration_name'] = save_to_config_name
        my_pluginconfig['meta']['tooltip'] = 'Manually created custom set'
        my_pluginconfig['meta']['custom'] = True
        my_pluginconfig['meta']['built_in'] = False
        my_pluginconfig['meta']['parameters'] = {'config': '', 'value': 'custom'} # I can't tell the value of "config". It depends on the parameter file available to the stuffs selected by the user.

        # If start the plugin with the plan, use the reference/target region/HS specified in barcodes.json.
        # I must follow whatever instance.html does.
        if my_configutation['start_mode'].lower() == 'auto start':
            # Auto start mode has no panel.
            my_pluginconfig['meta']['tagseq_panel'] = ''
            my_pluginconfig['meta']['tagseq_panel_id'] = 'Unspecified'
            my_pluginconfig['meta']['ampliseq_panel'] = ''
            my_pluginconfig['meta']['ampliseq_panel_id'] = 'Unspecified'
            my_pluginconfig['meta']['reference'] = my_configutation['options'].serve_option('reference_genome_name', my_bam_dict['name'])
            # Deal with referenceid 
            reference_full_name = vc_plugin.BARCODES_JSON[my_bam_dict['name']].get('reference_full_name', '') # Should be available if TS-15330 is included.
            if reference_full_name == '':
                my_pluginconfig['meta']['referenceid'] = my_pluginconfig['meta']['reference']
            else:
                my_pluginconfig['meta']['referenceid'] = my_pluginconfig['meta']['reference'] +  " - " + reference_full_name
            # Hotspots
            my_pluginconfig['meta']['targetloci'] = my_configutation['options'].serve_option('hotspots_bed_unmerged', my_bam_dict['name'])
            my_pluginconfig['meta']['targetloci_id'] = my_configutation['options'].serve_option('hotspots_name', my_bam_dict['name'])
            my_pluginconfig['meta']['targetloci_merge'] = my_configutation['options'].serve_option('hotspots_bed_merged', my_bam_dict['name'])
            # Target Regions
            my_pluginconfig['meta']['targetregions'] = my_configutation['options'].serve_option('targets_bed_unmerged', my_bam_dict['name'])
            my_pluginconfig['meta']['targetregions_id'] = my_configutation['options'].serve_option('targets_name', my_bam_dict['name'])
            my_pluginconfig['meta']['targetregions_merge'] = my_configutation['options'].serve_option('targets_bed_merged', my_bam_dict['name'])
        
        # Now deal with parameters
        # Get local_parameters.json
        local_param_json_path = my_configutation['options'].serve_option('parameters_file')
        try:
            with open(local_param_json_path, 'rb') as f_local_json:
                local_parameters = json.load(f_local_json)
        except:
            return {'Error': 'Fail to load %s.' %local_param_json_path}    
        # The parameters of the new configuration are based on "local_parameters.json".
        for section in ['torrent_variant_caller', 'freebayes', 'long_indel_assembler']:
            my_pluginconfig[section] = local_parameters[section]
        # The tuned parameters
        if type(adjusted_tvc_params) is not dict:
            adjusted_tvc_params = json.loads(adjusted_tvc_params)
        for key, value in adjusted_tvc_params.iteritems():
            my_pluginconfig['torrent_variant_caller'][key] = value        
        # The custom args
        for arg_key in ['tvcargs', 'tmapargs', 'unifyargs']:
            if arg_key in local_parameters['meta']:
                my_pluginconfig['meta'][arg_key] = local_parameters['meta'][arg_key]
            else: 
                my_pluginconfig['meta'].pop(arg_key, None)
    
        # load all configurations
        try:
            with open(variantCallerConfigurations_path, 'r') as f_configs:
                all_contents = f_configs.read()
        except IOError:
            all_contents = ''
        
        if all_contents == '':
            all_configs = {}
        else:
            # load stringify content
            all_configs = json.loads(all_contents)
        # I must "serialize" one configuration
        all_configs[save_to_config_name] = json.dumps({'pluginconfig': my_pluginconfig, 
                                                       'plugin':  [vc_plugin.STARTPLUGIN_JSON['runinfo']['plugin_name'], ],
                                                       })
        try:
            with open(variantCallerConfigurations_path, 'w') as f_configs:
                f_configs.write(json.dumps(all_configs))
                try:
                    os.chmod(variantCallerConfigurations_path, 0777)
                except:
                    pass
        except IOError:
            return {'Error': 'Fail to write to %s.' %variantCallerConfigurations_path}        
    except Exception as e:
        if hasattr(e, 'message'):
            err_msg = e.message
        else:
            err_msg = str(e)
        return {'Error': err_msg}

    return {'Success': 'Adjusted parameters are saved to the configuration "%s".' %save_to_config_name}

def slicer_main(path, temp_path, barcode):
    '''
    path: path to the barcode directory
    temp_path: path to the sliced data directory
    barcode: barcode of interest. Empty string refers to as no barcode.
    '''

    full_path = os.path.join(path, temp_path)

    # Simulate what variantCaller plugin does and gets the configuration/options for the barcode   
    vc_plugin, my_configutation, my_bam_dict = simulate_vc_plugin(path, barcode)

    # Get the prefix
    prefix = ''
    if my_bam_dict['name'] != vc_plugin.NONBARCODED:
        prefix = my_bam_dict['name'] + '_'

    # Get all bed files
    source_bed_files = glob.glob(my_bam_dict['results_directory'] + '/*.bed')

    results_name = vc_plugin.STARTPLUGIN_JSON.get("expmeta", {}).get("results_name", "results")
    variants = json.load(open(os.path.join(full_path, "variants.json")))

    status_update(path, "Stat Generation in progress")
    printtime("Generating BAM stats")

    #TODO BAM stats should be made by the plugin

    #TODO check to see if it exists
    #TODO if not then make it in the parent dir then copy it over

    #if it is there just added it to the zip later
    #Get full bam stats
    rawlib_stats = subprocess.Popen(['samtools', 'flagstat', my_bam_dict['untrimmed_bam']],
                                    stdout=subprocess.PIPE).communicate()[0]

    with open(os.path.join(full_path, prefix + "rawlib_stats.txt"),"w+") as f:
        f.write(rawlib_stats)

    if my_bam_dict['post_processed_bam'] is not None:
        rawlib_prtim_stats = subprocess.Popen(['samtools', 'flagstat', my_bam_dict['post_processed_bam']],
                                              stdout=subprocess.PIPE).communicate()[0]

        with open(os.path.join(full_path, prefix + "rawlib_ptrim_stats.txt"),"w+") as f:
            f.write(rawlib_prtim_stats)

    vcf_files = ["small_variants.vcf", "small_variants_filtered.vcf", "TSVC_variants.vcf", "indel_assembly.vcf"]
    # Hotspots vcf
    hotspots_name = my_configutation['options'].serve_option('hotspots_name', my_bam_dict['name'])
    if hotspots_name != '':
        try_hs_vcf_path = os.path.join(path, hotspots_name + '.hotspot.vcf')
        if os.path.exists(try_hs_vcf_path):
            vcf_files.append(os.path.basename(try_hs_vcf_path))
    # sse vcf
    sse_bed = my_configutation['options'].serve_option('sse_bed', my_bam_dict['name'])
    if sse_bed.endswith('bed') :
        try_sse_vcf_path = os.path.join(path, os.oath.basename(sse_bed)[:-4] + '.vcf')
        if os.path.exists(try_sse_vcf_path):
            vcf_files.append(os.path.basename(try_sse_vcf_path))

    status_update(path, "BAM and VCF files are being sliced")
    printtime("Generating expected VCF files")

    to_zip = []

    #write hotspot variants to force eval

    #TODO write one at a time
    for k,v in variants.iteritems():
        expected_bed_filename = prefix + str(v["chrom"]) + "_" + str(v["pos"]) + "_" + "expected.bed"
        expected_vcf_filename = prefix + str(v["chrom"]) + "_" + str(v["pos"]) + "_" + "expected.vcf"
        
        with open(os.path.join(full_path, expected_bed_filename),"w+") as f:
            pos = int(v.get("pos",0))
            ref = str(v.get("ref",""))
            f.write('track type=bedDetail\n')
            f.write(str(v.get("chrom",".")) + "\t" +
                    str(pos-1) + "\t" +
                    str(pos-1+len(ref)) + "\t" +
                    "." + "\t" +
                    "REF=" + ref + ";OBS=" + str(v.get("expected","")) + "\t" +
                    "." + "\n"
            )
        add_to_zip_list(to_zip, os.path.join(full_path, expected_bed_filename), results_name)  
        
        args =  "%s prepare_hotspots " %vc_plugin.TVCUTILS
        args += " --input-bed %s " %expected_bed_filename
        args += " --output-vcf %s " %expected_vcf_filename
        args += " --reference %s " %my_configutation['options'].serve_option('reference_genome_fasta', my_bam_dict['name'])
        args += " --left-alignment on"
        printtime(args)
        subprocess.check_call(args, cwd=full_path, shell=True)
        add_to_zip_list(to_zip, os.path.join(full_path, expected_vcf_filename), results_name)  
        
    #store all the names so that we don't use the same one twice
    position_names = []
    #Do splicing for each of the variants
    for id, variant in variants.iteritems():
        
        #base filename
        base = clean_position_name(variant["chrom"], variant["pos"], position_names, WINDOW, id)
        position_names.append(base)

        printtime("Slicing BAM and VCF files for " + base)

        # rawlib bam
        rawlib_variant = '%s_%s.bam' %(os.path.basename(my_bam_dict['untrimmed_bam'])[:-4], base)
        args = bam_split(my_bam_dict['untrimmed_bam'], rawlib_variant, variant["chrom"], variant["pos"], WINDOW)
        subprocess.check_call(args, cwd=full_path)
        add_to_zip_list(to_zip, os.path.join(full_path, rawlib_variant), results_name)  

        # make indexes for rawlib bam
        args = bam_index(os.path.join(full_path, rawlib_variant))
        subprocess.check_call(args, cwd=full_path)
        add_to_zip_list(to_zip, os.path.join(full_path, rawlib_variant + ".bai"), results_name)  

        if my_bam_dict['post_processed_bam'] is not None:
            # processed bam
            rawlib_ptrim_variant = '%s_%s.bam' %(os.path.basename(my_bam_dict['post_processed_bam'])[:-4], base) 
            args = bam_split(my_bam_dict['post_processed_bam'], rawlib_ptrim_variant, variant["chrom"], variant["pos"], WINDOW)
            subprocess.check_call(args, cwd=full_path)
            add_to_zip_list(to_zip, os.path.join(full_path, rawlib_ptrim_variant), results_name)  

            # make indexes for processed bam
            args = bam_index(os.path.join(full_path, rawlib_ptrim_variant))
            subprocess.check_call(args, cwd=full_path)
            add_to_zip_list(to_zip, os.path.join(full_path, rawlib_ptrim_variant + '.bai'), results_name)  

        # make tiny vcf files
        printtime('Making tiny vcf files from %s' %', '.join(vcf_files))
        for vcf in vcf_files:
            assert(vcf.endswith('.vcf'))
            vcf_for_variant = '%s_%s' %(vcf[:-4], base)
            args = vcf_split(os.path.join(path, vcf), vcf_for_variant, variant["chrom"], variant["pos"], WINDOW)
            #I don't think the error code that is returned can be trusted.
            vcf_status = subprocess.check_call(args, cwd=full_path)
            add_to_zip_list(to_zip, os.path.join(full_path, vcf_for_variant + ".recode.vcf"), results_name)  
        
        # make tiny bed files
        printtime('Making tiny bed files from %s' %', '.join(source_bed_files))
        for bed in source_bed_files:
            assert(bed.endswith('.bed'))
            bed_for_variant = os.path.join(full_path,os.path.basename(bed)[:-4] + "_" + base + '.bed')
            printtime("Converting " + bed + " to " + bed_for_variant)
            with open(bed,"r") as i:
                with open(bed_for_variant,"w") as o:
                    o.write(i.readline())
                    for line in i:
                        fields = line.strip().split('\t')
                        if len(fields) < 3:
                            continue
                        startpos = int(fields[1])
                        endpos = int(fields[2])
                        if fields[0] != variant["chrom"]:
                            continue
                        if startpos > int(variant["pos"]) + (WINDOW/2):
                            continue
                        if endpos < int(variant["pos"]) - (WINDOW/2):
                            continue
                        o.write(line)
            add_to_zip_list(to_zip, bed_for_variant, results_name)  

    #add bam stats to the zip
    add_to_zip_list(to_zip, os.path.join(full_path, prefix + "rawlib_stats.txt"), results_name)  
    if my_bam_dict['post_processed_bam'] is not None:
        add_to_zip_list(to_zip, os.path.join(full_path, prefix + "rawlib_ptrim_stats.txt"), results_name)  

    #parameters
    parameter_path = my_configutation['options'].serve_option('parameters_file')
    add_to_zip_list(to_zip, parameter_path, results_name)  

    #add the variants.json file
    add_to_zip_list(to_zip, os.path.join(full_path, "variants.json"), results_name)
    
    # make zip file
    status_update(path, "Creating ZIP")
    printtime("Generating final ZIP file")
    zip_path = os.path.join(full_path, "%s.zip" %results_name)    
    missing_files = []
    for source, dest in to_zip:
        try:
            vc_plugin.compress.make_zip(zip_path, source, arcname=dest, use_sys_zip = False)
        except:
            missing_files.append(source)
    
        if source.endswith(".vcf"):
             #so if it got here then we now the vcf was there, we can know try to bgzip and index it.
            try:
                #make the bgzip, same file name with .gz added to the end it also replaces the old file
                #yes it is redundant to include this file twice. but it should be tiny
                subprocess.check_call(["bgzip", source], cwd=full_path)
                subprocess.check_call(["tabix", "-f" , "-p", "vcf", source + ".gz"], cwd=full_path)
                vc_plugin.compress.make_zip(zip_path, source + '.gz', arcname = dest + '.gz', use_sys_zip = False)                
                vc_plugin.compress.make_zip(zip_path, source + '.gz.tbi', arcname = dest + '.gz.tbi', use_sys_zip = False)                
            except:
                missing_files.append(source + '.gz')
                missing_files.append(source + '.gz.tbi')

    #if there are missing vcfs add those to the zip
    if missing_files:
        printtime('Missing files: %s' %', '.join(missing_files))
        with open(os.path.join(full_path, "missing_files.txt"), "w+") as f:
            for missing_file in missing_files:
                f.write(missing_file + "\n")
        vc_plugin.compress.make_zip(zip_path, os.path.join(full_path, "missing_files.txt"), arcname = os.path.join(results_name, "missing_files.txt"), use_sys_zip = False) 

    #Now that everything is done write out the status file which will be checked by the VC JavaScript
    with open(os.path.join(path, "split_status.json"), "w+") as f:
        f.write(json.dumps({"split_status": "done", "url" : os.path.join(temp_path, results_name + ".zip")}))

def are_parameters_valid(bucket):
    return_dict = {'param_error_msg': [], 'debug_msg': []}
    try:
        # import from pluginMedia/parameter_sets/test_format.py
        parameter_sets_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pluginMedia/parameter_sets')
        if parameter_sets_dir not in sys.path:
            sys.path.append(parameter_sets_dir)
        from test_format import check_one_parameter            
        from test_format import custom_check
        
        # Load range.json
        description_json_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pluginMedia/configs/description.json')
        with open(description_json_path, 'rb') as f_json:
            description_json = json.load(f_json)
        
        # Note that base_set is stringified if it is sent by plugin api. Must be decoded by json.loads
        # But I will still let it handle the unstringified case.
        my_parameter_json = bucket["request_get"].get("base_set", "")
        if not isinstance(my_parameter_json, dict):           
            my_parameter_json = json.loads(my_parameter_json)
        if not my_parameter_json:
            return_dict['debug_msg'].append('Fail to get the requested base_set.')
            return return_dict
        
        # Check the following sections
        for section_key in ['torrent_variant_caller', 'long_indel_assembler', 'freebayes']:
            if section_key not in my_parameter_json:
                return_dict['debug_msg'].append('The section "%s" is not found in base_set.'%(section_key))
                continue
            for param_key, param_value in my_parameter_json[section_key].iteritems():
                if param_key not in description_json[section_key]:
                    return_dict['debug_msg'].append('The parameter "%s.%s" has no discription specified in %s' %(section_key, param_key, description_json_path))
                else:
                    try:
                        check_one_parameter(param_value, description_json[section_key][param_key])                    
                    except Exception as e_param:
                        return_dict['param_error_msg'].append('Invalid parameter "%s.%s": %s' %(section_key, param_key, e_param.message))
        try:
            custom_check(my_parameter_json)
        except Exception as e_param:
            return_dict['param_error_msg'].append(e_param.message)
    except Exception as e_debug:
        return_dict['debug_msg'].append(e_debug.message)
    return return_dict

if __name__ == '__main__':
    """
    extend.py main will do the data slicing, and spit out a zip
    """
    printtime('Slicing started using: ' + (' '.join(sys.argv)))
    #where the run data lives
    path = sys.argv[1]
    #name of the working dir used for the temp files
    temp_path = sys.argv[2]
    try:
        barcode = sys.argv[3]
    except IndexError:
        barcode = ""

    try:
        slicer_main(path, temp_path, barcode)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        sys.stdout.flush()
        sys.stderr.flush()        
        # If an error occures, I must update the status to tell allelesTable.js don't have to wait until timeout (1000 sec).
        status_update(path, 'failed', {'path': path, 'temp_path': temp_path})