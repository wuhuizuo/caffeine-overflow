package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/allegro/bigcache/v3"
	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkcontact "github.com/larksuite/oapi-sdk-go/v3/service/contact/v3"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/wuhuizuo/caffeine-overflow/lark-bot/pkg/response"
)

const (
	ctxKeyGithubToken     = "github_token"
	ctxKeyLarkSenderEmail = "lark.sender.email"

	// Message types
	msgTypePrivate = "private"
	msgTypeGroup   = "group"
)

type CommandHandler func(context.Context, []string) (string, error)

type CommandConfig struct {
	Handler      CommandHandler
	NeedsAudit   bool
	AuditWebhook string
	SetupContext func(ctx context.Context, config map[string]any, sender *CommandSender) context.Context
}

// TODO: support command /sync_docker_image
var commandConfigs = map[string]CommandConfig{
	"/ask": {
		Handler:      runCommandAsk,
		SetupContext: setupAskCtx,
	},
}

type Command struct {
	Name   string
	Args   []string
	Sender *CommandSender
}

type CommandSender struct {
	OpenID string
	Email  string
}

type CommandResponse struct {
	Status  string
	Message string
	Error   string
}

type commandLarkMsgContent struct {
	Text string `json:"text"`
}

type rootHandler struct {
	*lark.Client
	eventCache *bigcache.BigCache
	Config     map[string]any
	botName    string
	logger     zerolog.Logger
}

// InformationError represents an information level error that occurred during command execution.
// it will give some information but not error, such as help and skip reasons.
type InformationError error

// SkipError represents a skip level error that occurred during command execution.
type SkipError error

// Status enums
const (
	StatusSuccess = "success"
	StatusFailure = "failure"
	StatusSkip    = "skip"
	StatusInfo    = "info"
)

// Pre-computed help text for available commands
var availableCommandsHelpText string

func init() {
	// Initialize the help text for available commands
	var commandsList []string
	for cmd := range commandConfigs {
		commandsList = append(commandsList, cmd)
	}

	// Build the help text that will be reused
	helpText := "Available commands:\n"
	for _, cmd := range commandsList {
		switch cmd {
		case "/cherry-pick-invite":
			helpText += fmt.Sprintf("• %s - Grant a collaborator permission to edit a cherry-pick PR\n", cmd)
		case "/devbuild":
			helpText += fmt.Sprintf("• %s - Trigger a devbuild or check build status\n", cmd)
		default:
			helpText += fmt.Sprintf("• %s\n", cmd)
		}
	}
	helpText += "\nUse [command] --help for more information"

	availableCommandsHelpText = helpText
}

func NewRootForMessage(respondCli *lark.Client, cfg map[string]any) func(ctx context.Context, event *larkim.P2MessageReceiveV1) error {
	cacheCfg := bigcache.DefaultConfig(10 * time.Minute)
	cacheCfg.Logger = &log.Logger
	cache, _ := bigcache.New(context.Background(), cacheCfg)

	baseLogger := log.With().Str("component", "rootHandler").Logger()

	botName, ok := cfg["bot_name"].(string)
	if !ok {
		// This shouldn't happen because main.go already validates this
		// We're keeping this check as a safeguard with a more specific error message
		baseLogger.Fatal().Msg("Bot name was not provided in config. This should have been caught earlier.")
	}

	h := &rootHandler{
		Client:     respondCli,
		Config:     cfg,
		eventCache: cache,
		botName:    botName,
		logger:     baseLogger,
	}
	return h.Handle
}

