from flask import Flask, render_template

from all_functions import *

app = Flask(__name__)

@app.route("/")
def index():
    PATS_dir = "C:\\Users\\acwh025\OneDrive - City, University of London\\PhD\\PAT\\PATS"

    testbat_dir = os.path.join(PATS_dir, "test.bat")

    if not exists(testbat_dir):
        console.print("test.bat file not found.", style="bold red")
        raise Exception()

    defined_tests = collect_defined_tests(testbat_dir)
    assign_test_statuses(defined_tests, testbat_dir)
    pending_tests = [test for test in defined_tests if test["status"] == "pending"]
    return render_template('index.html', tests=defined_tests, pending=True)