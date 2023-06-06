/* A class for populating the data set information card */ 
class DataSetInformationCardPopulator{
    constructor(){
        this.data_set_meta_info_holder = $("#dataset_info_collapse");
        this.data_set_meta_info = getDataSetMetaData();
        this.data_set_meta_info_properties_array = [
            "num_datasets", "names(s)", "UID(s)", "num_samples", "time_stamp(s)", "average_sequencing_depth",
            "average_Sym_sequences_absolute", "average_Sym_sequences_unique"
        ];
        this.data_set_meta_info_prop_to_key_dict = {
            "num_datasets": "num_associated_data_sets",
            "names(s)": "ds_names",
            "UID(s)": "ds_uids",
            "num_samples": "num_samples",
            "time_stamp(s)": "ds_time_stamps",
            "average_sequencing_depth": "seq_depth_av",
            "average_Sym_sequences_absolute": "sym_seqs_absolute_av",
            "average_Sym_sequences_unique": "sym_seqs_unique_av"
        };
    }
    populate_data_set_information_card_fields(){
        for (let i = 0; i < this.data_set_meta_info_properties_array.length; i++) {
            this.data_set_meta_info_holder.find(".row").append(`<div class="col-sm-6 data_property">${this.data_set_meta_info_properties_array[i] + ':'}</div>`);
            this.data_set_meta_info_holder.find(".row").append(`<div class="col-sm-6 data_value">${this.data_set_meta_info[this.data_set_meta_info_prop_to_key_dict[this.data_set_meta_info_properties_array[i]]]}</div>`);
        }
    }
}

/* A class for populating the data set information card */ 
class DataAnalysisInformationPopulator{
    constructor(){
        this.data_analysis_meta_info = getDataAnalysisMetaInfo();
        this.data_analysis_meta_info_properties_array = [
            "name", "UID", "time_stamp", "samples_in_output", "sample_in_analysis",
            "unique_profiles_local", "profile_instances_local", "unique_profiles_analysis", "profile_instances_analysis"
        ];
        this.data_analysis_meta_info_prop_to_key_dict = {
            "name": "name",
            "UID": "uid",
            "time_stamp": "time_stamp",
            "samples_in_output": "samples_in_output",
            "sample_in_analysis": "samples_in_analysis",
            "unique_profiles_local": "unique_profile_local",
            "profile_instances_local": "instance_profile_local",
            "unique_profiles_analysis": "unique_profile_analysis",
            "profile_instances_analysis": "instances_profile_analysis"
        };
        this.data_analysis_meta_info_holder = $("#analysis_info_collapse");
        
    }
    populate_data_analysis_information_card_fields(){
        for (let i = 0; i < this.data_analysis_meta_info_properties_array.length; i++) {
            this.data_analysis_meta_info_holder.find(".row").append(`<div class="col-sm-6 data_property">${this.data_analysis_meta_info_properties_array[i] + ':'}</div>`);
            this.data_analysis_meta_info_holder.find(".row").append(`<div class="col-sm-6 data_value">${this.data_analysis_meta_info[this.data_analysis_meta_info_prop_to_key_dict[this.data_analysis_meta_info_properties_array[i]]]}</div>`);
        }
    }
}

/* A class for populating the downloadable resources */
class DownloadResourcesPopulator{
    constructor(){
        this.data_file_paths = getDataFilePaths();
        this.data_file_paths_keys = Object.keys(this.data_file_paths);
        this.clade_array = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'];
        this.dist_type_array = ['unifrac', 'braycurtis'];
        this.sample_profile_array = ['sample', 'profile'];
        this.sqrt_array = ['sqrt', 'no_sqrt'];
        // We have both profile_absolute_meta_only_count and profile_meta in here
        // This is because we have moved from outputing two profile meta only files
        // (relative and abosulte) to only one (because they are identical).
        // We removed the profile_relative_meta_only_count so that this is not displayed
        // for the older outputs. For the newer outputs profile_absolute_meta_only_count won't exist
        // because we renamed it profile_meta. As such this will be output.
        this.file_type_array = [
            "post_med_absolute_abund_meta_count", "post_med_absolute_abund_only_count",
            "post_med_absolute_meta_only_count", "post_med_relative_abund_meta_count",
            "post_med_relative_abund_only_count", "post_med_relative_meta_only_count",
            "post_med_fasta", "post_med_additional_info", "pre_med_absolute_count",
            "pre_med_relative_count", "pre_med_fasta", "profile_absolute_abund_meta_count",
            "profile_absolute_abund_only_count", "profile_absolute_meta_only_count",
            "profile_relative_abund_meta_count", "profile_relative_abund_only_count",
            "profile_meta", "profile_additional_info_file"
        ];
    }
    populate_downloads(){
        this._populate_explicit_file_types();
        this._populate_dist_and_pcoa_files_dynamically();
    }

