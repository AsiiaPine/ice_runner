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

FILES_ARRAY=()
send_media_group_to_telegram() {
    output=$(python src/ice_runner/bot/telegram/helper.py $BOT_TOKEN $CHAT_ID $FILES_ARRAY "Logs backup from ${DIR_TO_WATCH}")
    echo $output
}

add_file_to_media_group() {
    local FILE="$1"
    echo "Added $FILE to media group"
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
        PREFIX=$(echo "$FILE_NAME" | sed -E 's/(.*)_[0-9]{4}-[0-9]{2}-[0-9]{2}_.*/\1/')
        # echo "PREFIX: $PREFIX"
        FILE_GROUPS["$PREFIX"]+="$FILE_PATH "
    done

    # Iterate over grouped files
    for PREFIX in "${!FILE_GROUPS[@]}"; do
        FILES=(${FILE_GROUPS[$PREFIX]})
        if [[ ${#FILES[@]} -gt 1 ]]; then
            # Sort by timestamp (assumes the part after the prefix is sortable)
            SORTED_FILES=($(printf "%s\n" "${FILES[@]}" | sort))
            for FILE in ${SORTED_FILES[*]}; do
                # Check if the file is empty
                if [ -s "$FILE" ]; then
                    if lsof "$FILE" >/dev/null 2>&1; then
                        echo "File $FILE is locked"
                        continue
                    fi
                    FILES_ARRAY+=("$FILE")
                    break
                else
                    echo "File $FILE is empty, deleting"
                    rm "$FILE"
                    log "File deleted: $FILE"
                fi
            done

        fi
    done

    echo "Sending media group ${DIR_TO_WATCH}"
    if [ ${#FILES_ARRAY[@]} -eq 0 ]; then
        log "No files to send\n"
        return
    fi
    echo "Files to send: ${FILES_ARRAY[*]}"
    res=$(send_media_group_to_telegram)
    echo "res $res"
    if [ $res -ne 1 ]; then
        sleep 2
        echo "Deleting oldest file in group '$PREFIX': $OLDEST_FILE"
        for FILE in ${FILES_ARRAY[*]}; do
            rm "$FILE"
            log "File deleted: $FILE"
        done
        return
    fi
    log "Failed to send media group: $res"
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
