package osoperations

import (
	"os"
	"path/filepath"
	"time"

	"github.com/martijnspitter/transcriber/internal/types"
)

func FormatFileName(domain string, timestamp time.Time, extension string) string {
	// Format the timestamp to a string
	timestampStr := timestamp.Format("20060102_150405")
	// Construct the file name using the domain, timestamp, and extension
	return domain + "_" + timestampStr + extension
}

func CreateTempDirectory(prefix string) (string, error) {
	// Create a temporary directory with the specified prefix
	tempDir, err := os.MkdirTemp("", prefix)
	if err != nil {
		return "", err
	}
	return tempDir, nil
}

func RemoveTempDirectory(dirName string) error {
	// Remove the temporary directory and its contents
	return os.RemoveAll(dirName)
}

func CreateFilePath(dirName, fileName string) string {
	return filepath.Join(dirName, fileName)
}

func CreateFile(dirName, fileName string, data []byte) error {
	// Create a new file in the specified directory
	filePath := CreateFilePath(dirName, fileName)
	err := os.WriteFile(filePath, data, 0644)
	if err != nil {
		return err
	}
	return nil
}

func GetFileNameWithoutExtension(filePath string) string {
	// Get the base name of the file
	baseName := filepath.Base(filePath)
	// Get the file extension
	ext := filepath.Ext(baseName)
	// Return the base name without the extension
	return baseName[:len(baseName)-len(ext)]
}

func SaveMeetingToVault(meeting *types.Meeting) error {
	dirName := "obsidian-vault"
	fileName := FormatFileName("meeting", meeting.CreatedAt, ".md")

	err := CreateFile(dirName, fileName, []byte(meeting.Summary))

	return err
}