    _populate_explicit_file_types(){
        // Popualate the files which can be found in the file_type_array
        // A seperate method will be used to populate the distance and pcoa files
        // as these will be searched for dynamically
        for (let i = 0; i < this.file_type_array.length; i++) {
            // Go in order of the file_type_array being sure to check if the file in question
            // is found in the output of this study
            if (this.data_file_paths_keys.includes(this.file_type_array[i])) {
                $("#resource_download_info_collapse").find(".row").append(`<div class="col-sm-6 data_property">${this.file_type_array[i] + ':'}</div>`);
                $("#resource_download_info_collapse").find(".row").append(`<div class="col-sm-6 data_value"><a href="/get_study_data/${study_to_load}/${this.data_file_paths[this.file_type_array[i]]}.zip" download>${this.data_file_paths[this.file_type_array[i]]}</a></div>`);
            }
        };
    }

    _populate_dist_and_pcoa_files_dynamically(){
        // Then we will iterate through the possible distance files that may exist and populate those
        // First go by clade, then sample/profile, then dist type
        // NB here we have to take into account that there will have been analyses conducted that did not output both types of
        // distance files (i.e. braycurtis and unifrac) and they also will not have output both sqrt and no sqrt versions.
        // In fact there will be no sqrt indication at all in the file names in the older analyses.
        for (let i = 0; i < this.clade_array.length; i++) {
            for (let j = 0; j < this.sample_profile_array.length; j++) {
                for (let k = 0; k < this.dist_type_array.length; k++) {
                    
                    // We will do a check here for the older style of files that do not have the sqrt transformation indication
                    let f_name_dist_no_transformation = "btwn_" + this.sample_profile_array[j] + "_" + this.dist_type_array[k] + "_" + this.clade_array[i] + "_dist";
                    this._populate_dist_pcoa_rows_in_download_card(f_name_dist_no_transformation);
                    let f_name_pcoa_no_transformation = "btwn_" + this.sample_profile_array[j] + "_" + this.dist_type_array[k] + "_" + this.clade_array[i] + "_pcoa";
                    this._populate_dist_pcoa_rows_in_download_card(f_name_pcoa_no_transformation);

                    // Then check for the files that have the sqrt or no_sqrt infomation in the file name
                    for (let m = 0; m < this.sqrt_array.length; m++) {
                        
                        let f_name_dist_w_transformation = "btwn_" + this.sample_profile_array[j] + "_" + this.dist_type_array[k] + "_" + this.clade_array[i] + "_dist_" + this.sqrt_array[m];
                        this._populate_dist_pcoa_rows_in_download_card(f_name_dist_w_transformation);
                        
                        let f_name_pcoa_w_transformation = "btwn_" + this.sample_profile_array[j] + "_" + this.dist_type_array[k] + "_" + this.clade_array[i] + "_pcoa_" + this.sqrt_array[m];
                        this._populate_dist_pcoa_rows_in_download_card(f_name_pcoa_w_transformation);

                    }
                }
            }
        }
    }

    _populate_dist_pcoa_rows_in_download_card(file_name){
        if (this.data_file_paths_keys.includes(file_name)) {
            $("#resource_download_info_collapse").find(".row").append(`<div class="col-sm-6 data_property">${file_name + ':'}</div>`);
            $("#resource_download_info_collapse").find(".row").append(`<div class="col-sm-6 data_value"><a href="/get_study_data/${study_to_load}/${this.data_file_paths[file_name]}.zip" download>${this.data_file_paths[file_name]}</a></div>`);
        }
    }
};