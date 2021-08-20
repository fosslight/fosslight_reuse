#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2021 LG Electronics Inc.
# SPDX-License-Identifier: GPL-3.0-only
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import logging
import locale
from datetime import datetime
from binaryornot.check import is_binary
import fosslight_util.constant as constant
from fosslight_util.set_log import init_log
from yaml import safe_dump
from reuse._main import parser as reuse_arg_parser
from reuse import report
from reuse.project import Project
from reuse.report import ProjectReport
from reuse.header import run
from reuse._comment import EXTENSION_COMMENT_STYLE_MAP

_PKG_NAME = "fosslight_reuse"
_RULE_LINK = "https://oss.lge.com/guide/process/osc_process/1-identification/copyright_license_rule.html"
_MSG_REFERENCE = "Ref. Copyright and License Writing Rules in Source Code. : " + _RULE_LINK
_MSG_FOLLOW_LIC_TXT = "Follow the Copyright and License Writing Rules in Source Code. : " + _RULE_LINK
_REUSE_CONFIG_FILE = ".reuse/dep5"
_DEFAULT_EXCLUDE_EXTENSION_FILES = []  # Exclude files from reuse
_DEFAULT_EXCLUDE_EXTENSION = ["jar", "png", "exe", "so", "a", "dll", "jpeg", "jpg", "ttf", "lib", "ttc", "pfb",
                              "pfm", "otf", "afm", "dfont", "json"]
_turn_on_default_reuse_config = True
_check_only_file_mode = False
_root_xml_item = ET.Element('results')
_start_time = ""
_result_log = {}

logger = logging.getLogger(constant.LOGGER_NAME)

def find_oss_pkg_info(path):
    global _DEFAULT_EXCLUDE_EXTENSION_FILES
    _OSS_PKG_INFO_FILES = ["oss-pkg-info.yaml", "oss-pkg-info.yml", "oss-package.info", "requirement.txt",
                           "requirements.txt", "package.json", "pom.xml",
                           "build.gradle",
                           "podfile.lock", "cartfile.resolved"]

    oss_pkg_info = []
    all_files = []
    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                file_lower_case = file.lower()
                file_abs_path = os.path.join(root, file)
                file_rel_path = os.path.relpath(file_abs_path, path)
                all_files.append(file_rel_path)

                if file_lower_case in _OSS_PKG_INFO_FILES or file_lower_case.startswith("module_license_"):
                    oss_pkg_info.append(file_rel_path)
                elif is_binary(file_abs_path):
                    _DEFAULT_EXCLUDE_EXTENSION_FILES.append(file_rel_path)
                else:
                    extension = file_lower_case.split(".")[-1]
                    if extension in _DEFAULT_EXCLUDE_EXTENSION:
                        _DEFAULT_EXCLUDE_EXTENSION_FILES.append(file_rel_path)

    except Exception as ex:
        print_error('Error_FIND_OSS_PKG :' + str(ex))

    return oss_pkg_info, all_files


def create_reuse_dep5_file(path):
    # Create .reuse/dep5 for excluding directories from reuse.
    _DEFAULT_CONFIG_PREFIX = "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\nUpstream-Name: \
                        reuse\nUpstream-Contact: Carmen Bianca Bakker <carmenbianca@fsfe.org>\nSource: https://github.com/fsfe/reuse-tool\n"
    _DEFAULT_EXCLUDE_FOLDERS = ["venv*/*", "node_modules*/*", ".*/*"]

    reuse_config_file = os.path.join(path, _REUSE_CONFIG_FILE)
    file_to_remove = reuse_config_file
    dir_to_remove = os.path.dirname(reuse_config_file)
    need_rollback = False
    str_contents = ""

    try:
        if not os.path.exists(dir_to_remove):
            os.makedirs(dir_to_remove, exist_ok=True)
        else:
            dir_to_remove = ""
        if os.path.exists(reuse_config_file):
            file_to_remove = reuse_config_file + "_" + _start_time + ".bk"
            shutil.copy2(reuse_config_file, file_to_remove)
            need_rollback = True

        _DEFAULT_EXCLUDE_EXTENSION_FILES.extend(_DEFAULT_EXCLUDE_FOLDERS)
        for file_to_exclude in _DEFAULT_EXCLUDE_EXTENSION_FILES:
            str_contents += "\nFiles: " + file_to_exclude + "\nCopyright: -\nLicense: -\n"

        with open(reuse_config_file, "a") as f:
            if not need_rollback:
                f.write(_DEFAULT_CONFIG_PREFIX)
            f.write(str_contents)
    except Exception as ex:
        print_error('Error_Create_Dep5 :' + str(ex))

    return need_rollback, file_to_remove, dir_to_remove


