sudo apt update && sudo apt upgrade
sudo apt-get install python-rpi.gpio python3-rpi.gpio
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service
sudo systemctl restart mosquitto
sudo chmod +x ./raspberry/create_slcan.sh
sudo ./raspberry/create_slcan.sh
