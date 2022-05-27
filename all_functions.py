import time
import os
from pathlib import Path
import json
import stat
from socket import *
from os.path import exists
import re
import datetime
from statistics import *
from pprint import pprint
import paramiko

from rich.console import Console
console = Console(record = True)

from PRIVATE import *

PTS_DIR = "C:/Users/acwh025/Downloads/PTS"

def connect_to_vm():
    ip = '10.200.51.26'
    port = 22
    username = get_username()
    password = get_password()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ip, port, username, password)
        return ssh
    except Exception as e:
        console.print(e, style="bold red")

def get_files(ssh, dir_path):
    """
      Gets all the files from the folder stated - including files from subdirectories.
    
      Parameters:
        dir_path (string): Path of the folder from which to get the files from.
    
      Returns:
        all_files ( [strings] ): Paths of all files.
    """
    if ssh:
        sftp = ssh.open_sftp()
        file_list = sftp.listdir(str(dir_path))
        all_files = file_list
        sftp.close()
    else:
        file_list = os.listdir(dir_path)
        all_files = list()
        # Iterate over all the entries
        for entry in file_list:
            # Create full path
            full_path = os.path.join(dir_path, entry)
            # If entry is a directory then get the list of files in this directory 
            if os.path.isdir(full_path):
                all_files = all_files + get_files(None, full_path)
            else:
                all_files.append(full_path)
                
    return all_files

def get_test_config(ssh, test_name):
    # TODO: THIS
    test_config = None
    sftp = ssh.open_sftp()
    
    pprint(sftp.listdir(PTS_DIR))
    
    sftp.close()
    return test_config

def get_test_amount(ssh, type):
    sftp = ssh.open_sftp()
    pts_files = sftp.listdir(PTS_DIR)
    if 'queued' in type:
        if len([file for file in pts_files if 'test.bat' in file]) == 0:
            raise Exception("test.bat file not found in " + PTS_DIR)
        else:
            testbat = os.path.join(PTS_DIR, "test.bat")
            with sftp.open(testbat, 'r') as f:
                contents = f.readlines()
                contents = contents[:-1]
                return len([line for line in contents if '@REM' not in line])
    elif 'completed' in type:
        metadata_files = [file for file in pts_files if 'metadata.txt' in file]
        ran_amount = 0
        if len([file for file in pts_files if 'test.bat' in file]) == 0:
            raise Exception("test.bat file not found in " + PTS_DIR)
        else:
            testbat = os.path.join(PTS_DIR, "test.bat")
            with sftp.open(testbat, 'r') as f:
                contents = f.readlines()
                contents = contents[:-1]
                for file in metadata_files:
                    for line in contents:
                        if file.replace("_metadata.txt", "") in line:
                            ran_amount += 1
    sftp.close()
    return ran_amount

def get_nums_from_string(text):
    """
      Gets numbers from a string.
    
      Parameters:
        text (string): string to take numbers from.
    
      Returns:
        number_list [int]: list of numbers inside of string. 
    """
    return [int(s) for s in re.findall(r'\d+', text)]

def assign_test_statuses(ssh, defined_tests):
    # curdir_files = get_files(os.path.dirname(testbat_dir))
    sftp = ssh.open_sftp()
    curdir_files = sftp.listdir(PTS_DIR)
    for test in defined_tests:
        name = test["name"]
        if len([file for file in curdir_files if name in file and 'metadata' in file]) > 0:
            config_file = [file for file in curdir_files if name in file and 'metadata' in file][0]
            with open(config_file, 'r') as f:
                content = f.readlines()
                
                test_start_lines = [line for line in content if 'Test Start' in line]
                test_end_lines = [line for line in content if 'Test End' in line]
                
                """
                1. if test_start and test_end exists: status = completed
                2. if test_start exists and test_end doesn't exist: status = in progress
                3. if test_start doesn't exist and test_end exists: status = error
                """
                if len(test_start_lines) > 0 and len(test_end_lines) > 0:
                    test["status"] = "complete"
                    test["duration"] = [line.split(" ")[2].split(".")[0] for line in content if 'Test Duration' in line][0]
                elif len(test_start_lines) > 0 and len(test_end_lines) == 0:
                    test["status"] = "in progress"
                    test_start_data = [line.split(" ")[2:] for line in content if 'Test Start' in line][0]
                    test_start_date = test_start_data[0].replace(":", "").replace("[", "").replace("]", "")
                    start_date = datetime.strptime(test_start_date, "%d/%m/%y")
                    
                    test_start_time = test_start_data[1].replace("\n", "")
                    start_time = datetime.strptime(test_start_time, "%H:%M:%S")

                    test_start = datetime.combine(start_date.date(), start_time.time())
                    now = datetime.now()

                    duration = datetime.strptime(str(now - test_start), "%H:%M:%S.%f").strftime("%H:%M:%S")
                    test["duration"] = str(duration)
                    
                else:
                    test["status"] = "error"
        else:
            test["status"] = "pending"
        sftp.close()

