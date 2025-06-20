package logger

import (
	"log/slog"
	"os"
)

type Logger struct {
	Info  func(msg string, args ...any)
	Error func(msg string, args ...any)
	Debug func(msg string, args ...any)
}

func NewLogger() *Logger {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}))

	return &Logger{
		Info: func(msg string, args ...any) {
			logger.Info(msg, args...)
		},
		Error: func(msg string, args ...any) {
			logger.Error(msg, args...)
		},
		Debug: func(msg string, args ...any) {
			logger.Debug(msg, args...)
		},
	}

}
