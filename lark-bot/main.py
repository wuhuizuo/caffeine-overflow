import asyncio
import logging, colorlog
import logging.handlers
from contextlib import AsyncExitStack
from typing import Any
import yaml
import json
from mcp import ClientSession
from mcp.client.sse import sse_client
import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody, CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji
import openai
from openai import OpenAI



class Server:
    """Manages MCP server connections and tool execution."""

    def __init__(self, name: str, cfg: dict[str, str]) -> None:
        self.name: str = name
        self.sse_url: str = cfg["sse_url"]
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize the server connection."""

        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                sse_client(self.sse_url)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[Any]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()
        tools = []

        for item in tools_response:
            if isinstance(item, tuple) and item[0] == "tools":
                for tool in item[1]:
                    tools.append(Tool(tool.name, tool.description, tool.inputSchema))

        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        """Format tool information for LLM.

        Returns:
            A formatted string describing the tool.
        """
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {self.name}
Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""


class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, lark_client: lark.Client, servers: list[Server], llm_cfg: dict[str, str]) -> None:
        self.lark_client = lark_client
        self.servers: list[Server] = servers

        # AI
        openai.api_type = llm_cfg["api_type"]
        openai.api_version = llm_cfg["api_version"]
        self.llm_client: OpenAI = OpenAI(api_key=llm_cfg["api_key"], base_url=llm_cfg["base_url"])
        self.llm_model = llm_cfg["model"]
        self.system_message = ""


    async def cleanup_servers(self) -> None:
        """Clean up all servers properly."""
        cleanup_tasks = []
        for server in self.servers:
            cleanup_tasks.append(asyncio.create_task(server.cleanup()))

        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            except Exception as e:
                logging.warning(f"Warning during final cleanup: {e}")

    async def process_llm_response(self, llm_response: str) -> str:
        """Process the LLM response and execute tools if needed.

        Args:
            llm_response: The response from the LLM.

        Returns:
            The result of tool execution or the original response.
        """
        import json

        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                logging.info(f"Executing tool: {tool_call['tool']}")
                logging.info(f"With arguments: {tool_call['arguments']}")

                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )

                            if isinstance(result, dict) and "progress" in result:
                                progress = result["progress"]
                                total = result["total"]
                                percentage = (progress / total) * 100
                                logging.info(
                                    f"Progress: {progress}/{total} "
                                    f"({percentage:.1f}%)"
                                )

                            return f"Tool execution result: {result}"
                        except Exception as e:
                            error_msg = f"Error executing tool: {str(e)}"
                            logging.error(error_msg)
                            return error_msg

                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    def do_p2_im_message_receive_v1(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        message_content = json.loads(data.event.message.content)
        # print the message content
        print(message_content)
        text = message_content["text"].strip()

        # Example integration: If the message starts with "fetch", use the tool
        if text.startswith("/ask"):
            self._reply_text(data, "🤔")
            user_input = text[4:].strip() # Extract the URL after "ask"
            if user_input:
                result = self._handle_message(model=self.llm_model, user_input=user_input)
                if result:
                    self._reply_text(data, result)
                else:
                    self._reply_text(data, "No answer found.")
            else:
                self._reply_text(data, "Please provide your question.")


    def _reply_text(self, data: lark.im.v1.P2ImMessageReceiveV1, text: str):
        if data and data.event and data.event.message and data.event.message.message_id:
            message_id = data.event.message.message_id
            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(CreateMessageReactionRequestBody.builder()
                    .reaction_type(Emoji.builder()
                        .emoji_type("SMILE")
                        .build())
                    .build()) \
                .build()

            response = self.lark_client.im.v1.message.reply(request)

            if response.success():
                logging.debug("response successful")
            else:
                logging.error("response failed")

        else:
            logging.error("Invalid message data structure")

    async def initialize(self) -> None:
        for server in self.servers:
            try:
                await server.initialize()
            except Exception as e:
                logging.error(f"Failed to initialize server: {e}")
                await self.cleanup_servers()
                return

        all_tools = []
        for server in self.servers:
            tools = await server.list_tools()
            all_tools.extend(tools)

        tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])

        self.system_message = (
            "You are a helpful assistant with access to these tools:\n\n"
            f"{tools_description}\n"
            "Choose the appropriate tool based on the user's question. "
            "If no tool is needed, reply directly.\n\n"
            "IMPORTANT: When you need to use a tool, you must ONLY respond with "
            "the exact JSON object format below, nothing else:\n"
            "{\n"
            '    "tool": "tool-name",\n'
            '    "arguments": {\n'
            '        "argument-name": "value"\n'
            "    }\n"
            "}\n\n"
            "After receiving a tool's response:\n"
            "1. Transform the raw data into a natural, conversational response\n"
            "2. Keep responses concise but informative\n"
            "3. Focus on the most relevant information\n"
            "4. Use appropriate context from the user's question\n"
            "5. Avoid simply repeating the raw data\n\n"
            "Please use only the tools that are explicitly defined above."
        )


    def _handle_message(self, model: str, user_input: str) -> str | None:
        """Main chat session handler."""
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": user_input},
        ]

        response = self.llm_client.chat.completions.create(model=model, messages=messages)
        llm_response = response.choices[0].message.content
        logging.info("\nAssistant: %s", llm_response)

        result = self.process_llm_response(llm_response)
        if result != llm_response:
            messages.append({"role": "assistant", "content": llm_response})
            messages.append({"role": "system", "content": result})

            final_response = self.llm_client.get_response(messages)
            logging.info("\nFinal response: %s", final_response)
            return final_response
        else:
            return llm_response

async def main():
    """Initialize and run the chat session."""
    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    # Lark
    lark_app_id = config["lark"]["app_id"]
    lark_app_secret = config["lark"]["app_secret"]
    lark_log_level = lark.LogLevel.DEBUG
    lark_response_client = lark.Client.builder() \
        .app_id(lark_app_id) \
        .app_secret(lark_app_secret) \
        .log_level(lark_log_level) \
        .build()

    # Check if mcpServers configuration exists
    if "mcpServers" not in config or not config["mcpServers"]:
        logging.warning("No MCP servers configured. Continuing without server initialization.")
        servers = []
    else:
        servers = [
            Server(name, srv_config)
            for name, srv_config in config["mcpServers"].items()
        ]

    chat_handler = ChatSession(lark_response_client, servers, config["ai"])
    event_handler = lark.EventDispatcherHandler.builder("", "", lark.LogLevel.DEBUG) \
        .register_p2_im_message_receive_v1(chat_handler.do_p2_im_message_receive_v1) \
        .build()

    # Create the Lark WS client
    lark_app = lark.ws.Client(lark_app_id, lark_app_secret, event_handler= event_handler,
        log_level=lark_log_level)

    # Initialize chat handler and servers
    await chat_handler.initialize()
    logging.info("Chat session initialized")

    # Instead of calling lark_app.start(), use its async connection method directly
    return lark_app

if __name__ == "__main__":
    # Configure logging

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
	'%(log_color)s%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[handler],
    )

    client = asyncio.run(main())
    client.start()
