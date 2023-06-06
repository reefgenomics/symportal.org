/* Create the plot objects via class abstraction
The post-MED and profile plots share a lot in common and can easily be represented
as a single classs. However, the  modal stacked bar plot is much more complicated.
It has basically double of everything that the simple stacked bar plots have.
I don't think its a good idea to work with a base class is extended. It will be to 
complicated and the abstraction will not be clear. Instead I think it will be
easiest and clearest to have a seperate class. We can call the classes
SimpleStackedBarPlot and ModalStackedBarPlot.*/

class SimpleStackedBarPlot{
    // This base class will hold most of the setup for the stacked bar
    // plots
    // We will use an extension of this for each of the post_med and 
    // profile plots that will contain the methods for doing the plotting
    constructor({name_of_html_svg_object, get_data_method, get_max_y_val_method, plot_type}){
        // Get the object that has the sorting parameter as key
        // and a sorted list of the uids (either samples or profiles) as value
        this.plot_type = plot_type;
        this.sorted_uid_arrays = getSampleSortedArrays();
        this.sorting_keys = Object.keys(this.sorted_uid_arrays);
        this.svg = d3.select(name_of_html_svg_object);
        [this.$progress_bar_container, this.$progress_bar, this.$progress_bar_text_holder] = this._init_progress_bar();
        
        
        // The object containing the rectangle data to be plotted
        this.data = get_data_method();
        // The maximum absolute count for a given sample
        // This is used to scale the y axis
        this.max_y = get_max_y_val_method();
        // The object that holds the meta info for the samples
        this.sample_meta_info = getSampleMetaInfo();
        // Create a name to uid dictionary for the samples
        this.sample_name_to_uid_dict = this._make_name_to_uid_dict(this.sample_meta_info);
        if (this.plot_type == 'profile'){
            // If we are working with the profile plot instance
            // We will need a profile meta info dictionary as well and the corresponding
            // profile name to uid dictt
            this.profile_meta_info = getProfileMetaInfo();
            this.profile_name_to_uid_dict = this._make_name_to_uid_dict(this.profile_meta_info);
        }
        
        // The array that contains the current order of the samples
        // This will changed based on the parameter that is sorting the plot
        // If profile_based is available (i.e. if there was an analysis) start
        // with this. Else start with similarity.
        this.current_sample_order_array = this._init_current_sample_order_array();
        this.progress_bar_increment = 100/this.current_sample_order_array.length;
        this.margin = this._init_margin();
        [this.width, this.height] = this._init_width_and_height();
        [this.x_scale, this.y_scale] = this._init_scales();
        // Init the axis group
        //NB the axis no need translating down or left in the direction they orientate.
        // I.e. x axis doesn't need to be translated right (only down)
        // and yaxis doesn't need translating down (only right).
        // This is because they apparently use their ranges to set their positions
        [this.x_axis_id_string, this.y_axis_id_string] = this._init_axes_ids();
        [this.x_axis, this.y_axis] = this._init_axes();
        
        // INIT the drop down with the sample sorting categories we have available
        this._init_sorting_drop_down_menus();
    
        // Add a g to the bar plot svgs that we will use for the bars on a sample by sample basis
        // We will have a seperate g for each of the samples so that we can plot column by column
        // The pre-med plot will not get init until later.
        this._add_sample_groups_to_bar_svgs();
        
        // Create and call the tool tip
        this.tips = this._init_tips();
        this.svg.call(this.tips);
        
        this.color_scale = this._init_color_scale();

        // Whether the plot is currently displaying absolute or relative abundances
        this.absolute_relative = this._init_absolute_realtive();

        //Variables for initiating the meta information below the plots
        [
            this.meta_annotation_to_key, 
            this.meta_info_annotation_order_array_primary, 
            this.meta_info_annotation_order_array_secondary,
            this.available_meta_info
        ] = this._init_meta_info_vars();
        // Then populate the info containers below the plots
        this._init_plot_meta_info_holders();

        // Listeners
        // Relative to Absolute data distplay toggle
        let self = this;
        $(".dtype-btn").click(function () {
            // Check to see that we are not dealing with the modal button
            if ($(this).attr('data-data-type') == self.plot_type){
                //If the button is of class btn light then it is not selected and this click should fire
                // the change in datatype event for the relevant svg
                if ($(this).hasClass("btn-light")) {
                    //First change the button attributes so that it looks like we've registered the clicks
                    $(this).parents(".btn-group").find('.dtype-btn').each(function () {
                        if ($(this).hasClass("btn-light")) {
                            //Switch around the btn styles so that light becomes primary and viceversa
                            $(this).addClass("btn-primary").removeClass("btn-light")
                        } else if ($(this).hasClass("btn-primary")) {
                            $(this).addClass("btn-light").removeClass("btn-primary")
                        }
                    });
                    //Second update the plot to represent the newly selected datatype
                    // If one of the modal buttons then need to update both plots
                    // else just the one plot.
                    self._update_absolute_realtive();
                    self.update_plot();
                }
            }
        });

        // Listening for the bar chart sorting button clicks
        $(".svg_sort_by a").click(function () {
            // Check to see that it is a click on the plot instance in question
            if ($(this).closest(".btn-group").find(".svg_sort_by").attr("data-data-type") == self.plot_type){
                let current_text = $(this).closest(".btn-group").find(".btn").text();
                let selected_text = $(this).text()
                // Only proceed if the button text has changed
                if (current_text !== selected_text) {
                    // Update the text on the sort button
                    $(this).closest(".btn-group").find(".btn").text(selected_text);
                    // Update the current sample array
                    self._update_current_sample_order_array(selected_text);
                    self.update_plot();
                }
            }
        });

        // Finally, init the plot for the very first time
        this.update_plot();
    }

