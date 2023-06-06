$(document).ready(function () {

    /* Populate the tabs that display the information on the DataSet, the DataAnalysis
    and the resources that can be downloaded */
    const data_set_info_populator = new DataSetInformationCardPopulator();
    data_set_info_populator.populate_data_set_information_card_fields();

    if (analysis){ 
        const data_analysis_info_populator = new DataAnalysisInformationPopulator();
        data_analysis_info_populator.populate_data_analysis_information_card_fields();    
    }else{
        $("#analysis_meta_info_card").remove();
    }

    const download_popualtor = new DownloadResourcesPopulator();
    download_popualtor.populate_downloads();
    
    // The post_med_stacked_bar_plot, profile_stacked_bar_plot and profile 
    /* Create the plot objects via class abstraction
    The post-MED and profile plots share a lot in common and can easily be represented
    as a single classs. However, the  modal stacked bar plot is much more complicated.
    It has basically double of everything that the simple stacked bar plots have.
    I don't think its a good idea to work with a base class is extended. It will be to 
    complicated and the abstraction will not be clear. Instead I think it will be
    easiest and clearest to have a seperate class. We can call the classes
    SimpleStackedBarPlot and ModalStackedBarPlot.*/
    const post_med_stacked_bar_plot = new SimpleStackedBarPlot(
        {name_of_html_svg_object: "#chart_post_med", get_data_method: getRectDataPostMEDBySample, 
        get_max_y_val_method: getRectDataPostMEDBySampleMaxSeq, plot_type: 'post_med'}
    );
    
    if (analysis){
        const profile_stacked_bar_plot = new SimpleStackedBarPlot(
            {name_of_html_svg_object: "#chart_profile", get_data_method: getRectDataProfileBySample,
            get_max_y_val_method: getRectDataProfileBySampleMaxSeq, plot_type: 'profile'}
        );
        const modal_stacked_bar_plot = new ModalStackedBarPlot();
    } else {
        // Hide the card if the data to populate it doesn't exist
        $("#profile_card").css("display", "none");
        // if the profile data doesn't exist then we don't have need for the modal so we should hide
        // the modal buttons.
        $(".viewer_link_seq_prof").remove();
    }
    // The modal plot will init itself once the lister for the modal opening is fired.
    
    // Init the two distance plots
    // First need to check to see if we are working with the bray curtis
    // or the unifrac distance
    const btwn_sample_plot = new DistancePlot({
        name_of_html_svg_object: "#chart_btwn_sample", 
        plot_type: 'sample'});
    if (analysis){
        const btwn_profile_plot = new DistancePlot({
        name_of_html_svg_object: "#chart_btwn_profile", 
        plot_type: 'profile'});
    }else {
            // btwn_sample data not available
            // make display none for the btwn sample card
            $("#between_profile_distances").css("display", "none");
    }
    
    // Init Map if lat_lon data available
    if (Object.keys(getSampleSortedArrays()).includes('lat_lon')){
        const map = new SampleLocationMap();
    }else{
        // If there is no map then set the helper text to say this
        $("#map_helper_text").text("No lat lon data for samples. No map available.")
        // Then hide the map object.
        $("#map").css("display", "none");
    }
    
    

});