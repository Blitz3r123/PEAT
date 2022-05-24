import os
import pythoncom
from socket import *
from os.path import exists
import re
from datetime import datetime
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
        file_list = sftp.listdir(dir_path)
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

def assign_test_statuses(defined_tests, testbat_dir):
    curdir_files = get_files(os.path.dirname(testbat_dir))
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

def monitor_tests():
    PTS_dir = "C:\\Users\\acwh025\OneDrive - City, University of London\\PhD\\PAT\\PATS"

    testbat_dir = os.path.join(PTS_dir, "test.bat")

    if not exists(testbat_dir):
        console.print("test.bat file not found.", style="bold red")
        raise Exception()

    defined_tests = collect_defined_tests(testbat_dir)
    assign_test_statuses(defined_tests, testbat_dir)
    return defined_tests

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
        
    return cur_test
    sftp.close()                    

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