    // Base level plotting functions
    // Plotting methods
    update_plot(){
        // First show the progress bar
        this.$progress_bar_container.show();
        // Init the text of the progress bar
        this.$progress_bar_text_holder.text(`Plotting ${this.plot_type} stacked bar plots`);
        
        //First update the x_scale and y_scale domains
        this._update_axes_domains();
        
        // Code that does the majoirty of the replotting
        // TODO lets try to run this as a series of call backs and see where that gets us
        // we can increment the i within the method and pass it back in and check if it is less than
        // this.current_sample_order_array.length
        
        
        // setTimeout(this._replot_data.bind(this), 0, 0);
        for (let i = 0; i < this.current_sample_order_array.length; i++) {
            // Then we want to pass in the _update_axes method as a callback
            setTimeout(this._replot_data.bind(this), 0, i);            
        }
    }
    _update_axes_domains(){
        if (this.absolute_relative == 'absolute'){
            this.y_scale.domain([0, this.max_y]).nice();
        }else if (this.absolute_relative == 'relative'){
            this.y_scale.domain([0,1]).nice();
        }
        this.x_scale.domain(this.current_sample_order_array);
    }
    _replot_data(index_int){
        let sample_uid = this.current_sample_order_array[index_int];
        
        // Bars is the join that we will call exit
        let bars = this.svg.select("g.s" + sample_uid).selectAll("rect").data(this.data[sample_uid], function (d) {
            if (this.plot_type == 'post_med'){
                return d.seq_name;
            }else if (this.plot_type == 'profile'){
                return d.profile_name;
            }
        });

        // Remove any data points from the plot that don't exist
        bars.exit().remove()
        
        // Transitions
        let abs_rel;
        if (this.absolute_relative == 'absolute'){
            abs_rel = 'abs';
        }else if (this.absolute_relative == 'relative'){
            abs_rel = 'rel';
        }
        let color_scale = this.color_scale;
        let x_scale = this.x_scale;
        let y_scale = this.y_scale;
        let plot_type = this.plot_type;
        let profile_name_to_uid_dict = this.profile_name_to_uid_dict;
        bars.attr("x", function (d) {
            return x_scale(sample_uid);
        }).attr("y", function (d) {
            return y_scale(+d["y_" + abs_rel]);
        }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
            return Math.max(y_scale(0) - y_scale(+d["height_" + abs_rel]), 1);
        }).attr("fill", function (d) {
            if (plot_type == 'post_med'){
                return color_scale(d.seq_name);
            }else if (plot_type == 'profile'){
                return color_scale(profile_name_to_uid_dict[d.profile_name])
            }
        });

