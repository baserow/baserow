#!/bin/bash
# Bash strict mode: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail

RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
NC=$(tput sgr0) # No Color
read -p "${YELLOW}This script will overwrite any existing Zed config you might already have for this Baserow repo with a standard set of config, are you sure? ${NC}${GREEN}Enter Y or y to continue${NC}${RED}, or any other character to abort.${NC}" -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cp -a "${SCRIPT_DIR}/.zed" "${SCRIPT_DIR}/../../"
echo "${GREEN}Successfully applied the default Baserow Zed config...${NC}"
else
echo "${RED}Aborted application of the default Baserow Zed config...${NC}"
fi
