#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: GPL-3.0-only
import logging
import os
import sys
import yaml
from fosslight_util.constant import LOGGER_NAME
from fosslight_util.parsing_yaml import find_all_oss_pkg_files, parsing_yml
from fosslight_util.output_format import write_output_file
from fosslight_util.write_yaml import create_yaml_with_ossitem
from fosslight_util.read_excel import read_oss_report

logger = logging.getLogger(LOGGER_NAME)
IDX_CANNOT_FOUND = -1


def convert_yml_to_excel(oss_pkg_files, output_file, file_option_on, base_path, window):
    items_to_print = []
    sheet_list = {}

    if not file_option_on:
        oss_pkg_files = find_all_oss_pkg_files(base_path, oss_pkg_files)

    for oss_pkg_file in oss_pkg_files:
        try:
            if os.path.isfile(oss_pkg_file):
                logger.warning(f"Read data from : {oss_pkg_file}")

                if file_option_on:
                    base_path = os.path.dirname(oss_pkg_file)
                oss_items, _ = parsing_yml(oss_pkg_file, base_path)
                for item in oss_items:
                    items_to_print.extend(item.get_print_array())
        except Exception as ex:
            logger.error(f"Read yaml file: {ex}")

    try:
        sheet_list["SRC_FL_Reuse"] = items_to_print
        success, msg, result_file = write_output_file(output_file, '.xlsx',
                                                      sheet_list)
        if success:
            if result_file:
                logger.info(f"Output: {result_file}")
            else:
                logger.warning("Nothing is detected to convert so output file is not generated.")
        else:
            logger.error(f"Error to write excel file : {msg}")
    except Exception as ex:
        logger.error(f"Error to write excel file : {ex}")


def convert_excel_to_yaml(oss_report_to_read, output_file, sheet_names=""):
    _file_extension = ".yaml"
    yaml_dict = {}

    if os.path.isfile(oss_report_to_read):
        try:
            items = read_oss_report(oss_report_to_read, sheet_names)
            for item in items:
                create_yaml_with_ossitem(item, yaml_dict)
            if yaml_dict:
                output_file = output_file if output_file.endswith(_file_extension) else output_file + _file_extension
                success = write_yaml_file(output_file, yaml_dict)
                if success:
                    logger.warning(f"Output: {output_file}")
                else:
                    logger.error(f"Can't write yaml file : {output_file}")
                    sys.exit(1)
        except Exception as error:
            logger.error(f"Convert yaml: {error}")
    else:
        logger.error(f"Can't find a file: {oss_report_to_read}")


def write_yaml_file(output_file, json_output):
    success = True
    error_msg = ""

    try:
        with open(output_file, 'w') as f:
            yaml.dump(json_output, f, sort_keys=False)
    except Exception as ex:
        error_msg = str(ex)
        success = False
    return success, error_msg
