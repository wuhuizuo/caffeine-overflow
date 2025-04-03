package botinfo

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

// MockHTTPClient is a mock implementation of HTTPClient for testing
type MockHTTPClient struct {
	DoFunc func(req *http.Request) (*http.Response, error)
}

// Do implements the HTTPClient interface
func (m *MockHTTPClient) Do(req *http.Request) (*http.Response, error) {
	return m.DoFunc(req)
}

// setupMockClient sets up the mock HTTP client for testing
func setupMockClient(t *testing.T, doFunc func(req *http.Request) (*http.Response, error)) {
	// Save the original client to restore later
	originalClient := defaultHTTPClient
	t.Cleanup(func() {
		// Restore the original client after test
		setHTTPClient(originalClient)
	})

	// Set the mock client
	mockClient := &MockHTTPClient{DoFunc: doFunc}
	setHTTPClient(mockClient)
}

// Test setHTTPClient function
func TestSetHTTPClient(t *testing.T) {
	// Save original client to restore later
	originalClient := defaultHTTPClient
	defer func() {
		defaultHTTPClient = originalClient
	}()

	// Create a mock client
	mockClient := &MockHTTPClient{
		DoFunc: func(req *http.Request) (*http.Response, error) {
			return &http.Response{StatusCode: 200}, nil
		},
	}

	// Set the mock client
	setHTTPClient(mockClient)

	// Verify the client was set correctly
	if defaultHTTPClient != mockClient {
		t.Errorf("setHTTPClient failed to set the client")
	}
}

// Test getTenantAccessToken with successful response
func TestGetTenantAccessToken_Success(t *testing.T) {
	// Mock token response
	mockResp := TenantAccessTokenResponse{
		Code:              0,
		Msg:               "ok",
		TenantAccessToken: "mock-token-123",
		Expire:            7200,
	}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		// Verify request URL
		if req.URL.String() != tenantAccessTokenURL {
			t.Errorf("unexpected URL, got %s, want %s", req.URL.String(), tenantAccessTokenURL)
		}

		// Verify request method
		if req.Method != "POST" {
			t.Errorf("unexpected method, got %s, want POST", req.Method)
		}

		// Verify request body
		bodyBytes, _ := io.ReadAll(req.Body)
		req.Body = io.NopCloser(bytes.NewBuffer(bodyBytes)) // Replace the body for future reads

		var reqBody TenantAccessTokenRequest
		if err := json.Unmarshal(bodyBytes, &reqBody); err != nil {
			t.Fatalf("failed to unmarshal request body: %v", err)
		}

		if reqBody.AppID != "test-app-id" || reqBody.AppSecret != "test-app-secret" {
			t.Errorf("unexpected request body, got %+v", reqBody)
		}

		// Return mock response
		respBody, _ := json.Marshal(mockResp)
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBuffer(respBody)),
		}, nil
	})

	ctx := context.Background()
	token, err := getTenantAccessToken(ctx, "test-app-id", "test-app-secret")

	// Check results
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if token != "mock-token-123" {
		t.Errorf("unexpected token, got %s, want mock-token-123", token)
	}
}

