# Baserow Documentation

Source: https://baserow.io/user-docs/mcp-server

---

[![Baserow logo](/_nuxt/img/logo.3d74eb4.svg)](/) Docs
# MCP Server Overview

![ntegrate Baserow with LLMs using the Model Context Protocol \(MCP\) Server](https://baserow-backend-production20240528124524339000000001.s3.amazonaws.com/pagedown-uploads/d5d74fe1-99e2-4bb6-80bf-993c7b177dfa/MCP%20server.png)

Introducing the Model Context Protocol (MCP) Server: A seamless integration with Large Language Models.

We’ve integrated an MCP server directly into Baserow, enabling easy interaction with Large Language Models like Claude or Cursor that support the protocol.

## Getting Started with MCP Server

The MCP server URL is compatible with any supported client, providing a unique endpoint that allows the LLM to perform actions in your workspace on your behalf.

## Supported Operations

The MCP server supports all standard CRUD operations through natural language prompts.

**Operation** | **Description** | **Example Prompt**  
---|---|---  
Create | Add new records | “Add a new task called ‘Review Documentation’”  
Read | Query existing data | “Find all projects due this week”  
Update | Modify records | “Change the status to ‘In Progress’”  
Delete | Remove records | “Delete completed tasks older than 30 days”  
  
**We recommend using a high-parameter model for the MCP to function properly.**

## Setting up the MCP Server

Here are the detailed steps to set up an MCP server:

  1. Click on your Workspace name in the top navigation bar
  2. Select **My Settings** from the dropdown menu
  3. Click on the **MCP Server** tab in the settings panel
  4. Click the **Create New Endpoint** button
  5. Enter a descriptive name for your endpoint
  6. Select your workspace from the dropdown list
  7. Click **More Details** to expand additional options
  8. Choose your preferred LLM from the available options: 
     * Claude
     * Cursor
     * Windsurf
  9. Follow the specific configuration instructions for your chosen LLM (detailed in sections below)

### Claude:

Three simple steps to get started with Claude Desktop and the Baserow MCP:

  1. Open the Claude Desktop settings from the navigation bar (⌘+,)
  2. Go to the “Develop” tab and click “Edit Config”
  3. Include the following JSON configuration in `claude_desktop_config.json`

### Cursor:

Three simple steps to get started with Cursor and the Baserow MCP:

  1. Open Cursor settings (⇧+⌘+J)
  2. Navigate to the “MCP” tab and click “Add MCP Server”
  3. Add the JSON configuration

### Windsurf:

Two easy steps to set up MCP with Cascade in Windsurf:

  1. Navigate to Windsurf - Settings → Advanced Settings or Command Palette → Open Windsurf settings page
  2. Scroll down to the Cascade section where you’ll find options to add a new server, view existing servers, and a button to view the raw JSON config file at `mcp_config.json`. Add the JSON configuration

### JSON configuration
    
    
    {
      "mcpServers": {
        "Baserow MCP": {
          "command": "npx",
          "args": [
            "mcp-remote",
            "MCP URL"
          ]
        }
      }
    }
    

Treat your MCP URL as securely as a password, since it grants full access to modify your Baserow data.

**Security Note:** Your MCP URL contains sensitive credentials. Never share it publicly or store it in an unsecured location.

