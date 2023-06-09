""" Module for checking file and datasheet upload"""
from werkzeug.utils import secure_filename
import os
import pandas as pd
from collections import Counter, defaultdict
import logging
from numpy import NaN, isnan
import ntpath
import json
import re
from calendar import month_abbr, month_name

# TODO QC
# Staged same file twice
# Check that both a fwd and rev file are given for every sample

# Most modern way of defining advanced exceptions here:
# https://stackoverflow.com/a/53469898/5516420
class DatasheetGeneralFormattingError(Exception):
    """Exception raised when a general formatting error has occured
        For example, if non-unique sample names are used
    """
    def __init__(self, message, data=None):
        self.message = message
        self.data = data

    def __str__(self):
        return str(self.message)

class AddedFilesError(Exception):
    """
    Raised when there are either files missing,
    there are files that are not in the supplied datasheet
    or if there are files that are too small.
    """
    def __init__(self, message, data):
        self.message = message
        self.data = data

    def __str__(self):
        return str(self.message)

class DateFormatError(Exception):
    """
    Raised when there is an error in the date format in the
    supplied datasheet.
    """
    def __init__(self, message, data):
        self.message = message
        self.data = data

    def __str__(self):
        return str(self.message)

class LatLonError(Exception):
    """
    Raised when there is an error in the latitude or longitude provided
    in the supplied datasheet.
    """
    def __init__(self, message, data):
        self.message = message
        self.data = data

    def __str__(self):
        return str(self.message)

class UploadedFilesError(Exception):
    """
    Raised when something has gone wrong when uploading seq files to the server
    """
    def __init__(self, message, data):
        self.message = message
        self.data = data

    def __str__(self):
        return str(self.message)

