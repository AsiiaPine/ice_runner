#!/bin/bash
# This software is distributed under the terms of the MIT License.
# Copyright (c) 2024 Anastasiia Stepanova.
# Author: Anastasiia Stepanova <asiiapine@gmail.com>

SCRIPT_NAME=$(basename $BASH_SOURCE)

RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

venv_dir="venv"
check_interval=60

print_help() {
    echo "Usage: $SCRIPT_NAME [-h] [-v <venv_dir>] [-i <check_interval_sec>] [-e <env_file>] [-l <log_dir>]
This utility facilitates the automatic background initialization of server, client, and bot processes. It monitors these processes at set intervals and restarts them if they are found to be inactive. All actions carried out by this script are logged via the associated Telegram bot. It is imperative that the BOT_TOKEN and CHAT_ID variables are defined, either as environment variables or within the specified .env file.

Options:
    -i, --interval                  The interval, in seconds, between process status checks (default: 60).
    -e, --env                       File path to the .env file containing BOT_TOKEN and CHAT_ID (default: .env).
    -v, --venv                      File path to the Python virtual environment (default: venv).
    -l, --log_dir                   Path to the log directory (default: logs).
    -h, --help                      Display this help message and terminate.
    
Example: ./$SCRIPT_NAME -v venv -i 60 -e .env"
}

function log_error() {
    lineno=($(caller))
    printf "$RED$SCRIPT_NAME ERROR on line ${lineno}: $1!$NC\n"
}

function log_warn() {
    lineno=($(caller))
    printf "$YELLOW$SCRIPT_NAME WARN on line ${lineno}: $1.$NC\n"
}

function log_info() {
    printf "$SCRIPT_NAME INFO: $1.\n"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_help
            exit 0
            ;;
        -v|--venv)
            venv_dir=$2
            if [ ! -d "$venv_dir" ]; then
                echo "$venv_dir no such directory! Exiting..."
                exit 1
            fi
            shift
            ;;
        -e|--env)
            if [ -f $2 ]; then
                source $2
            else
                echo ".env file not found! Exiting..."
                exit 1
            fi
            shift
            ;;
        -i|--interval)
            re='^[0-9]+$'
            if ! [[ $2 =~ $re ]] ; then
                log_error "i option error: $2 is not a number" >&2; exit 1
            else
                check_interval=$2
                echo "Check interval set to $check_interval"
            fi
            shift
            ;;
        --l|--log_dir)
            log_dir=$2
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


JOB2="src/ice_runner/main.py"
JOB1="src/ice_runner/main.py"
JOB3="src/ice_runner/main.py"


JOB1_PARAMS="--log_dir=$log_dir srv"
JOB2_PARAMS="--id=1 --config=ice_configuration.yml --log_dir=$log_dir client"
JOB3_PARAMS="--log_dir=$log_dir bot"

JOB1_NAME="Сервер"
JOB2_NAME="Обкатчик"
JOB3_NAME="Бот"

# Telegram bot setup: 
if [[ -z "$BOT_TOKEN" || -z "$CHAT_ID" ]]; then
    echo "Telegram BOT_TOKEN or CHAT_ID not set!"
    exit 1
fi

# Telegram bot setup: Replace with your actual credentials
TELEGRAM_API="https://api.telegram.org/bot$BOT_TOKEN/sendMessage"

# trying to acrivate a venv:
file="$venv_dir/bin/activate"
if [ ! -f "$file" ]; then
    echo "venv activate script not found! Exiting..."
    exit 1
fi

# Function to send a message to a Telegram chat
send_telegram_message() {
    MESSAGE=$1
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "{
        \"chat_id\": \"${CHAT_ID}\",
        \"text\": \"$MESSAGE\",
        \"parse_mode\": \"HTML\",
        \"disable_web_page_preview\": true,
        \"disable_notification\": true,
    }" > /dev/null
    if [ $? -ne 0 ]; then
        echo "Failed to send Telegram message!"
    fi
    sleep 1
}

# Function to start a job in the background
start_job() {
    local JOB_CALL=$1
    local JOB_PARAMS=$2
    local JOB_NAME=$3
    output_file="$log_dir/$JOB_NAME.log"
    source $venv_dir/bin/activate
    nohup python $JOB_CALL $JOB_PARAMS > $output_file 2>&1 &
    echo $!
}

# Trap EXIT signal to ensure processes are stopped when the script exits
cleanup() {
    kill $JOB1_PID
    kill $JOB2_PID
    kill $JOB3_PID
    send_telegram_message "Все запущенные процессы остановлены."
}

trap "cleanup" EXIT

# Start the jobs
JOB1_PID=$(start_job "$JOB1" "$JOB1_PARAMS" "$JOB1_NAME")
JOB2_PID=$(start_job "$JOB2" "$JOB2_PARAMS" "$JOB2_NAME")
JOB3_PID=$(start_job "$JOB3" "$JOB3_PARAMS" "$JOB3_NAME")


# Send initial Telegram message
send_telegram_message "Усе запущено!"

# Continuously check if jobs are still running
while true; do
    sleep $check_interval  # Check every 60 seconds

    # Check if each job is still running
    if ! kill -0 $JOB1_PID 2>/dev/null; then
        log_warn "$JOB1_NAME остановленн. Перезапуск."
        JOB1_PID=$(start_job $JOB1 $JOB1_PARAMS)
        send_telegram_message "$JOB1_NAME перезапущен, новый PID $JOB1_PID."
    fi

    if ! kill -0 $JOB2_PID 2>/dev/null; then
        log_warn "$JOB2_NAME остановленн. Перезапуск."
        JOB2_PID=$(start_job $JOB2 $JOB2_PARAMS)
        send_telegram_message "$JOB2_NAME перезапущен, новый PID $JOB2_PID."
    fi

    if ! kill -0 $JOB3_PID 2>/dev/null; then
        log_warn "$JOB3_NAME остановленн. Перезапуск."
        JOB3_PID=$(start_job $JOB3 $JOB3_PARAMS)
        send_telegram_message "$JOB3_NAME перезапущен, новый PID $JOB3_PID."
    fi
done