def get_test_participant_amounts(ssh, tests):
    sftp = ssh.open_sftp()
    for test in tests:
        config_path = os.path.join(PTS_DIR, "configs")
        config_path = os.path.join(config_path, test["config"])
        with sftp.open(config_path, 'r') as f:
            contents = f.readlines()
            pub_amount = sum(get_nums_from_string("".join([line for line in contents if "pub_amount" in line and "mal" not in line])))
            mal_pub_amount = sum(get_nums_from_string("".join([line for line in contents if "mal_pub_amount" in line])))
            sub_amount = sum(get_nums_from_string("".join([line for line in contents if "sub_amount" in line and "mal" not in line])))
            mal_sub_amount = sum(get_nums_from_string("".join([line for line in contents if "mal_sub_amount" in line])))
        test["sub_amount"] = sub_amount
        test["mal_sub_amount"] = mal_sub_amount
        test["pub_amount"] = pub_amount
        test["mal_pub_amount"] = mal_pub_amount

def collect_defined_tests(ssh):
    sftp = ssh.open_sftp()
    defined_tests = []
    with sftp.open(os.path.join(PTS_DIR, 'test.bat'), 'r') as f:
        contents = f.readlines()
        for i in range(len(contents)):
            if 'msg acwh025' not in contents[i]:
                test = {
                    "name": "",
                    "config": "",
                    "runs": 0,
                    "status": "",
                    "duration": ""
                }
                line = contents[i].replace(" --display-config", "").replace(" &", "")
                if '@REM' not in line:
                    test["name"] = line.split(" ")[2]
                    test["config"] = os.path.basename(line.split(" ")[3])
                    test["runs"] = get_nums_from_string(line.split(" ")[4])[0]
                    defined_tests.append(test)     
    get_test_participant_amounts(ssh, defined_tests)
    assign_test_statuses(ssh, defined_tests)
    sftp.close()
    return defined_tests

def get_current_test(ssh):
    sftp = ssh.open_sftp()
    curdir_files = get_files(ssh, PTS_DIR)
    cur_test = None
    for file in curdir_files:
        if 'metadata.txt' in file:
            with sftp.open(os.path.join(PTS_DIR, file), 'r') as f:
                contents = f.readlines()
                if 'Test Duration' not in contents[-1]:
                    cur_test = file
        
    cur_test_config = None
    if cur_test is not None:
        cur_test_config = get_test_config(ssh, cur_test)
    
    sftp.close()                    
    return cur_test, cur_test_config

def get_settings(type, settings):
    if 'pub' in type:
        pub_settings = {
            "dataLen": "",
            "executionTime": "",
            "domain": 0,
            "communication": ""
        }
        settings = settings.split(" -")
        pub_settings["dataLen"] = int([setting for setting in settings if 'dataLen' in setting][0].split(" ")[1])
        pub_settings["executionTime"] = int([setting for setting in settings if 'executionTime' in setting][0].split(" ")[1])
        pub_settings["domain"] = int(get_nums_from_string([setting for setting in settings if 'domain' in setting][0].split(" ")[1])[0])
        if len([setting for setting in settings if 'multicast' in setting]) >= 1:
            pub_settings["communication"] = "Multicast"
        else:
            pub_settings["communication"] = "Unicast"
            
        return pub_settings
    elif 'sub' in type:
        sub_settings = {
            "dataLen": "",
            "domain": 0,
            "communication": ""
        }
        settings = settings.split(" -")
        sub_settings["dataLen"] = int([setting for setting in settings if 'dataLen' in setting][0].split(" ")[1])
        sub_settings["domain"] = int(get_nums_from_string([setting for setting in settings if 'domain' in setting][0].split(" ")[1])[0])
        if len([setting for setting in settings if 'multicast' in setting]) >= 1:
            sub_settings["communication"] = "Multicast"
        else:
            sub_settings["communication"] = "Unicast"
            
        return sub_settings
    else:
        raise Exception("Type not known in get_settings(%s, %s)" %(type, settings))

