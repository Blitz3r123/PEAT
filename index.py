from gc import collect
from flask import Flask, render_template
from matplotlib.pyplot import connect

from all_functions import *
from PRIVATE import *

app = Flask(__name__)

PTS_DIR = str(Path("C:/Users/acwh025/Downloads/PTS").absolute())

@app.route("/")
def index():
    ssh = connect_to_vm()
        
    data = {
        "queued_test_amount": 0,
        "completed_test_amount": 0,
        "test_error_amount": 0,
        "current_test": ""
    }
    
    data["queued_test_amount"] = get_test_amount(ssh, 'queued')
    data["completed_test_amount"] = get_test_amount(ssh, 'completed')
    data["current_test"] = get_current_test(ssh)
    
    return render_template('index.html', data=data)

@app.route("/create")
def create_base():
    ssh = connect_to_vm()
    data = {
        "tests": [],
        "test_amount": 0
    }
    
    data["tests"] = collect_defined_tests(ssh)
    data["test_amount"] = len(collect_defined_tests(ssh))
    
    return render_template('create.html', data=data)

@app.route("/create/<string:test_name>/<string:config_file>")
def create(test_name, config_file):
    ssh = connect_to_vm()
    data = {
        "tests": [],
        "test_amount": 0
    }
    
    data = get_test_details(ssh, test_name, config_file)
    data["tests"] = collect_defined_tests(ssh)
    data["test_amount"] = len(collect_defined_tests(ssh))
    data["pub_amount"] = sum(data["pub_alloc"])
    data["mal_pub_amount"] = sum(data["mal_pub_alloc"])
    data["sub_amount"] = sum(data["sub_alloc"])
    data["mal_sub_amount"] = sum(data["mal_sub_alloc"])
    config_content = get_config_content(ssh, config_file)
    config_content = "".join(config_content).replace("\\n", "\n")
    pprint(json.dumps(json.loads(config_content), indent = 4, sort_keys = True))
    data["config_content"] = config_content
    
    return render_template(
        'create_view_test.html', 
        data=data, 
        pub_settings=data['pub_settings'], 
        sub_settings=data['sub_settings'], 
        mal_pub_settings=data['mal_pub_settings'], 
        mal_sub_settings=data['mal_sub_settings']
    )

@app.route("/run")
def run():
    ssh = connect_to_vm()
    data = {
        "current_test": None,
        "defined_tests": []
    }
    data["current_test"], data["current_test_config"] = get_current_test(ssh)
    data["defined_tests"] = collect_defined_tests(ssh)
    pprint(data)
    return render_template('run.html', data=data)