def remove_reuse_dep5_file(rollback, file_to_remove, temp_dir_name):
    try:
        if rollback:
            _origin_file = os.path.join(os.path.dirname(file_to_remove), os.path.basename(_REUSE_CONFIG_FILE))
            shutil.copy2(file_to_remove, _origin_file)

        os.remove(file_to_remove)

        if temp_dir_name != "":
            os.rmdir(temp_dir_name)

    except Exception as ex:
        print_error('Error_Remove_Dep5 :' + str(ex))


def reuse_for_files(path, files):
    global _DEFAULT_EXCLUDE_EXTENSION_FILES

    missing_license_list = []
    missing_copyright_list = []
    error_occurred = False

    try:
        prj = Project(path)

        for file in files:
            try:
                file_abs_path = os.path.join(path, file)
                if not os.path.isfile(file_abs_path) or is_binary(file_abs_path):
                    _DEFAULT_EXCLUDE_EXTENSION_FILES.append(file)
                else:
                    extension = file.split(".")[-1]
                    if extension in _DEFAULT_EXCLUDE_EXTENSION:
                        _DEFAULT_EXCLUDE_EXTENSION_FILES.append(file)
                    else:
                        logger.info("# " + file)
                        rep = report.FileReport.generate(prj, file_abs_path)

                        logger.info("* License: " + ", ".join(rep.spdxfile.licenses_in_file))
                        logger.info("* Copyright: " + rep.spdxfile.copyright + "\n")

                        if rep.spdxfile.licenses_in_file is None or len(rep.spdxfile.licenses_in_file) == 0:
                            missing_license_list.append(file)
                        if rep.spdxfile.copyright is None or len(rep.spdxfile.copyright) == 0:
                            missing_copyright_list.append(file)

            except Exception as ex:
                print_error('Error_Reuse_for_file_to_read :' + str(ex))

    except Exception as ex:
        print_error('Error_Reuse_for_file :' + str(ex))
        error_occurred = True

    return missing_license_list, missing_copyright_list, error_occurred

def check_file_extension(all_files):
    files_filtered = []
    _POSSIBLE_EXTENSION = list(EXTENSION_COMMENT_STYLE_MAP.keys())

    if all_files != "":
        for file in all_files:
            file_extension = os.path.splitext(file)[1]
            if file_extension in _POSSIBLE_EXTENSION:
                files_filtered.append(file)

    return files_filtered
        

def check_license_and_copyright(path_to_find, all_files, missing_license, missing_copyright):
    # Check file extension for each list
    all_files_fitered = check_file_extension(all_files)
    logger.info("all_files_fitered : " + str(all_files))
    missing_license_filtered = check_file_extension(missing_license)
    logger.info("missing_license_filtered : " + str(missing_license_filtered))
    missing_copyright_filtered = check_file_extension(missing_copyright)
    logger.info("missing_copyright_filtered : " + str(missing_copyright_filtered))

    skip_files = sorted(list(set(all_files_fitered) - set(missing_license_filtered) - set(missing_copyright_filtered)))   
    logger.info("\n# File list that have both license and copyright : {count} / {total}".format(
            count=len(skip_files),
            total=len(all_files)))

    for file in skip_files:
        file_list = list()
        file_list.append(file)

        unused_lic_list, usused_cop_list, error_occurred = reuse_for_files(path_to_find, file_list)

    return missing_license_filtered, missing_copyright_filtered

def set_missing_license_copyright(missing_license_filtered, missing_copyright_filtered, project, path_to_find):
    input_license = None
    input_copyright = None

    main_parser = reuse_arg_parser()

    # Print missing license
    if missing_license_filtered is not None and len(missing_license_filtered) > 0:
        lic_path = []

        for lic_file in sorted(missing_license_filtered):
            lic_path.append(os.getcwd() + '/' + path_to_find + '/' + lic_file)

        logger.info("# Select a license to write in the license missing files ")
        select = input("   1.MIT,  2.Apache-2.0,  3.LGE Proprietary License,  4.Not select now : " )
        if select == '1' or select =='MIT':
            input_license = 'MIT'
        elif select == '2' or select == 'Apache-2.0':
            input_license = 'Apache-2.0'
        elif select == '3' or select == 'LGE Proprietary License':
            input_license = 'LGE Proprietary License'
        elif select == '4' or select == 'Quit' or select == 'quit':
            logger.info(" Not selected any license to write ")
            return
        logger.warning(f"# Your input license : {input_license}")

        parsed_args = main_parser.parse_args(['addheader', '--license', str(input_license)] + lic_path)
        run(parsed_args, project)

    # Print copyright license
    if missing_copyright_filtered is not None and len(missing_copyright_filtered) > 0:
        cop_path = []

        for cop_file in sorted(missing_copyright_filtered):
            cop_path.append(os.getcwd() + '/' + path_to_find + '/' + cop_file)
        input_copyright = input("\n# Input Copyright to write in the copyright missing files (ex, (c) LGE) : ")
        logger.warning(f"# Your input copyright : {input_copyright}")

        parsed_args = main_parser.parse_args(['addheader', '--copyright', str(input_copyright)] + cop_path)
        run(parsed_args, project)
    logger.info("\n")