def get_test_details(ssh, test_name, config_file):
    sftp = ssh.open_sftp()
    test = {
        "name": "",
        "sub_alloc": [],
        "pub_alloc": [],
        "mal_sub_alloc": [],
        "mal_pub_alloc": [],
        "sub_settings": {},
        "pub_settings": {}
    }
    test["name"] = test_name
    config_path = os.path.join(PTS_DIR, "configs")
    config_path = os.path.join(config_path, config_file)
    with sftp.open(config_path, 'r') as f:
        contents = f.readlines()
        test["pub_alloc"] = get_nums_from_string("".join([line for line in contents if "pub_amount" in line and "mal" not in line]))
        test["mal_pub_alloc"] = get_nums_from_string("".join([line for line in contents if "mal_pub_amount" in line]))
        test["sub_alloc"] = get_nums_from_string("".join([line for line in contents if "sub_amount" in line and "mal" not in line]))
        test["mal_sub_alloc"] = get_nums_from_string("".join([line for line in contents if "mal_sub_amount" in line]))
        pub_settings = [line for line in contents if 'pub_settings' in line][0]
        test["pub_settings"] = get_settings('pub', pub_settings)
        mal_pub_settings = [line for line in contents if 'mal_pub_settings' in line][0]
        test["mal_pub_settings"] = get_settings('pub', mal_pub_settings)
        sub_settings = [line for line in contents if 'sub_settings' in line][0]
        test["sub_settings"] = get_settings('sub', sub_settings)
        mal_sub_settings = [line for line in contents if 'mal_sub_settings' in line][0]
        test["mal_sub_settings"] = get_settings('sub', mal_sub_settings)
    sftp.close()
    return test

def get_config_content(ssh, config_file):
    config_content = None
    sftp = ssh.open_sftp()
    
    config_file_path = os.path.join(PTS_DIR, os.path.join("configs", config_file))
    
    with sftp.open(config_file_path, 'r') as f:
        config_content = f.readlines()
    
    sftp.close()
    return config_content

def get_test_folders():
    """
    1. Get list of folders
    2. Get list of tests
    3. Find the matches and return the list of folders
    """
    ssh = connect_to_vm()
    sftp = ssh.open_sftp()
    
    folders = []
    # 1. Get list of folders
    for fileattr in sftp.listdir_attr(PTS_DIR):
        if stat.S_ISDIR(fileattr.st_mode):
            folders.append(fileattr.filename)

    # 2. Get list of tests
    tests = []
    test_bat = os.path.join(PTS_DIR, 'test.bat')
    with sftp.open(test_bat, 'r') as f:
        contents = f.readlines()
    tests = [line.split("controller.py")[1].split("./configs")[0].strip() for line in contents if 'controller.py' in line]

    # 3. Find the matches and return the list of folders
    test_folders = []
    for test in tests:
        if len([folder for folder in folders if test in folder]) > 0:
            test_folders.append([folder for folder in folders if test in folder][0])

    sftp.close()
    return test_folders

def format_test_titles(test_folders):
    """
      Takes folder names and formats them into titles.
    
      Parameters:
        test_folders [string]: Array of all folder names.
    
      Returns:
        new_files_names [string]: Array of new formatted folder names. 
    """
    new_file_names = []

    for file in test_folders:
        if "\\" in file:
            new_file_name = file.split("\\")[1]
        else:
            new_file_name = file
        split_new_file_name = new_file_name.split("_")
        has_single_digit = len(split_new_file_name[1]) == 1
        
        if has_single_digit:
            split_new_file_name[1] = "0" + split_new_file_name[1]
            new_file_names.append((" ").join(split_new_file_name).replace("\\", " ").replace("/", " ").replace("data ", "").title())    
        else:
            new_file_names.append(new_file_name.replace("_", " ").replace("\\", " ").replace("/", " ").replace("data ", "").title())

    return new_file_names

def get_configs(test_folders, config_files, data):
    """
      Checks if config file is present, if so then appends True and config_file location, if not, it appends False and empty string to data['config_file']
    
      Parameters:
        test_folders [string]: Array of test_folders
        config_files [string]: Array of config_files
        data [too advanced]: Huge data structure containing all information
    
      Returns:
        None 
    """
    for file in test_folders:
        if file + "_metadata.txt" in config_files:
            data['has_config'].append(True)
            data["config_files"].append(file + "_metadata.txt")
        else:
            data['has_config'].append(False)
            data["config_files"].append("")
            
def get_data_runs(test_folders):
    """
      Returns the amount of run_n folders within the test folders for each test.
    
      Parameters:
        test_folders [string]: Array of test_folders.
    
      Returns:
         runs_per_test [int]: Array containing the numbers of run_n folders for each test within test_folders.
    """
    ssh = connect_to_vm()
    sftp = ssh.open_sftp()
    return [len([file for file in sftp.listdir(os.path.join(PTS_DIR, file)) if '.csv' not in file and 'run_' in file]) for file in test_folders]