@app.route("/analyse")
def analyse():
    data = {
        "test_files": [],
        "test_names": [],
        "has_config": [],
        "config_files": [],
        "config_runs": [],
        "data_runs": [],
        "sub_count": [],
        "mal_sub_count": [],
        "pub_count": [],
        "mal_pub_count": [],
        "run_participants": [],
        "total_test_durations": [],
        "errors": []
    }
    
    ssh = connect_to_vm()
    
    test_folders = get_test_folders()
    
    new_file_names = format_test_titles(test_folders)

    # Sort both in the same order
    new_file_names, test_folders = zip(*sorted(zip(new_file_names, test_folders)))

    config_files = [file for file in get_files(ssh, PTS_DIR) if 'metadata.txt' in file]

    get_configs(test_folders, config_files, data)

    data['test_files'] = test_folders
    
    data['test_names'] = new_file_names
    
    data['data_runs'] = get_data_runs(test_folders)


    get_config_runs_and_participants(ssh, data)

    get_run_participants(ssh, data)

    get_total_test_durations(ssh, data)

    """
    Identify all errors and add to data['errors'].
    Errors:
    1. Config not found.
        - Can't read any config data.
    2. 0 runs.
        - No restarts recorded in the config file.
        - Normally happens when test is interrupted before first restart.
    3. Config run and run_n folder amount mismatch.
        3.1. run_n < run
            - Hasn't completed all runs.
        3.2. run_n > run
            - HUH?!
    4. Can't read run amount from config.
        - Config file is corrupted/incomplete/something is wrong with it.
    5. Participant amount == 0 from config.
        - Either error with analysis.py or for some reason there are no participants in the config file.
    6. Config participants and test result participant amount mismatch.
        - Test results haven't been downloaded properly.
        6.1. Config participants > test result participants
            - Missing test data
        6.2. Config participants < test result participants
            - HUH?!
    7. Test duration hasn't been calculated in the config file.
        - Test has probably been interrupted and there is no test end
        7.1. Test Start exists but Test End doesn't
            - Test has been interrupted and didn't complete properly
        7.2. Test End exists but Test Start doesn't
            - HUH?!
    8. Test duration doesn't match duration set in config
        - Very weird...
    """
    for i in range(len(data['test_files'])):
        error = ""
        # 1. Config not found.
        if data["has_config"][i] == False:
            error = "Config file not found."
        else:
            # 2. 0 runs.
            if int(data["config_runs"][i]) == 0:
                error = error + "\n0 runs recorded from config file. It's probably the case that no restarts have been recorded."
            
            # 3. Config run and run_n folder mismatch.
            if not (data["config_runs"][i] == data["data_runs"][i]):
                error = error + "\nMismatch between config run amount and run_n folders."
                if data["data_runs"][i] < data["config_runs"][i]:
                    error = error + "\n\tTest hasn't completed all runs. Missing run_n folders."
                    error = error + "\n\tResults contain " +str(data["data_runs"][i])+ "/" +str(data["config_runs"][i])+ " runs."
                else:
                    error = error + "\n\tHUH?! What happened here? How has this happened???"
                    error = error + "\n\tResults contain " +str(data["data_runs"][i])+ "/" +str(data["config_runs"][i])+ " runs."
                    error = error + "\n\tYeah...somehow...there is more run data than configured runs...."

            # 4. Can't read run amount from config.
            if data["config_runs"][i] == 0:
                error = error + "\nCouldn't read run amount from config."
                error = error + "\n\tConfig file is corrupted or incomplete or something else is wrong with it:"
                # error = error + "\n\t" + data["config_files"][i]

            # 5. Participant amount == 0 from config.
            if data["pub_count"][i] == 0 and data["sub_count"][i] == 0 and data["mal_pub_count"][i] == 0 and data["mal_sub_count"][i] == 0:
                error = error + "\nParticipant amount is 0 according to the config file."
                error = error + "\n\tEither there is a bug in analysis.py (the code behind this) or it's actually set to 0 in the config file..."

            # 6. Config participant and test results participant amount mismatch.
            runs_arr = data["run_participants"][i]
            for run in runs_arr:
                if len(run) > 0:
                    if not (run['pub_count'] + run['mal_pub_count'] == data['pub_count'][i] + data['mal_pub_count'][i]):
                        error = error + "\nPublisher amount mismatch for Run " + str(runs_arr.index(run) + 1)  + " results."

                    if not (run['sub_count'] + run['mal_sub_count'] == data['sub_count'][i] + data['mal_sub_count'][i]):
                        error = error + "\nSubscriber amount mismatch for Run " + str(runs_arr.index(run) + 1)  + " results."

            # 7. Test duration hasn't been calculated in the config file
            test_duration = data['total_test_durations'][i]
            config_file = data['config_files'][i]
            
            if test_duration == "-":
                error = error + "\nTest Duration not seen in config file."

            with ssh.open_sftp().open(os.path.join(PTS_DIR, config_file), "r") as f:
                file_contents = f.readlines()
                test_start_lines = [line for line in file_contents if "Test Start" in line]
                test_end_lines = [line for line in file_contents if "Test End" in line]
                # 7.1. Test Start exists but Test End doesn't
                if len(test_start_lines) > 0 and len(test_end_lines) == 0:
                    test_start = test_start_lines[0].split(" ")[3]
                    error = error + "\n\tTest Start found to be " + str(test_start) + " \tbut there is no Test End..."

                    restart_lines = [line for line in file_contents if "Restart VM" in line]

                    error = error + "\n\t\tVM 1 restarted " + str(len([line for line in restart_lines if "10.200.51.21" in line])) + " time(s)."
                    error = error + "\n\t\tVM 2 restarted " + str(len([line for line in restart_lines if "10.200.51.22" in line])) + " time(s)."
                    error = error + "\n\t\tVM 3 restarted " + str(len([line for line in restart_lines if "10.200.51.23" in line])) + " time(s)."
                    error = error + "\n\t\tVM 4 restarted " + str(len([line for line in restart_lines if "10.200.51.24" in line])) + " time(s)."

                elif len(test_start_lines) == 0 and len(test_end_lines) > 0:
                    error = error + "\n\tHUH?! There is a Test End but no Test Start in the config file. How has that happened?!"

            # 8. Test duration doesn't match duration set in config
            with ssh.open_sftp().open(os.path.join(PTS_DIR, config_file), 'r') as f:
                content = f.readlines()
                execution_times = []
                for line in content:
                    if '-executionTime' in line:
                        for time in [item for item in line.split(" -") if "executionTime" in item]:
                            execution_times.append(get_nums_from_string(time)[0])

            # Make sure all execution_times match
            no_dupe_execution_times = list(dict.fromkeys(execution_times))
            if len(no_dupe_execution_times) > 1:
                error = error + "\nThe -executionTime amounts do NOT match."
                error = error + "\n\t" + str(len(no_dupe_execution_times)) + " values have been seen: "
                error = error + "\n\t"
                for time in no_dupe_execution_times:
                    error = error + str(time) + " "
            else:
                config_duration = no_dupe_execution_times[0]
                actual_duration = convert_to_secs(test_duration)
                config_duration_hours = config_duration // 3600
                actual_duration_hours = actual_duration // 3600

                if config_duration_hours != actual_duration_hours:
                    error = error + "\nConfig duration and actual test duration do NOT match:"
                    error = error + "\n\tConfig Duration: " + str(datetime.timedelta(seconds=config_duration))
                    error = error + "\n\tActual Duration: " + str(datetime.timedelta(seconds=actual_duration))

            execution_times = []

        data['errors'][i] = error.lstrip()
    data["amount"] = range(len(data['test_files']))
    return render_template('analyse.html', data=data)