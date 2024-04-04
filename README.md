# OpenAPI/Swagger Crawler

# Introduction
This software, referred to as the crawler, is specifically engineered to mine GitHub repositories for OpenAPI and Swagger documentation files. Its purpose is to systematically collect and catalog API descriptions that adhere to these widely recognized specifications, facilitating a comprehensive analysis of web API trends and practices directly from source code repositories.

# Requirements
This software is built with Python3.
For installing all required dependencies, execute the command: `pip install -r requirements.txt`, or refer to the Installation section of this document for detailed instructions. 

# Installation
To initiate the wizard configurator, execute the command: `python3 install.py`. 
This script handles populating the .env file and installing all necessary dependencies via pip. Ensure to populate the `github_tokens` table with your GitHub tokens.

# Usage
To launch the crawler, run `./start.sh` which initiates all components at once. If you prefer to start each component individually, use the specific command for each:

- To start Curiosity: `./curiosity`
- To start Parser: `./parser`
- To start PathFinder: `./pathfinder`
- To start Updater: `./updater`
- To start Validator: `./validator`

Before running these commands, make sure to set the appropriate execution permissions for each file by using: 
`chmod +x <filename>`