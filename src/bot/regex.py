import re

command = "./script.py --chat-id 12345 --rpm 4500 --time 3600 --report-period 600"

# Adjusting the regex pattern to standard character classes
pattern = r'--(\S+) (\d+)'

# Extract the matches
matches = re.findall(pattern, command)

# Convert matches to list of dictionaries
result = [{'name': name, 'value': int(value)} for name, value in matches]

print(result)
