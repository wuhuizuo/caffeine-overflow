package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/openai/openai-go"
	"github.com/openai/openai-go/shared/constant"
	"github.com/rs/zerolog/log"
)

const (
	sseMcpConnectTimeout = 5 * time.Second

	McpClientName    = "ee-chatops-lark"
	McpClientVersion = "1.0.0"
)

// newSSEMcpClient creates a new SSE MCP client.
// connects it and initializes it.
func newSSEMcpClient(ctx context.Context, baseURL string) (*client.SSEMCPClient, error) {
	client, err := client.NewSSEMCPClient(baseURL + "/sse")
	if err != nil {
		return nil, fmt.Errorf("Failed to create client: %v", err)
	}

	// Connect
	if err := client.Start(ctx); err != nil {
		return nil, fmt.Errorf("Failed to start client: %v", err)
	}

	// Initialize
	initRequest := mcp.InitializeRequest{}
	initRequest.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initRequest.Params.ClientInfo = mcp.Implementation{
		Name:    McpClientName,
		Version: McpClientVersion,
	}

	_, err = client.Initialize(ctx, initRequest)
	if err != nil {
		return nil, fmt.Errorf("Failed to initialize: %v", err)
	}

	return client, nil
}

func processMcpToolCall(ctx context.Context, client client.MCPClient, toolCall openai.ChatCompletionMessageToolCall) ([]openai.ChatCompletionContentPartTextParam, error) {
	// convert the params format from openai style to mcp style.
	var params map[string]any
	err := json.Unmarshal([]byte(toolCall.Function.Arguments), &params)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal tool call arguments: %w", err)
	}

	// call the MCP tool
	contents, err := callMcpTool(ctx, client, toolCall.Function.Name, params)
	if err != nil {
		return nil, fmt.Errorf("failed to call MCP tool: %w", err)
	}

	// convert the response format from mcp style to openai style.
	var toolResData []openai.ChatCompletionContentPartTextParam
	for _, content := range contents {
		switch v := content.(type) {
		case mcp.TextContent:
			toolResData = append(toolResData, openai.ChatCompletionContentPartTextParam{
				Text: v.Text,
				Type: constant.Text(v.Type),
			})
		default:
			return nil, fmt.Errorf("unknown content type: %T", v)
		}
	}

	return toolResData, nil
}

func callMcpTool(ctx context.Context, client client.MCPClient, name string, args map[string]any) ([]mcp.Content, error) {
	request := mcp.CallToolRequest{}
	request.Params.Name = name
	request.Params.Arguments = args

	result, err := client.CallTool(ctx, request)
	if err != nil {
		return nil, err
	}
	if result.IsError {
		return nil, fmt.Errorf("tool call failed: %v", result.Result)
	}
	if len(result.Content) != 1 {
		return nil, fmt.Errorf("empty content")
	}

	return result.Content, nil
}

func initializeMCPClient(ctx context.Context, name, url string) (client.MCPClient, []openai.ChatCompletionToolParam, error) {
	// Create a logger with the provided name and URL
	logger := log.With().Str("name", name).Str("url", url).Logger()

	// Create a new SSE MCP client
	c, err := newSSEMcpClient(ctx, url)
	if err != nil {
		logger.Err(err).Msg("failed to create mcp client")
		return nil, nil, err
	}

	// List available tools from the MCP client
	ret, err := c.ListTools(ctx, mcp.ListToolsRequest{})
	if err != nil {
		logger.Err(err).Msg("failed to list tools")
		return nil, nil, err
	}

	// Check if any tools were found
	if len(ret.Tools) == 0 {
		logger.Warn().Msg("no tools found")
		return nil, nil, nil
	}

	// Prepare tool declarations for OpenAI ChatCompletion
	var llmToolDeclaration []openai.ChatCompletionToolParam
	for _, tool := range ret.Tools {
		schemaBytes, err := json.Marshal(tool.InputSchema)
		if err != nil {
			logger.Err(err).Msg("marshal MCP tool input schema failed")
			return nil, nil, err
		}
		toolParams := make(openai.FunctionParameters)
		if err := json.Unmarshal(schemaBytes, &toolParams); err != nil {
			logger.Err(err).Msg("unmarshal MCP tool input schema failed")
			return nil, nil, err
		}

		toolParam := openai.ChatCompletionToolParam{
			Type: "function",
			Function: openai.FunctionDefinitionParam{
				Name:        tool.Name,
				Description: openai.String(tool.Description),
				Parameters:  toolParams,
			},
		}
		llmToolDeclaration = append(llmToolDeclaration, toolParam)
	}

	return c, llmToolDeclaration, nil
}

func getFunctionMCPClientMap(ctx context.Context, clients []client.MCPClient) map[string]client.MCPClient {
	ret := make(map[string]client.MCPClient)

	for _, client := range clients {
		result, err := client.ListTools(ctx, mcp.ListToolsRequest{})
		if err != nil {
			log.Err(err).Msg("failed to list tools")
			continue
		}

		for _, tool := range result.Tools {
			ret[tool.Name] = client
		}
	}

	return ret
}
