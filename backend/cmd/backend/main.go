package main

import (
	"log"
	"os"

	"github.com/martijnspitter/transcriber/internal/api"
	"github.com/martijnspitter/transcriber/internal/logger"
	"github.com/martijnspitter/transcriber/internal/transcriber"
)

func main() {
	logger := logger.NewLogger()
	logger.Info("Starting Transcriber API server...")

	transcriber := transcriber.NewTranscriberService(logger)

	// Create a new API server
	server := api.NewServer(logger, transcriber)

	// Start the server
	if err := server.Start(); err != nil {
		log.Printf("Error: %v", err)
		os.Exit(1)
	}
}