def reuse_for_project(repository):
    result = ""
    missing_license = []
    missing_copyright = []
    error_occured = False

    oss_pkg_info_files, all_files = find_oss_pkg_info(repository)

    if _turn_on_default_reuse_config:
        need_rollback, temp_file_name, temp_dir_name = create_reuse_dep5_file(repository)

    try:
        project = Project(repository)
        report = ProjectReport.generate(project)
        file_total = len(report.file_reports)

        # Summary Message
        result += "* Used licenses:"
        for i, lic in enumerate(sorted(report.used_licenses)):
            if i:
                result += ","
            result += " "
            result += lic        

        result += ("\n* Files with copyright information: {count} / {total}").format(
            count=file_total - len(report.files_without_copyright),
            total=file_total
        )

        result += ("\n* Files with license information: {count} / {total}").format(
            count=file_total - len(report.files_without_licenses),
            total=file_total
        )

        # File list that missing license text
        missing_license = [str(sub) for sub in set(report.files_without_licenses)]
        if not repository.endswith("/"):
            repository += "/"
        missing_license = [sub.replace(repository, '') for sub in missing_license]

        # File list that missing copyright text
        missing_copyright = [str(sub) for sub in set(report.files_without_copyright)]
        if not repository.endswith("/"):
            repository += "/"
        missing_copyright = [sub.replace(repository, '') for sub in missing_copyright]

        # Print Skipped Files
        missing_license_filtered, missing_copyright_filtered = check_license_and_copyright(repository, all_files, missing_license, missing_copyright)

    except Exception as ex:
        print_error('Error_Reuse_lint:' + str(ex))
        error_occured = True

    if _turn_on_default_reuse_config:
        remove_reuse_dep5_file(need_rollback, temp_file_name, temp_dir_name)
    return result, missing_license_filtered, missing_copyright_filtered, oss_pkg_info_files, error_occured, project


def print_error(error_msg: str):
    global _root_xml_item
    error_item = ET.Element('system_error')
    error_item.text = error_msg
    _root_xml_item.append(error_item)


def result_for_summary(str_lint_result, oss_pkg_info, path, msg_missing_files, files_without_license, copyright_without_files, project):
    global _root_xml_item

    reuse_compliant = False
    str_oss_pkg = "* Open Source Package info: "
    try:
        if oss_pkg_info is not None and len(oss_pkg_info) > 0:
            reuse_compliant = True
            str_oss_pkg += ", ".join(oss_pkg_info)
    except Exception as ex:
        print_error('Error_Print_OSS_PKG_INFO:' + str(ex))

    if msg_missing_files == "":
        reuse_compliant = True

    # Add Summary Comment
    _SUMMARY_PREFIX = '# SUMMARY\n'
    _SUMMARY_SUFFIX = '\n\n' + _MSG_REFERENCE
    str_summary = _SUMMARY_PREFIX + str_oss_pkg + '\n' + str_lint_result + _SUMMARY_SUFFIX
    items = ET.Element('error')
    items.set('id', 'rule_key_osc_checker_01')
    items.set('line', '0')
    items.set('msg', str_summary)
    if not reuse_compliant:
        _root_xml_item.append(items)

    logger.info(msg_missing_files + str_summary)

    # Set missing license and copyright
    set_missing_license_copyright(files_without_license, copyright_without_files, project, path)


