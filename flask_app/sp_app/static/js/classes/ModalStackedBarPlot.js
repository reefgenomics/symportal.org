class ModalStackedBarPlot{
    // Given that there will only be the one instance of the class we 
    // can be quite explicit, rather than dynamic, about defining its
    // attributes.
    constructor(){
        this.sorted_uid_arrays = getSampleSortedArrays();
        this.sorting_keys = Object.keys(this.sorted_uid_arrays);
        this.post_med_svg = d3.select("#chart_post_med_modal");
        this.profile_svg = d3.select("#chart_profile_modal");
        [this.$progress_bar_container, this.$progress_bar, this.$progress_bar_text_holder] = this._init_progress_bar();
        this.post_med_data = getRectDataPostMEDBySample();
        this.post_med_max_y = getRectDataPostMEDBySampleMaxSeq();
        // Because this dataset is going to be used in the inverted modal plot we need to
        // remove the cummulative y values that have been added to the above
        this.inv_profile_data = this._get_inv_profile_data();
        this.inv_profile_max_y = getRectDataProfileBySampleMaxSeq();
        // The object that holds the meta info for the samples
        this.sample_meta_info = getSampleMetaInfo();
        // Create a name to uid dictionary for the samples
        this.sample_name_to_uid_dict = this._make_name_to_uid_dict(this.sample_meta_info);
        // Same for the profiles
        this.profile_meta_info = getProfileMetaInfo();
        this.profile_name_to_uid_dict = this._make_name_to_uid_dict(this.profile_meta_info);
        
        // The array that contains the current order of the samples
        // This will changed based on the parameter that is sorting the plot
        // If profile_based is available (i.e. if there was an analysis) start
        // with this. Else start with similarity.
        this.current_sample_order_array = this._init_current_sample_order_array();
        this.progress_bar_increment = 100/this.current_sample_order_array.length;
        [this.margin, this.inv_margin] = this._init_margin();
        // Same width for both of the chart areas but difference widths
        [this.width, this.post_med_height, this.profile_height] = this._init_width_and_height();
        [this.x_scale, this.post_med_y_scale, this.profile_y_scale] = this._init_scales();
        [this.post_med_x_axis_id, this.post_med_y_axis_id] = this._init_post_med_axis_ids();
        [this.profile_x_axis_id, this.profile_y_axis_id] = this._init_profile_axis_ids();
        [this.post_med_x_axis, this.post_med_y_axis] = this._init_post_med_axes();
        [this.profile_x_axis, this.profile_y_axis] = this._init_profile_axes();
        this._init_sorting_drop_down_menus();
        this._add_sample_groups_to_bar_svgs();
        [this.post_med_tips, this.profile_tips] = this._init_tips();
        this.post_med_svg.call(this.post_med_tips);
        this.profile_svg.call(this.profile_tips);
        [this.post_med_color_scale, this.profile_color_scale] = this._init_color_scale();
        // Whether the plot is currently displaying absolute or relative abundances
        this.absolute_relative = this._init_absolute_realtive();
        //Listening for opening of seq-profile modal
        let self = this;
        $("#seq-prof-modal").on("shown.bs.modal", function (e) {
            self.update_post_med_and_profile_plots();
        })
        // Relative to Absolute data distplay toggle
        $(".dtype-btn").click(function () {
            // Check to see that the click happened on the modal button
            if ($(this).attr('data-data-type') == 'post-profile'){
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
                    self.update_post_med_and_profile_plots();
                }
            }
        });
        // Listening for the bar chart sorting button clicks
        $(".svg_sort_by a").click(function () {
            // Check to see that it is a click on the plot instance in question
            if ($(this).closest(".btn-group").find(".svg_sort_by").attr("data-data-type") == 'post-profile'){
                let current_text = $(this).closest(".btn-group").find(".btn").text();
                let selected_text = $(this).text()
                // Only proceed if the button text has changed
                if (current_text !== selected_text) {
                    // Update the text on the sort button
                    $(this).closest(".btn-group").find(".btn").text(selected_text);
                    // Update the current sample array
                    self._update_current_sample_order_array(selected_text);
                    self.update_post_med_and_profile_plots();
                }
            }
        });
    }

    // Plotting methods
    update_post_med_and_profile_plots(){
        // Unlike the simple stacked bar class, here we need to run the
        // plot updates on both the profile and the post-med seqs
        // each time an update is required. As such we will have this additional
        // method that will call the methods of the simple stacked bar giving a
        // argument that details which plot we are updating. This is alittle ugly
        // as it brings us back almost to the original method format, but at least
        // everything for the modal is within the class now.
        this._update_plot()
    }

    _update_plot(){
        // First show the progress bar
        this.$progress_bar_container.show();
        // Init the text of the progress bar
        this.$progress_bar_text_holder.text(`Plotting modal stacked bar plots`);
        
        //First update the x_scale and y_scale domains
        this._update_axes_domains();
        
        // Code that does the majoirty of the replotting
        for (let i = 0; i < this.current_sample_order_array.length; i++) {
            // Then we want to pass in the _update_axes method as a callback
            setTimeout(this._replot_data.bind(this), 0, i);            
        }
        
    }
    _update_axes_domains(){
        if (this.absolute_relative == 'absolute'){
            this.post_med_y_scale.domain([0, this.post_med_max_y]).nice();
            this.profile_y_scale.domain([0, this.inv_profile_max_y]).nice();
        }else if (this.absolute_relative == 'relative'){
            this.post_med_y_scale.domain([0,1]).nice();
            this.profile_y_scale.domain([0,1]).nice();
        }
        this.x_scale.domain(this.current_sample_order_array);
    }
    _replot_data(index_int){
        let sample_uid = this.current_sample_order_array[index_int];
        
        // Bars is the join that we will call exit
        let post_med_bars = this.post_med_svg.select("g.s" + sample_uid).selectAll("rect").data(this.post_med_data[sample_uid], function (d) {
                return d.seq_name;
        });
        let profile_bars = this.profile_svg.select("g.s" + sample_uid).selectAll("rect").data(this.inv_profile_data[sample_uid], function (d) {
            return d.profile_name;
        });

        // Remove any data points from the plot that don't exist
        post_med_bars.exit().remove();
        profile_bars.exit().remove();
        
        // Transitions
        let abs_rel;
        if (this.absolute_relative == 'absolute'){
            abs_rel = 'abs';
        }else if (this.absolute_relative == 'relative'){
            abs_rel = 'rel';
        }
        let post_med_color_scale = this.post_med_color_scale;
        let profile_color_scale = this.profile_color_scale;
        let x_scale = this.x_scale;
        let post_med_y_scale = this.post_med_y_scale;
        let profile_y_scale = this.profile_y_scale;
        // First do it for the post_med_bars
        post_med_bars.attr("x", function (d) {
            return x_scale(sample_uid);
        }).attr("y", function (d) {
            return post_med_y_scale(+d["y_" + abs_rel]);
        }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
            return Math.max(post_med_y_scale(0) - post_med_y_scale(+d["height_" + abs_rel]), 1);
        }).attr("fill", function (d) {
            return post_med_color_scale(d.seq_name);
        });
        // Now for the profile bars
        let profile_name_to_uid_dict = this.profile_name_to_uid_dict;
        profile_bars.attr("x", function (d) {
            return x_scale(sample_uid);
        }).attr("y", function (d) {
            return profile_y_scale(+d["y_" + abs_rel]);
        }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
            return Math.max(profile_y_scale(+d["height_" + abs_rel]), 1);
        }).attr("fill", function (d) {
            return profile_color_scale(profile_name_to_uid_dict[d.profile_name])
        });

        // New objects to be created (enter phase)
        let post_med_tips = this.post_med_tips;
        post_med_bars.enter().append("rect")
            .attr("x", function (d) {
                return x_scale(sample_uid);
            }).attr("y", post_med_y_scale(0)).on('mouseover', function (d) {
                post_med_tips.show(d);
                d3.select(this).attr("style", "stroke-width:1;stroke:rgb(0,0,0);");
            })
            .on('mouseout', function (d) {
                post_med_tips.hide(d);
                d3.select(this).attr("style", null);
            }).attr("y", function (d) {
                return post_med_y_scale(+d["y_" + abs_rel]);
            }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
                return Math.max(post_med_y_scale(0) - post_med_y_scale(+d["height_" + abs_rel]), 1);
            }).attr("fill", function (d) {
                return post_med_color_scale(d.seq_name);
            });
        
        // New objects to be created (enter phase)
        let profile_tips = this.profile_tips;
        let profile_meta_info = this.profile_meta_info;
        profile_bars.enter().append("rect")
            .attr("x", function (d) {
                return x_scale(sample_uid);
            }).on('mouseover', function (d) {
                profile_tips.show(d);
                d3.select(this).attr("style", "stroke-width:1;stroke:rgb(0,0,0);");
                let profile_uid = profile_name_to_uid_dict[d["profile_name"]];
                let profile_data_series = profile_meta_info[profile_uid.toString()];
                $(this).closest(".plot_item").find(".profile_meta_item").each(function () {
                    $(this).text(profile_data_series[$(this).attr("data-key")]);
                });
                $(this).closest(".plot_item").find(".meta_profile_name").text(d["profile_name"]);
            })
            .on('mouseout', function (d) {
                profile_tips.hide(d);
                d3.select(this).attr("style", null);
            }).attr("y", function (d) {
                return profile_y_scale(+d["y_" + abs_rel]);
            }).attr("width", x_scale.bandwidth()).attr("height", function (d) {
                return Math.max(profile_y_scale(+d["height_" + abs_rel]), 1);
            }).attr("fill", function (d) {
                return profile_color_scale(profile_name_to_uid_dict[d.profile_name]);
            });

        // Get the current width of the progress bar
        let current_width_of_prog_bar = (this.$progress_bar.width() / this.$progress_bar.parent().width()) * 100
        let new_width = current_width_of_prog_bar + this.progress_bar_increment;
        
        // finally if the call axes method has been passed in then call it
        if (index_int == this.current_sample_order_array.length - 1){
            // Then we just plotted the last sample and we should now call axes
            this._post_med_update_axes();
            this._profile_update_axes();
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
    _post_med_update_axes(){
        // y axis
        d3.select("#" + this.post_med_y_axis_id)
        .transition()
        .duration(1000)
        .call(
            d3.axisLeft(this.post_med_y_scale).ticks(null, "s")
        );

        // The variable that we will use to house the widths of the sample name objects
        let sample_name_width_obj = {};
        let sample_meta_info = this.sample_meta_info;
        let sample_names = this.current_sample_order_array.map(sample_uid => sample_meta_info[sample_uid]["name"]);
        let margin = this.margin;
        this.post_med_svg.append('g').attr("class", '.dummyTextG')
            .selectAll('.dummyText')
            .data(sample_names)
            .enter()
            .append("text")
            .attr("style", "font-size:10px;")
            .text(function(d) { return d})
            .attr("x", "10")
            .attr("y", "10")
            .each(function(d,i) {
                let length_of_text = this.getComputedTextLength();
                let self = d3.select(this),
                    text = self.text(),
                    current_x = self.attr("x");
                let available_space = margin.bottom - current_x - 2;
                if (length_of_text > available_space){
                    // Perform the ellipse shortening here
                    while (length_of_text > (margin.bottom - current_x) && text.length > 0) {
                        text = text.slice(0, -1);
                        self.text(text + '...');
                        length_of_text = self.node().getComputedTextLength();
                    }
                    sample_name_width_obj[d] = {"ellipse":true, "ellipse_text":self.text()};
                }else{
                    sample_name_width_obj[d] = {"width":length_of_text, "ellipse":false};
                }
                this.remove();
            })
        $("#chart_post_med_modal").find(".dummyTextG").remove();

        // x axis
        let self = this;
        d3.selectAll("#" + this.post_med_x_axis_id)
        .call(d3.axisBottom(this.x_scale).tickFormat(function(d) {
            let sample_name = sample_meta_info[d]["name"];
            if (sample_name_width_obj[sample_name]["ellipse"]){
                return sample_name_width_obj[sample_name]["ellipse_text"];
            }else{return sample_name;}
        }).tickSizeOuter(0)).selectAll("text").each(function(){
            self._center_or_ellipse_axis_labels(this, sample_name_width_obj)
        });
        
        // Listener to highlight sample names on mouse over.
        d3.select("#" + this.post_med_x_axis_id).selectAll(".tick")._groups[0].forEach(function (d1) {
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
    _profile_update_axes(){
        // y axis
        d3.select("#" + this.profile_y_axis_id)
        .transition()
        .duration(1000)
        .call(
            d3.axisLeft(this.profile_y_scale).ticks(null, "s")
        );

        // x axis
        // Axis with ticks above and no text
        d3.select(this.profile_x_axis_id)
            .call(d3.axisTop(this.x_scale).tickSizeOuter(0));
    }
    _center_or_ellipse_axis_labels(text_obj, sample_name_width_obj){
        let sample_meta_info = this.sample_meta_info;
        // text has already been ellipsed. So we just need to do centering here.
        d3.select(text_obj).attr("y", 0).attr("x", 9).attr("dy", "0.35em").attr("style", "font-size:10px;").attr("transform", "rotate(90)")
        .style("text-anchor", "start");
        // Set the values we need to here dynamically according to the dict that we worked out above. but still need to find some way of linking.
        //This has a data node.
        let sample_name = sample_meta_info[text_obj.__data__]["name"];
        // Available width is the margin - 9 for the displacement of the sequence tick and -2 for displacement of the profile tick
        // So figure out if our text is larger than the available space. If it is larger, then ellipse until smaller
        // If its smaller, center
        if (sample_name_width_obj[sample_name]["ellipse"]){
            return;
        }else{
            // Then this needs centering
            // Have to take into account the fact that the labels are already displaced by an amount x
            // Also have to take into account that the ticks from the inv profile axis are protruding
            // Into the space of the seq modal margin. To account for this we will adjust by 2 px
            let current_x = +$(text_obj).attr("x");
            let length_of_text = sample_name_width_obj[sample_name]["width"]
            let translate_by = ((this.margin.bottom - (length_of_text+current_x))/2)-2;
            $(text_obj).attr("x", `${current_x + translate_by}`);
        }
    }
    // Private init methods
    _init_progress_bar(){
        
        return [$("#modal_progress_bar_container"), $("#modal_progress_bar"), $("#modal_progress_bar_text_holder")]
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
    _init_margin(){return [{top: 30, left: 35, bottom: 60, right: 0}, {top: 5, left: 35, bottom: 5, right: 0}];}
    _init_width_and_height(){
        this.post_med_svg.attr("width", ((this.current_sample_order_array.length * 13) + 70).toString());
        this.profile_svg.attr("width", ((this.current_sample_order_array.length * 13) + 70).toString());
        let width = +this.post_med_svg.attr("width") - this.margin.left - this.margin.right;
        let post_med_svg_height = 0.30 * window.innerHeight;
        let profile_svg_height = post_med_svg_height - this.margin.bottom;
        this.post_med_svg.attr("height", post_med_svg_height);
        this.profile_svg.attr("height", profile_svg_height);
        let post_med_plot_height = +this.post_med_svg.attr("height") - this.margin.top - this.margin.bottom;
        let profile_plot_height = +this.profile_svg.attr("height") - this.inv_margin.top - this.inv_margin.bottom;
        return [width, post_med_plot_height, profile_plot_height];
    }
    _init_scales(){
        let x_scale = d3.scaleBand()
            .range([this.margin.left, this.width + this.margin.left])
            .padding(0.1);
        let post_med_y_scale = d3.scaleLinear()
            .rangeRound([this.post_med_height + this.margin.top, this.margin.top]);
        let profile_y_scale = d3.scaleLinear()
        .rangeRound([this.inv_margin.top, this.profile_height + this.inv_margin.top]);
        return [x_scale, post_med_y_scale, profile_y_scale];
    }
    _init_post_med_axis_ids(){
        return ["x_axis_post_med_modal", "y_axis_post_med_modal"];
    }
    _init_profile_axis_ids(){
        return ["x_axis_profile_modal", "y_axis_profile_modal"];
    }
    _init_post_med_axes(){
        let post_med_x_axis = this.post_med_svg.append("g")
            .attr("transform", `translate(0,${this.post_med_height + this.margin.top})`)
            .attr("id", this.post_med_x_axis_id);
        let post_med_y_axis = this.post_med_svg.append("g")
            .attr("transform", `translate(${this.margin.left},0)`)
            .attr("id", this.post_med_y_axis_id);
        return [post_med_x_axis, post_med_y_axis];
    }
    _init_profile_axes(){
        // inverted profile modal plot is axis is only moved down by top margin
        let profile_x_axis = this.profile_svg.append("g")
            .attr("transform", `translate(0,${this.inv_margin.top})`)
            .attr("id", this.profile_x_axis_id);
        // This should also be moved down by the top axis
        let profile_y_axis = this.profile_svg.append("g")
            .attr("transform", `translate(${this.margin.left}, 0)`)
            .attr("id", this.profile_y_axis_id);
        return [profile_x_axis, profile_y_axis];
    }
    _init_sorting_drop_down_menus(){
        let sort_dropdown_to_populate_modal = $("#seq-prof-modal").find(".svg_sort_by");
        for (let i = 0; i < this.sorting_keys.length; i++) {
            sort_dropdown_to_populate_modal.append(`<a class="dropdown-item" >${this.sorting_keys[i]}</a>`);
        }
    }
    _add_sample_groups_to_bar_svgs() {
        let post_med_svg = this.post_med_svg;
        this.current_sample_order_array.forEach(function (sample) {
            post_med_svg.append("g").attr("class", "s" + sample);
        })
        let profile_svg = this.profile_svg;
        this.current_sample_order_array.forEach(function (sample) {
            profile_svg.append("g").attr("class", "s" + sample);
        })
    }
    _init_tips(){
        let post_med_tips = d3.tip().attr('class', 'd3-tip').direction('e').offset([0, 5])
            .html(function (d) {
                let content = '<div style="background-color:rgba(255,255,255,0.9);">' +
                    '<span style="margin-left: 2.5px;"><b>' + d.seq_name + '</b></span><br>' +
                    '</div>';
                return content;
            });
        let profile_tips = d3.tip().attr('class', 'd3-tip').direction('e').offset([0, 5])
            .html(function (d) {
                let content = '<div style="background-color:rgba(255,255,255,0.9);">' +
                    '<span style="margin-left: 2.5px;"><b>' + d.profile_name + '</b></span><br>' +
                    '</div>';
                return content;
            });
        return [post_med_tips, profile_tips];
    }
    _get_inv_profile_data(){
        let data = getRectDataProfileBySample();
        Object.keys(data).forEach(function (dkey) {
            // First check to see if there are any rectangles for this sample
            if (data[dkey].length == 0) {
                return;
            }

            // Go through each element removing the cummulative y
            // we can do this by setting the y to 0 for the first element and then
            // for each next element we can set it to the y of the element that is n-1
            let new_y_rel = 0;
            let new_y_abs = 0;
            let old_y_rel;
            let old_y_abs;
            for (let j = 0; j < data[dkey].length; j++) {
                old_y_rel = data[dkey][j]["y_rel"];
                old_y_abs = data[dkey][j]["y_abs"];
                data[dkey][j]["y_rel"] = new_y_rel;
                data[dkey][j]["y_abs"] = new_y_abs;
                new_y_rel = old_y_rel;
                new_y_abs = old_y_abs;
            }

        })
        return data;
    }
    _init_color_scale(){
        
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
        let post_med_color_scale =  d3.scaleOrdinal().domain(seq_names).range(seq_colors);
    
        let prof_color = getProfColor();
        let prof_names = Object.keys(prof_color);
        let prof_colors = prof_names.map(function (prof_name) {
            return prof_color[prof_name]
        });
        let profile_color_scale = d3.scaleOrdinal().domain(prof_names).range(prof_colors);          
        return [post_med_color_scale, profile_color_scale];
    }
    _init_absolute_realtive(){
        if ($("#ModalAbsDType").hasClass("btn-primary")) {
            return 'absolute';
        } else if ($("#ModalRelDType").hasClass("btn-primary")) {
            return 'relative';
        }
    }
    _update_absolute_realtive(){
        if ($("#ModalAbsDType").hasClass("btn-primary")) {
            this.absolute_relative = 'absolute';
        } else if ($("#ModalRelDType").hasClass("btn-primary")) {
            this.absolute_relative = 'relative';
        }
    }
};