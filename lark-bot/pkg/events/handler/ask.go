package handler

import (
	"context"
	"fmt"
	"strings"

	mcpclient "github.com/mark3labs/mcp-go/client"
	"github.com/openai/openai-go"
	"github.com/openai/openai-go/azure"
	"github.com/rs/zerolog/log"
)

const (
	cfgKeyAskLlmCfg          = "ask.llm.azure_config"
	cfgKeyAskLlmModel        = "ask.llm.model"
	cfgKeyAskLlmSystemPrompt = "ask.llm.system_prompt"
	cfgKeyAskLlmMcpServers   = "ask.llm.mcp_servers"

	ctxKeyLlmClient       = "llm.client"
	ctxKeyLlmModel        = "llm.model"
	ctxKeyLlmSystemPrompt = "llm.system_prompt"
	ctxKeyLLmTools        = "llm.tools"
	ctxKeyMcpClients      = "llm.mcp_clients"
)

const (
	askHelpText = `missing question

Usage: /ask <question...>

Example:
  /ask What is the on-call schedule for the infra team this week?
  /ask How do I debug error code 1234 in service X?

For more details, use: /ask --help
`

	askDetailedHelpText = `Usage: /ask <question...>

Description:
  Asks an AI assistant a question. The assistant may leverage internal tools (MCP context)
  to provide relevant and up-to-date information alongside its general knowledge.

Examples:
  /ask What is the current status of the main production cluster?
  /ask Explain the purpose of the 'widget-processor' microservice.
  /ask Summarize the recent alerts for the database tier.
  /ask How do I request access to the staging environment?

Use '/ask --help' or '/ask -h' to see this message.
`
)

// runCommandAsk handles the /ask command logic.
func runCommandAsk(ctx context.Context, args []string) (string, error) {
	if len(args) == 0 {
		// No question provided
		return "", fmt.Errorf(askHelpText)
	}

	// Check for help flags explicitly, as there are no subcommands
	firstArg := args[0]
	if firstArg == "-h" || firstArg == "--help" {
		if len(args) == 1 {
			return askDetailedHelpText, nil
		}
		// Allow asking help *about* something, e.g. /ask --help tools
		// But for now, just treat any args after --help as part of the help request itself.
		// Let's just return the detailed help for simplicity.
		// Alternatively, could error out:
		// return "", fmt.Errorf("unknown arguments after %s: %v", firstArg, args[1:])
		return askDetailedHelpText, nil
	}

	// The entire argument list forms the question
	question := strings.Join(args, " ")

	// AI/Tool interaction
	// Here you would:
	// 1. Parse the question for intent or specific tool requests (if applicable).
	// 2. Potentially query MCP tools based on the question to gather context.
	// 3. Format a prompt including the user's question and any gathered context.
	// 4. Send the prompt to the configured LLM.
	// 5. Receive the LLM's response.
	// 6. Format the response for Lark.
	result, err := processAskRequest(ctx, question)
	if err != nil {
		return "", fmt.Errorf("failed to process ask request: %w", err)
	}

	return result, nil
}

// processAskRequest will interact with the LLM and tools.
func processAskRequest(ctx context.Context, question string) (string, error) {
	client := ctx.Value(ctxKeyLlmClient).(*openai.Client)
	// openaiModel := ctx.Value(ctxKeyLlmModel).(shared.ChatModel)
	systemPrompt := ctx.Value(ctxKeyLlmSystemPrompt).(string)
	tools := ctx.Value(ctxKeyLLmTools).([]openai.ChatCompletionToolParam)

	llmParams := openai.ChatCompletionNewParams{
		Messages: []openai.ChatCompletionMessageParamUnion{
			openai.SystemMessage(systemPrompt),
			openai.UserMessage(question),
		},
		Tools: tools,
		Model: openai.ChatModelGPT4o,
		Seed:  openai.Int(1),
	}

	clients := ctx.Value(ctxKeyMcpClients).([]mcpclient.MCPClient)
	mcpToolMap := getFunctionMCPClientMap(ctx, clients)

	for {
		completion, err := client.Chat.Completions.New(ctx, llmParams)
		if err != nil {
			log.Err(err).Msg("failed to create chat completion")
			return "", fmt.Errorf("failed to create chat completion: %w", err)
		}

		toolCalls := completion.Choices[0].Message.ToolCalls
		if len(toolCalls) == 0 {
			return completion.Choices[0].Message.Content, nil
		}

		// If there is a was a function call, continue the conversation
		llmParams.Messages = append(llmParams.Messages, completion.Choices[0].Message.ToParam())
		for _, toolCall := range toolCalls {
			if client, ok := mcpToolMap[toolCall.Function.Name]; ok {
				toolResData, err := processMcpToolCall(ctx, client, toolCall)
				if err != nil {
					log.Err(err).Msg("failed to process tool call")
					return "", fmt.Errorf("failed to process tool call: %w", err)
				}

				llmParams.Messages = append(llmParams.Messages, openai.ToolMessage(toolResData, toolCall.ID))
				log.Debug().Any("message", llmParams.Messages[len(llmParams.Messages)-1]).Msg("message")
			}
		}
	}
}

func setupAskCtx(ctx context.Context, config map[string]any, _ *CommandSender) context.Context {
	// Initialize LLM client
	var client openai.Client
	{
		log.Debug().Msg("initializing LLM client")
		llmCfg := config[cfgKeyAskLlmCfg]
		switch v := llmCfg.(type) {
		case map[string]any:
			apiKey := v["api_key"].(string)
			endpointURL := v["base_url"].(string)
			apiVesion := v["api_version"].(string)
			client = openai.NewClient(
				azure.WithAPIKey(apiKey),
				azure.WithEndpoint(endpointURL, apiVesion),
			)
		default:
			client = openai.NewClient()
		}

		log.Debug().Msg("initialized LLM client")
	}

	// Initialize LLM tools
	var mcpClients []mcpclient.MCPClient
	var toolDeclarations []openai.ChatCompletionToolParam
	{
		mcpCfg := config[cfgKeyAskLlmMcpServers]
		switch v := mcpCfg.(type) {
		case map[string]any:
			for name, cfg := range v {
				url := cfg.(map[string]any)["base_url"].(string)
				log.Debug().Str("name", name).Str("url", url).Msg("initializing MCP SSE client")
				client, declarations, err := initializeMCPClient(ctx, name, url)
				if err != nil {
					log.Err(err).Str("name", name).Str("url", url).Msg("failed to initialize MCP SSE client")
					continue
				}
				mcpClients = append(mcpClients, client)
				toolDeclarations = append(toolDeclarations, declarations...)
				log.Debug().Str("name", name).Str("url", url).Msg("initialized MCP SSE client")
			}
		}
	}

	// Setup context
	newCtx := context.WithValue(ctx, ctxKeyLlmClient, &client)
	newCtx = context.WithValue(newCtx, ctxKeyLlmModel, config[cfgKeyAskLlmModel])
	newCtx = context.WithValue(newCtx, ctxKeyLlmSystemPrompt, config[cfgKeyAskLlmSystemPrompt])
	newCtx = context.WithValue(newCtx, ctxKeyLLmTools, toolDeclarations)
	newCtx = context.WithValue(newCtx, ctxKeyMcpClients, mcpClients)

	return newCtx
}
