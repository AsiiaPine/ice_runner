#!/usr/bin/env bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2025 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

PY_VERSION=3.10.16

print_help() {
    echo "usage: $script_name [-h] <version>"
    echo "The script will create new python environment with provided python version using pyenv.
    If python or pyenv are not installed, the script will suggest the installation."
    echo "example: $script_name 3.10.16"
}


function log_error() {
    lineno=($(caller))
    printf "$RED$SCRIPT_NAME ERROR on line ${lineno}: $1!$NC\n"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_help
            exit 0
            ;;
        -v|--version)
            PY_VERSION=$2
            shift
            ;;
            *)
        log_error "Unknown option: $1"
        echo "$HELP"
        [[ "${BASH_SOURCE[0]}" -ef "$0" ]] && exit 1 || return 1
        ;;
    esac
    shift
done

function yes_or_no {
    while true; do
        read -p "$* [Y/n]: " yn
        yn=${yn:-Y}  # Set yn to Y if the user pressed Enter (default)
        case $yn in
            [Yy]*) echo 1 ; return 0 ;;  
            [Nn]*) echo "Aborted" ; echo  0; return  0 ;;
            *) echo "Please answer Y or n." ;;  # Handle invalid input
        esac
    done
}

function get_installer_command() {
    #check OS version
    if [ -f /etc/os-release ]; then
        # freedesktop.org and systemd
        . /etc/os-release
        OS=$NAME
        VER=$ID
    elif [ -f /etc/lsb-release ]; then
        # For some versions of Debian/Ubuntu without lsb_release command
        . /etc/lsb-release
        OS=$DISTRIB_ID
        VER=$DISTRIB_RELEASE
    elif [ -f /etc/debian_version ]; then
        # Older Debian/Ubuntu/etc.
        OS="Debian"
        VER=$(cat /etc/debian_version)
    fi
    if [ "$OS" = "Ubuntu" ] || [[ "$OS" == *"Debian"* ]] || [[ "$OS" == *"Raspbian"* ]]; then
        installer_command="apt install"
    elif [ "$OS" = "Manjaro Linux" ]; then
        installer_command="pacman -S"
    else
        echo "Unsupported OS {$OS}"
        exit 1
    fi
    echo $installer_command
}

# check if python use virtual environment
function check_virtual_env() {
    python_str=$(which python3)
    if [[ $python_str == *"bin"* ]]; then
        echo 1
        else
        echo 0
    fi
}

function check_python_version() {
    data=$(python -V | grep -o "Python ${PY_VERSION}")
    echo $data
    if [ "${data}" != "Python ${PY_VERSION}" ]; then
        echo "You are not using Python 3.10."
        switch_python=$(yes_or_no "Do you want to switch to it?")
        if [ "$switch_python" == 1 ]; then
            pyenv=$(which pyenv 2>&1)
            echo "Checking if pyenv is installed..."
            # if [[ $pyenv == *"no pyenv"* ]]; then
            if [ -z "$pyenv" ]; then
                echo "Pyenv is a tool that allows you to easily switch between multiple versions of Python. It is recommended to use pyenv to manage your Python versions."
                install_pyenv=$(yes_or_no "Do you want to install pyenv?")

                if [ "$install_pyenv" == 1 ]; then
                    echo "Installing pyenv..."
                    installer_command=$(get_installer_command)
                    if [[ $installer_command == *"Unsupported"* ]]; then
                        echo $installer_command
                        exit 1
                    fi
                    sudo $installer_command pyenv
                    echo "Done."
                fi
                    echo "pyenv is not installed."
                    echo "Exiting..."
                    exit 1
            fi
            echo "Switching to Python 3.10..."
            is_there_needed_version=$(pyenv local 3.10.16 2>&1)
            if [[ $is_there_needed_version == *"not installed"* ]]; then
                pyenv install 3.10.16
                pyenv local 3.10.16
            fi
            echo "Done."
        else
            echo "Exiting..."
            exit 1
        fi
    fi
}

function check_python_packages() {
    echo "Checking if you have the required packages..."
    errormessage=$(pip -vvv freeze -r requirements.txt 2>&1)

    if [[ $errormessage == *"not installed"* ]]; then
        install_packages=$(yes_or_no "Some required packages are not installed. Do you want to install them?")
        if [ "$install_packages" == 1 ]; then
            echo "Installing required packages..."
            pip install -r requirements.txt
            echo "Done."
        else
            echo "Exiting..."
            exit 1
        fi
    else
        echo "Required packages are already installed."
    fi
}

check_python_version
is_venv_activated=$(check_virtual_env)

if [ "$is_venv_activated" == 0 ]; then
    create_venv=$(yes_or_no "You are not in a virtual environment. Do you want to create one?")
    if [ "$create_venv" == 1 ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        echo "Exiting..."
        exit 1
    fi
else
    check_python_packages
fi