        // New objects to be created (enter phase)
        let tips = this.tips;
        let profile_meta_info = this.profile_meta_info;
        bars.enter().append("rect")
            .attr("x", function (d) {
                return x_scale(sample_uid);
            }).on('mouseover', function (d) {
                tips.show(d);
                d3.select(this).attr("style", "stroke-width:1;stroke:rgb(0,0,0);");
                if (plot_type == 'profile'){
                    let profile_uid = profile_name_to_uid_dict[d["profile_name"]];
                    let profile_data_series = profile_meta_info[profile_uid.toString()];
                    $(this).closest(".plot_item").find(".profile_meta_item").each(function () {
                        $(this).text(profile_data_series[$(this).attr("data-key")]);
                    });
                    $(this).closest(".plot_item").find(".meta_profile_name").text(d["profile_name"]);
                }
            })
            .on('mouseout', function (d) {
                tips.hide(d);
                d3.select(this).attr("style", null);
            }).attr("y", function (d) {
                return y_scale(+d["y_" + abs_rel]);
            }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
                return Math.max(y_scale(0) - y_scale(+d["height_" + abs_rel]), 1);
            }).attr("fill", function (d) {
                if (plot_type == 'post_med'){
                    return color_scale(d.seq_name);
                }else if (plot_type == 'profile'){
                    return color_scale(profile_name_to_uid_dict[d.profile_name]);
                }
            });
        
        
        // Get the current width of the progress bar
        let current_width_of_prog_bar = (this.$progress_bar.width() / this.$progress_bar.parent().width()) * 100
        let new_width = current_width_of_prog_bar + this.progress_bar_increment;
        
        // finally if the call axes method has been passed in then call it
        if (index_int == this.current_sample_order_array.length - 1){
            // Then we just plotted the last sample and we should now call axes
            this._update_axes();
            this.$progress_bar.width("100%");
            this.$progress_bar_text_holder.text(`Plotting complete. Rendering axes...`)
        }else{
            // There are more samples to plot
            if (new_width < 100){
                this.$progress_bar.width(`${new_width}%`);
                this.$progress_bar_text_holder.text(`Plotting sample ${index_int} outof ${this.current_sample_order_array.length}`)
            }else{
                this.$progress_bar.width("100%");
            }
        }
        
    }
    _update_axes(){
        // y axis
        d3.select("#" + this.y_axis_id_string)
        .transition()
        .duration(1000)
        .call(
            d3.axisLeft(this.y_scale).ticks(null, "s")
        );

        // x axis
        let self = this;
        let sample_meta_info = this.sample_meta_info;
        d3.selectAll("#" + this.x_axis_id_string)
        .call(d3.axisBottom(this.x_scale).tickFormat(d => sample_meta_info[d]["name"]).tickSizeOuter(0)).selectAll("text")
        .attr("y", 0).attr("x", 9).attr("dy", ".35em").attr("transform", "rotate(90)")
        .style("text-anchor", "start").on(
            "end", function(){
                // This is a little tricky. The .on method is being called
                // on th text object and therefore in this scope here
                // the 'this' object is the text object.
                // So, to call the ellipse method of this class we have set
                // self to equal the class instance and becuase the class
                // instance is calling the _ellipse method, the 'this' object
                // will be callable from within the _ellipse method. However,
                // we still need access to the text object in this method so 
                // we will pass it in.
                self._ellipse_axis_labels(this);
            });

        // Listener to highlight sample names on mouse over.
        d3.select("#" + this.x_axis_id_string).selectAll(".tick")._groups[0].forEach(function (d1) {
            d3.select(d1).on("mouseover", function () {
                d3.select(this).select("text").attr("fill", "blue").attr("style", "cursor:pointer;text-anchor: start;");
                let sample_uid = this.__data__;
                let sample_data_series = sample_meta_info[sample_uid];
                $(this).closest(".plot_item").find(".sample_meta_item").each(function () {
                    $(this).text(sample_data_series[$(this).attr("data-key")]);
                })
            }).on("mouseout", function () {
                d3.select(this).select("text").attr("fill", "black").attr("style", "cursor:auto;text-anchor: start;");
            })
        })

        // Hide the progress bar
        setTimeout(function (self){
            self.$progress_bar_container.hide();
        }, 2000, self);
        // And reset the width to 0
        setTimeout(function (self){
            self.$progress_bar.width('0%');
        }, 2000, self);
    }
    _ellipse_axis_labels(text_obj){
        var self = d3.select(text_obj),
        textLength = self.node().getComputedTextLength(),
        text = self.text(),
        current_x = self.attr("x");
        while (textLength > (this.margin.bottom - current_x) && text.length > 0) {
            text = text.slice(0, -1);
            self.text(text + '...');
            textLength = self.node().getComputedTextLength();
        }
    }

    // Private init methods
    _init_progress_bar(){
        if (this.plot_type == 'post_med'){
            return [$("#post_med_progress_bar_container"), $("#post_med_progress_bar"), $("#post_med_progress_bar_text_holder")]
        }else if (this.plot_type == 'profile'){
            return [$("#profile_progress_bar_container"), $("#profile_progress_bar"), $("#profile_progress_bar_text_holder")]
        }
    }
    _init_plot_meta_info_holders(){
        // Init the primary info: "sample", "UID", "taxa", "lat", "lon"
        for (let i = 0; i < this.meta_info_annotation_order_array_primary.length; i++) {
            let annotation = this.meta_info_annotation_order_array_primary[i];
            if (this.available_meta_info.includes(this.meta_annotation_to_key[annotation])) {
                // We want to put taxa on its own line because it is so big and the other two paris on the same line
                if (annotation == "taxa") {
                    if (this.plot_type == 'post_med'){
                        $(".primary_sample_meta").append(`<div style="width:100%;"><span style="font-weight:bold;">${annotation}: </span><span class="sample_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }else if (this.plot_type == 'profile'){
                        $(".primary_profile_meta").append(`<div style="width:100%;"><span style="font-weight:bold;">${annotation}: </span><span class="profile_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }
                } else {
                    if (this.plot_type == 'post_med'){
                        $(".primary_sample_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="sample_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }else if (this.plot_type == 'profile'){
                        $(".primary_profile_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="profile_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }
                }
            }
        }
        
        // Init the secondary info: "collection_date", "depth",
        // "clade_relative_abund", "clade_absolute_abund", "raw_contigs", "post_qc_absolute", "post_qc_unique",
        // "post_med_absolute", "post_med_unique", "non_Symbiodiniaceae_absolute", "non_Symbiodiniaceae_unique"
        for (let i = 0; i < this.meta_info_annotation_order_array_secondary.length; i++) {
            let annotation = this.meta_info_annotation_order_array_secondary[i];
            // TODO here we have to take into account the annotation keys:
            // "post_qc_absolute", "post_qc_unique", "non_Symbiodiniaceae_absolute", "non_Symbiodiniaceae_unique"
            // will return a list rather than a string due to the fact that the key we are searching for may either
            // contain 'symbiodinium' or 'symbiodiniaceae'
            if (["post_qc_absolute", "post_qc_unique", "non_Symbiodiniaceae_absolute", "non_Symbiodiniaceae_unique"].includes(annotation)){
                // this.meta_annotation_to_key[annotation] will return a list
                for (let j = 0; j < this.meta_annotation_to_key[annotation].length; j++){
                    // For each of the possible strings housed in the list
                    if (this.available_meta_info.includes(this.meta_annotation_to_key[annotation][j])){
                        // Then we have found the correct symbiodinium or symbiodiniaceae string
                        // This will only work for max one of the items in the list
                        if (this.plot_type == 'post_med'){
                            $(".secondary_sample_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="sample_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation][j]}>--</span></div>`);
                        }else if (this.plot_type == 'profile'){
                            $(".secondary_profile_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="profile_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation][j]}>--</span></div>`);
                        }
                    }
                }
            }else{
                if (this.available_meta_info.includes(this.meta_annotation_to_key[annotation])) {
                    if (this.plot_type == 'post_med'){
                        $(".secondary_sample_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="sample_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }else if (this.plot_type == 'profile'){
                        $(".secondary_profile_meta").append(`<div><span style="font-weight:bold;">${annotation}: </span><span class="profile_meta_item mr-1" data-key=${this.meta_annotation_to_key[annotation]}>--</span></div>`);
                    }
                }
            }

        }
    }
    _init_meta_info_vars(){
        if (this.plot_type == 'post_med'){
            // TODO we have changed all instances of symbiodinium in symportal to symbiodiniaceae
            // As such, we will now need to take into account that studies could have either symbiodinium
            // in the meta info string or symbiodiniaceae depending on whether they were output
            // and uploaded before or after this change in symportal.
            // As such, we will build in a system where we will look for the symbiodinium version
            // first and if we don't find that we will look for the symbiodiniaceae system.
            // To make that work we will make the concerned meta info categories map to a list
            // rather than a string.
            let meta_annotation_to_key = {
            "sample": "name",
            "UID": "uid",
            "taxa": "taxa_string",
            "lat": "lat",
            "lon": "lon",
            "collection_date": "collection_date",
            "depth": "collection_depth",
            "clade_relative_abund": "clade_prop_string",
            "clade_absolute_abund": "clade_abs_abund_string",
            "raw_contigs": "raw_contigs",
            "post_qc_absolute": ["post_taxa_id_absolute_symbiodinium_seqs", "post_taxa_id_absolute_symbiodiniaceae_seqs"],
            "post_qc_unique": ["post_taxa_id_unique_symbiodinium_seqs", "post_taxa_id_unique_symbiodiniaceae_seqs"],
            "post_med_absolute": "post_med_absolute",
            "post_med_unique": "post_med_unique",
            "non_Symbiodiniaceae_absolute": ["post_taxa_id_absolute_non_symbiodinium_seqs", "post_taxa_id_absolute_non_symbiodiniaceae_seqs"],
            "non_Symbiodiniaceae_unique": ["post_taxa_id_unique_non_symbiodinium_seqs", "post_taxa_id_unique_non_symbiodiniaceae_seqs"]
            };
            let meta_info_annotation_order_array_primary = ["sample", "UID", "taxa", "lat", "lon"];
            let meta_info_annotation_order_array_secondary = ["collection_date", "depth",
                "clade_relative_abund", "clade_absolute_abund", "raw_contigs", "post_qc_absolute", "post_qc_unique",
                "post_med_absolute", "post_med_unique", "non_Symbiodiniaceae_absolute", "non_Symbiodiniaceae_unique"
            ];
            let available_meta_info = Object.keys(this.sample_meta_info[Object.keys(this.sample_meta_info)[0]]);
            return [meta_annotation_to_key, meta_info_annotation_order_array_primary, meta_info_annotation_order_array_secondary, available_meta_info];
        }else if (this.plot_type == 'profile'){
            let meta_annotation_to_key = {
                "profile": "name",
                "UID": "uid",
                "genera": "genera",
                "maj_seq": "maj_its2_seq",
                "associated species": "assoc_species",
                "local_abund": "local_abund",
                "db_abund": "db_abund",
                "seq_uids": "seq_uids",
                "seq_abund_string": "seq_abund_string"
            };
            let meta_info_annotation_order_array_primary = ["profile", "UID", "genera"];
            let meta_info_annotation_order_array_secondary = ["maj_seq", "species", "local_abund", "db_abund",
                "seq_uids", "seq_abund_string"
            ];
            let available_meta_info = Object.keys(this.profile_meta_info[Object.keys(this.profile_meta_info)[0]]);
            return [meta_annotation_to_key, meta_info_annotation_order_array_primary, meta_info_annotation_order_array_secondary, available_meta_info];
        }
    }
    _make_name_to_uid_dict(meta_info_obj){
        let temp_dict = {};
        Object.keys(meta_info_obj).forEach(function (uid) {
            temp_dict[meta_info_obj[uid]["name"]] = +uid;
        })
        return temp_dict;
    }
    _init_current_sample_order_array(){
        if (this.sorting_keys.includes('profile_based')) {
            return this.sorted_uid_arrays['profile_based'];
        } else {
            return this.sorted_uid_arrays['similarity'];
        }
    }
    _update_current_sample_order_array(sorting_key){
        this.current_sample_order_array = this.sorted_uid_arrays[sorting_key];
        this.progress_bar_increment = 100/this.current_sample_order_array.length;
    }
    _init_margin(){return {top: 30, left: 35, bottom: 60, right: 0};}  
    _init_width_and_height(){
        this.svg.attr("width", ((this.current_sample_order_array.length * 13) + 70).toString());
        let width = +this.svg.attr("width") - this.margin.left - this.margin.right;
        let height = +this.svg.attr("height") - this.margin.top - this.margin.bottom;
        return [width, height];
    }
    _init_scales(){
        let x_scale = d3.scaleBand()
            .range([this.margin.left, this.width + this.margin.left])
            .padding(0.1);
        let y_scale = d3.scaleLinear()
            .rangeRound([this.height + this.margin.top, this.margin.top]);
        return [x_scale, y_scale];
    }
    _init_axes_ids(){
        if (this.plot_type == 'post_med'){
            return ["x_axis_post_med", "y_axis_post_med"];
        }else if (this.plot_type == 'profile'){
            return ["x_axis_profile", "y_axis_profile"];
        }
    }
    _init_axes(){
        let x_axis = this.svg.append("g")
            .attr("transform", `translate(0,${this.height + this.margin.top})`)
            .attr("id", this.x_axis_id_string);
        let y_axis = this.svg.append("g")
            .attr("transform", `translate(${this.margin.left},0)`)
            .attr("id", this.y_axis_id_string);
        return [x_axis, y_axis];
    }
    _init_sorting_drop_down_menus(){
        let sort_dropdown_to_populate;
        if (this.plot_type == 'post_med'){
            sort_dropdown_to_populate = $("#post_med_card").find(".svg_sort_by");
        }else if (this.plot_type == 'profile'){
            sort_dropdown_to_populate = $("#profile_card").find(".svg_sort_by");
        }
        for (let i = 0; i < this.sorting_keys.length; i++) {
            sort_dropdown_to_populate.append(`<a class="dropdown-item" >${this.sorting_keys[i]}</a>`);
        }
    }
    _add_sample_groups_to_bar_svgs() {
        let svg = this.svg;
        this.current_sample_order_array.forEach(function (sample) {
            svg.append("g").attr("class", "s" + sample);
        })
    }
    _init_tips(){
        let tips;
        if (this.plot_type == 'post_med'){
            tips = d3.tip().attr('class', 'd3-tip').direction('e').offset([0, 5])
                .html(function (d) {
                    let content = '<div style="background-color:rgba(255,255,255,0.9);">' +
                        '<span style="margin-left: 2.5px;"><b>' + d.seq_name + '</b></span><br>' +
                        '</div>';
                    return content;
                });
        }else if (this.plot_type == 'profile'){
            tips = d3.tip().attr('class', 'd3-tip').direction('e').offset([0, 5])
                .html(function (d) {
                    let content = '<div style="background-color:rgba(255,255,255,0.9);">' +
                        '<span style="margin-left: 2.5px;"><b>' + d.profile_name + '</b></span><br>' +
                        '</div>';
                    return content;
                });
        }
        return tips
    }
    _init_color_scale(){
        if (this.plot_type == 'post_med'){
            // We can set both the range and domain of this as these are invariable between absolute and relative
            // data types
            // If we ran the data loading or analysis using the --no_pre_med_seqs flag
            // then the getSeqColor method will not have been output.
            // However the getSeqColorPostMED function should have been output and we will
            // use this instead
            let seq_color;
            try{
                seq_color = getSeqColor();
            }
            catch(err){
                seq_color = getSeqColorPostMED();
            }
            let seq_names = Object.keys(seq_color);
            let seq_colors = seq_names.map(function (seq_name) {
                return seq_color[seq_name]
            });
            return d3.scaleOrdinal().domain(seq_names).range(seq_colors);
        }else if (this.plot_type == 'profile'){
            let prof_color = getProfColor();
            let prof_names = Object.keys(prof_color);
            let prof_colors = prof_names.map(function (prof_name) {
                return prof_color[prof_name]
            });
            return d3.scaleOrdinal().domain(prof_names).range(prof_colors);
        }
        
    }
    _init_absolute_realtive(){
        if (this.plot_type == 'post_med'){
            if ($("#PostMEDAbsDType").hasClass("btn-primary")) {
                return 'absolute';
            } else if ($("#PostMEDRelDType").hasClass("btn-primary")) {
                return 'relative';
            }
        }else if (this.plot_type == 'profile'){
            if ($("#ProfileMEDAbsDType").hasClass("btn-primary")) {
                return 'absolute';
            } else if ($("#ProfileMEDRelDType").hasClass("btn-primary")) {
                return 'relative';
            }
        }
    }
    _update_absolute_realtive(){
        if (this.plot_type == 'post_med'){
            if ($("#PostMEDAbsDType").hasClass("btn-primary")) {
                this.absolute_relative = 'absolute';
            } else if ($("#PostMEDRelDType").hasClass("btn-primary")) {
                this.absolute_relative = 'relative';
            }
        }else if (this.plot_type == 'profile'){
            if ($("#ProfileMEDAbsDType").hasClass("btn-primary")) {
                this.absolute_relative = 'absolute';
            } else if ($("#ProfileMEDRelDType").hasClass("btn-primary")) {
                this.absolute_relative = 'relative';
            }
        }
    }
};