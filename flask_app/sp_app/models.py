from sp_app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sp_app import login

@login.user_loader
def load_user(id):
    return SPUser.query.get(int(id))

cladeCollectionType = db.Table('dbApp_cladecollectiontype',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('analysis_type_of_id', db.Integer, db.ForeignKey('dbApp_analysistype.id'), primary_key=True),
    db.Column('clade_collection_found_in_id', db.Integer, db.ForeignKey('dbApp_cladecollection.id'), primary_key=True),
    info={'bind_key': 'symportal_database'}
)

Study__DataSetSample = db.Table('dbApp_study_data_set_samples', 
    db.Column('id', db.Integer, primary_key=True),
    db.Column('datasetsample_id', db.Integer, db.ForeignKey('dbApp_datasetsample.id'), primary_key=True),
    db.Column('study_id', db.Integer, db.ForeignKey('dbApp_study.id'), primary_key=True),
    info={'bind_key': 'symportal_database'}
    )

SPUser__Study = db.Table('dbApp_user_studies',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('study_id', db.Integer, db.ForeignKey('dbApp_study.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('dbApp_user.id'), primary_key=True),
    info={'bind_key': 'symportal_database'}
    )

class SPDataSet(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_dataset'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    reference_fasta_database_used = db.Column(db.String(60), nullable=False)
    submitting_user = db.Column(db.String(100), nullable=False)
    submitting_user_email = db.Column(db.String(100), nullable=False)
    working_directory = db.Column(db.String(300), nullable=False)
    time_stamp = db.Column(db.String(100), nullable=False)
    loading_complete_time_stamp = db.Column(db.String(100), nullable=False)
    data_set_samples = db.relationship('DataSetSample', backref='dataset')
    def __str__(self):
        return self.name
    def __repr__(self):
        return f'<SPDataSet {self.name}>'

class DataSetSample(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_datasetsample'
    id = db.Column(db.Integer, primary_key=True)
    data_submission_from_id = db.Column(db.Integer, db.ForeignKey('dbApp_dataset.id'), nullable=False)
    clade_collections = db.relationship('CladeCollection', backref='dataset_sample')
    data_set_sample_sequences = db.relationship('DataSetSampleSequence', backref='datasetsample')
    data_set_sample_sequences_pm = db.relationship('DataSetSampleSequencePM', backref='datasetsample')
    name = db.Column(db.String(200), nullable=False)
    # This is the absolute number of sequences after make.contigs
    num_contigs = db.Column(db.Integer, default=0)
    # store the aboslute number of sequences after inital mothur QC i.e. before tax and size screening
    post_qc_absolute_num_seqs = db.Column(db.Integer, default=0)
    # This is the unique number of sequences after inital mothur QC i.e. before tax and size screening
    post_qc_unique_num_seqs = db.Column(db.Integer, default=0)
    # Absolute number of sequences after sequencing QC and screening for Symbiodinium (i.e. Symbiodinium only)
    absolute_num_sym_seqs = db.Column(db.Integer, default=0)
    # Same as above but the number of unique seqs
    unique_num_sym_seqs = db.Column(db.Integer, default=0)
    # store the abosolute number of sequenes that were not considered Symbiodinium
    non_sym_absolute_num_seqs = db.Column(db.Integer, default=0)
    # This is the number of unique sequences that were not considered Symbiodinium
    non_sym_unique_num_seqs = db.Column(db.Integer, default=0)
    # store the abosulte number of sequences that were lost during the size selection
    size_violation_absolute = db.Column(db.Integer, default=0)
    # store the unique number of sequences that were lost during the size screening
    size_violation_unique = db.Column(db.Integer, default=0)
    # store the number of absolute sequences remaining after MED
    post_med_absolute = db.Column(db.Integer, default=0)
    # store the number of unique sequences remaining after MED (nodes)
    post_med_unique = db.Column(db.Integer, default=0)
    error_in_processing = db.Column(db.Boolean, default=False)
    error_reason = db.Column(db.String(100), nullable=False)
    cladal_seq_totals = db.Column(db.String(5000), nullable=False)
    # Meta data for the sample
    sample_type = db.Column(db.String(50), nullable=False)
    host_phylum = db.Column(db.String(50), nullable=False)
    host_class = db.Column(db.String(50), nullable=False)
    host_order = db.Column(db.String(50), nullable=False)
    host_family = db.Column(db.String(50), nullable=False)
    host_genus = db.Column(db.String(50), nullable=False)
    host_species = db.Column(db.String(50), nullable=False)
    collection_latitude = db.Column(db.Numeric(11,8), nullable=False)
    collection_longitude = db.Column(db.Numeric(11,8), nullable=False)
    # do not use the django date field as this causes problems when trying to dump and load the database
    collection_date = db.Column(db.String(40), nullable=False)
    # store a string rather than a number as this may be given as a range e.g. 6 - 12
    collection_date = db.Column(db.String(40), nullable=False)

    def __str__(self):
        return self.name
    def __repr__(self):
        return f'<DataSetSample {self.name}>'

def set_creation_time_stamp_default():
    return str(datetime.now()).replace(' ', '_').replace(':', '-')

class Study(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_study'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), index=True, unique=True, nullable=False)
    title = db.Column(db.String(250), nullable=True)
    is_published = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(50), nullable=True)
    run_type = db.Column(db.String(50), default='remote')
    article_url = db.Column(db.String(250), nullable=True)
    display_online = db.Column(db.Boolean, default=False)
    data_url = db.Column(db.String(250), nullable=True)
    data_explorer = db.Column(db.Boolean, default=False)
    analysis = db.Column(db.Boolean, default=True)
    author_list_string = db.Column(db.String(500))
    additional_markers = db.Column(db.String(200))
    creation_time_stamp = db.Column(db.String(100), default=set_creation_time_stamp_default)
    data_set_samples = db.relationship('DataSetSample', secondary=Study__DataSetSample, lazy='dynamic',
     backref=db.backref('studies', lazy='dynamic'))
    # num_samples = self.get_num_samples()
    
    def __str__(self):
        return self.name
    def __repr__(self):
        return f'<Study {self.name}>'

    def get_num_samples(self):
        return len(list(self.data_set_samples))

class SPUser(UserMixin, db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), index=True, unique=True, nullable=False)
    studies = db.relationship('Study', secondary=SPUser__Study, lazy='dynamic',
     backref=db.backref('users', lazy='dynamic'))
    
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<SPUser {self.name}>'

class DataAnalysis(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_dataanalysis'
    id = db.Column(db.Integer, primary_key=True)
    analysis_types = db.relationship('AnalysisType', backref='data_analysis')
    # This will be a jsoned list of uids of the dataSubmissions that are included in this analysis
    list_of_data_set_uids = db.Column(db.String(500), nullable=True)
    # within_clade_cutoff = models.FloatField(default=0.04)
    within_clade_cutoff = db.Column(db.Float(), nullable=False)
    name = db.Column(db.String(500), nullable=True)
    # name = models.CharField(max_length=100, null=True)
    # description = models.CharField(max_length=5000, null=True)
    description = db.Column(db.String(5000), nullable=True)
    time_stamp = db.Column(db.String(100), nullable=False)
    submitting_user = db.Column(db.String(100), nullable=False)
    submitting_user_email = db.Column(db.String(100), nullable=False)
    analysis_complete_time_stamp = db.Column(db.String(100), nullable=False)

class CladeCollection(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_cladecollection'
    id = db.Column(db.Integer, primary_key=True)
    data_set_sample_from_id = db.Column(db.Integer, db.ForeignKey('dbApp_datasetsample.id'), nullable=False)
    analysis_types = db.relationship('AnalysisType', secondary=cladeCollectionType, backref=db.backref('clade_collections'))
    data_set_sample_sequences = db.relationship('DataSetSampleSequence', backref='cladecollection')
    # data_set_sample_from = models.ForeignKey(DataSetSample, on_delete=models.CASCADE, null=True)
    clade = db.Column(db.String(1), nullable=False)
    # the method below to get the footprint of the clade_collection_object is incredibly slow.
    # Hopefully a much faster way will be to store the ID's of the refseqs that make up the footprint
    # I will therefore store the reference uids in the field below
    footprint = db.Column(db.String(100000), nullable=False)

    def __str__(self):
        return self.datasetsample.name

class AnalysisType(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_analysistype'
    id = db.Column(db.Integer, primary_key=True)
    data_analysis_from_id = db.Column(db.Integer, db.ForeignKey('dbApp_dataanalysis.id'), nullable=False)
    # This should be a frozen set of referenceSequences
    # As this is not possible in a django field or jsonable
    # I will instead make it a string of reference sequence uids
    # I will make set and get methods for the footprint
    # This will be a list of refSeqs that make up the footprint in order of their abundance when type first defined
    # This is a commar separated string of the uids of the ref seqs that define the type
    ordered_footprint_list = db.Column(db.String(200), nullable=True)
    # Same for listOfMajs
    # set() of refseqs that are Majs in each of the CCs this type was initially identified in.
    # Note that this is therefore in no particular order
    majority_reference_sequence_set = db.Column(db.String(40), nullable=True)

    list_of_clade_collections = db.Column(db.String(100000), nullable=True)
    # This is a 2D list, a list for each clade collection in order of the listofCladeCollections
    # Within each list the absolute abundances of the defining seqs in order of ordered_footprint_list
    footprint_sequence_abundances = db.Column(db.String(100000), nullable=True)

    # Same as above but the proportion of the seqs to each other in the cladecollection.
    footprint_sequence_ratios = db.Column(db.String(100000), nullable=True)

    clade = db.Column(db.String(1), nullable=False)
    co_dominant = db.Column(db.Boolean, default=False)

    name = db.Column(db.String(1000), nullable=True)

    # The list of speceis that this type is associated with
    species = db.Column(db.String(200), nullable=True)

    # this list will keep track of which of the defining intras of this type are 'unlocked' i.e. at least one
    # of the instances of that intra were found at <5%. We will use this list to the 'artefact type creation'
    # This artefact_intras will hold a char string of comma separated ints that represent the id's of the
    # refseqs that are unlocked
    artefact_intras = db.Column(db.String(5000), default='')

    def get_ratio_list(self):
        return json.loads(self.footprint_sequence_ratios)

    def __str__(self):
        return self.name

class ReferenceSequence(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_referencesequence'
    id = db.Column(db.Integer, primary_key=True)
    data_set_sample_sequences = db.relationship('DataSetSampleSequence', backref='referencesequence', lazy='select')
    data_set_sample_sequences_pm = db.relationship('DataSetSampleSequencePM', backref='referencesequence', lazy='select')
    name = db.Column(db.String(30), default='noName')
    has_name = db.Column(db.Boolean, default=False)
    clade = db.Column(db.String(30))
    accession = db.Column(db.String(50), nullable=True)
    sequence = db.Column(db.String(500), nullable=False)

    def __str__(self):
        if self.has_name:
            return self.name
        else:
            return f'{self.id}_{self.clade}'

    def __repr__(self):
        if self.has_name:
            return self.name
        else:
            return f'{self.id}_{self.clade}'

class DataSetSampleSequence(db.Model):
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_datasetsamplesequence'
    id = db.Column(db.Integer, primary_key=True)
    # FKeys
    data_set_sample_from_id = db.Column(db.Integer, db.ForeignKey('dbApp_datasetsample.id'))
    clade_collection_found_in_id = db.Column(db.Integer, db.ForeignKey('dbApp_cladecollection.id'))
    reference_sequence_of_id = db.Column(db.Integer, db.ForeignKey('dbApp_referencesequence.id'))
    abundance = db.Column(db.Integer, default=0)

    def __str__(self):
        if self.referencesequence.has_name:
            return self.referencesequence.name
        else:
            return 'ID=' + str(self.id)

class DataSetSampleSequencePM(db.Model):
    # this is the pre-MED version of the DataSetSampleSequence object
    # its purpose is to keep track of the
    __bind_key__ = 'symportal_database'
    __tablename__ = 'dbApp_datasetsamplesequencepm'
    id = db.Column(db.Integer, primary_key=True)
    # FKeys
    data_set_sample_from_id = db.Column(db.Integer, db.ForeignKey('dbApp_datasetsample.id'))
    reference_sequence_of_id = db.Column(db.Integer, db.ForeignKey('dbApp_referencesequence.id'))
    abundance = db.Column(db.Integer, default=0)

    def __str__(self):
        if self.referencesequence.has_name:
            return self.referncesequence.name
        else:
            return 'ID=' + str(self.id)