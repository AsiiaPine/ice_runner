import argparse
import os.path

script_dir = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['bot', 'sim', 'client', 'srv'])
parser.add_argument('--log_dir', default=script_dir)
command, rem = parser.parse_known_args()

if command.command == 'bot':
    from ice_runner.bot.main import start
    start(command.log_dir, rem)

elif command.command == 'sim':
    from ice_runner.ice_sim.test_commander import start
    start(rem)

elif command.command == 'client':
    from ice_runner.raspberry.main import start
    start(command.log_dir, rem)

elif command.command == 'srv':
    from ice_runner.server.main import start
    start(command.log_dir, rem)
