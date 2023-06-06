class SampleLocationMap{
    constructor(){
        this.sorting_keys = Object.keys(getSampleSortedArrays());
        this._init_map_helper_text();
        // The object that holds the meta info for the samples
        this.sample_meta_info = getSampleMetaInfo();
        // Create a name to uid dictionary for the samples
        this.sample_meta_info_keys = Object.keys(this.sample_meta_info);
        this.unique_site_set = new Set();
        
        // Create a dict of sites to an array of samples that are at that site
        this.site_to_sample_uid_dict = {};
        [this.max_lat, this.min_lat, this.max_lon, this.min_lon] = this._init_site_to_sample_uid_dict();
        this.center_location = this._init_center_location();
        
        // Init the map
        this.map_canvas = document.getElementById('map');
        this.map_options = {
            center: this.center_location, 
            zoom: 5, 
            panControl: false, 
            mapTypeId: google.maps.MapTypeId.SATELLITE
        };
        this.map = new google.maps.Map(this.map_canvas, this.map_options);

        // For each of the unique sites, put a marker on the map and populate the table
        // for that marker that will hold the info for the samples found at that site
        this._init_map_markers();

    }
    _init_map_markers(){
        // Here we need to cyle through the unique lat long positions.
        // Create a marker
        // And then create an info window for each of the markers with dynamic content
        let self = this;
        this.unique_site_set.forEach(function (site_loc_str) {
            let lat_numeric = +site_loc_str.split(';')[0];
            let lon_numeric = +site_loc_str.split(';')[1];
            let marker = new google.maps.Marker({
                position: {
                    lat: lat_numeric,
                    lng: lon_numeric
                },
                map: self.map
            });

            marker.addListener('click', function () {
                let $content_object = $("<div></div>", {
                    "class": "map_info_window"
                });
                //Add the spans that will hold the meta info
                let $meta_div = $('<div></div>');
                $meta_div.appendTo($content_object);
                $meta_div.append(`<span class="iwindowprop">lat: </span><span class="iwindowval">${lat_numeric}</span>`) // lat
                $meta_div.append(`<span class="iwindowprop">lon: </span><span class="iwindowval">${lon_numeric}</span>`) // lat
                $meta_div.append(`<span class="iwindowprop">site_name: </span><span class="iwindowval">--</span>`) // site_name TODO
                $meta_div.append(`<span class="iwindowprop">num_samples: </span><span class="iwindowval">${self.site_to_sample_uid_dict[site_loc_str].length}</span>`) // num_samples
                // Then the table that will hold data for each sample
                let $table_div = $('<div></div>');
                $table_div.appendTo($content_object);

                let $table = $('<table></table>', {
                    "class": "table table-hover table-sm",
                    "style": "font-size:0.5rem;"
                });
                $table.appendTo($table_div);

                let $thead = $('<thead></thead>');
                $thead.appendTo($table);
                let $tr = $('<tr></tr>');
                $tr.appendTo($thead);
                $tr.append('<th>sample_name</th>');
                $tr.append('<th>host_taxa</th>');
                $tr.append('<th>depth</th>');
                let $tbody = $('<tbody></tbody>');
                $tbody.appendTo($table);

                // Add a tr and cells for every sample of at the location
                for (let j = 0; j < self.site_to_sample_uid_dict[site_loc_str].length; j++) {
                    let sample_uid = self.site_to_sample_uid_dict[site_loc_str][j];
                    $tr = $('<tr></tr>');
                    $tr.appendTo($tbody);
                    $tr.append(`<td>${self.sample_meta_info[sample_uid]["name"]}</td>`);
                    // The full taxa string is really too long here so get the last element that isn't NoData
                    let tax_str = self.sample_meta_info[sample_uid]["taxa_string"];
                    let short_tax = self._get_short_tax_string(tax_str);
                    $tr.append(`<td>${short_tax}</td>`);
                    $tr.append(`<td>${self.sample_meta_info[sample_uid]["collection_depth"]}</td>`);
                }
                // Here we should have the info window content built and stored in the variable $content_object
                // Now put the info window together
                let infowindow = new google.maps.InfoWindow();
                infowindow.setContent($content_object[0]);
                infowindow.open(self.map, this);
            });
        });
    }
    _get_short_tax_string(full_tax_string){
        let tax_elements = full_tax_string.split(';');
        tax_elements.reverse();
        let shortTax = "NoData";
        for (let i = 0; i < tax_elements.length; i++) {
            if (tax_elements[i] != "NoData") {
                // If we have a species name then report the first letter of the genera too
                if (i == 0) {
                    if (tax_elements[1] != "NoData") {
                        shortTax = tax_elements[1][0] + '. ' + tax_elements[0];
                        break;
                    } else { // If we don't have the genera then just report the species name
                        shortTax = tax_elements[0];
                        break;
                    }
                } else {
                    shortTax = tax_elements[i];
                    break;
                }
            }
        }
        return shortTax;
    }
    _init_center_location(){
        if (this.unique_site_set.size < 2) {
            return new google.maps.LatLng(this.max_lat, this.max_lon);
        } else {
            let center_lat = this.max_lat - ((this.max_lat - this.min_lat) / 2);
            let center_lon = this.max_lon - ((this.max_lon - this.min_lon) / 2);
            return new google.maps.LatLng(center_lat, center_lon);
        }
    }
    _init_map_helper_text(){
        // If there is data to do a map then set the helper text
        $("#map_helper_text").text("Click markers for site details")
    }
    _init_site_to_sample_uid_dict(){
        // Keep track of the largest and smallest lat and long so that we can work out an average to center the map on
        let max_lat = -90;
        let min_lat = +90;
        let max_lon = -180;
        let min_lon = +180;

        // Need to take into account that samples with bad or no lat lon details will have been set to the 
        // default value of 999
        for (let i = 0; i < this.sample_meta_info_keys.length; i++) {
            let sample_obj = this.sample_meta_info[this.sample_meta_info_keys[i]];
            let numeric_lat = +sample_obj['lat'];
            let numeric_lon = +sample_obj['lon'];
            if (numeric_lat == 999 || numeric_lon == 999) {
                continue;
            }
            if (numeric_lat > max_lat) {
                max_lat = numeric_lat;
            }
            if (numeric_lat < min_lat) {
                min_lat = numeric_lat;
            }
            if (numeric_lon > max_lon) {
                max_lon = numeric_lon;
            }
            if (numeric_lon < min_lon) {
                min_lon = numeric_lon;
            }
            let lat_lon_str = sample_obj['lat'].toString() + ';' + sample_obj['lon'].toString();
            this.unique_site_set.add(lat_lon_str);
            // if lat_lon already in the dict then simply add the sample uid to the list
            // else create a new list and add the sample uid to this list
            if (Object.keys(this.site_to_sample_uid_dict).includes(lat_lon_str)) {
                this.site_to_sample_uid_dict[lat_lon_str].push(this.sample_meta_info_keys[i]);
            } else {
                this.site_to_sample_uid_dict[lat_lon_str] = [this.sample_meta_info_keys[i]];
            }
        }
        return [max_lat, min_lat, max_lon, min_lon];
    }
}