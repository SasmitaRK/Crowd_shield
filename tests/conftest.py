import sys

# The tests never change the app's code while they run, and they swap parts of its modules for
# stand-ins, so main.py must not reload those modules (see the code-stamp check at its top).
sys.crowdshield_code_stamp = "tests"
