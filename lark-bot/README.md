# Lark Bot work together with LLM ability.

## Debug or Run locally

You can run it by following steps:

1. Prepare the configuration file `config.yaml`, example:
  ```yaml
  ask.llm.system_prompt: <your_system_prompt>
  ask.llm.model: <your_model>
  ask.llm.azure_config:
    api_key: <your_azure_api_key>
    base_url: <your_azure_base_url>
    api_version: <your_azure_api_version>
  ask.llm.mcp_servers:
    <a-mcp-tool-name>:
      base_url: <your_mcp_server_base_url(without /sse path)>
  ```
2. Run the lark bot app:
  ```bash
  go run ./cmd/server -app-id=<your_app_id> -app-secret=<your_app_secret>
  ```
