from sp_app import db
from sp_app.models import DataSetSample, Study, ReferenceSequence, DataSetSampleSequencePM, DataSetSampleSequence, Study__DataSetSample
import json
import sys
from sqlalchemy.orm.exc import NoResultFound
from datetime import datetime
import os
import subprocess
from sqlalchemy import distinct

class OutputResourceFastas:
    """
    In addition to syncing the database we should update the fasta resources on the index page.
    We want to have three different resources here.
    pre_MED
    post_MED
    DIVs
    Each of these will be a fasta file. for pre_MED and post_MED we want all the reference sqeuences found in
    all published Studies. DataSetSampleSequencePM and DataSetSampleSeqeunce respectively.
    For the DIVs, we have some named sequences in the SP database that may not have
    been found in a sample yet (because we initially populated the SP database with named sequences).
    As such to make this fasta we will output all named sequences, unless they a given sequences is
    only found in unpublished Studies. I.e. If the sequences is not found in a DataSetSample, then
    we put it in the fasta, if it is found in a number of DataSetSamples, and any of them are published
    then we put it in the fasta.

    Pseudo-code:
    Every time we run the sync, we can overwite the three fastas that are currently available.
    As well as the three fasta files we can also output an associated json info file.
    This json info file can hold as a dictionary the name of the resource, the description,
    the number of sequences, the number of published studies and the update date.
    """
    def __init__(self, cache=False):
        self.resource_dir = os.path.join(os.getcwd(), 'sp_app', 'static', 'resources')
        self.pre_med_unpublished_temp_path = os.path.join(self.resource_dir, "pre_med_unpublished_tmp")
        self._get_objects_from_db()
        self.pre_med_fasta_path = os.path.join(self.resource_dir, 'published_pre_med.fasta')
        self.post_med_fasta_path = os.path.join(self.resource_dir, 'published_post_med.fasta')
        self.div_fasta_path = os.path.join(self.resource_dir, 'published_div.fasta')
        self.json_path = os.path.join(self.resource_dir, 'resource_info.json')
        self.json_dict = {}
        
    def _get_objects_from_db(self):
        self.published_studies = [ps.id for ps in db.session.query(Study).filter(Study.is_published==True)]
        self.unpublished_studies = [ups.id for ups in db.session.query(Study).filter(Study.is_published==False)]
        
        print('Retrieving published DataSetSamples')
        self.published_data_set_samples = [dss.datasetsample_id for dss in db.session.query(Study__DataSetSample.c.datasetsample_id).filter(Study__DataSetSample.c.study_id.in_(self.published_studies)).distinct()]
        print(f'Retrieved {len(self.published_data_set_samples)} DataSetSamples')
        
        print('Retrieving unpublished DataSetSamples')
        self.unpublished_data_set_samples = [dss.datasetsample_id for dss in db.session.query(Study__DataSetSample.c.datasetsample_id).filter(Study__DataSetSample.c.study_id.in_(self.unpublished_studies)).distinct()]
        print(f'Retrieved {len(self.unpublished_data_set_samples)} DataSetSamples')

        # NB we timed if it would be quicker to return specific columns of ReferenceSequence rather than the
        # whole object, and surprisingly, it wasn't.
        print('Retrieving pre-MED seqs from published DataSetSamples')
        self.pre_med_reference_sequences_published = [_.reference_sequence_of_id for _ in db.session.query(DataSetSampleSequencePM.reference_sequence_of_id).filter(DataSetSampleSequencePM.data_set_sample_from_id.in_(self.published_data_set_samples)).distinct()]
        self.pre_med_reference_sequences_published = db.session.query(ReferenceSequence).filter(ReferenceSequence.id.in_(self.pre_med_reference_sequences_published)).all()
        print(f'Retrieved {len(self.pre_med_reference_sequences_published)} ReferenceSeqeuences')
        
        print('Retrieving post-MED seqs from published DataSetSamples')
        self.post_med_reference_sequences_published = [dsss.reference_sequence_of_id for dsss in db.session.query(DataSetSampleSequence.reference_sequence_of_id).filter(DataSetSampleSequence.data_set_sample_from_id.in_(self.published_data_set_samples)).distinct()]
        self.post_med_reference_sequences_published = db.session.query(ReferenceSequence).filter(ReferenceSequence.id.in_(self.post_med_reference_sequences_published)).all()
        print(f'Retrieved {len(self.published_data_set_samples)} ReferenceSeqeuences')

        # NB we were running out of memory on the Linode server when trying to work with the
        # ReferenceSequence objects. As such we will use only the list of IDs for the RefSeq objects

        print('Retrieving pre-MED seqs from unpublished DataSetSamples')
        self.pre_med_reference_sequence_ids_unpublished = [_.reference_sequence_of_id for _ in db.session.query(DataSetSampleSequencePM.reference_sequence_of_id).filter(DataSetSampleSequencePM.data_set_sample_from_id.in_(self.unpublished_data_set_samples)).distinct()]
        print(f'Identified {len(self.pre_med_reference_sequence_ids_unpublished)} ReferenceSequences')

    def _chunk_pre_med_ref_seq_unpub(self, list_of_ids):
        all_ids = list_of_ids
        all_ids.sort()
        count = 0
        while all_ids:
            chunk = all_ids[:200000]
            all_ids = all_ids[200000:]
            ref_seqs = db.session.query(ReferenceSequence).filter(
                ReferenceSequence.id.in_(chunk)).all()
            count += len(ref_seqs)
            with open(self.pre_med_unpublished_temp_path, "a") as f:
                for rs_obj in ref_seqs:
                    f.write(f'>{rs_obj}\n')
                    f.write(f'{rs_obj.sequence}\n')
        return count

    def make_fasta_resources(self):
        self._pre_med()
        self._post_med()
        self._div()
        self._populate_and_write_json_dict()

    def _populate_and_write_json_dict(self):
        """
        Populate the json dict with the information that we will display in the resources section
        for each of the alignments giving the number of samples and datasets and that sort of thing
        """
        self.json_dict['number_published_studies'] = len(self.published_studies)
        self.json_dict['published_data_set_samples'] = len(self.published_data_set_samples)
        self.json_dict['update_date'] = str(datetime.now())
        self.json_dict['num_pre_med_seqs'] = len(self.pre_med_reference_sequences_published)
        self.json_dict['num_post_med_seqs'] = len(self.post_med_reference_sequences_published)
        # Descriptions
        self.json_dict['published_pre_med_seqs_description'] = "Fasta file containing sequences from published " \
        "samples that have been through the SymPortal quality control pipeline but have not yet been " \
        f"through Minimum Entropy Decomposition. \n{len(self.pre_med_reference_sequences_published)} sequences, " \
        f"from {len(self.published_data_set_samples)} samples, from {len(self.published_studies)} published " \
        f"studies. Last updated: {str(datetime.now()).split()[0]}"
        
        self.json_dict['published_post_med_seqs_description'] = "Fasta file containing sequences from published " \
        "samples that have been through the SymPortal quality control pipeline and " \
        f"Minimum Entropy Decomposition. \n{len(self.post_med_reference_sequences_published)} sequences, " \
        f"from {len(self.published_data_set_samples)} samples, from {len(self.published_studies)} published " \
        f"studies. Last updated: {str(datetime.now()).split()[0]}"
        
        self.json_dict['published_named_seqs_description'] = "Fasta file containing sequences from the SymPortal database " \
        "that have a name associated to them. These sequences represent either sequences that the SymPortal database was seeded " \
        "with when it was first created (see associated MS for more details), or sequences that have been used " \
        "to define an ITS2 type profile (i.e. Defining Intragenomic [Seqeunce] Variant; DIVs) in a published study. Named sequences " \
        "held in the SymPortal database that are only found in unpublished datasets are not included in this fasta file. " \
        f"\nFasta contains {len(self.published_named_ref_seqs)} published sequences, " \
        f"from {len(self.published_data_set_samples)} samples, from {len(self.published_studies)} published " \
        f"studies. {len(self.withheld_divs)} named but unpublished sequences were withheld from this release. Last updated: {str(datetime.now()).split()[0]}"
        with open(self.json_path, 'w') as f:
            json.dump(self.json_dict, f)
        
    def _pre_med(self):
        print('Creating pre_MED_fasta')
        self._write_ref_seqs_to_path(path=self.pre_med_fasta_path, ref_seqs=self.pre_med_reference_sequences_published)

    def _post_med(self):
        print('\n\nCreating post_MED_fasta')
        self._write_ref_seqs_to_path(path=self.post_med_fasta_path, ref_seqs=self.post_med_reference_sequences_published)

    def _div(self):
        """The DIVs are a little more tricky.
        1 - Get all named seqs
        2 - Get all named seqs found in published studies
        3 - remove 2 from 1. This leaves us with unpublished and starter DIVs
        4 - Get divs from all unpublished studies (Will be massive)
        5 - for each DIV in 3, if not in 4, then this is safe to use
        """
        print('\n\nCreating DIV_fasta')
        #1
        # all_named_ref_seqs = list(ReferenceSequence.query.filter(ReferenceSequence.has_name==True).all())
        all_named_ref_seqs = db.session.query(ReferenceSequence).filter(ReferenceSequence.has_name==True)
        #2
        published_named_ref_seqs = [_ for _ in self.pre_med_reference_sequences_published if _.has_name]
        #3
        unpub_and_starter = list(set(all_named_ref_seqs).difference(published_named_ref_seqs))
        #4
        # It is unreasonable to work with every DataSet that is in the symportal_database,
        # Rather we will work with the unpublised Study objects. As symportal progresses
        # every submitted dataset will become a Study object
        # self.pre_med_reference_sequences is calculated in the __init__ so that it can be cached.
        # add the good DIVS directly to the published_named_ref_seqs_list
        withheld_divs = []
        for div in unpub_and_starter:
            if div.id not in self.pre_med_reference_sequence_ids_unpublished:
                published_named_ref_seqs.append(div)
            else:
                withheld_divs.append(div)
        self.withheld_divs = withheld_divs
        self.published_named_ref_seqs = published_named_ref_seqs
        self.json_dict['num_div_seqs'] = len(published_named_ref_seqs)
        self.json_dict['num_unpublished_divs'] = len(withheld_divs)
        self._write_ref_seqs_to_path(path=self.div_fasta_path, ref_seqs=published_named_ref_seqs)

    def _write_ref_seqs_to_path(self, path, ref_seqs):
        with open(path, 'w') as f:
            for rs_obj in ref_seqs:
                f.write(f'>{rs_obj}\n')
                f.write(f'{rs_obj.sequence}\n')
        # Then compress as this will be large
        subprocess.run(['gzip', '-f', path])

OutputResourceFastas().make_fasta_resources()