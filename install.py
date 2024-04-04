import shutil

def update_env_file():
    # Specify the path to your .env file
    env_file_path = '.env'

    # Define the placeholders and their corresponding user prompts
    placeholders = {
        '<mysql_host>': 'Enter your MySQL host: ',
        '<mysql_user>': 'Enter your MySQL username: ',
        '<mysql_password>': 'Enter your MySQL password: ',
        '<output folder>': 'Enter the path to the output folder: ',
    }

    # Read the current content of the .env file
    try:
        with open(env_file_path, 'r') as file:
            content = file.readlines()
    except FileNotFoundError:
        print(f"The file {env_file_path} does not exist.")
        return

    # Ask the user for new values and replace the placeholders
    new_content = []
    for line in content:
        for placeholder, prompt in placeholders.items():
            if placeholder in line:
                # Ask the user for input
                new_value = input(prompt)
                # Replace the placeholder in the line
                line = line.replace(placeholder, new_value)
        new_content.append(line)

    # Write the updated content back to the .env file
    with open(env_file_path, 'w') as file:
        file.writelines(new_content)

    print("The .env file has been updated successfully.")

def install_requirements():
    print("Installing the required packages...")
    import subprocess

    # Install the required packages
    # run python -m pip install -r requirements.txt
    subprocess.run(['python3', '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)

    print("The required packages have been installed successfully.")

if __name__ == "__main__":
    shutil.copy('.env.template', '.env')
    update_env_file()
    install_requirements()
    print()
    print("The installation has been completed successfully.")
    print("You can now run the application using the command: ./start.sh")
    print("Make sure to populate the database table github_tokens with your GitHub tokens.")
