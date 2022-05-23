from gc import collect
from flask import Flask, render_template

from all_functions import *
from PRIVATE import *

app = Flask(__name__)

@app.route("/")
def index():
    # pythoncom.CoInitialize()
    # ip = get_ip()
    # try:
    #     connection = wmi.WMI(ip)
    #     testbat_dir = os.path.join(PATS_DIR, "test.bat")
    
    #     if not exists(testbat_dir):
    #         console.print("test.bat file not found.", style="bold red")
    #         raise Exception()

    #     defined_tests = collect_defined_tests(testbat_dir)
    #     assign_test_statuses(defined_tests, testbat_dir)
    #     pending_tests = [test for test in defined_tests if test["status"] == "pending"]
    #     pending = True if len(pending_tests) > 0 else False
        
    # except Exception as e:
    #     print(e)
    #     output=e
    #     defined_tests = []
    #     pending=False
    
    data = {
        "queued_test_amount": 0,
        "completed_test_amount": 0,
        "test_error_amount": 0,
        "current_test": ""
    }
    
    data["queued_test_amount"] = get_test_amount('queued')
    data["completed_test_amount"] = get_test_amount('completed')
    data["current_test"] = get_current_test()
    
    return render_template('index.html', data=data)

@app.route("/create")
def create():
    """
    1. Check if test.bat exists
    2. Get all tests that have been defined
    3. Output on create
    """
    data = {
        "tests": [],
        "test_amount": 0
    }
    
    data["tests"] = collect_defined_tests()
    data["test_amount"] = len(collect_defined_tests())
    
    return render_template('create.html', data=data)

@app.route("/run")
def run():
    return render_template('run.html')

@app.route("/analyse")
def analyse():
    return render_template('analyse.html')