// Test getTenantAccessToken with API error
func TestGetTenantAccessToken_APIError(t *testing.T) {
	// Mock error response
	mockResp := TenantAccessTokenResponse{
		Code: 99999,
		Msg:  "app not found",
	}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		respBody, _ := json.Marshal(mockResp)
		return &http.Response{
			StatusCode: 200, // API returns 200 even on logical errors
			Body:       io.NopCloser(bytes.NewBuffer(respBody)),
		}, nil
	})

	ctx := context.Background()
	_, err := getTenantAccessToken(ctx, "invalid-app-id", "invalid-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "API error: app not found (code: 99999)"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getTenantAccessToken with HTTP client error
func TestGetTenantAccessToken_HTTPError(t *testing.T) {
	// Set up the mock client to simulate network error
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return nil, errors.New("network error")
	})

	ctx := context.Background()
	_, err := getTenantAccessToken(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error making request: network error"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getTenantAccessToken with JSON parsing error
func TestGetTenantAccessToken_JSONError(t *testing.T) {
	// Set up the mock client to return invalid JSON
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBufferString("invalid json")),
		}, nil
	})

	ctx := context.Background()
	_, err := getTenantAccessToken(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error parsing response"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getTenantAccessToken with error during response body read
func TestGetTenantAccessToken_BodyReadError(t *testing.T) {
	// Create a mock response body that returns an error when read
	errorReader := &ErrorReader{err: errors.New("read error")}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(errorReader),
		}, nil
	})

	ctx := context.Background()
	_, err := getTenantAccessToken(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error reading response"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// ErrorReader is a helper type to simulate read errors
type ErrorReader struct {
	err error
}

func (e *ErrorReader) Read(p []byte) (n int, err error) {
	return 0, e.err
}

// Test getBotInfo with successful response
func TestGetBotInfo_Success(t *testing.T) {
	// Create mock response
	mockResp := BotInfoResponse{
		Code: 0,
		Msg:  "ok",
		Bot: struct {
			ActivateStatus int      `json:"activate_status"`
			AppName        string   `json:"app_name"`
			AvatarURL      string   `json:"avatar_url"`
			IPWhiteList    []string `json:"ip_white_list"`
			OpenID         string   `json:"open_id"`
		}{
			ActivateStatus: 1,
			AppName:        "TestBot",
			AvatarURL:      "https://example.com/avatar.jpg",
			IPWhiteList:    []string{"127.0.0.1"},
			OpenID:         "test-open-id",
		},
	}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		// Verify request URL
		if req.URL.String() != botInfoURL {
			t.Errorf("unexpected URL, got %s, want %s", req.URL.String(), botInfoURL)
		}

		// Verify request method
		if req.Method != "GET" {
			t.Errorf("unexpected method, got %s, want GET", req.Method)
		}

		// Verify auth header
		authHeader := req.Header.Get("Authorization")
		expectedAuth := "Bearer mock-token"
		if authHeader != expectedAuth {
			t.Errorf("unexpected auth header, got %s, want %s", authHeader, expectedAuth)
		}

		// Return mock response
		respBody, _ := json.Marshal(mockResp)
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBuffer(respBody)),
		}, nil
	})

	ctx := context.Background()
	botInfo, err := getBotInfo(ctx, "mock-token")

	// Check results
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if botInfo.Bot.AppName != "TestBot" {
		t.Errorf("unexpected bot name, got %s, want TestBot", botInfo.Bot.AppName)
	}
}

// Test getBotInfo with API error
func TestGetBotInfo_APIError(t *testing.T) {
	// Mock error response
	mockResp := BotInfoResponse{
		Code: 99999,
		Msg:  "invalid token",
	}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		respBody, _ := json.Marshal(mockResp)
		return &http.Response{
			StatusCode: 200, // API returns 200 even on logical errors
			Body:       io.NopCloser(bytes.NewBuffer(respBody)),
		}, nil
	})

	ctx := context.Background()
	_, err := getBotInfo(ctx, "invalid-token")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "API error: invalid token (code: 99999)"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getBotInfo with HTTP client error
func TestGetBotInfo_HTTPError(t *testing.T) {
	// Set up the mock client to simulate network error
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return nil, errors.New("network error")
	})

	ctx := context.Background()
	_, err := getBotInfo(ctx, "mock-token")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error making request: network error"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getBotInfo with JSON parsing error
func TestGetBotInfo_JSONError(t *testing.T) {
	// Set up the mock client to return invalid JSON
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBufferString("invalid json")),
		}, nil
	})

	ctx := context.Background()
	_, err := getBotInfo(ctx, "mock-token")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error parsing response"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test getBotInfo with error during response body read
func TestGetBotInfo_BodyReadError(t *testing.T) {
	// Create a mock response body that returns an error when read
	errorReader := &ErrorReader{err: errors.New("read error")}

	// Set up the mock client
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(errorReader),
		}, nil
	})

	ctx := context.Background()
	_, err := getBotInfo(ctx, "mock-token")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error reading response"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test GetBotName for successful full flow
