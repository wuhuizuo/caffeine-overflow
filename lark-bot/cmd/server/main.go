package main

import (
	"context"
	"flag"
	"net/http"
	"os"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher"
	larkws "github.com/larksuite/oapi-sdk-go/v3/ws"
	"github.com/rs/zerolog/log"
	"gopkg.in/yaml.v3"

	"github.com/wuhuizuo/caffeine-overflow/lark-bot/pkg/botinfo"
	"github.com/wuhuizuo/caffeine-overflow/lark-bot/pkg/events/handler"
)

func main() {
	var (
		// Flags still define defaults and allow overrides
		appID       = flag.String("app-id", "", "app id (overrides config if provided)")
		appSecret   = flag.String("app-secret", "", "app secret (overrides config if provided)")
		config      = flag.String("config", "config.yaml", "config yaml file")
		debugMode   = flag.Bool("debug", false, "debug mode")
		httpAddress = flag.String("http-addr", ":8080", "HTTP listen address for health checks")
	)
	flag.Parse()

	// Load config first
	cfg := loadConfig(*config)

	// Use config values if flags are not set
	if *appID == "" {
		if id, ok := cfg["app_id"].(string); ok && id != "" {
			*appID = id
			log.Info().Msg("Using app_id from config file")
		}
	} else {
		log.Info().Msg("Using app-id from command line flag")
	}

	if *appSecret == "" {
		if secret, ok := cfg["app_secret"].(string); ok && secret != "" {
			*appSecret = secret
			log.Info().Msg("Using app_secret from config file")
		}
	} else {
		log.Info().Msg("Using app-secret from command line flag")
	}

	// Check if appID and appSecret are set
	if *appID == "" || *appSecret == "" {
		log.Fatal().Msg("app_id and app_secret must be provided either via command-line flags (--app-id, --app-secret) or in the config file.")
	}

	// Start the HTTP server in a separate goroutine
	go func() {
		http.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("OK"))
		})
		http.HandleFunc("/livez", func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("OK"))
		})
		log.Info().Msgf("Starting health check server on %s", *httpAddress)
		if err := http.ListenAndServe(*httpAddress, nil); err != nil {
			log.Fatal().Err(err).Msg("Failed to start health check server")
		}
	}()

	// Set up Lark (Feishu) WebSocket client
	producerOpts := []lark.ClientOptionFunc{}
	if *debugMode {
		producerOpts = append(producerOpts, lark.WithLogLevel(larkcore.LogLevelDebug), lark.WithLogReqAtDebug(true))
	} else {
		producerOpts = append(producerOpts, lark.WithLogLevel(larkcore.LogLevelInfo))
	}
	// Use the potentially updated appID and appSecret
	producerCli := lark.NewClient(*appID, *appSecret, producerOpts...)

	// Get bot name at startup if not already in config
	if _, ok := cfg["bot_name"].(string); !ok { // Removed check for *appID != "" && *appSecret != "" as we now ensure they are set
		botName, err := botinfo.GetBotName(context.Background(), *appID, *appSecret)
		if err != nil {
			log.Fatal().Err(err).Msg("Failed to get bot name from API. Please verify your App ID and App Secret, and ensure the bot is properly configured in the Lark platform. Alternatively, set a default bot name in the config.")
		} else if botName == "" {
			log.Fatal().Msg("Retrieved empty bot name from API. Please check your app configuration.")
		} else {
			log.Info().Str("botName", botName).Msg("Bot name retrieved from API successfully")
			// Store the bot name in the config for later use
			cfg["bot_name"] = botName
		}
	}

	eventHandler := dispatcher.NewEventDispatcher("", "").
		OnP2MessageReceiveV1(handler.NewRootForMessage(producerCli, cfg))

	consumerOpts := []larkws.ClientOption{larkws.WithEventHandler(eventHandler)}
	if *debugMode {
		consumerOpts = append(consumerOpts,
			larkws.WithLogLevel(larkcore.LogLevelDebug),
			larkws.WithAutoReconnect(true))
	} else {
		// Set log level to Warn in non-debug mode to avoid logging sensitive connection URLs
		consumerOpts = append(consumerOpts, larkws.WithLogLevel(larkcore.LogLevelWarn))
	}

	// Use the potentially updated appID and appSecret
	consumerCli := larkws.NewClient(*appID, *appSecret, consumerOpts...)
	// Now start the WebSocket client (blocking call)
	err := consumerCli.Start(context.Background())
	if err != nil {
		log.Fatal().Err(err).Msg("run failed for Lark WebSocket client")
	}
}

// loadConfig loads the YAML config into a map[string]any
func loadConfig(file string) map[string]any {
	f, err := os.Open(file)
	if err != nil {
		// Log warning instead of fatal if config doesn't exist, return empty map
		if os.IsNotExist(err) {
			log.Warn().Str("file", file).Msg("Config file not found, continuing without it.")
			return make(map[string]any)
		}
		log.Fatal().Err(err).Msg("failed to open config file")
	}
	defer f.Close()

	var cfg map[string]any
	err = yaml.NewDecoder(f).Decode(&cfg)
	if err != nil {
		log.Fatal().Err(err).Msg("failed to decode config file")
	}
	// Initialize map if file is empty
	if cfg == nil {
		cfg = make(map[string]any)
	}
	return cfg
}