def result_for_missing_license_and_copyright_files(files_without_license, copyright_without_files, oss_pkg_info, project, path_to_find):
    global _root_xml_item
    message = ""
    # If the oss_pkg_file exists,
    # it is unnecessary to print the result for each file without a license.
    if oss_pkg_info is not None and len(oss_pkg_info) > 0:
        print_mode = False
    else:
        print_mode = True

    str_missing_lic_files = ""
    str_missing_cop_files = ""
    for file_name in files_without_license:
        items = ET.Element('error')
        items.set('file', file_name)
        items.set('id', 'rule_key_osc_checker_02')
        items.set('line', '0')
        items.set('msg', _MSG_FOLLOW_LIC_TXT)
        if _check_only_file_mode:
            _root_xml_item.append(items)
        str_missing_lic_files += ("* " + file_name + "\n")

    for file_name in copyright_without_files:
        items = ET.Element('error')
        items.set('file', file_name)
        items.set('id', 'rule_key_osc_checker_02')
        items.set('line', '0')
        items.set('msg', _MSG_FOLLOW_LIC_TXT)
        if _check_only_file_mode:
            _root_xml_item.append(items)
        str_missing_cop_files += ("* " + file_name + "\n")

    if _check_only_file_mode and _DEFAULT_EXCLUDE_EXTENSION_FILES is not None and len(
            _DEFAULT_EXCLUDE_EXTENSION_FILES) > 0:
        logger.info("# FILES EXCLUDED - NOT SUBJECT TO REUSE")
        logger.info('* %s' % '\n* '.join(map(str, _DEFAULT_EXCLUDE_EXTENSION_FILES)))
        logger.info("\n" + _MSG_REFERENCE)
    else:
        if print_mode and files_without_license is not None and len(files_without_license) > 0:
            message = "# MISSING LICENSES FROM FILE LIST TO CHECK\n" + str_missing_lic_files + "\n"
        if print_mode and copyright_without_files is not None and len(copyright_without_files) > 0:
            message += "# MISSING COPYRIGHT FROM FILE LIST TO CHECK\n" + str_missing_cop_files + "\n"

    return message


def write_xml_and_exit(result_file: str, exit_code: int) -> None:
    # Create a new XML file with the results
    try:
        ET.ElementTree(_root_xml_item).write(result_file, encoding="UTF-8", xml_declaration=True)
        error_items = ET.ElementTree(_root_xml_item).findall('system_error')
        if len(error_items) > 0:
            logger.warning("# SYSTEM ERRORS")
            for xml_item in error_items:
                logger.warning(xml_item.text)
    except Exception as ex:
        logger.error('Error_to_write_xml:', ex)
        exit_code = os.EX_IOERR
    try:
        _str_final_result_log = safe_dump(_result_log, allow_unicode=True, sort_keys=True)
        logger.info(_str_final_result_log)
    except Exception as ex:
        logger.warning("Failed to print result log. " + str(ex))
    sys.exit(exit_code)


def init(path_to_find, result_file, file_list):
    global logger, _start_time, _result_log

    _start_time = datetime.now().strftime('%Y%m%d_%H-%M-%S')
    output_dir = os.path.dirname(os.path.abspath(result_file))
    logger, _result_log = init_log(os.path.join(output_dir, "fosslight_reuse_log_"+_start_time+".txt"),
                                   True, logging.INFO, logging.DEBUG, _PKG_NAME, path_to_find)
    if file_list:
        _result_log["File list to check"] = file_list


def run_lint(path_to_find, file, disable, result_file):
    global _turn_on_default_reuse_config, _check_only_file_mode

    file_to_check_list = []
    _exit_code = os.EX_OK

    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except Exception as ex:
        print_error('Error' + str(ex))

    if file != "":
        file_to_check_list = file.split(',')
        _check_only_file_mode = True
    if path_to_find == "":
        path_to_find = os.getcwd()
    if result_file == "":
        result_file = "reuse_checker.xml"
    _turn_on_default_reuse_config = not disable

    # reuse lint can only be executed on a directory.
    if not os.path.isdir(path_to_find):
        print_error("Error_-p param should be given a directory, not a file.")
        write_xml_and_exit(result_file, os.EX_DATAERR)
    else:
        init(path_to_find, result_file, file_to_check_list)

    if _check_only_file_mode:
        license_missing_files, copyright_missing_files, error_occurred = reuse_for_files(path_to_find, file_to_check_list)
        oss_pkg_info = []
    else:
        str_lint_result, license_missing_files, copyright_missing_files, oss_pkg_info, error_occurred, project = reuse_for_project(path_to_find)

    if error_occurred:  # In case reuse lint failed
        _exit_code = os.EX_SOFTWARE
    else:
        msg_missing_files = result_for_missing_license_and_copyright_files(license_missing_files, copyright_missing_files, oss_pkg_info, project, path_to_find)
        if not _check_only_file_mode:
            result_for_summary(str_lint_result, oss_pkg_info, path_to_find, msg_missing_files, license_missing_files, copyright_missing_files, project)

    write_xml_and_exit(result_file, _exit_code)
