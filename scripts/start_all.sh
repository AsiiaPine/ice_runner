#!/bin/bash
script_name=`basename "$0"`

venv_dir=$1
check_interval=60

print_help() {
    echo "usage: $script_name [-h] <path_to_venv> <check_interval>"
    echo "example: $script_name venv 60"
}

if [ "$1" = "--help" ]; then
    print_help
    [[ "${BASH_SOURCE[0]}" -ef "$0" ]] && exit 0 || return
elif [ $# -lt 1 ]; then
    print_help
    echo "$script_name: error: the following arguments are required: path_to_venv"
    [[ "${BASH_SOURCE[0]}" -ef "$0" ]] && exit 0 || return
fi

re='^[0-9]+$'
if [ $# -eq 2  ]; then
    if ! [[ $2 =~ $re ]] ; then
        echo "error: Not a number" >&2; exit 1
    else
        check_interval=$2
        echo "Check interval set to $check_interval"
    fi
fi

JOB2="src/ice_runner/main.py"
JOB1="src/ice_runner/main.py"
JOB3="src/ice_runner/main.py"


JOB1_PARAMS="--log_dir=logs srv"
JOB2_PARAMS="--id=1 --config=ice_configuration.yml --log_dir=logs client"
JOB3_PARAMS="--log_dir=logs bot"

JOB1_NAME="Server"
JOB2_NAME="Client"
JOB3_NAME="Bot"

# Check if .env file exists and source it
if [ -f .env ]; then
    source .env
else
    echo ".env file not found! Exiting..."
    exit 1
fi

# Telegram bot setup: 
if [[ -z "$BOT_TOKEN" || -z "$CHAT_ID" ]]; then
    echo "Telegram BOT_TOKEN or CHAT_ID not set!"
    exit 1
fi

# Telegram bot setup: Replace with your actual credentials
TELEGRAM_API="https://api.telegram.org/bot$BOT_TOKEN/sendMessage"

# trying to acrivate a venv:
if [ ! -d "$venv_dir" ]; then
    echo "venv not found! Exiting..."
    exit 1
else 
    file="$venv_dir/bin/activate"
    if [ ! -f "$file" ]; then
        echo "venv not found! Exiting..."
        exit 1
    fi
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
    output_file="logs/$JOB_NAME.log"
    source $venv_dir/bin/activate
    nohup python $JOB_CALL $JOB_PARAMS > $output_file 2>&1 &
    echo $!
}

# Trap EXIT signal to ensure processes are stopped when the script exits
cleanup() {
    send_telegram_message "Stopping all jobs..."
    kill $JOB1_PID
    kill $JOB2_PID
    kill $JOB3_PID
    send_telegram_message "All jobs stopped."
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
        send_telegram_message "$JOB1 остановленн. Перезапуск."
        JOB1_PID=$(start_job $JOB1 $JOB1_PARAMS)
        send_telegram_message "$JOB1 перезапущена, новый PID $JOB1_PID."
    fi

    if ! kill -0 $JOB2_PID 2>/dev/null; then
        send_telegram_message "$JOB2 остановленн. Перезапуск."
        JOB2_PID=$(start_job $JOB2 $JOB2_PARAMS)
        send_telegram_message "$JOB2 перезапущена, новый PID $JOB2_PID."
    fi

    if ! kill -0 $JOB3_PID 2>/dev/null; then
        send_telegram_message "$JOB3 остановленн. Перезапуск."
        JOB3_PID=$(start_job $JOB3 $JOB3_PARAMS)
        send_telegram_message "$JOB3 перезапущена, новый PID $JOB3_PID."
    fi
done
