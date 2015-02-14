# Copyright (C) 2014 Ion Torrent Systems, Inc. All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import print_function
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models
import time
import os
import os.path
import sys


class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        print("Symlinking old sigproc_results/ chip heat maps into the main report folder for backward compatibility.")
        DMFileStat = orm['rundb.DMFileStat']
        Rig = orm['rundb.Rig']

        rigs = dict((r.name, r) for r in Rig.objects.all().select_related('location'))

        def get_path(report):
            """We can't call code outside the migration and standard library,
            so this re-implements a version of the report path finding code,
            but it caches the rigs so that we only have to query them once.
            """
            if not report.reportLink or report.reportLink.endswith('.php') or report.reportLink.endswith('.html'):
                return None
            else:
                report_directory = os.path.basename(os.path.abspath(report.reportLink))

            pgm_name = report.experiment.pgmName
            if pgm_name in rigs:
                loc_name = rigs[pgm_name].location.name
                return os.path.join(report.reportstorage.dirPath, loc_name, report_directory)

        def queryset_iterator(queryset, chunksize=100):
            """Generator to iterate over a Queryset, chunksize elements at a time.

            This determines the size of queryset's results, and it then iteratively
            queries that number of results, chunksize elements at a time and then
            yields those records one at a time.  Due to the iterative nature of  these
            queries, it cannot be guaranteed that elements are not added, removed, or
            modified during querying.  Querysets with no ordering will be order_by pk.
            """
            current = 0
            count = queryset.count()
            if not queryset.ordered:
                queryset = queryset.order_by('pk')
            while current < count:
                for row in queryset[current:current + chunksize]:
                    yield row
                current += chunksize

        results = DMFileStat.objects.select_related('result', "result__reportstorage", "result__experiment", "result__experiment__rig").filter(dmfileset__type='Output Files').exclude(action_state__in=['AG','DG','AD','DD'])
        chip_count = 0
        n=0
        error_counts = {}
        last_time = time.time()
        print("Checking {0:d} results\n".format(results.count()))
        print("Checked  Linked")
        for n, d in enumerate(queryset_iterator(results)):
            at_least_one = False
            at_least_one_error = set()
            now = time.time()
            if now - last_time >= 1:
                print("\r{0:<8d} {1:<8d}".format(n, chip_count), end='')
                sys.stdout.flush()
                last_time = now
            report = d.result
            root_path = get_path(report)
            if root_path:
                file_names = [
                    'Bead_density_1000.png',
                    'Bead_density_200.png',
                    'Bead_density_70.png',
                    'Bead_density_20.png',
                    'Bead_density_raw.png',
                    'Bead_density_contour.png',
                ]
                for file_name in file_names:
                    root_file_path = os.path.join(root_path, file_name)
                    if not os.path.exists(root_file_path):
                        sp_file_path = os.path.join(root_path, "sigproc_results", file_name)
                        if os.path.exists(sp_file_path):
                            try:
                                os.symlink(sp_file_path, root_file_path)
                                at_least_one = True
                            except OSError as err:
                                if err.errno not in at_least_one_error:
                                    at_least_one_error.add(err.errno)
                                    error_counts[err.errno] = error_counts.get(err.errno, 0) + 1
                if at_least_one:
                    chip_count += 1
        print('')
        print("{0} of {1} chip run were symlinked.".format(chip_count, n+1))
        if error_counts:
            print("! There were {0} OS errors during migration !".format(sum(error_counts.values())))
        for errnumber, count in sorted(error_counts.items()):
            print("{0:<8d} reports had an OS Error '{1}'".format(count, os.strerror(errnumber)))


    def backwards(self, orm):
        """Phone this in.  There's no reason to hit the disk for every result in
        the entire system to delete these symlinks"""
        pass

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Group']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': u"orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'rundb.analysisargs': {
            'Meta': {'object_name': 'AnalysisArgs'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'alignmentargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'analysisargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'basecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'beadfindargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'calibrateargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'chipType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'chip_default': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'libraryKitName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'prebasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'prethumbnailbasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'samplePrepKitName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'sequenceKitName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'templateKitName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'thumbnailalignmentargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailanalysisargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailbasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailbeadfindargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailcalibrateargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'})
        },
        u'rundb.analysismetrics': {
            'Meta': {'object_name': 'AnalysisMetrics'},
            'adjusted_addressable': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'amb': ('django.db.models.fields.IntegerField', [], {}),
            'bead': ('django.db.models.fields.IntegerField', [], {}),
            'dud': ('django.db.models.fields.IntegerField', [], {}),
            'empty': ('django.db.models.fields.IntegerField', [], {}),
            'excluded': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ignored': ('django.db.models.fields.IntegerField', [], {}),
            'keypass_all_beads': ('django.db.models.fields.IntegerField', [], {}),
            'lib': ('django.db.models.fields.IntegerField', [], {}),
            'libFinal': ('django.db.models.fields.IntegerField', [], {}),
            'libKp': ('django.db.models.fields.IntegerField', [], {}),
            'libLive': ('django.db.models.fields.IntegerField', [], {}),
            'libMix': ('django.db.models.fields.IntegerField', [], {}),
            'lib_pass_basecaller': ('django.db.models.fields.IntegerField', [], {}),
            'lib_pass_cafie': ('django.db.models.fields.IntegerField', [], {}),
            'live': ('django.db.models.fields.IntegerField', [], {}),
            'loading': ('django.db.models.fields.FloatField', [], {'default': '0.0'}),
            'pinned': ('django.db.models.fields.IntegerField', [], {}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'analysismetrics_set'", 'to': u"orm['rundb.Results']"}),
            'sysCF': ('django.db.models.fields.FloatField', [], {}),
            'sysDR': ('django.db.models.fields.FloatField', [], {}),
            'sysIE': ('django.db.models.fields.FloatField', [], {}),
            'tf': ('django.db.models.fields.IntegerField', [], {}),
            'tfFinal': ('django.db.models.fields.IntegerField', [], {}),
            'tfKp': ('django.db.models.fields.IntegerField', [], {}),
            'tfLive': ('django.db.models.fields.IntegerField', [], {}),
            'tfMix': ('django.db.models.fields.IntegerField', [], {}),
            'total': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'washout': ('django.db.models.fields.IntegerField', [], {}),
            'washout_ambiguous': ('django.db.models.fields.IntegerField', [], {}),
            'washout_dud': ('django.db.models.fields.IntegerField', [], {}),
            'washout_library': ('django.db.models.fields.IntegerField', [], {}),
            'washout_live': ('django.db.models.fields.IntegerField', [], {}),
            'washout_test_fragment': ('django.db.models.fields.IntegerField', [], {})
        },
        u'rundb.applicationgroup': {
            'Meta': {'object_name': 'ApplicationGroup'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '127'}),
            'uid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'})
        },
        u'rundb.applproduct': {
            'Meta': {'object_name': 'ApplProduct'},
            'applType': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.RunType']"}),
            'barcodeKitSelectableType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'defaultAvalancheSequencingKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'avalancheSeqKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultAvalancheTemplateKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'avalancheTemplateKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultBarcodeKitName': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'defaultChipType': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'defaultControlSeqKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'controlSeqKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultFlowCount': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'defaultGenomeRefName': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'defaultHotSpotRegionBedFileName': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'defaultIonChefPrepKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ionChefPrepKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultIonChefSequencingKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ionChefSeqKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultLibraryKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'libKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultPairedEndAdapterKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'peAdapterKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultPairedEndLibraryKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'peLibKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultPairedEndSequencingKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'peSeqKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultSamplePrepKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'samplePrepKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultSequencingKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'seqKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'defaultTargetRegionBedFileName': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'defaultTemplateKit': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'templateKit_applProduct_set'", 'null': 'True', 'to': u"orm['rundb.KitInfo']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instrumentType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isBarcodeKitSelectionRequired': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isControlSeqTypeBySampleSupported': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isDefault': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isDefaultBarcoded': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isDefaultPairedEnd': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isDualNucleotideTypeBySampleSupported': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isHotspotRegionBEDFileSuppported': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isPairedEndSupported': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isReferenceBySampleSupported': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isSamplePrepKitSupported': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isTargetRegionBEDFileSupported': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isTargetTechniqueSelectionSupported': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isVisible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'productCode': ('django.db.models.fields.CharField', [], {'default': "'any'", 'unique': 'True', 'max_length': '64'}),
            'productName': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'rundb.backup': {
            'Meta': {'object_name': 'Backup'},
            'backupDate': ('django.db.models.fields.DateTimeField', [], {}),
            'backupName': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'backupPath': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'experiment': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Experiment']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isBackedUp': ('django.db.models.fields.BooleanField', [], {})
        },
        u'rundb.backupconfig': {
            'Meta': {'object_name': 'BackupConfig'},
            'backup_directory': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '256', 'blank': 'True'}),
            'backup_threshold': ('django.db.models.fields.IntegerField', [], {'blank': 'True'}),
            'bandwidth_limit': ('django.db.models.fields.IntegerField', [], {'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'grace_period': ('django.db.models.fields.IntegerField', [], {'default': '72'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keepTN': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Location']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'number_to_backup': ('django.db.models.fields.IntegerField', [], {'blank': 'True'}),
            'online': ('django.db.models.fields.BooleanField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'timeout': ('django.db.models.fields.IntegerField', [], {'blank': 'True'})
        },
        u'rundb.chip': {
            'Meta': {'object_name': 'Chip'},
            'description': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instrumentType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'slots': ('django.db.models.fields.IntegerField', [], {})
        },
        u'rundb.content': {
            'Meta': {'object_name': 'Content'},
            'contentupload': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'contents'", 'to': u"orm['rundb.ContentUpload']"}),
            'file': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'contents'", 'to': u"orm['rundb.Publisher']"})
        },
        u'rundb.contentupload': {
            'Meta': {'object_name': 'ContentUpload'},
            'file_path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'publisher': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Publisher']", 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'})
        },
        u'rundb.cruncher': {
            'Meta': {'object_name': 'Cruncher'},
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'info': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'null': 'True', 'blank': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Location']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'U'", 'max_length': '8'})
        },
        u'rundb.dm_prune_field': {
            'Meta': {'object_name': 'dm_prune_field'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'rule': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64'})
        },
        u'rundb.dm_prune_group': {
            'Meta': {'object_name': 'dm_prune_group'},
            'editable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'ruleNums': ('django.db.models.fields.CommaSeparatedIntegerField', [], {'default': "''", 'max_length': '128', 'blank': 'True'})
        },
        u'rundb.dm_reports': {
            'Meta': {'object_name': 'dm_reports'},
            'autoAge': ('django.db.models.fields.IntegerField', [], {'default': '90'}),
            'autoPrune': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'autoType': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '32'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'pruneLevel': ('django.db.models.fields.CharField', [], {'default': "'No-op'", 'max_length': '128'})
        },
        u'rundb.dmfileset': {
            'Meta': {'object_name': 'DMFileSet'},
            'auto_action': ('django.db.models.fields.CharField', [], {'default': "'OFF'", 'max_length': '8'}),
            'auto_trigger_age': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'auto_trigger_usage': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'backup_directory': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'bandwidth_limit': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'del_empty_dir': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'exclude': ('iondb.rundb.separatedValuesField.SeparatedValuesField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'include': ('iondb.rundb.separatedValuesField.SeparatedValuesField', [], {'null': 'True', 'blank': 'True'}),
            'keepwith': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'null': 'True', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '48'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '8'})
        },
        u'rundb.dmfilestat': {
            'Meta': {'object_name': 'DMFileStat'},
            'action_state': ('django.db.models.fields.CharField', [], {'default': "'L'", 'max_length': '8'}),
            'archivepath': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'diskspace': ('django.db.models.fields.FloatField', [], {'null': 'True', 'blank': 'True'}),
            'dmfileset': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.DMFileSet']", 'null': 'True', 'blank': 'True'}),
            'files_in_use': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'preserve_data': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'result': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Results']", 'null': 'True', 'blank': 'True'}),
            'user_comment': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'})
        },
        u'rundb.dnabarcode': {
            'Meta': {'object_name': 'dnaBarcode'},
            'adapter': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'blank': 'True'}),
            'annotation': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'floworder': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'id_str': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'index': ('django.db.models.fields.IntegerField', [], {}),
            'length': ('django.db.models.fields.IntegerField', [], {'default': '0', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'score_cutoff': ('django.db.models.fields.FloatField', [], {'default': '0'}),
            'score_mode': ('django.db.models.fields.IntegerField', [], {'default': '0', 'blank': 'True'}),
            'sequence': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'type': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'})
        },
        u'rundb.emailaddress': {
            'Meta': {'object_name': 'EmailAddress'},
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'selected': ('django.db.models.fields.BooleanField', [], {})
        },
        u'rundb.eventlog': {
            'Meta': {'object_name': 'EventLog'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'content_type_set_for_eventlog'", 'to': u"orm['contenttypes.ContentType']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_pk': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'text': ('django.db.models.fields.TextField', [], {'max_length': '3000'}),
            'username': ('django.db.models.fields.CharField', [], {'default': "'ION'", 'max_length': '32', 'blank': 'True'})
        },
        u'rundb.experiment': {
            'Meta': {'object_name': 'Experiment'},
            'autoAnalyze': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'baselineRun': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'chipBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'chipType': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'cycles': ('django.db.models.fields.IntegerField', [], {}),
            'date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'diskusage': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'displayName': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'expCompInfo': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'expDir': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'expName': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'flows': ('django.db.models.fields.IntegerField', [], {}),
            'flowsInOrder': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ftpStatus': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isReverseRun': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'log': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'metaData': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'notes': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'pgmName': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'pinnedRepResult': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'plan': ('django.db.models.fields.related.OneToOneField', [], {'blank': 'True', 'related_name': "'experiment'", 'unique': 'True', 'null': 'True', 'to': u"orm['rundb.PlannedExperiment']"}),
            'platform': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'blank': 'True'}),
            'rawdatastyle': ('django.db.models.fields.CharField', [], {'default': "'single'", 'max_length': '24', 'null': 'True', 'blank': 'True'}),
            'reagentBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'repResult': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'+'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['rundb.Results']", 'blank': 'True', 'unique': 'True'}),
            'resultDate': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'db_index': 'True', 'blank': 'True'}),
            'reverse_primer': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'runMode': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'seqKitBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'sequencekitbarcode': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'sequencekitname': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'star': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'storageHost': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'storage_options': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '200'}),
            'unique': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'}),
            'usePreBeadfind': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'user_ack': ('django.db.models.fields.CharField', [], {'default': "'U'", 'max_length': '24'})
        },
        u'rundb.experimentanalysissettings': {
            'Meta': {'object_name': 'ExperimentAnalysisSettings'},
            'alignmentargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'analysisargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'barcodeKitName': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'barcodedSamples': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'null': 'True', 'blank': 'True'}),
            'base_recalibrate': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'basecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'beadfindargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'calibrateargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'experiment': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'eas_set'", 'null': 'True', 'to': u"orm['rundb.Experiment']"}),
            'hotSpotRegionBedFile': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isDuplicateReads': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isEditable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isOneTimeOverride': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'libraryKey': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'libraryKitBarcode': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'libraryKitName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'prebasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'prethumbnailbasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'realign': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'reference': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'selectedPlugins': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'targetRegionBedFile': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'tfKey': ('django.db.models.fields.CharField', [], {'max_length': '64', 'blank': 'True'}),
            'threePrimeAdapter': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'thumbnailalignmentargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailanalysisargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailbasecallerargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailbeadfindargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'}),
            'thumbnailcalibrateargs': ('django.db.models.fields.CharField', [], {'max_length': '5000', 'blank': 'True'})
        },
        u'rundb.filemonitor': {
            'Meta': {'object_name': 'FileMonitor'},
            'celery_task_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '60', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'local_dir': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512'}),
            'md5sum': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255'}),
            'progress': ('django.db.models.fields.BigIntegerField', [], {'default': '0'}),
            'size': ('django.db.models.fields.BigIntegerField', [], {'default': 'None', 'null': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '60'}),
            'tags': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '1024'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.CharField', [], {'max_length': '2000'})
        },
        u'rundb.fileserver': {
            'Meta': {'object_name': 'FileServer'},
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'filesPrefix': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Location']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'percentfull': ('django.db.models.fields.FloatField', [], {'default': '0.0', 'null': 'True', 'blank': 'True'})
        },
        u'rundb.globalconfig': {
            'Meta': {'object_name': 'GlobalConfig'},
            'auto_archive_ack': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'auto_archive_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'barcode_args': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'base_recalibrate': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'check_news_posts': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'default_flow_order': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'default_library_key': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'default_plugin_script': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'default_storage_options': ('django.db.models.fields.CharField', [], {'default': "'D'", 'max_length': '500', 'blank': 'True'}),
            'default_test_fragment_key': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'enable_auto_pkg_dl': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_auto_security': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_compendia_OCP': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'enable_nightly_email': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'enable_support_upload': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'enable_version_lock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'fasta_path': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mark_duplicates': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'plugin_folder': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'plugin_output_folder': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'realign': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'records_to_display': ('django.db.models.fields.IntegerField', [], {'default': '20', 'blank': 'True'}),
            'reference_path': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'sec_update_status': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            'selected': ('django.db.models.fields.BooleanField', [], {}),
            'site_name': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'}),
            'ts_update_status': ('django.db.models.fields.CharField', [], {'max_length': '256', 'blank': 'True'}),
            'web_root': ('django.db.models.fields.CharField', [], {'max_length': '500', 'blank': 'True'})
        },
        u'rundb.kitinfo': {
            'Meta': {'unique_together': "(('kitType', 'name'),)", 'object_name': 'KitInfo'},
            'applicationType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'categories': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '3024', 'blank': 'True'}),
            'flowCount': ('django.db.models.fields.PositiveIntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instrumentType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'kitType': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'}),
            'nucleotideType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'runMode': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'uid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '10'})
        },
        u'rundb.kitpart': {
            'Meta': {'unique_together': "(('barcode',),)", 'object_name': 'KitPart'},
            'barcode': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kit': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.KitInfo']"})
        },
        u'rundb.libmetrics': {
            'Genome_Version': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'Index_Version': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'Meta': {'object_name': 'LibMetrics'},
            'align_sample': ('django.db.models.fields.IntegerField', [], {}),
            'aveKeyCounts': ('django.db.models.fields.FloatField', [], {}),
            'cf': ('django.db.models.fields.FloatField', [], {}),
            'dr': ('django.db.models.fields.FloatField', [], {}),
            'duplicate_reads': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'genome': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'genomesize': ('django.db.models.fields.BigIntegerField', [], {}),
            'i100Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i100Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i100Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i100Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i100Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i150Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i150Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i150Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i150Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i150Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i200Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i200Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i200Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i200Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i200Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i250Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i250Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i250Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i250Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i250Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i300Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i300Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i300Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i300Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i300Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i350Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i350Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i350Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i350Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i350Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i400Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i400Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i400Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i400Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i400Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i450Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i450Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i450Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i450Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i450Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i500Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i500Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i500Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i500Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i500Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i50Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i50Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i50Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i50Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i50Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i550Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i550Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i550Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i550Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i550Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i600Q10_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i600Q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i600Q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i600Q47_reads': ('django.db.models.fields.IntegerField', [], {}),
            'i600Q7_reads': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ie': ('django.db.models.fields.FloatField', [], {}),
            'q10_alignments': ('django.db.models.fields.IntegerField', [], {}),
            'q10_longest_alignment': ('django.db.models.fields.IntegerField', [], {}),
            'q10_mapped_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q10_mean_alignment_length': ('django.db.models.fields.IntegerField', [], {}),
            'q17_alignments': ('django.db.models.fields.IntegerField', [], {}),
            'q17_longest_alignment': ('django.db.models.fields.IntegerField', [], {}),
            'q17_mapped_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q17_mean_alignment_length': ('django.db.models.fields.IntegerField', [], {}),
            'q20_alignments': ('django.db.models.fields.IntegerField', [], {}),
            'q20_longest_alignment': ('django.db.models.fields.IntegerField', [], {}),
            'q20_mapped_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q20_mean_alignment_length': ('django.db.models.fields.IntegerField', [], {}),
            'q47_alignments': ('django.db.models.fields.IntegerField', [], {}),
            'q47_longest_alignment': ('django.db.models.fields.IntegerField', [], {}),
            'q47_mapped_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q47_mean_alignment_length': ('django.db.models.fields.IntegerField', [], {}),
            'q7_alignments': ('django.db.models.fields.IntegerField', [], {}),
            'q7_longest_alignment': ('django.db.models.fields.IntegerField', [], {}),
            'q7_mapped_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q7_mean_alignment_length': ('django.db.models.fields.IntegerField', [], {}),
            'raw_accuracy': ('django.db.models.fields.FloatField', [], {}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'libmetrics_set'", 'to': u"orm['rundb.Results']"}),
            'sysSNR': ('django.db.models.fields.FloatField', [], {}),
            'totalNumReads': ('django.db.models.fields.IntegerField', [], {}),
            'total_mapped_reads': ('django.db.models.fields.BigIntegerField', [], {}),
            'total_mapped_target_bases': ('django.db.models.fields.BigIntegerField', [], {})
        },
        u'rundb.librarykey': {
            'Meta': {'object_name': 'LibraryKey'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'direction': ('django.db.models.fields.CharField', [], {'default': "'Forward'", 'max_length': '20'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isDefault': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'runMode': ('django.db.models.fields.CharField', [], {'default': "'single'", 'max_length': '64', 'blank': 'True'}),
            'sequence': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'rundb.librarykit': {
            'Meta': {'object_name': 'LibraryKit'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '3024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'sap': ('django.db.models.fields.CharField', [], {'max_length': '7', 'blank': 'True'})
        },
        u'rundb.location': {
            'Meta': {'object_name': 'Location'},
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'defaultlocation': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        u'rundb.message': {
            'Meta': {'object_name': 'Message'},
            'body': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'expires': ('django.db.models.fields.TextField', [], {'default': "'read'", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.IntegerField', [], {'default': '20'}),
            'route': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'status': ('django.db.models.fields.TextField', [], {'default': "'unread'", 'blank': 'True'}),
            'tags': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'time': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'})
        },
        u'rundb.monitordata': {
            'Meta': {'object_name': 'MonitorData'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'treeDat': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'})
        },
        u'rundb.newspost': {
            'Meta': {'object_name': 'NewsPost'},
            'guid': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2000', 'blank': 'True'}),
            'summary': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '300', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '140', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'})
        },
        u'rundb.plannedexperiment': {
            'Meta': {'ordering': "['-id']", 'object_name': 'PlannedExperiment'},
            'adapter': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'applicationGroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.ApplicationGroup']", 'null': 'True'}),
            'autoName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'categories': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'chefLastUpdate': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'chefLogPath': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'chefMessage': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'chefProgress': ('django.db.models.fields.FloatField', [], {'default': '0.0', 'blank': 'True'}),
            'chefStatus': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256', 'blank': 'True'}),
            'chipBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'controlSequencekitname': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'cycles': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'expName': ('django.db.models.fields.CharField', [], {'max_length': '128', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'irworkflow': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'isFavorite': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isPlanGroup': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isReusable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isReverseRun': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isSystem': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'isSystemDefault': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'latestEAS': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'+'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': u"orm['rundb.ExperimentAnalysisSettings']", 'blank': 'True', 'unique': 'True'}),
            'libkit': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'metaData': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'pairedEndLibraryAdapterName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'parentPlan': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'childPlan_set'", 'null': 'True', 'to': u"orm['rundb.PlannedExperiment']"}),
            'planDisplayedName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'planExecuted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'planExecutedDate': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'planGUID': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'planName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'planPGM': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'planShortID': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '5', 'null': 'True', 'blank': 'True'}),
            'planStatus': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'preAnalysis': ('django.db.models.fields.BooleanField', [], {}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'plans'", 'blank': 'True', 'to': u"orm['rundb.Project']"}),
            'qcValues': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['rundb.QCType']", 'null': 'True', 'through': u"orm['rundb.PlannedExperimentQC']", 'symmetrical': 'False'}),
            'reverse_primer': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'runMode': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'runType': ('django.db.models.fields.CharField', [], {'default': "'GENS'", 'max_length': '512'}),
            'runname': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'sampleGrouping': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['rundb.SampleGroupType_CV']", 'null': 'True', 'blank': 'True'}),
            'samplePrepKitName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'sampleSet': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'plans'", 'null': 'True', 'to': u"orm['rundb.SampleSet']"}),
            'sampleSet_planIndex': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'sampleSet_planTotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'sampleSet_uid': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'sampleTubeLabel': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'seqKitBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'storageHost': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'storage_options': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '200'}),
            'templatingKitBarcode': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'templatingKitName': ('django.db.models.fields.CharField', [], {'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'usePostBeadfind': ('django.db.models.fields.BooleanField', [], {}),
            'usePreBeadfind': ('django.db.models.fields.BooleanField', [], {}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'})
        },
        u'rundb.plannedexperimentqc': {
            'Meta': {'unique_together': "(('plannedExperiment', 'qcType'),)", 'object_name': 'PlannedExperimentQC'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'plannedExperiment': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.PlannedExperiment']"}),
            'qcType': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.QCType']"}),
            'threshold': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'})
        },
        u'rundb.plugin': {
            'Meta': {'unique_together': "(('name', 'version'),)", 'object_name': 'Plugin'},
            'active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'autorun': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'autorunMutable': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'config': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'majorBlock': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512', 'db_index': 'True'}),
            'path': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'}),
            'pluginsettings': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'}),
            'script': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256', 'blank': 'True'}),
            'selected': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'status': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'default': "''", 'max_length': '256', 'blank': 'True'}),
            'userinputfields': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'null': 'True', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '256'})
        },
        u'rundb.pluginresult': {
            'Meta': {'ordering': "['-id']", 'object_name': 'PluginResult'},
            'apikey': ('django.db.models.fields.CharField', [], {'max_length': '256', 'null': 'True', 'blank': 'True'}),
            'config': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'endtime': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'inodes': ('django.db.models.fields.BigIntegerField', [], {'default': '-1'}),
            'jobid': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            'plugin': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Plugin']"}),
            'result': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'pluginresult_set'", 'to': u"orm['rundb.Results']"}),
            'size': ('django.db.models.fields.BigIntegerField', [], {'default': '-1'}),
            'starttime': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'store': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'})
        },
        u'rundb.project': {
            'Meta': {'object_name': 'Project'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'rundb.publisher': {
            'Meta': {'object_name': 'Publisher'},
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'global_meta': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '256'})
        },
        u'rundb.qctype': {
            'Meta': {'object_name': 'QCType'},
            'defaultThreshold': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maxThreshold': ('django.db.models.fields.PositiveIntegerField', [], {'default': '100'}),
            'minThreshold': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'qcName': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'})
        },
        u'rundb.qualitymetrics': {
            'Meta': {'object_name': 'QualityMetrics'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'q0_100bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q0_150bp_reads': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q0_50bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q0_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q0_max_read_length': ('django.db.models.fields.IntegerField', [], {}),
            'q0_mean_read_length': ('django.db.models.fields.FloatField', [], {}),
            'q0_median_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q0_mode_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q0_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q17_100bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q17_150bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q17_50bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q17_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q17_max_read_length': ('django.db.models.fields.IntegerField', [], {}),
            'q17_mean_read_length': ('django.db.models.fields.FloatField', [], {}),
            'q17_median_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q17_mode_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q17_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q20_100bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q20_150bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q20_50bp_reads': ('django.db.models.fields.IntegerField', [], {}),
            'q20_bases': ('django.db.models.fields.BigIntegerField', [], {}),
            'q20_max_read_length': ('django.db.models.fields.FloatField', [], {}),
            'q20_mean_read_length': ('django.db.models.fields.IntegerField', [], {}),
            'q20_median_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q20_mode_read_length': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'q20_reads': ('django.db.models.fields.IntegerField', [], {}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'qualitymetrics_set'", 'to': u"orm['rundb.Results']"})
        },
        u'rundb.referencegenome': {
            'Meta': {'ordering': "['short_name']", 'object_name': 'ReferenceGenome'},
            'celery_task_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '60', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'enabled': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'file_monitor': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['rundb.FileMonitor']", 'unique': 'True', 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'identity_hash': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '40', 'null': 'True', 'blank': 'True'}),
            'index_version': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'notes': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'reference_path': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'short_name': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'species': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'verbose_error': ('django.db.models.fields.CharField', [], {'max_length': '3000', 'blank': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'})
        },
        u'rundb.remoteaccount': {
            'Meta': {'object_name': 'RemoteAccount'},
            'access_token': ('django.db.models.fields.CharField', [], {'max_length': '2048', 'null': 'True', 'blank': 'True'}),
            'account_label': ('django.db.models.fields.CharField', [], {'default': "'Unnamed Account'", 'max_length': '64'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'refresh_token': ('django.db.models.fields.CharField', [], {'max_length': '2048', 'null': 'True', 'blank': 'True'}),
            'remote_resource': ('django.db.models.fields.CharField', [], {'max_length': '2048'}),
            'token_expires': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'user_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'})
        },
        u'rundb.reportstorage': {
            'Meta': {'object_name': 'ReportStorage'},
            'default': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'dirPath': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'webServerPath': ('django.db.models.fields.CharField', [], {'max_length': '200'})
        },
        u'rundb.results': {
            'Meta': {'object_name': 'Results'},
            'analysisVersion': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'analysismetrics': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['rundb.AnalysisMetrics']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'autoExempt': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'diskusage': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'eas': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'results_set'", 'null': 'True', 'to': u"orm['rundb.ExperimentAnalysisSettings']"}),
            'experiment': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'results_set'", 'to': u"orm['rundb.Experiment']"}),
            'fastqLink': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'framesProcessed': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'libmetrics': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['rundb.LibMetrics']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'log': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'metaData': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'parentIDs': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'processedCycles': ('django.db.models.fields.IntegerField', [], {}),
            'processedflows': ('django.db.models.fields.IntegerField', [], {}),
            'projects': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'results'", 'symmetrical': 'False', 'to': u"orm['rundb.Project']"}),
            'qualitymetrics': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['rundb.QualityMetrics']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'reference': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'}),
            'reportLink': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'reportStatus': ('django.db.models.fields.CharField', [], {'default': "'Nothing'", 'max_length': '64', 'null': 'True'}),
            'reportstorage': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'storage'", 'null': 'True', 'to': u"orm['rundb.ReportStorage']"}),
            'representative': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'resultsName': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'resultsType': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'runid': ('django.db.models.fields.CharField', [], {'max_length': '10', 'blank': 'True'}),
            'sffLink': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'status': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'tfFastq': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'tfSffLink': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'timeStamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'timeToComplete': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        u'rundb.rig': {
            'Meta': {'object_name': 'Rig'},
            'alarms': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'}),
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ftppassword': ('django.db.models.fields.CharField', [], {'default': "'ionguest'", 'max_length': '64'}),
            'ftprootdir': ('django.db.models.fields.CharField', [], {'default': "'results'", 'max_length': '64'}),
            'ftpserver': ('django.db.models.fields.CharField', [], {'default': "'192.168.201.1'", 'max_length': '128'}),
            'ftpusername': ('django.db.models.fields.CharField', [], {'default': "'ionguest'", 'max_length': '64'}),
            'host_address': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'last_clean_date': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'last_experiment': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'last_init_date': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'location': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Location']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200', 'primary_key': 'True'}),
            'serial': ('django.db.models.fields.CharField', [], {'max_length': '24', 'null': 'True', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'updateflag': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'updatehome': ('django.db.models.fields.CharField', [], {'default': "'192.168.201.1'", 'max_length': '256'}),
            'version': ('django.db.models.fields.TextField', [], {'default': "'{}'", 'blank': 'True'})
        },
        u'rundb.runscript': {
            'Meta': {'object_name': 'RunScript'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'script': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'rundb.runtype': {
            'Meta': {'object_name': 'RunType'},
            'alternate_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'null': 'True', 'blank': 'True'}),
            'applicationGroups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'applications'", 'null': 'True', 'to': u"orm['rundb.ApplicationGroup']"}),
            'barcode': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True', 'blank': 'True'}),
            'nucleotideType': ('django.db.models.fields.CharField', [], {'default': "'dna'", 'max_length': '64', 'blank': 'True'}),
            'runType': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '512'})
        },
        u'rundb.sample': {
            'Meta': {'unique_together': "(('name', 'externalId'),)", 'object_name': 'Sample'},
            'date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'displayedName': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'experiments': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'samples'", 'null': 'True', 'to': u"orm['rundb.Experiment']"}),
            'externalId': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '127', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'})
        },
        u'rundb.sampleannotation_cv': {
            'Meta': {'object_name': 'SampleAnnotation_CV'},
            'annotationType': ('django.db.models.fields.CharField', [], {'max_length': '127'}),
            'iRAnnotationType': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'iRValue': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isIRCompatible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sampleGroupType_CV': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'sampleAnnotation_set'", 'null': 'True', 'to': u"orm['rundb.SampleGroupType_CV']"}),
            'uid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '127', 'blank': 'True'})
        },
        u'rundb.sampleattribute': {
            'Meta': {'object_name': 'SampleAttribute'},
            'creationDate': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_sampleAttribute'", 'to': u"orm['auth.User']"}),
            'dataType': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sampleAttributes'", 'to': u"orm['rundb.SampleAttributeDataType']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'displayedName': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '127'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isMandatory': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'lastModifiedDate': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'lastModifiedUser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'lastModified_sampleAttribute'", 'to': u"orm['auth.User']"})
        },
        u'rundb.sampleattributedatatype': {
            'Meta': {'object_name': 'SampleAttributeDataType'},
            'dataType': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'rundb.sampleattributevalue': {
            'Meta': {'object_name': 'SampleAttributeValue'},
            'creationDate': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_sampleAttributeValue'", 'to': u"orm['auth.User']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastModifiedDate': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'lastModifiedUser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'lastModified_sampleAttributeValue'", 'to': u"orm['auth.User']"}),
            'sample': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sampleAttributeValues'", 'to': u"orm['rundb.Sample']"}),
            'sampleAttribute': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'samples'", 'to': u"orm['rundb.SampleAttribute']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'})
        },
        u'rundb.samplegrouptype_cv': {
            'Meta': {'object_name': 'SampleGroupType_CV'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'displayedName': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '127'}),
            'iRAnnotationType': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'iRValue': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isActive': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'isIRCompatible': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'uid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'})
        },
        u'rundb.sampleset': {
            'Meta': {'object_name': 'SampleSet'},
            'SampleGroupType_CV': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sampleSets'", 'null': 'True', 'to': u"orm['rundb.SampleGroupType_CV']"}),
            'creationDate': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_sampleSet'", 'to': u"orm['auth.User']"}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'null': 'True', 'blank': 'True'}),
            'displayedName': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '127'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastModifiedDate': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'lastModifiedUser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'lastModified_sampleSet'", 'to': u"orm['auth.User']"}),
            'status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '512', 'blank': 'True'})
        },
        u'rundb.samplesetitem': {
            'Meta': {'object_name': 'SampleSetItem'},
            'cancerType': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'cellularityPct': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'creationDate': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'created_sampleSetItem'", 'to': u"orm['auth.User']"}),
            'dnabarcode': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.dnaBarcode']", 'null': 'True', 'blank': 'True'}),
            'gender': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'lastModifiedDate': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'lastModifiedUser': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'lastModified_sampleSetItem'", 'to': u"orm['auth.User']"}),
            'relationshipGroup': ('django.db.models.fields.IntegerField', [], {}),
            'relationshipRole': ('django.db.models.fields.CharField', [], {'max_length': '127', 'null': 'True', 'blank': 'True'}),
            'sample': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sampleSets'", 'to': u"orm['rundb.Sample']"}),
            'sampleSet': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'samples'", 'to': u"orm['rundb.SampleSet']"})
        },
        u'rundb.sequencingkit': {
            'Meta': {'object_name': 'SequencingKit'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '3024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'}),
            'sap': ('django.db.models.fields.CharField', [], {'max_length': '7', 'blank': 'True'})
        },
        u'rundb.supportupload': {
            'Meta': {'object_name': 'SupportUpload'},
            'account': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.RemoteAccount']"}),
            'celery_task_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '60', 'blank': 'True'}),
            'contact_email': ('django.db.models.fields.EmailField', [], {'default': "''", 'max_length': '75'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'file': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['rundb.FileMonitor']", 'unique': 'True', 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'local_message': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2048', 'blank': 'True'}),
            'local_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'result': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['rundb.Results']", 'null': 'True', 'blank': 'True'}),
            'ticket_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'ticket_message': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '2048', 'blank': 'True'}),
            'ticket_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['auth.User']"})
        },
        u'rundb.template': {
            'Meta': {'object_name': 'Template'},
            'comments': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isofficial': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'sequence': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'rundb.tfmetrics': {
            'HPAccuracy': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'Meta': {'object_name': 'TFMetrics'},
            'Q10Histo': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'Q10Mean': ('django.db.models.fields.FloatField', [], {}),
            'Q10ReadCount': ('django.db.models.fields.FloatField', [], {}),
            'Q17Histo': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'Q17Mean': ('django.db.models.fields.FloatField', [], {}),
            'Q17ReadCount': ('django.db.models.fields.FloatField', [], {}),
            'SysSNR': ('django.db.models.fields.FloatField', [], {}),
            'aveKeyCount': ('django.db.models.fields.FloatField', [], {}),
            'corrHPSNR': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keypass': ('django.db.models.fields.FloatField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'number': ('django.db.models.fields.FloatField', [], {}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'tfmetrics_set'", 'to': u"orm['rundb.Results']"}),
            'sequence': ('django.db.models.fields.CharField', [], {'max_length': '512'})
        },
        u'rundb.threeprimeadapter': {
            'Meta': {'object_name': 'ThreePrimeadapter'},
            'chemistryType': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'blank': 'True'}),
            'description': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'direction': ('django.db.models.fields.CharField', [], {'default': "'Forward'", 'max_length': '20'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'isDefault': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'runMode': ('django.db.models.fields.CharField', [], {'default': "'single'", 'max_length': '64', 'blank': 'True'}),
            'sequence': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'uid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '32'})
        },
        u'rundb.usereventlog': {
            'Meta': {'object_name': 'UserEventLog'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'text': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'timeStamp': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'upload': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'logs'", 'to': u"orm['rundb.ContentUpload']"})
        },
        u'rundb.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_read_news_post': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1984, 11, 5, 0, 0)'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '93'}),
            'note': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'phone_number': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'default': "'user'", 'max_length': '256'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': u"orm['auth.User']", 'unique': 'True'})
        },
        u'rundb.variantfrequencies': {
            'Meta': {'object_name': 'VariantFrequencies'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '3024', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512', 'blank': 'True'})
        }
    }

    complete_apps = ['rundb']
    symmetrical = True