func TestGetBotName_Success(t *testing.T) {
	// Set up the mock client to handle both API calls sequentially
	mockCalls := 0
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		mockCalls++

		// First call - tenant access token
		if mockCalls == 1 {
			mockResp := TenantAccessTokenResponse{
				Code:              0,
				Msg:               "ok",
				TenantAccessToken: "mock-token-123",
				Expire:            7200,
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		// Second call - bot info
		if mockCalls == 2 {
			mockResp := BotInfoResponse{
				Code: 0,
				Msg:  "ok",
				Bot: struct {
					ActivateStatus int      `json:"activate_status"`
					AppName        string   `json:"app_name"`
					AvatarURL      string   `json:"avatar_url"`
					IPWhiteList    []string `json:"ip_white_list"`
					OpenID         string   `json:"open_id"`
				}{
					ActivateStatus: 1,
					AppName:        "TestBotIntegration",
					AvatarURL:      "https://example.com/avatar.jpg",
					IPWhiteList:    []string{"127.0.0.1"},
					OpenID:         "test-open-id",
				},
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		t.Fatalf("unexpected additional API call #%d", mockCalls)
		return nil, nil
	})

	ctx := context.Background()
	botName, err := GetBotName(ctx, "test-app-id", "test-app-secret")

	// Check results
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}

	if botName != "TestBotIntegration" {
		t.Errorf("unexpected bot name, got %s, want TestBotIntegration", botName)
	}

	if mockCalls != 2 {
		t.Errorf("expected 2 API calls, got %d", mockCalls)
	}
}

// Test GetBotName when token retrieval fails
func TestGetBotName_TokenError(t *testing.T) {
	// Set up the mock client to fail on the first call
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		mockResp := TenantAccessTokenResponse{
			Code: 99999,
			Msg:  "invalid app credentials",
		}
		respBody, _ := json.Marshal(mockResp)
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBuffer(respBody)),
		}, nil
	})

	ctx := context.Background()
	_, err := GetBotName(ctx, "invalid-app-id", "invalid-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "failed to get tenant access token"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test GetBotName when bot info retrieval fails
func TestGetBotName_BotInfoError(t *testing.T) {
	// Set up the mock client to handle both API calls sequentially
	mockCalls := 0
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		mockCalls++

		// First call - tenant access token (success)
		if mockCalls == 1 {
			mockResp := TenantAccessTokenResponse{
				Code:              0,
				Msg:               "ok",
				TenantAccessToken: "mock-token-123",
				Expire:            7200,
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		// Second call - bot info (fails)
		if mockCalls == 2 {
			mockResp := BotInfoResponse{
				Code: 99999,
				Msg:  "invalid token",
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		t.Fatalf("unexpected additional API call #%d", mockCalls)
		return nil, nil
	})

	ctx := context.Background()
	_, err := GetBotName(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "failed to get bot info"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test GetBotName when bot name is empty
func TestGetBotName_EmptyBotName(t *testing.T) {
	// Set up the mock client to handle both API calls sequentially
	mockCalls := 0
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		mockCalls++

		// First call - tenant access token (success)
		if mockCalls == 1 {
			mockResp := TenantAccessTokenResponse{
				Code:              0,
				Msg:               "ok",
				TenantAccessToken: "mock-token-123",
				Expire:            7200,
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		// Second call - bot info (success but empty name)
		if mockCalls == 2 {
			mockResp := BotInfoResponse{
				Code: 0,
				Msg:  "ok",
				Bot: struct {
					ActivateStatus int      `json:"activate_status"`
					AppName        string   `json:"app_name"`
					AvatarURL      string   `json:"avatar_url"`
					IPWhiteList    []string `json:"ip_white_list"`
					OpenID         string   `json:"open_id"`
				}{
					ActivateStatus: 1,
					AppName:        "", // Empty bot name
					AvatarURL:      "https://example.com/avatar.jpg",
					IPWhiteList:    []string{"127.0.0.1"},
					OpenID:         "test-open-id",
				},
			}
			respBody, _ := json.Marshal(mockResp)
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBuffer(respBody)),
			}, nil
		}

		t.Fatalf("unexpected additional API call #%d", mockCalls)
		return nil, nil
	})

	ctx := context.Background()
	_, err := GetBotName(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "bot name is empty in API response"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}

// Test GetBotName with context cancellation
func TestGetBotName_ContextCancelled(t *testing.T) {
	// Set up the mock client to simulate context cancellation
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		return nil, context.Canceled
	})

	// Create a context
	ctx := context.Background()

	_, err := GetBotName(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	// The exact error message should contain context cancellation
	if !strings.Contains(err.Error(), "context") {
		t.Errorf("error should mention context cancellation, got: %s", err.Error())
	}
}

// Test GetBotName with context timeout
func TestGetBotName_ContextTimeout(t *testing.T) {
	// Create a context with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Millisecond)
	defer cancel()

	// Wait a bit to ensure the context times out before we even make the request
	time.Sleep(5 * time.Millisecond)

	_, err := GetBotName(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error due to context timeout, got nil")
	}

	// The error should be context deadline exceeded or context cancelled
	if !strings.Contains(err.Error(), "context") && !strings.Contains(err.Error(), "deadline") {
		t.Errorf("unexpected error message, got %s, expected context timeout related error", err.Error())
	}
}

// Test getTenantAccessToken with request error (would happen pre-marshaling)
func TestGetTenantAccessToken_RequestError(t *testing.T) {
	// Set up the mock client to simulate an error that would happen before marshaling
	setupMockClient(t, func(req *http.Request) (*http.Response, error) {
		// This error would occur at request creation time, before marshaling
		return nil, errors.New("request creation error")
	})

	ctx := context.Background()
	_, err := getTenantAccessToken(ctx, "test-app-id", "test-app-secret")

	// Check results - should return error
	if err == nil {
		t.Fatal("expected an error, got nil")
	}

	expectedErrMsg := "error making request"
	if !strings.Contains(err.Error(), expectedErrMsg) {
		t.Errorf("unexpected error message, got %s, want to contain %s", err.Error(), expectedErrMsg)
	}
}
