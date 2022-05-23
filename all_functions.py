import os
import pythoncom
from socket import *
from os.path import exists
import re
from datetime import datetime
from statistics import *
from pprint import pprint

from rich.console import Console
console = Console(record = True)

pythoncom.CoInitialize()

PATS_DIR = "C:\\Users\\acwh025\OneDrive - City, University of London\\PhD\\PAT\\PATS"

def get_files(dir_path):
    """
      Gets all the files from the folder stated - including files from subdirectories.
    
      Parameters:
        dir_path (string): Path of the folder from which to get the files from.
    
      Returns:
        all_files ( [strings] ): Paths of all files.
    """
    file_list = os.listdir(dir_path)
    all_files = list()
    # Iterate over all the entries
    for entry in file_list:
        # Create full path
        full_path = os.path.join(dir_path, entry)
        # If entry is a directory then get the list of files in this directory 
        if os.path.isdir(full_path):
            all_files = all_files + get_files(full_path)
        else:
            all_files.append(full_path)
                
    return all_files

def get_test_amount(type):
    pats_files = os.listdir(PATS_DIR)
    if 'queued' in type:
        if len([file for file in pats_files if 'test.bat' in file]) == 0:
            raise Exception("test.bat file not found in " + PATS_DIR)
        else:
            testbat = os.path.join(PATS_DIR, "test.bat")
            with open(testbat, 'r') as f:
                contents = f.readlines()
                contents = contents[:-1]
                return len([line for line in contents if '@REM' not in line])
    elif 'completed' in type:
        metadata_files = [file for file in pats_files if 'metadata.txt' in file]
        ran_amount = 0
        if len([file for file in pats_files if 'test.bat' in file]) == 0:
            raise Exception("test.bat file not found in " + PATS_DIR)
        else:
            testbat = os.path.join(PATS_DIR, "test.bat")
            with open(testbat, 'r') as f:
                contents = f.readlines()
                contents = contents[:-1]
                for file in metadata_files:
                    for line in contents:
                        if file.replace("_metadata.txt", "") in line:
                            ran_amount += 1
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

def collect_defined_tests(testbat_dir):
	"""
	1. Collect all tests defined in test.bat.
	"""
	defined_tests = []
	with open(testbat_dir, 'r') as f:
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
				test["name"] = line.split(" ")[2]
				test["config"] = os.path.basename(line.split(" ")[3])
				test["runs"] = get_nums_from_string(line.split(" ")[4])[0]
				defined_tests.append(test)
	return defined_tests

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
    PATS_dir = "C:\\Users\\acwh025\OneDrive - City, University of London\\PhD\\PAT\\PATS"

    testbat_dir = os.path.join(PATS_dir, "test.bat")

    if not exists(testbat_dir):
        console.print("test.bat file not found.", style="bold red")
        raise Exception()

    defined_tests = collect_defined_tests(testbat_dir)
    assign_test_statuses(defined_tests, testbat_dir)
    return defined_tests

def collect_defined_tests():
	defined_tests = []
	with open(os.path.join(PATS_DIR, 'test.bat'), 'r') as f:
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
	return defined_tests

def get_current_test():
    curdir_files = get_files(os.path.curdir)
    for test in collect_defined_tests():
        name = test["name"]
        if not len([file for file in curdir_files if name in file and 'metadata' in file]) > 0:
            return name

    