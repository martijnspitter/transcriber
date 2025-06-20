package transcriber

import (
	"fmt"

	"github.com/martijnspitter/transcriber/internal/ollama"
)

func Summarize(transcription string) (string, error) {
	// Placeholder for the actual implementation
	// This function should call the Ollama API with the mistal model to summarize the transcription
	// For now, we return a dummy summary

	if transcription == "" {
		return "", fmt.Errorf("transcription cannot be empty")
	}

	msgs := []ollama.Message{
		{
			Role:    "system",
			Content: "You are an assistant that summarizes meeting transcripts concisely, highlighting key points, action items, and decisions made. If the transcript is too long, focus on the most important parts and provide a brief summary. If the transcript is very short, provide a detailed summary with all relevant information. If the transcript is empty or contains no meaningful content, return No content to summarize.",
		},
		{
			Role:    "user",
			Content: fmt.Sprintf("Summarize the following meeting: %s", transcription),
		},
	}

	res, err := ollama.TalkToOllama(msgs)
	if err != nil {
		return "", fmt.Errorf("failed to talk to Ollama: %w", err)
	}

	return res.Message.Content, nil
}
