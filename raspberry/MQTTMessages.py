# Comander is used to store raspberry state like is it started or stopped
# Bot receives statuses from raspberry and sends them to telegram
# Bot commands firstly received by commander and then send to raspberry

# Raspberry decides how to handle commands based on nodes statuses by its own

bot_transmit_messages = {
    "start": "start",
    "stop": "stop",
    "configuration": "configuration"
}

bot_receive_messages = {
    "configuration": "configuration",
    "nodes_status": "nodes_status"
}

raspberry_transmit_messages = {
    "commands": "commands",
    "commander": "commander"
}

commander_receive_messages = {
    "start": "start",
    "stop": "stop"
}

commander_transmit_messages = {
    ""
}