func (r *rootHandler) Handle(ctx context.Context, event *larkim.P2MessageReceiveV1) error {
	eventID := event.EventV2Base.Header.EventID

	msgType := "unknown"
	if event.Event.Message.ChatType != nil {
		msgType = *event.Event.Message.ChatType
	}

	hl := r.logger.With().
		Str("eventId", eventID).
		Str("msgType", msgType).
		Logger()

	// check if the event has been handled.
	_, err := r.eventCache.Get(eventID)
	if err == nil {
		return nil
	} else if err == bigcache.ErrEntryNotFound {
		r.eventCache.Set(eventID, []byte(eventID))
	} else {
		hl.Err(err).Msg("Unexpected error accessing event cache")
		return err
	}

	command := shouldHandle(event, r.botName)
	if command == nil {
		return nil
	}

	hl.Info().
		Str("command", command.Name).
		Str("sender", *event.Event.Sender.SenderId.OpenId).
		Int("argsCount", len(command.Args)).
		Msg("Processing command")

	refactionID, err := r.addReaction(*event.Event.Message.MessageId)
	if err != nil {
		hl.Err(err).Msg("send heartbeat failed")
		return err
	}

	senderOpenID := *event.Event.Sender.SenderId.OpenId
	res, err := r.Contact.User.Get(ctx, larkcontact.NewGetUserReqBuilder().
		UserIdType(larkcontact.UserIdTypeOpenId).
		UserId(senderOpenID).
		Build())
	if err != nil {
		hl.Err(err).Msg("get user info failed.")
		return err
	}

	if !res.Success() {
		hl.Error().Msg("get user info failed")
		return nil
	}

	command.Sender = &CommandSender{OpenID: senderOpenID, Email: *res.Data.User.Email}

	go func() {
		defer r.deleteReaction(*event.Event.Message.MessageId, refactionID)
		message, err := r.handleCommand(ctx, command)
		if err == nil {
			r.sendResponse(*event.Event.Message.MessageId, StatusSuccess, message)
			return
		}

		// send different level response for the error types.
		switch e := err.(type) {
		case SkipError:
			message = fmt.Sprintf("%s\n---\n**skip:**\n%v", message, e)
			r.sendResponse(*event.Event.Message.MessageId, StatusSkip, message)
		case InformationError:
			message = fmt.Sprintf("%s\n---\n**information:**\n%v", message, e)
			r.sendResponse(*event.Event.Message.MessageId, StatusInfo, message)
		default:
			message = fmt.Sprintf("%s\n---\n**error:**\n%v", message, err)
			r.sendResponse(*event.Event.Message.MessageId, StatusFailure, message)
		}
	}()

	return nil
}

func (r *rootHandler) handleCommand(ctx context.Context, command *Command) (string, error) {
	cmdLogger := r.logger.With().
		Str("command", command.Name).
		Str("sender", command.Sender.Email).
		Logger()

	cmdConfig, exists := commandConfigs[command.Name]
	if !exists {
		cmdLogger.Warn().Msg("Unsupported command")

		errorMsg := fmt.Sprintf("Unsupported command: %s\n\n%s", command.Name, availableCommandsHelpText)
		return "", fmt.Errorf(errorMsg)
	}

	runCtx := cmdConfig.SetupContext(ctx, r.Config, command.Sender)
	result, err := cmdConfig.Handler(runCtx, command.Args)

	return result, err
}

func (r *rootHandler) sendResponse(reqMsgID string, status, message string) error {
	replyMsg, err := response.NewReplyMessageReq(reqMsgID, status, message)
	if err != nil {
		log.Err(err).Msg("render msg faled.")
		return err
	}

	res, err := r.Im.Message.Reply(context.Background(), replyMsg)
	if err != nil {
		log.Err(err).Msg("send msg error.")
		return err
	}

	if !res.Success() {
		log.Error().Msg("response message sent failed")
	}

	return nil
}

func (r *rootHandler) addReaction(reqMsgID string) (string, error) {
	req := larkim.NewCreateMessageReactionReqBuilder().
		MessageId(reqMsgID).
		Body(larkim.NewCreateMessageReactionReqBodyBuilder().
			ReactionType(larkim.NewEmojiBuilder().EmojiType("OnIt").Build()).
			Build()).
		Build()

	res, err := r.Im.MessageReaction.Create(context.Background(), req)
	if err != nil {
		log.Err(err).Msg("send reaction failed.")
		return "", err
	}
	if !res.Success() {
		log.Error().Msg("send reaction failed")
		return "", nil
	}

	return *res.Data.ReactionId, nil
}

func (r *rootHandler) deleteReaction(reqMsgID, reactionID string) error {
	req := larkim.NewDeleteMessageReactionReqBuilder().
		MessageId(reqMsgID).
		ReactionId(reactionID).
		Build()

	if _, err := r.Im.MessageReaction.Delete(context.Background(), req); err != nil {
		log.Err(err).Msg("delete reaction failed.")
		return err
	}

	return nil
}

// determineMessageType determines the message type and checks if the bot was mentioned
func determineMessageType(event *larkim.P2MessageReceiveV1, botName string) (msgType string, chatID string, isMentionBot bool) {
	// Check if the message is from a group chat
	if event.Event.Message.ChatType != nil && *event.Event.Message.ChatType == "group" {
		msgType = msgTypeGroup
		if event.Event.Message.ChatId != nil {
			chatID = *event.Event.Message.ChatId
		}
		isMentionBot = checkIfBotMentioned(event, botName)
	} else {
		msgType = msgTypePrivate
	}

	return msgType, chatID, isMentionBot
}

// checkIfBotMentioned checks if the bot was mentioned in the message
func checkIfBotMentioned(event *larkim.P2MessageReceiveV1, botName string) bool {
	if event.Event.Message.Mentions == nil || len(event.Event.Message.Mentions) == 0 {
		return false
	}

	for _, mention := range event.Event.Message.Mentions {
		if mention == nil {
			continue
		}
		if mention.Name != nil && *mention.Name == botName {
			return true
		}
	}
	return false
}

// parseGroupCommand parses commands from group messages
// Supported format: @bot /command arg1 arg2...
func parseGroupCommand(event *larkim.P2MessageReceiveV1) *Command {
	messageContent := strings.TrimSpace(*event.Event.Message.Content)

	var content commandLarkMsgContent
	if err := json.Unmarshal([]byte(messageContent), &content); err != nil {
		log.Error().Err(err).Msg("Failed to unmarshal message content")
		return nil
	}

	// In Lark messages, mentions are converted to @_user_X format
	// Use regex to match commands after @_user_X: /command arg1 arg2...
	re := regexp.MustCompile(`@_user_\d+\s+(/\S+)(.*)`)
	matches := re.FindStringSubmatch(content.Text)

	if len(matches) < 3 {
		return nil
	}

	commandName := matches[1]
	argsStr := strings.TrimSpace(matches[2])
	var args []string
	if argsStr != "" {
		args = strings.Fields(argsStr)
	}

	return &Command{Name: commandName, Args: args}
}

// parsePrivateCommand parses commands from private messages
func parsePrivateCommand(event *larkim.P2MessageReceiveV1) *Command {
	messageContent := strings.TrimSpace(*event.Event.Message.Content)

	var content commandLarkMsgContent
	if err := json.Unmarshal([]byte(messageContent), &content); err != nil {
		log.Error().Err(err).Msg("Failed to unmarshal message content")
		return nil
	}

	messageParts := strings.Fields(content.Text)
	if len(messageParts) < 1 {
		return nil
	}

	return &Command{Name: messageParts[0], Args: messageParts[1:]}
}

func shouldHandle(event *larkim.P2MessageReceiveV1, botName string) *Command {
	// Determine message type and whether the bot was mentioned
	msgType, _, isMentionBot := determineMessageType(event, botName)

	if msgType == msgTypeGroup && isMentionBot {
		return parseGroupCommand(event)
	} else if msgType == msgTypePrivate {
		return parsePrivateCommand(event)
	}
	return nil
}
