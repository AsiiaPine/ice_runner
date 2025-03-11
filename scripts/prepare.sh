#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

function check_python_version() {
    if ! command -v python &> /dev/null
    then
        echo "python is not installed"
        exit 1
    fi
    # check if python 3.10 is installed
    if "$PYTHON" -V 2>&1 | grep -q "Python 3.10"; then
        echo "Python 3.10 is installed"
    else
        echo "Python 3.10 is not installed"
        exit 1
    fi
}

# check if python use virtual environment
function check_virtual_env() {
echo $(python <<EOF
import sys
if sys.prefix == sys.base_prefix:
    print("No, you are not in a virtual environment.")
else:
    print("Yes, you are in a virtual environment.")
EOF
)
}

check_python_version
check_virtual_env
