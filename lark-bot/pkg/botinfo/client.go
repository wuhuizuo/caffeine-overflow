package botinfo

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/rs/zerolog/log"
)

// Lark API endpoints
const (
	tenantAccessTokenURL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
	botInfoURL           = "https://open.larksuite.com/open-apis/bot/v3/info"
)

// HTTPClient interface for easier testing
type HTTPClient interface {
	Do(req *http.Request) (*http.Response, error)
}

// defaultHTTPClient is the default HTTP client
var defaultHTTPClient HTTPClient = &http.Client{}

// setHTTPClient allows setting a custom HTTP client (used for testing)
func setHTTPClient(client HTTPClient) {
	defaultHTTPClient = client
}

// TenantAccessTokenRequest represents the request body for getting a tenant access token
type TenantAccessTokenRequest struct {
	AppID     string `json:"app_id"`
	AppSecret string `json:"app_secret"`
}

// TenantAccessTokenResponse represents the response from the tenant access token API
type TenantAccessTokenResponse struct {
	Code              int    `json:"code"`
	Msg               string `json:"msg"`
	TenantAccessToken string `json:"tenant_access_token"`
	Expire            int    `json:"expire"`
}

// BotInfoResponse represents the response from the bot info API
type BotInfoResponse struct {
	Code int    `json:"code"`
	Msg  string `json:"msg"`
	Bot  struct {
		ActivateStatus int      `json:"activate_status"`
		AppName        string   `json:"app_name"`
		AvatarURL      string   `json:"avatar_url"`
		IPWhiteList    []string `json:"ip_white_list"`
		OpenID         string   `json:"open_id"`
	} `json:"bot"`
}

// GetBotName fetches the bot name from Lark API using app credentials
func GetBotName(ctx context.Context, appID, appSecret string) (string, error) {
	logger := log.With().Str("component", "botinfo").Logger()

	ctxWithTimeout, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	token, err := getTenantAccessToken(ctxWithTimeout, appID, appSecret)
	if err != nil {
		logger.Err(err).Msg("Failed to get tenant access token")
		return "", fmt.Errorf("failed to get tenant access token: %w", err)
	}

	botInfo, err := getBotInfo(ctxWithTimeout, token)
	if err != nil {
		logger.Err(err).Msg("Failed to get bot info")
		return "", fmt.Errorf("failed to get bot info: %w", err)
	}

	if botInfo.Bot.AppName == "" {
		logger.Warn().Msg("Bot name is empty in API response")
		return "", fmt.Errorf("bot name is empty in API response")
	}

	return botInfo.Bot.AppName, nil
}

// getTenantAccessToken gets a tenant access token using app credentials
func getTenantAccessToken(ctx context.Context, appID, appSecret string) (string, error) {
	reqBody := TenantAccessTokenRequest{
		AppID:     appID,
		AppSecret: appSecret,
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return "", fmt.Errorf("error marshaling request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", tenantAccessTokenURL, bytes.NewBuffer(jsonBody))
	if err != nil {
		return "", fmt.Errorf("error creating request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := defaultHTTPClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("error making request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("error reading response: %w", err)
	}

	var tokenResp TenantAccessTokenResponse
	if err := json.Unmarshal(body, &tokenResp); err != nil {
		return "", fmt.Errorf("error parsing response: %w", err)
	}

	if tokenResp.Code != 0 {
		return "", fmt.Errorf("API error: %s (code: %d)", tokenResp.Msg, tokenResp.Code)
	}

	return tokenResp.TenantAccessToken, nil
}

// getBotInfo gets information about the bot using the tenant access token
func getBotInfo(ctx context.Context, token string) (*BotInfoResponse, error) {
	// Create a new request
	req, err := http.NewRequestWithContext(ctx, "GET", botInfoURL, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}

	req.Header.Add("Authorization", "Bearer "+token)
	req.Header.Add("Content-Type", "application/json")

	resp, err := defaultHTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error making request: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response: %w", err)
	}

	var botResp BotInfoResponse
	if err := json.Unmarshal(body, &botResp); err != nil {
		return nil, fmt.Errorf("error parsing response: %w", err)
	}

	if botResp.Code != 0 {
		return nil, fmt.Errorf("API error: %s (code: %d)", botResp.Msg, botResp.Code)
	}

	return &botResp, nil
}
