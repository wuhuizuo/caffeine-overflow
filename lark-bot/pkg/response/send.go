package response

import (
	"bytes"
	"encoding/json"
	"html/template"

	sprig "github.com/Masterminds/sprig/v3"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	"gopkg.in/yaml.v3"

	_ "embed"
)

//go:embed command-response.yaml.tmpl
var larkTemplateBytes string

type info struct {
	Status  string
	Message string
}

func NewReplyMessageReq(msgID string, status, msg string) (*larkim.ReplyMessageReq, error) {
	rawContent, err := newLarkCardWithGoTemplate(&info{Status: status, Message: msg})
	if err != nil {
		return nil, err
	}

	return larkim.NewReplyMessageReqBuilder().
		MessageId(msgID).
		Body(larkim.NewReplyMessageReqBodyBuilder().
			MsgType(larkim.MsgTypeInteractive).
			ReplyInThread(true).
			Content(rawContent).
			Build()).
		Build(), nil
}

func newLarkCardWithGoTemplate(i *info) (string, error) {
	tmpl, err := template.New("lark").Funcs(sprig.FuncMap()).Parse(larkTemplateBytes)
	if err != nil {
		return "", err
	}

	tmplResult := new(bytes.Buffer)
	if err := tmpl.Execute(tmplResult, i); err != nil {
		return "", err
	}

	values := make(map[string]interface{})
	if err := yaml.Unmarshal(tmplResult.Bytes(), &values); err != nil {
		return "", err
	}

	jsonBytes, err := json.Marshal(values)
	if err != nil {
		return "", err
	}

	return string(jsonBytes), nil
}
