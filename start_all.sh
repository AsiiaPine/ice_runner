#!/bin/bash

JOB2="src/ice_runner/main.py"
JOB1="src/ice_runner/main.py"
JOB3="src/ice_runner/main.py"

JOB1_PARAMS="--log_dir=logs bot"
JOB2_PARAMS="--log_dir=logs srv"
JOB3_PARAMS=" --id=1 --config=ice_configuration.yml --log_dir=logs client"

JOB1_NAME="Bot"
JOB2_NAME="Server"
JOB3_NAME="Client"

source .env

# Telegram bot setup: Replace with your actual credentials
TELEGRAM_API="https://api.telegram.org/bot$BOT_TOKEN/sendMessage"

# Function to send a message to a Telegram chat
send_telegram_message() {
    MESSAGE=$1
    curl -s --data "chat_id=$CHAT_ID&text=$MESSAGE" $TELEGRAM_API > /dev/null
}

# Function to start a job in the background
start_job() {
    local JOB_NAME="$1"
    local JOB_CALL="$2"
    local JOB_PARAMS="$3"
    echo "Starting job: $JOB_NAME with params: $JOB_PARAMS"
    python $JOB_CALL $JOB_PARAMS > /dev/null
    echo $!
}

# Start the jobs
JOB1_PID=$(start_job "$JOB1_NAME" "$JOB1" "$JOB1_PARAMS")
JOB2_PID=$(start_job "$JOB2_NAME" "$JOB2" "$JOB2_PARAMS")
JOB3_PID=$(start_job "$JOB3_NAME" "$JOB3" "$JOB3_PARAMS")

# Send initial Telegram message
send_telegram_message "Hello, World!
Jobs started:
$JOB1_PID NAME=${JOB1_NAME},
$JOB2_PID NAME=${JOB2_NAME},
$JOB3_PID NAME=${JOB3_NAME}."

# Continuously check if jobs are still running
while true; do
    sleep 60  # Check every 60 seconds

    # Check if each job is still running
    if ! kill -0 $JOB1_PID 2>/dev/null; then
        send_telegram_message "$JOB1 stopped. Restarting."
        JOB1_PID=$(start_job $JOB1 $JOB1_PARAMS)
        send_telegram_message "$JOB1 restarted with PID $JOB1_PID."
    fi

    if ! kill -0 $JOB2_PID 2>/dev/null; then
        send_telegram_message "$JOB2 stopped. Restarting."
        JOB2_PID=$(start_job $JOB2 $JOB2_PARAMS)
        send_telegram_message "$JOB2 restarted with PID $JOB2_PID."
    fi

    if ! kill -0 $JOB3_PID 2>/dev/null; then
        send_telegram_message "$JOB3 stopped. Restarting."
        JOB3_PID=$(start_job $JOB3 $JOB3_PARAMS)
        send_telegram_message "$JOB3 restarted with PID $JOB3_PID."
    fi
done