class DatasheetChecker:
    """
    This class is responsible for checking the format of the datasheet and also for checking the contents
    Out of this class we want to out put:
    good rows - These will a row per sample that has the fwd and rev seq files present
        It will include having colour codes for missing files or meta information
    extra objects - These are seq files that have been uploaded but are not included in the datasheet
    missing objects - These are the seq files that are missing.
    general errors - and warnings. Errors will be in red, warnings will be in yellow.
        These will include things like duplication errors
    This should be output as a json.
    """

    def __init__(self, request, user_upload_directory, datasheet_path=None):
        self.request = request
        self.datasheet_path = datasheet_path
        self.user_upload_directory = user_upload_directory
        os.makedirs(self.user_upload_directory, exist_ok=True)
        # self.datasheet_path = datasheet_path
        self.duplication_dict = {}
        if not self.datasheet_path:
            # Then we need to get the datasheet from the uploaded files
            # and save it to disk
            self.datasheet_filename = self._get_and_save_datasheet()

        self.sample_meta_info_df = self._make_sample_meta_info_df()
        # The list of the files that are in the datasheet but not found in the local dir
        # Key will be sample name value will be list of the files that are missing
        self.missing_files = defaultdict(list)
        # The list of the files that have been uploaded but that have not been
        self.extra_files = []
        # We must ensure that the same file has not been staged more than once
        # Key is file name, value is number of times it appears in the staged area
        self.duplicate_staged_files = defaultdict(int)
        # Warning containers
        # We will have a missing container for each of the fields, grouping taxonomy together
        # We will have a further lat_long_dict that will hold the details for those lat long values that
        # were provided but were in a bad format and had to be converted to 999.
        # We will also have a dict that hold the details for those binomial values that we had to convert
        self.sample_type_missing_list = []
        self.taxonomy_missing_set = set()
        self.depth_missing_list = []
        self.date_missing_list = []
        self.lat_lon_missing = []
        # Key will be sample, value will be list with original and new species value.
        self.binomial_dict = {}
        # Key will be sample name value will be string of user-provided lat lon values comma separated
        self.lat_long_dict = {}
        # Key will be sample name, value will be string of the user-provided date
        self.date_dict = {}

    def do_general_format_check(self):
        # drop any cells in which the sample name is null
        self.sample_meta_info_df = self.sample_meta_info_df[~pd.isnull(self.sample_meta_info_df['sample_name'])]
        if self.sample_meta_info_df.empty:
            raise DatasheetGeneralFormattingError(
                message='<strong class="text-danger">The datasheet appears to be empty.</strong><br>'
                        'Please fix this problem and upload again.',
                data={"error_type": "df_empty"}
            )
        self._format_sample_names()

        self._check_valid_file_names()

        # This will raise a DatasheetFormattingError
        # It will be handled in routes.py
        self._check_datasheet_df_vals_unique()

        

    def _check_valid_file_names(self):
        """
        Check that every file name cell has a valid fastq.gz filename listed in it
        If a fastq file is listed raise an error and explicitly warn that files must be compressed.
        NB Users are not able to select fastq or fq files for upload so there is no need to
        check that files are in .gz format here.
        """
        self.sample_meta_info_df.set_index('sample_name', inplace=True)
        for sample_name in self.sample_meta_info_df.index:
            # First check that the sample_name only contains sane characters:
            for c in sample_name:
                if c not in list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."):
                    raise DatasheetGeneralFormattingError(
                    message=f'<strong class="text-danger">Invalid sample name.</strong><br>'
                            f"The sample {sample_name} contains invalid characters.<br>"
                            f"Sample names may only contain alphanumeric characters [A-Z,a-z,0-9], underscores [_], dashes [-] and periods [.].<br>"
                            f"Please fix this problem and upload again.<br>",
                    data={"error_type": "invalid_sample_name_format"}
                )

            # Check that the sequencing file names exist
            if pd.isnull(self.sample_meta_info_df.at[sample_name, 'fastq_fwd_file_name']) or pd.isnull(self.sample_meta_info_df.at[sample_name, 'fastq_fwd_file_name']):
                raise DatasheetGeneralFormattingError(
                message=f'<strong class="text-danger">Invalid file name.</strong><br>'
                        f"A fwd and rev seq file must be provided for every sample.<br>"
                        f"All seq files must be in fastq.gz format.<br>"
                        f"Please fix this problem and upload again.<br>"
                        f"This error was raised because one of the file names for '{sample_name}' did not end with 'fastq.gz' or 'fq.gz'.",
                data={"error_type": "invalid_file_format"}
            )
            try:
                fwd_str = self.sample_meta_info_df.at[sample_name, 'fastq_fwd_file_name'].rstrip().lstrip()
                rev_str = self.sample_meta_info_df.at[sample_name, 'fastq_rev_file_name'].rstrip().lstrip()
            except AttributeError:
                raise DatasheetGeneralFormattingError(
                    message=f'<strong class="text-danger">Invalid file name.</strong><br>'
                            f"A fwd and rev seq file must be provided for every sample.<br>"
                            f"All seq files must be in fastq.gz format.<br>"
                            f"Please fix this problem and upload again.<br>"
                            f"This error was raised because one of the file names for '{sample_name}' did not end with 'fastq.gz' or 'fq.gz'.",
                    data={"error_type": "invalid_file_format"}
                )

            if (
                    not fwd_str.endswith('fastq.gz') and not fwd_str.endswith('fq.gz')
            ) or (
                    not rev_str.endswith('fastq.gz') and not rev_str.endswith('fq.gz')
            ):

                raise DatasheetGeneralFormattingError(
                    message=f'<strong class="text-danger">Invalid file name.</strong><br>'
                            f"A fwd and rev seq file must be provided for every sample.<br>"
                            f"All seq files must be in fastq.gz format.<br>"
                            f"Please fix this problem and upload again.<br>"
                            f"This error was raised because one of the file names for '{sample_name}' did not end with 'fastq.gz' or 'fq.gz'.",
                    data={"error_type": "invalid_file_format"}
                )


    def _format_sample_names(self):
        # Convert sample names to strings and remove white space and greek characters
        self.sample_meta_info_df['sample_name'] = self.sample_meta_info_df['sample_name'].astype(str)
        self.sample_meta_info_df['sample_name'] = self.sample_meta_info_df['sample_name'].str.rstrip() \
            .str.lstrip().str.replace(' ', '_').str.replace('/', '_').str.replace('α', 'alpha').str.replace('β', 'beta')

    def check_valid_seq_files_added(self):
        # drop any cells in which the sample name is null
        self.sample_meta_info_df = self.sample_meta_info_df[~pd.isnull(self.sample_meta_info_df['sample_name'])]
        self._format_sample_names()

        self.sample_meta_info_df.set_index('sample_name', inplace=True, drop=True)
        self.sample_meta_info_df.index = self.sample_meta_info_df.index.map(str)

        # Checking for format elements that cause errors

        # If this check fails, an AddedFilesError is raised and this will cause an error message
        # to be reported to the user. The user will have to fix the errors before they can upload
        # Errors will be caused by missing seq files, extra seq files, seq files that are too small
        # If this is passed, then we will do checks that if failed will result in warnings.
        # Warnings will not prevent users from submitting their seq files
        self._check_seq_files_exist()

        self._check_for_missing_info_and_convert_to_str()

        # this will also cause an error if there are bad formats
        self._check_lat_long()

        # This will also cause an error if there are bad formats
        self._check_date_format()
        
        # Checking for format elements that cause warnings
        self._check_for_binomial()

        self._replace_null_vals_in_meta_info_df()

        

        

    def _check_date_format(self):
        """
        Try to coerce some of the common date format errors into YYYYMMDD format
        Common inputs will be DD.MM.YYYY, DD.MM.YY, MM.YYYY or MM.YY
        We shold throw an error if there is some
        other format given (i.e. one that is not just '.' and integers)
        """
        bad_formats = []
        lower_month_abbr = [_.lower() for _ in month_abbr][1:]
        lower_month_name = [_.lower() for _ in month_name][1:]
        for row_name in self.sample_meta_info_df.index:
            current_date_value = self.sample_meta_info_df.at[row_name, 'collection_date']
            if current_date_value == "NoData":
                continue
            if not pd.isnull(current_date_value):
                # sometime a weird float string was coming in e.g. 20220601.0
                try:
                    current_date_value = str(int(float(current_date_value)))
                except ValueError:
                    pass
                if re.findall("[A-Za-z]+", current_date_value):
                    # Then this date is in a bad format
                    # We will try to extract a year and a month from it
                    # We will assume that the year is in YYYY format
                    # and that the month is in either in the common abbreviation form
                    # or written out in form.
                    putative_months = re.findall("[A-Za-z]+", current_date_value)
                    if len(putative_months) == 1:
                        putative_month = putative_months[0].lower()
                        if putative_month in lower_month_abbr:
                            month_ind = lower_month_abbr.index(putative_month) + 1
                        elif putative_month in lower_month_name:
                            month_ind = lower_month_name.index(putative_month) + 1
                        else:
                            # not recognised so log as error
                            bad_formats.append((row_name, current_date_value))
                            continue
                        # If we got here then we have month_id
                        if month_ind < 10:
                            month_ind = f"0{month_ind}"
                        else:
                            month_ind = str(month_ind)

                        # Then we need to pull out the year
                        if len(re.findall("[0-9]{4}", current_date_value)) == 1:
                            year = re.findall("[0-9]{4}", current_date_value)[0]
                        else:
                            bad_formats.append((row_name, current_date_value))
                            continue

                        # Finally check that there is nothing less after we remove the month and the year
                        remaining = current_date_value.lower().replace(putative_month, "").replace(year, "").rstrip()
                        if remaining == "":
                            # Then we can convert
                            new_date_value = f"{year}{month_ind}"
                            print(f'changing {current_date_value} to {new_date_value} for {row_name}')
                            self.sample_meta_info_df.at[row_name, 'collection_date'] = new_date_value
                            continue
                        else:
                            # There is something left and we call it bad
                            bad_formats.append((row_name, current_date_value))
                            continue
                    else:
                        # Add to the bad_formats list so that we can print out and
                        # exit at the end of this
                        bad_formats.append((row_name, current_date_value))
                        continue
                elif "." in current_date_value:
                    if current_date_value.count(".") == 2:
                        # Then this is DD.MM.YYYY or DD.MM.YY
                        new_date_value = current_date_value.replace(".", "")
                        if len(new_date_value) == 6:
                            new_date_value = ''.join(["20", new_date_value[4:], new_date_value[2:4], new_date_value[:2]])
                            print(f'changing {current_date_value} to {new_date_value} for {row_name}')
                            self.sample_meta_info_df.at[row_name, 'collection_date'] = new_date_value
                        elif len(new_date_value) == 8:
                            new_date_value = ''.join([new_date_value[4:], new_date_value[2:4], new_date_value[:2]])
                            print(f'changing {current_date_value} to {new_date_value} for {row_name}')
                            self.sample_meta_info_df.at[row_name, 'collection_date'] = new_date_value
                        else:
                            bad_formats.append((row_name, current_date_value))
                    elif current_date_value.count(".") == 1:
                        # Then this is MM.YY or MM.YYYY
                        new_date_value = current_date_value.replace(".", "")
                        if len(new_date_value) == 4:
                            new_date_value = ''.join(["20", new_date_value[2:], new_date_value[:2]])
                            print(f'changing {current_date_value} to {new_date_value} for {row_name}')
                            self.sample_meta_info_df.at[row_name, 'collection_date'] = new_date_value
                        elif len(new_date_value) == 6:
                            new_date_value = ''.join([new_date_value[2:], new_date_value[:2]])
                            print(f'changing {current_date_value} to {new_date_value} for {row_name}')
                            self.sample_meta_info_df.at[row_name, 'collection_date'] = new_date_value
                        else:
                            bad_formats.append((row_name, current_date_value))
                    else:
                        bad_formats.append((row_name, current_date_value))

                elif len(re.findall("[0-9]{8}", current_date_value)) == 1:
                    # Then this is good: YYYYMMDD
                    continue
                elif len(re.findall("[0-9]{6}", current_date_value)) == 1:
                    # Then this is good: YYYYMM
                    continue
                elif len(re.findall("^[0-9]{4}$", current_date_value)) == 1:
                    # Then this is good: YYYY
                    continue
                else:
                    # Else, something else is going on
                    bad_formats.append((row_name, current_date_value))
            else:
                continue
        if bad_formats:
            print("There are errors in the date_collection formats")
            print("Date format should be YYYYMMDD or YYYYMM")
            for bad_sample, bad_val in bad_formats:
                self._log_date_error(bad_sample, bad_val)
                print(f"{bad_sample}: {bad_val}")

        if self.date_dict:
            # Then we either have missing files, size violation files or extra files
            message = "There are fomatting errors in the collection_date format.\nThe field should be formatted as YYYYMMDD or YYYYMM or YYYY"

            raise DateFormatError(
                message=message,
                data={"date_dict":self.date_dict}
                )
        else:
            # Otherwise there were no errors and we can proceed to check for
            # other errors and warnings
            return

    def _log_date_error(self, sample_name, bad_val):
        self.date_dict[sample_name] = str(bad_val)

    def _check_for_missing_info_and_convert_to_str(self):
        """First convert each of the columns to type string.
        Then make sure that all of the vals are genuine vals of NoData
        """
        for col in ['sample_type', 'host_phylum', 'host_class', 'host_order', 'host_family', 'host_genus',
                    'host_species', 'collection_depth', 'collection_date']:
            self.sample_meta_info_df[col] = self.sample_meta_info_df[col].astype(str)

        for sample_name in self.sample_meta_info_df.index:
            for col in ['sample_type', 'host_phylum', 'host_class', 'host_order', 'host_family', 'host_genus',
                        'host_species', 'collection_depth', 'collection_date']:
                try:
                    value = str(self.sample_meta_info_df.at[sample_name, col])
                    if value == 'nan' or value == 'NaT':
                        if 'host' in col: # If its a taxonomy column
                            self.taxonomy_missing_set.add(sample_name)
                        elif col == 'sample_type':
                            self.sample_type_missing_list.append(sample_name)
                        elif col == 'collection_depth':
                            self.depth_missing_list.append(sample_name)
                        elif col == 'collection_date':
                            self.date_missing_list.append(sample_name)
                        self.sample_meta_info_df.at[sample_name, col] = 'NoData'
                except:
                    self.sample_meta_info_df.at[sample_name, col] = 'NoData'

    def _check_lat_long(self):
        # check the lat long value for each sample listed
        for i, sample_name in enumerate(self.sample_meta_info_df.index):
            lat = self.sample_meta_info_df.at[sample_name, 'collection_latitude']
            lon = self.sample_meta_info_df.at[sample_name, 'collection_longitude']

            try:
                lat_float, lon_float = self._check_individual_lat_lon(lat, lon)
            except Exception:
                self._log_lat_lon_error(sample_name)
                self._set_lat_lon_to_999(sample_name)
                continue

            # final check to make sure that the values are in a sensible range
            if (-90 <= lat_float <= 90) and (-180 <= lon_float <= 180):
                self.sample_meta_info_df.at[sample_name, 'collection_latitude'] = lat_float
                self.sample_meta_info_df.at[sample_name, 'collection_longitude'] = lon_float
            elif lat_float==999 or lon_float==999:
                continue
            else:
                self._log_lat_lon_error(sample_name)
                self._set_lat_lon_to_999(sample_name)

        # finally make sure that the lat and long cols are typed as float
        self.sample_meta_info_df['collection_latitude'] = self.sample_meta_info_df['collection_latitude'].astype(float)
        self.sample_meta_info_df['collection_longitude'] = self.sample_meta_info_df['collection_longitude'].astype(
            float)

        if self.lat_long_dict:
            # There were erros in the lat lon formatting
            message = "There are fomatting errors in the lat lon format."

            raise LatLonError(
                message=message,
                data={"lat_long_dict":self.lat_long_dict}
                )
        else:
            # Otherwise there were no errors and we can proceed to check for
            # other errors and warnings
            return

    def _check_individual_lat_lon(self, lat, lon):
        """
        Takes a dirty lat and lon value and either converts to decimial degrees or raises a run time error.
        Should be able to handle:
            decimal degrees that have a N S W or E character added to it
            degrees decimal minute (with N S W or E)
            degrees minutes seconds (with N S W or E)
        """
        if lat == 'nan' or lon == 'nan': # This is OK simply set the lat lon to 999
            return 999, 999
        try:
            if isnan(lat) or isnan(lon):
                return 999, 999
        except TypeError:
            pass
        try:
            lat_float = float(lat)
            lon_float = float(lon)
        except ValueError as e:
            # Three options.
            # 1 - we have been given decimal degrees with a hemisphere sign
            # 2 - we have been given degree decimal minutes I.e. 27°38.611'N or N27°38.611'
            # 3 - we have been given degree minutes seconds
            try:
                if chr(176) in lat and chr(176) in lon:
                    # Then we are working with either 2 or 3
                    if "\"" in lat and "\"" in lon:
                        # Then we are working with degree minutes seconds (DMS)
                        # and we should convert using self.dms2dec
                        lat_float = self._dms2dec(lat)
                        lon_float = self._dms2dec(lon)
                    elif "\"" not in lat and "\"" not in lon:
                        # Then we are working with degree degree minutes (DDM)
                        # To convert to DD we simply need to remove the NWES characters,
                        # divide the decimal part by 60 and add it to the degrees part
                        if "N" in lat:
                            lat = lat.replace("N", "").replace("'", "")
                            (lat_deg, lat_degmin) = lat.split(chr(176))
                            lat_float = int(lat_deg) + (float(lat_degmin) / 60)
                            if lat_float < 0:
                                lat_float = lat_float * -1
                        elif "S" in lat:
                            lat = lat.replace("S", "").replace("'", "")
                            (lat_deg, lat_degmin) = lat.split(chr(176))
                            lat_float = int(lat_deg) + (float(lat_degmin) / 60)
                            if lat_float > 0:
                                lat_float = lat_float * -1
                        else:
                            raise RuntimeError
                        if "E" in lon:
                            lon = lon.replace("E", "").replace("'", "")
                            (lon_deg, lon_degmin) = lon.split(chr(176))
                            lon_float = int(lon_deg) + (float(lon_degmin) / 60)
                            if lon_float < 0:
                                lon_float = lon_float * -1
                        elif "W" in lon:
                            lon = lon.replace("W", "").replace("'", "")
                            (lon_deg, lon_degmin) = lon.split(chr(176))
                            lon_float = int(lon_deg) + (float(lon_degmin) / 60)
                            if lon_float > 0:
                                lon_float = lon_float * -1
                        else:
                            raise RuntimeError
                    else:
                        # Then the lat and lon are in different formats
                        raise RuntimeError

                elif chr(176) not in lat and chr(176) not in lon:
                    # Then we are working with 1
                    if "N" in lat:
                        lat_float = float(lat.replace("N", ""))
                        if lat_float < 0:
                            lat_float = lat_float * -1
                    elif "S" in lat:
                        lat_float = float(lat.replace("S", ""))
                        if lat_float > 0:
                            lat_float = lat_float * -1
                    else:
                        raise RuntimeError
                    if "E" in lon:
                        lon_float = float(lon.replace("E", ""))
                        if lon_float < 0:
                            lon_float = lon_float * -1
                    elif "W" in lon:
                        lon_float = float(lon.replace("W", ""))
                        if lon_float > 0:
                            lon_float = lon_float * -1
                    else:
                        raise RuntimeError
                elif chr(176) in lat or chr(176) in lon:
                    # THen there is a degree sign in only one of them and we should raise an error
                    raise RuntimeError
            except Exception:
                raise RuntimeError
        return lat_float, lon_float

    @staticmethod
    def _dms2dec(dms_str):
        """Return decimal representation of DMS

            dms2dec(utf8(48°53'10.18"N))
            48.8866111111F

            dms2dec(utf8(2°20'35.09"E))
            2.34330555556F

            dms2dec(utf8(48°53'10.18"S))
            -48.8866111111F

            dms2dec(utf8(2°20'35.09"W))
            -2.34330555556F

            """

        dms_str = re.sub(r'\s', '', dms_str)

        sign = -1 if re.search('[swSW]', dms_str) else 1

        numbers = [*filter(len, re.split('\D+', dms_str, maxsplit=4))]

        degree = numbers[0]
        minute = numbers[1] if len(numbers) >= 2 else '0'
        second = numbers[2] if len(numbers) >= 3 else '0'
        frac_seconds = numbers[3] if len(numbers) >= 4 else '0'

        second += "." + frac_seconds
        return sign * (int(degree) + float(minute) / 60 + float(second) / 3600)

    def _log_lat_lon_error(self, sample_name):
        self.lat_long_dict[sample_name] = ', '.join(
            [str(self.sample_meta_info_df.at[sample_name, 'collection_latitude']),
             str(self.sample_meta_info_df.at[sample_name, 'collection_longitude'])
             ])

    def _set_lat_lon_to_999(self, sample_name):
        self.sample_meta_info_df.at[sample_name, 'collection_latitude'] = float(999)
        self.sample_meta_info_df.at[sample_name, 'collection_longitude'] = float(999)

    @staticmethod
    def dms2dec(dms_str):
        """Return decimal representation of DMS

            dms2dec(utf8(48°53'10.18"N))
            48.8866111111F

            dms2dec(utf8(2°20'35.09"E))
            2.34330555556F

            dms2dec(utf8(48°53'10.18"S))
            -48.8866111111F

            dms2dec(utf8(2°20'35.09"W))
            -2.34330555556F

            """

        dms_str = re.sub(r'\s', '', dms_str)

        sign = -1 if re.search('[swSW]', dms_str) else 1

        numbers = [*filter(len, re.split('\D+', dms_str, maxsplit=4))]

        degree = numbers[0]
        minute = numbers[1] if len(numbers) >= 2 else '0'
        second = numbers[2] if len(numbers) >= 3 else '0'
        frac_seconds = numbers[3] if len(numbers) >= 4 else '0'

        second += "." + frac_seconds
        return sign * (int(degree) + float(minute) / 60 + float(second) / 3600)

    def _check_seq_files_exist(self):
        """
        Check that all of the sequencing files provided in the datasheet exist.
        Check that there are no additional files staged that are not in the datasheet
        Check that no files have been staged more than once
        Ensure that we lstrip and rstrip the entries to remove any spaces.
        Also check for size of file and require a 300B minimum. Remove from the sample from the data sheet if
        smaller than this.
        """

        # Get a list of the files that the user has added
        data_dict = json.loads(list(self.request.form.keys())[0])
        # A dict of filename to size
        self.added_files_dict = {}
        for file_dict in data_dict["files"]:
            for k, v in file_dict.items():
                self.duplicate_staged_files[k] += 1
                self.added_files_dict[k] = v

        # Delete any entries from the duplicate samples dict that are 1 and then remove
        for k_1 in [k for k, v in self.duplicate_staged_files.items() if v == 1]:
            del self.duplicate_staged_files[k_1]
        # Convert to plain dict
        # This dict will now be empty if there were no duplicate files.
        self.duplicate_staged_files = dict(self.duplicate_staged_files)

        self._strip_white_space_from_filenames()

        self.file_not_found_list = []
        self.size_violation_samples = []
        checked_files = []
        for df_ind in self.sample_meta_info_df.index.values.tolist():
            fwd_file = self.sample_meta_info_df.at[df_ind, 'fastq_fwd_file_name']
            rev_file = self.sample_meta_info_df.at[df_ind, 'fastq_rev_file_name']

            checked_files.extend([fwd_file, rev_file])

            # Check that full paths have not been provided
            self._check_for_full_path_error(fwd_file)
            self._check_for_full_path_error(rev_file)

            # Check for the fwd read
            # Unlike in the framework, we will not allow .fastq files. Only .fastq.gz
            self._check_file_in_added_list(df_ind, fwd_file)
            self._check_file_in_added_list(df_ind, rev_file)

            # NB if we were unable to find either the fwd or rev read then we will not be able
            # to continue with our checks
            if df_ind in self.missing_files:
                continue

            # Check file size
            if self.added_files_dict[fwd_file] < 300 or self.added_files_dict[rev_file] < 300:
                print(f'WARNING: At least one of the seq files for sample {df_ind} is less than 300 bytes in size')
                print(f'{df_ind} will be removed from your datasheet and analysis')
                self.size_violation_samples.append(df_ind)

        # drop the rows that had size violations
        # Not really necessary in terms of checking whether files exist
        # But good to undertake this action now to ensure that it doesn't create
        # Any issues during the framework's handling of the datasheet and files
        self.sample_meta_info_df.drop(index=self.size_violation_samples, inplace=True)

        # Check for files that have been added but haven't been listed in the df
        self.extra_files = [filename for filename in self.added_files_dict.keys() if filename not in checked_files]

        if self.missing_files or self.size_violation_samples or self.extra_files or self.duplicate_staged_files:
            # Then we either have missing files, size violation files or extra files
            message = []
            if self.missing_files:
                message.append("Some of the files listed in your datasheet cannot be found.")
            if self.size_violation_samples:
                message.append("Some of your files are too small.")
            if self.extra_files:
                message.append("There are files that are not listed in your datasheet.")
            if self.duplicate_staged_files:
                message.append("Some files have been staged twice.")
            message = '\n'.join(message)
            raise AddedFilesError(
                message=message,
                data={
                    "missing_files":self.missing_files,
                    "size_violation_samples":self.size_violation_samples,
                    "extra_files":self.extra_files,
                    "duplicate_staged_files": self.duplicate_staged_files
                })
        else:
            # Otherwise there were no errors and we can proceed to check for warnings
            return


    def _check_file_in_added_list(self, df_ind, filename):
        if not filename in self.added_files_dict:
            self.file_not_found_list.append(filename)
            self.missing_files[df_ind].append(filename)

    def _strip_white_space_from_filenames(self):
        self.sample_meta_info_df['fastq_fwd_file_name'] = self.sample_meta_info_df['fastq_fwd_file_name'].astype(
            str)
        self.sample_meta_info_df['fastq_fwd_file_name'] = self.sample_meta_info_df[
            'fastq_fwd_file_name'].str.rstrip() \
            .str.lstrip()
        self.sample_meta_info_df['fastq_rev_file_name'] = self.sample_meta_info_df['fastq_rev_file_name'].astype(
            str)
        self.sample_meta_info_df['fastq_rev_file_name'] = self.sample_meta_info_df[
            'fastq_rev_file_name'].str.rstrip() \
            .str.lstrip()

    def _check_for_full_path_error(self, file):
        if not file == ntpath.basename(file):
            raise DatasheetGeneralFormattingError(
                message=f'<strong class="text-danger">It appears that full paths have been provided for the seq files.</strong><br>'
                        f"Please provide only filenames.<br>Please fix this problem and upload again.",
                data={"error_type": "full_path", "example_filename": file})

    def _replace_null_vals_in_meta_info_df(self):
        self.sample_meta_info_df = self.sample_meta_info_df.replace('N/A', NaN).replace('NA', NaN).replace('na',
                                                                                                           NaN).replace(
            'n/a', NaN)

    def _check_for_binomial(self):
        """People were putting the full binomial in the speices colums. This crops this back to just the
        species component of binomial"""
        for sample_name in self.sample_meta_info_df.index:
            current_species_val = self.sample_meta_info_df.at[sample_name, 'host_species']
            if not pd.isnull(current_species_val):
                if ' ' in current_species_val:
                    new_species_val = current_species_val.split(' ')[-1]
                    self.binomial_dict[sample_name] = [current_species_val, new_species_val]
                    logging.warning(f'changing {current_species_val} to {new_species_val} for {sample_name}')
                    self.sample_meta_info_df.at[sample_name, 'host_species'] = new_species_val

    def _check_datasheet_df_vals_unique(self):
        # check sample names
        self._check_vals_of_col_unique(column_name='sample_name')
        # check fastq_fwd_file_name
        self._check_vals_of_col_unique(column_name='fastq_fwd_file_name')
        # check fastq_rev_file_name
        self._check_vals_of_col_unique(column_name='fastq_rev_file_name')

    def _check_vals_of_col_unique(self, column_name):
        # check to see that the values held in a column are unique
        if column_name == "sample_name":
            sample_name_counter = Counter(list(self.sample_meta_info_df.index))
        else:
            sample_name_counter = Counter(self.sample_meta_info_df[column_name].values.tolist())
        non_unique_name_list = []
        for col_val, count in sample_name_counter.items():
            if count != 1:
                non_unique_name_list.append(col_val)
        if non_unique_name_list:
            logging.error(f"The following items for column {column_name} were non unique:")
            for item in non_unique_name_list:
                logging.error(f"\t{item}")
            self.duplication_dict[column_name] = non_unique_name_list
            raise DatasheetGeneralFormattingError(
                message=f'<strong class="text-danger">Column "{column_name}" contains non unique values.</strong><br>For example, there cannot be two samples with the same name. Please fix this problem and upload again.',
                data={"error_type": "non_unique", "non_unique_data": self.duplication_dict})

    def _make_sample_meta_info_df(self):
        if self.datasheet_path.endswith('.xlsx'):
            return pd.read_excel(
                io=self.datasheet_path, header=0, usecols='A:N', skiprows=[0])
        elif self.datasheet_path.endswith('.csv'):
            with open(self.datasheet_path, 'r') as f:
                data_sheet_as_file = [line.rstrip() for line in f]
            if data_sheet_as_file[0].split(',')[0] == 'sample_name':
                return pd.read_csv(
                    filepath_or_buffer=self.datasheet_path)
            else:
                return pd.read_csv(
                    filepath_or_buffer=self.datasheet_path, skiprows=[0])
        else:
            raise RuntimeError(f'Data sheet: {self.datasheet_path} is in an unrecognised format. '
                               f'Please ensure that it is either in .xlsx or .csv format.')

    def _get_and_save_datasheet(self):
        # Then we need to get the datasheet from the uploaded files
        dsheet_files = [k for k in self.request.files if
                        self.request.files[k].filename.endswith('.xlsx') or
                        self.request.files[k].filename.endswith('.csv')]
        assert (len(dsheet_files) == 1)
        data_sheet_key = dsheet_files[0]
        # Save the datasheet to the temp directory
        # And then read in as a dataframe to work with using the current SymPortal code
        file = self.request.files.get(data_sheet_key)
        filename = secure_filename(file.filename)
        self.datasheet_path = os.path.join(self.user_upload_directory, filename)
        file.save(self.datasheet_path)
        return filename