def get_config_runs_and_participants(ssh, data):
    """
      Read the config file per test and store its pub/sub and mal_pub/mal_sub counts as well as how many runs there were.
    
      Parameters:
        data [too advanced]: Single huge data structure containing all information.
    
      Returns:
        None 
    """
    sftp = ssh.open_sftp()
    for file in data['config_files']:
        if len(file) > 0:
            with sftp.open(os.path.join(PTS_DIR, file).replace("[green]", "").replace("[/green]", ""), "r") as f:
                contents = f.readlines()
                
                pub_amounts = "".join([line for line in contents if '"pub_amount"' in line])
                mal_pub_amounts = "".join([line for line in contents if '"mal_pub_amount"' in line])
                sub_amounts = "".join([line for line in contents if '"sub_amount"' in line])
                mal_sub_amounts = "".join([line for line in contents if '"mal_sub_amount"' in line])

                data['pub_count'].append(sum(get_nums_from_string(pub_amounts)))
                data['mal_pub_count'].append(sum(get_nums_from_string(mal_pub_amounts)))
                data['sub_count'].append(sum(get_nums_from_string(sub_amounts)))
                data['mal_sub_count'].append(sum(get_nums_from_string(mal_sub_amounts)))
                
                restart_lines = [line for line in contents if 'Restart' in line]

            restart_counts = {
                "vm1": 0,
                "vm2": 0,
                "vm3": 0,
                "vm4": 0
            }
            for line in restart_lines:
                if "10.200.51.21" in line:
                    restart_counts["vm1"] = restart_counts["vm1"] + 1
                elif "10.200.51.22" in line:
                    restart_counts["vm2"] = restart_counts["vm2"] + 1
                elif "10.200.51.23" in line:
                    restart_counts["vm3"] = restart_counts["vm3"] + 1
                elif "10.200.51.24" in line:
                    restart_counts["vm4"] = restart_counts["vm4"] + 1

            data['config_runs'].append(restart_counts[max(restart_counts, key=restart_counts.get)])
        else:
            data['config_runs'].append(0)
            data['pub_count'].append(0)
            data['mal_pub_count'].append(0)
            data['sub_count'].append(0)
            data['mal_sub_count'].append(0)

        data["errors"].append("")
    sftp.close()
        
def get_run_participants(ssh, data):
    sftp = ssh.open_sftp()
    for i in range(len(data['test_files'])):
        runs_arr = []
        filename = data['test_files'][i]
        runs = data['config_runs'][i]
        run_folders = int(data['data_runs'][i])

        if int(runs) == run_folders or run_folders > 0:
            for i in range(run_folders):
                run_obj = {
                    "run_n": 0,
                    "pub_count": 0,
                    "sub_count": 0,
                    "mal_pub_count": 0,
                    "mal_sub_count": 0
                }
                # Get path to run_n folder
                run_dir = os.path.join(filename, "run_" + str(i + 1))
                # Read run_n folder contents
                all_files = sftp.listdir(os.path.join(PTS_DIR, run_dir))
                all_raw_files = [file for file in all_files if '.csv' in file and 'clean_' not in file]

                pub_count = len([file for file in all_raw_files if 'pub_' in file and 'mal_' not in file])
                mal_pub_count = len([file for file in all_raw_files if 'pub_' in file and 'mal_' in file])
                sub_count = len([file for file in all_raw_files if 'sub_' in file and 'mal_' not in file])
                mal_sub_count = len([file for file in all_raw_files if 'sub_' in file and 'mal_' in file])
                
                run_obj['run_n'] = i + 1
                run_obj['pub_count'] = pub_count                
                run_obj['mal_pub_count'] = mal_pub_count                
                run_obj['sub_count'] = sub_count                
                run_obj['mal_sub_count'] = mal_sub_count
                
                runs_arr.append(run_obj)

                run_obj = {
                    "run_n": 0,
                    "pub_count": 0,
                    "sub_count": 0,
                    "mal_pub_count": 0,
                    "mal_sub_count": 0
                }

        data['run_participants'].append(runs_arr)
    sftp.close()

def get_total_test_durations(ssh, data):
    sftp = ssh.open_sftp()
    for i in range(len(data['config_files'])):
        config_file = data['config_files'][i]
        has_config = data['has_config'][i]

        if has_config:
            with sftp.open(os.path.join(PTS_DIR, config_file), "r") as f:
                file_contents = f.readlines()
                try:
                    test_duration = [line for line in file_contents if "Duration" in line]
                    if len(test_duration) > 0:
                        test_duration = test_duration[0]
                        test_duration = test_duration.replace("Test Duration: ", "")
                        test_duration = test_duration.split(".")[0]
                    else:
                        test_duration = "-"
                except Exception as e:
                    print("Error: ")
                    print(e)
                    test_duration = "-"
        else:
            test_duration = "-"

        data['total_test_durations'].append(test_duration)
    sftp.close()
    
def convert_to_secs(time_string):
    """
      Converts hh:mm:ss to seconds.
    
      Parameters:
        time_string (string): String value of the time in the format hh:mm:ss.
    
      Returns:
        time_in_seconds (int): Number of seconds 
    """
    x = time.strptime(time_string,'%H:%M:%S')
    return int(datetime.timedelta(hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds())