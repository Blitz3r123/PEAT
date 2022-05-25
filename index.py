from gc import collect
from flask import Flask, render_template

from all_functions import *
from PRIVATE import *

app = Flask(__name__)

PTS_DIR = "C:/Users/acwh025/Downloads/PTS"

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
    return render_template('analyse.html')