package transcriber

import (
	"fmt"

	"github.com/martijnspitter/transcriber/internal/ollama"
)

func (t *TranscriberService) Summarize() (string, error) {
	if t.meeting.Transcript == "" {
		return "", fmt.Errorf("transcription cannot be empty")
	}

	// Comprehensive instructions with structured template
	systemPrompt := `You are an assistant that summarizes meeting transcripts into a standardized markdown format. You do not have to wrap the output in markdown code blocks.

Your summary MUST follow this exact structure, with all sections included even if empty:

---
id: {{meeting_title from transcript}}
tags:
  - meeting-notes
created: {{date from transcript}}
type: #meeting
updated: {{date from transcript}}
---

# {{meeting_title from transcript}}

## Participants
- [[{{participant1}}]]
- [[{{participant2}}]]
(include all participants mentioned in the transcript)

## Summary
(provide a concise summary of the entire meeting)

## Key Points
- Key point 1
- Key point 2
(list all important points discussed)

## Decisions
- Decision 1
- Decision 2
(list all decisions made during the meeting)

## Action Items
- [[Person responsible]] will do task by deadline
- [[Another person]] to follow up on X
(list all action items with responsible persons in [[name]] format and deadlines if mentioned)

Important guidelines:
1. ALL participant names MUST be formatted with double square brackets like [[Name]]
2. Extract the meeting title and date from the transcript
3. If certain sections have no content, include "None identified" rather than leaving blank
4. Focus on extracting factual information only
5. Maintain the exact structure provided - do not add or remove sections`

	msgs := []ollama.Message{
		{
			Role:    "system",
			Content: systemPrompt,
		},
		{
			Role:    "user",
			Content: fmt.Sprintf("Summarize the following meeting transcript into the required format: \n\n%s", t.meeting.Transcript),
		},
	}

	res, err := ollama.TalkToOllama(msgs)
	if err != nil {
		return "", fmt.Errorf("failed to talk to Ollama: %w", err)
	}

	return res.Message.Content, nil
}
