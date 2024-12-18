import yaml
import threading
import subprocess
import os
import shutil
import datetime
import sys

# Function to create temporary shell script
def create_temp_script(base_name, nesting_group, working_directory, venv_command, commands):
    script_filename = f"./tmp_scripts/{base_name}_{nesting_group}.sh"
    with open(script_filename, 'w') as script_file:
        script_file.write("#!/bin/bash\n")
        script_file.write(f"echo 'Date: {datetime.datetime.now()}'\n")
        script_file.write(f"echo 'Script: {script_filename}'\n")
        script_file.write(f"cd {working_directory}\n")  # Switch to the working directory
        if venv_command:
            script_file.write(f"{venv_command}\n")  # Activate the virtual environment
        for command in commands:
            script_file.write(f"{command}\n")
    os.chmod(script_filename, 0o755)  # Make the script executable
    return script_filename

# Function to execute a script in an xterm window
def execute_script(script_filename):
    xterm_command = f"xterm -e \"{script_filename}\""
    subprocess.Popen([xterm_command], shell=True)

def main(yaml_file):
    try:
        # Ensure the tmp_scripts directory exists
        if not os.path.exists("./tmp_scripts"):
            os.makedirs("./tmp_scripts")

        with open(yaml_file, 'r') as file:
            commands_list = yaml.safe_load(file)

        # Extract the base name of the YAML file
        base_name = os.path.splitext(os.path.basename(yaml_file))[0]

        nesting_group = 0
        for commands_info in commands_list:
            if not isinstance(commands_info, dict):
                raise ValueError("Each item in YAML file should be a dictionary")

            working_directory = commands_info.get('wd', '.')  # Default to current directory
            venv_command = commands_info.get('env', '')  # Default to empty string if no venv command specified
            command_list = commands_info.get('cmd', [])
            if command_list:
                nesting_group += 1
                script_filename = create_temp_script(base_name, nesting_group, working_directory, venv_command, command_list)
                print(script_filename)
                execute_script(script_filename)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <commands_yaml_file>")
    else:
        main(sys.argv[1])
