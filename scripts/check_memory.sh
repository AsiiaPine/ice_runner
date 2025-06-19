#!/usr/bin/env bash

# Constants

THRESHOLD=3000   # Memory threshold in MB
DIR_TO_WATCH="logs/raspberry"
LOG_FILE="logs/memory_manager.log"

# Functions
print_help() {
    echo "Usage: $SCRIPT_NAME [-h] [-m <memory_threshold>] [-d <dir_to_watch>] [-t <telegram_bot_token>] [-c <telegram_chat_id>] [-l <log_file>]
This script checks the available memory on the system and deletes files from a specified directory if the available memory is below a specified threshold. It sends a Telegram message to a specified chat if the memory is below the threshold.

Options:
    -m, --memory                    The memory threshold in MB (default: 3000).
    -d, --dir                       The directory to watch for files (default: logs/raspberry).
    -t, --telegram_bot_token        The Telegram bot token (default: your_telegram_bot_token).
    -c, --telegram_chat_id          The Telegram chat ID (default: your_chat_id).
    -l, --log_file                  The log file to write to (default: logs/memory_manager.log).
    -h, --help                      Display this help message and terminate.
"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_help
            exit 0
            ;;
        -m|--memory)
            re='^[0-9]+$'
            if ! [[ $2 =~ $re ]] ; then
                log_error "m option error: $2 is not a number" >&2; exit 1
            else
                THRESHOLD=$2
            fi
            shift
            ;;
        -d|--dir)
            DIR_TO_WATCH=$2
            shift
            ;;
        -t|--telegram_bot_token)
            BOT_TOKEN=$2
            shift
            ;;
        -c|--telegram_chat_id)
            CHAT_ID=$2
            shift
            ;;
        -l|--log_file)
            LOG_FILE=$2
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

# Telegram bot setup: 
if [[ -z "$BOT_TOKEN" || -z "$CHAT_ID" ]]; then
    echo "Telegram BOT_TOKEN or CHAT_ID not set!"
    exit 1
fi

# Function to send a message to Telegram
send_to_telegram() {
    local TEXT="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage"\
    -d chat_id=$CHAT_ID -d text="$TEXT" > /dev/null
}

# Function to send a file with file to Telegram
send_file_to_telegram() {
    local TEXT="$1"
        local RESPONSE

    # Send the file and capture the HTTP response status code
    # RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null -F "chat_id=${CHAT_ID}" -F document=@"${FILE_PATH}" -F caption="Бэкап файла, удаляем его" \
    # https://api.telegram.org/bot${BOT_TOKEN}/sendDocument)
    RESPONSE=$(curl -s -F "chat_id=${CHAT_ID}" -F document=@${TEXT} -F caption="Бэкап файла, удаляем его" https://api.telegram.org/bot${BOT_TOKEN}/sendDocument)
    echo $RESPONSE
}

# Logging function
log() {
    local TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    echo "$TIMESTAMP $1" | tee -a $LOG_FILE
}

# Check available memory
check_memory() {
    local AVAILABLE_MEMORY=$(free -m | awk '/^Mem:/{print $7}')
    echo $AVAILABLE_MEMORY
}

# Process file by prefix
process_files() {
    declare -A FILE_GROUPS

    # Group files by prefix
    for FILE_PATH in "$DIR_TO_WATCH"/*; do
        FILE_NAME=$(basename "$FILE_PATH")
        # should delete files for any date from 2000 to 9999th
        # PREFIX=$(echo "$FILE_NAME" | sed 's/\([a-zA-Z0-9._]*\)_2025_.*/\1/')  # Adjust pattern as needed
        # PREFIX=$(echo "$FILE_NAME" | sed 's/\([a-zA-Z0-9._]*\)_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_.*//')  # Adjust pattern as needed
        # PREFIX=$(echo "$FILE_NAME" | sed -E 's/(.*)_[0-9]{4}-[0-9]{2}-[0-9]{2}_.*/\1/')
        PREFIX=$(echo "$FILE_NAME" | sed -E 's/([^.]+)\.[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}\..*$/\1/')
        echo "PREFIX: $PREFIX"
        # PREFIX=$(echo "$FILE_NAME" | sed 's/\([a-zA-Z0-9._]*\)_[2-9][0-9][0-9][0-9]_.*/\1/')
        FILE_GROUPS["$PREFIX"]+="$FILE_PATH "
    done

    # Iterate over grouped files
    for PREFIX in "${!FILE_GROUPS[@]}"; do
        FILES=(${FILE_GROUPS[$PREFIX]})
        if [[ ${#FILES[@]} -gt 2 ]]; then
            # Sort by timestamp (assumes the part after the prefix is sortable)
            SORTED_FILES=($(printf "%s\n" "${FILES[@]}" | sort))

            # Delete only the oldest file in the group
            OLDEST_FILE=${SORTED_FILES[0]}
            echo "Deleting oldest file in group '$PREFIX': $OLDEST_FILE"
            if [ ! -s $OLDEST_FILE ]; then
                echo "The file is empty.";
                rm "$FILE_PATH"
                log "File deleted: $FILE_PATH"
            else
                res=$(send_file_to_telegram $OLDEST_FILE)
                # Parse the JSON to see if sending the file was successful
                if [[ $(echo $res | jq '.ok') == "true" ]]; then
                    log "File sent successfully: $FILE_PATH"
                    rm "$FILE_PATH"
                    log "File deleted: $FILE_PATH"
                else
                    log "Failed to send file: $FILE_PATH, HTTP response code: $res"
                fi
            fi
        fi
    done
}

# Main script logic
main() {
    local AVAILABLE_MEMORY=$(check_memory)

    if (( AVAILABLE_MEMORY < THRESHOLD )); then
        log "Available memory ($AVAILABLE_MEMORY MB) is below threshold ($THRESHOLD MB)."
        process_files
    fi
}

# Execute the main logic
main
